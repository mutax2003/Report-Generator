"""
Jinja2 sandbox for docxtpl merges (main report + appendices).

- ``autoescape=True``: Excel/sidebar values are XML-escaped before they land in
  WordprocessingML (``<0.005`` stays ``<0.005``; ``Smith & Sons`` keeps the ``&``;
  a cell cannot inject ``<w:r>`` markup). docxtpl ``RichText`` / ``Listing`` /
  ``InlineImage`` / ``Subdoc`` implement ``__html__`` and still render as XML.

Resource limits (all raise ``jinja2.sandbox.SecurityError``; budgets are per
environment, and ``make_report_jinja_env`` builds one environment per render):

- ``range()`` items (``MAX_RANGE_BUDGET``) and total ``{% for %}`` iterations,
  nested and recursive loops included (``MAX_LOOP_ITERATIONS``). Loops are
  budgeted by rewriting each ``For`` node's iterable at parse time.
- Total calls — macros, ``loop(...)`` recursion, methods (``MAX_CALLS``).
- Size of any value built by an expression (``MAX_SEQUENCE_LEN`` items/chars):
  ``*``, ``+``, ``%``, ``~``, every filter result, every call result, and the
  container a method mutates (``list.extend`` doubling). Operations that can
  amplify a small input are pre-checked before allocating: ``center`` /
  ``ljust`` / ``rjust`` / ``zfill`` widths, ``%`` and ``str.format`` field widths
  and precisions, ``replace``, ``join``, ``indent``, ``wordwrap``, ``expandtabs``,
  ``batch`` / ``slice`` fill counts and ``sum`` of sequences.
- ``**`` result size (``MAX_POW_BITS``) and rendered XML per document part
  (``MAX_RENDERED_PART_CHARS``).

Residual risk: a single pre-checked operation may still transiently allocate up
to about ``MAX_SEQUENCE_LEN`` x a small factor before its result is checked, and
CPU-heavy builtins on capped inputs (e.g. sorting a 1M-item list) are bounded by
input size, not time. Templates are uploaded only by authenticated consultants
(trusted authors); these limits stop runaway or careless templates, not a
determined attacker with unlimited template uploads.
"""

from __future__ import annotations

import functools
import inspect
import math
import operator
import re
import string
from collections.abc import Callable, Iterator, Sized
from typing import Any

from jinja2 import StrictUndefined, Template, Undefined, nodes
from jinja2.runtime import LoopContext
from jinja2.sandbox import SandboxedEnvironment, SecurityError
from jinja2.visitor import NodeTransformer

# Total range() items a single render may create (all parts, nested loops included).
MAX_RANGE_BUDGET = 100_000
# Total {% for %} iterations per render (10,000 lab rows x a few nested loops fit).
MAX_LOOP_ITERATIONS = 1_000_000
# Total calls (macros, loop recursion, methods, range) per render. Filters and
# attribute access are not calls.
MAX_CALLS = 100_000
# Longest str/list/tuple/dict any single template operation may build.
MAX_SEQUENCE_LEN = 1_000_000
# Largest integer (in bits) a template may build via **.
MAX_POW_BITS = 4_096
# Rendered XML characters per docx part (mirrors MAX_ZIP_UNCOMPRESSED_BYTES).
MAX_RENDERED_PART_CHARS = 120 * 1024 * 1024

_SEQUENCE_TYPES = (str, list, tuple)
_SIZED_TYPES = (str, list, tuple, dict, set, frozenset)
_MUTABLE_TYPES = (list, dict, set, bytearray)


def _too_large(what: str) -> SecurityError:
    return SecurityError(f"Template {what} too large (limit {MAX_SEQUENCE_LEN:,} items).")


def _check_size(value: Any, what: str = "value") -> Any:
    if isinstance(value, _SIZED_TYPES) and len(value) > MAX_SEQUENCE_LEN:
        raise _too_large(what)
    return value


def _check_width(width: Any, what: str) -> None:
    if isinstance(width, int) and width > MAX_SEQUENCE_LEN:
        raise _too_large(what)


def _check_product(count: int, size: int, what: str) -> None:
    if count > 0 and size > 0 and count * size > MAX_SEQUENCE_LEN:
        raise _too_large(what)


def _check_replace(s: Any, old: Any, new: Any, count: Any = None) -> None:
    s, old, new = str(s), str(old), str(new)
    if len(new) <= len(old):
        return
    occurrences = s.count(old) if old else len(s) + 1
    if isinstance(count, int) and 0 <= count < occurrences:
        occurrences = count
    _check_product(occurrences, len(new) - len(old), "replace() result")


def _check_join(sep: Any, items: Any) -> None:
    if isinstance(items, Sized):
        _check_product(len(items) - 1, len(str(sep)), "join() result")


def _int_values(values: Any) -> list[int]:
    if isinstance(values, dict):
        values = list(values.values())
    elif not isinstance(values, (list, tuple)):
        values = [values]
    return [v for v in values if isinstance(v, int) and not isinstance(v, bool)]


_PERCENT_SPEC = re.compile(r"%(?:\([^)]*\))?[#0\- +]*(\*|\d+)?(?:\.(\*|\d+))?")


def _check_percent_format(fmt: Any, values: Any) -> None:
    """Field widths/precisions in ``fmt % values`` (``*`` takes them from values)."""
    if not isinstance(fmt, str) or "%" not in fmt:
        return
    star = False
    for width, precision in _PERCENT_SPEC.findall(fmt):
        for part in (width, precision):
            if part == "*":
                star = True
            elif part:
                _check_width(int(part), "format width")
    if star:
        for v in _int_values(values):
            _check_width(v, "format width")


def _check_brace_format(fmt: str, args: Any, kwargs: Any) -> None:
    """Field widths/precisions in ``fmt.format(...)``, including nested ``{w}``."""
    try:
        fields = list(string.Formatter().parse(fmt))
    except ValueError:
        return  # malformed; str.format raises its own error
    nested = False
    for _literal, _field, spec, _conv in fields:
        if not spec:
            continue
        if "{" in spec:
            nested = True
        for digits in re.findall(r"\d+", spec):
            _check_width(int(digits), "format width")
    if nested:
        for v in _int_values(list(args)) + _int_values(dict(kwargs)):
            _check_width(v, "format width")


def _check_str_method(s: str, name: str, args: tuple, kwargs: dict) -> None:
    first = args[0] if args else None
    if name in ("center", "ljust", "rjust", "zfill"):
        _check_width(first if args else kwargs.get("width"), f"{name}() width")
    elif name == "expandtabs":
        tabsize = first if args else kwargs.get("tabsize", 8)
        if isinstance(tabsize, int):
            _check_product(s.count("\t"), tabsize, "expandtabs() result")
    elif name == "replace" and len(args) >= 2:
        _check_replace(s, args[0], args[1], args[2] if len(args) > 2 else kwargs.get("count"))
    elif name == "join" and args:
        _check_join(s, first)
    elif name in ("format", "format_map"):
        if name == "format_map" and args and isinstance(first, dict):
            _check_brace_format(s, (), first)
        else:
            _check_brace_format(s, args, kwargs)


# --- built-in filter pre-checks (arguments bound to the filter's own signature) ---


def _pre_center(a: dict[str, Any]) -> None:
    _check_width(a.get("width"), "center() width")


def _pre_indent(a: dict[str, Any]) -> None:
    width = a.get("width")
    size = len(width) if isinstance(width, str) else width
    if isinstance(size, int):
        _check_product(str(a.get("s", "")).count("\n") + 1, size, "indent() result")


def _pre_replace(a: dict[str, Any]) -> None:
    _check_replace(a.get("s", ""), a.get("old", ""), a.get("new", ""), a.get("count"))


def _pre_join(a: dict[str, Any]) -> None:
    _check_join(a.get("d", ""), a.get("value"))


def _pre_wordwrap(a: dict[str, Any]) -> None:
    width, wrap = a.get("width"), a.get("wrapstring") or "\n"
    if isinstance(width, int) and width > 0:
        _check_product(len(str(a.get("s", ""))) // width + 1, len(str(wrap)), "wordwrap() result")


def _pre_batch(a: dict[str, Any]) -> None:
    _check_width(a.get("linecount"), "batch() size")


def _pre_slice(a: dict[str, Any]) -> None:
    _check_width(a.get("slices"), "slice() count")


def _pre_sum(a: dict[str, Any]) -> None:
    items, start = a.get("iterable"), a.get("start")
    if isinstance(items, (list, tuple)):
        total = sum(len(x) for x in items if isinstance(x, _SEQUENCE_TYPES))
        if isinstance(start, _SEQUENCE_TYPES):
            total += len(start)
        _check_product(total, 1, "sum() result")


def _pre_format(a: dict[str, Any]) -> None:
    _check_percent_format(a.get("value"), a.get("args") or a.get("kwargs"))


_FILTER_PRECHECKS: dict[str, Callable[[dict[str, Any]], None]] = {
    "center": _pre_center,
    "indent": _pre_indent,
    "replace": _pre_replace,
    "join": _pre_join,
    "wordwrap": _pre_wordwrap,
    "batch": _pre_batch,
    "slice": _pre_slice,
    "sum": _pre_sum,
    "format": _pre_format,
}


def _limit_filter(name: str, func: Callable[..., Any]) -> Callable[..., Any]:
    precheck = _FILTER_PRECHECKS.get(name)
    try:
        sig = inspect.signature(func) if precheck else None
    except (TypeError, ValueError):
        sig = None

    @functools.wraps(func)  # keeps jinja_pass_arg (pass_context / eval_ctx / environment)
    def limited(*args: Any, **kwargs: Any) -> Any:
        if precheck is not None and sig is not None:
            try:
                bound = sig.bind(*args, **kwargs)
            except TypeError:
                bound = None  # let the filter raise its own argument error
            if bound is not None:
                bound.apply_defaults()
                precheck(dict(bound.arguments))
        return _check_size(func(*args, **kwargs), f"{name} result")

    return limited


class _BudgetedIterable:
    """Iterable wrapper charging each yielded item to the environment's loop budget."""

    __slots__ = ("_env", "_src")

    def __init__(self, env: LimitedSandboxedEnvironment, src: Any) -> None:
        self._env = env
        self._src = src

    def __iter__(self) -> Iterator[Any]:
        charge = self._env._charge_loop_item
        for item in self._src:
            charge()
            yield item

    def __len__(self) -> int:  # loop.length / revindex; TypeError if unsized
        return len(self._src)


def _env_call(name: str, arg: nodes.Expr, lineno: int) -> nodes.Call:
    return nodes.Call(nodes.EnvironmentAttribute(name, lineno=lineno), [arg], [], None, None, lineno=lineno)


class _LimitTransformer(NodeTransformer):
    """Route loop iterables and ``~`` concatenation through budget checks."""

    def visit_For(self, node: nodes.For) -> nodes.For:
        self.generic_visit(node)
        node.iter = _env_call("budget_loop_iterable", node.iter, node.lineno)
        return node

    def visit_Concat(self, node: nodes.Concat) -> nodes.Call:
        self.generic_visit(node)
        return _env_call("check_value_size", node, node.lineno)


class _CappedTemplate(Template):
    """Template whose ``render`` refuses to build oversized output."""

    def render(self, *args: Any, **kwargs: Any) -> str:
        chunks: list[str] = []
        total = 0
        for chunk in self.generate(*args, **kwargs):
            total += len(chunk)
            if total > MAX_RENDERED_PART_CHARS:
                raise SecurityError(
                    "Template output too large "
                    f"(over {MAX_RENDERED_PART_CHARS:,} characters in one document part)."
                )
            chunks.append(chunk)
        return "".join(chunks)


class LimitedSandboxedEnvironment(SandboxedEnvironment):
    """SandboxedEnvironment with CPU/memory limits for untrusted template expressions."""

    intercepted_binops = frozenset({"*", "+", "**", "%"})
    template_class = _CappedTemplate

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._range_used = 0
        self._loop_items = 0
        self._calls = 0
        self.globals["range"] = self._budgeted_range
        self.filters = {name: _limit_filter(name, f) for name, f in self.filters.items()}
        # Stored once so ``call`` can recognise them by identity (not budgeted as calls).
        self.budget_loop_iterable = self._budget_loop_iterable
        self.check_value_size = self._check_value_size

    # -- parse-time rewrite ---------------------------------------------------
    def _parse(self, source: str, name: str | None, filename: str | None) -> nodes.Template:
        tree = super()._parse(source, name, filename)
        tree = _LimitTransformer().visit(tree)
        tree.set_environment(self)
        return tree

    # -- budgets --------------------------------------------------------------
    def _budgeted_range(self, *args: int) -> range:
        rng = range(*args)
        self._range_used += len(rng)
        if self._range_used > MAX_RANGE_BUDGET:
            raise SecurityError(
                f"Template loops too large (range() budget of {MAX_RANGE_BUDGET:,} items exceeded)."
            )
        return rng

    def _charge_loop_item(self) -> None:
        self._loop_items += 1
        if self._loop_items > MAX_LOOP_ITERATIONS:
            raise SecurityError(
                f"Template loops too large (over {MAX_LOOP_ITERATIONS:,} iterations)."
            )

    def _budget_loop_iterable(self, iterable: Any) -> Any:
        if isinstance(iterable, Undefined):
            return iterable  # keep Undefined / StrictUndefined iteration semantics
        if isinstance(iterable, Sized):
            # No {% break %} in this environment: a sized loop runs len() times, so
            # charge it up front and iterate natively (no per-item overhead).
            self._loop_items += len(iterable)
            if self._loop_items > MAX_LOOP_ITERATIONS:
                raise SecurityError(
                    f"Template loops too large (over {MAX_LOOP_ITERATIONS:,} iterations)."
                )
            return iterable
        return _BudgetedIterable(self, iterable)

    def _check_value_size(self, value: Any) -> Any:
        return _check_size(value, "concatenation")

    # -- sandbox hooks --------------------------------------------------------
    def call(__self, __context: Any, __obj: Any, *args: Any, **kwargs: Any) -> Any:  # noqa: N805
        if __obj is __self.budget_loop_iterable or __obj is __self.check_value_size:
            return __obj(*args)
        __self._calls += 1
        if __self._calls > MAX_CALLS:
            raise SecurityError(f"Template makes too many calls (over {MAX_CALLS:,}).")
        if isinstance(__obj, LoopContext) and args:
            # Recursive loop: budget the iterable handed to loop(...).
            args = (__self._budget_loop_iterable(args[0]), *args[1:])
        target = getattr(__obj, "__wrapped__", __obj)  # sandbox wraps str.format
        owner = getattr(target, "__self__", None)
        if isinstance(owner, str):
            _check_str_method(owner, getattr(target, "__name__", ""), args, kwargs)
        result = super().call(__context, __obj, *args, **kwargs)
        _check_size(result, "call result")
        if isinstance(owner, _MUTABLE_TYPES):
            _check_size(owner, "container")
        return result

    def call_binop(self, context: Any, operator_: str, left: Any, right: Any) -> Any:
        if operator_ == "*":
            for seq, n in ((left, right), (right, left)):
                if isinstance(seq, _SEQUENCE_TYPES) and isinstance(n, int):
                    if len(seq) * max(n, 0) > MAX_SEQUENCE_LEN:
                        raise SecurityError(
                            f"Template repetition too large (limit {MAX_SEQUENCE_LEN:,} items)."
                        )
            return operator.mul(left, right)
        if operator_ == "+":
            if isinstance(left, _SEQUENCE_TYPES) and isinstance(right, _SEQUENCE_TYPES):
                if len(left) + len(right) > MAX_SEQUENCE_LEN:
                    raise SecurityError(
                        f"Template concatenation too large (limit {MAX_SEQUENCE_LEN:,} items)."
                    )
            return operator.add(left, right)
        if operator_ == "%":
            if isinstance(left, str):
                _check_percent_format(left, right)
                return _check_size(operator.mod(left, right), "% format result")
            return operator.mod(left, right)
        if operator_ == "**":
            if (
                isinstance(left, int)
                and isinstance(right, int)
                and abs(left) > 1
                and right > 0
                and right * math.log2(abs(left)) > MAX_POW_BITS
            ):
                raise SecurityError("Template exponent too large.")
            return operator.pow(left, right)
        return super().call_binop(context, operator_, left, right)


def make_report_jinja_env(*, strict: bool = True) -> LimitedSandboxedEnvironment:
    """New per-render environment (fresh budgets). ``strict`` → StrictUndefined."""
    return LimitedSandboxedEnvironment(
        undefined=StrictUndefined if strict else Undefined,
        autoescape=True,
    )
