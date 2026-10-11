"""
Jinja2 sandbox for docxtpl merges (main report + appendices).

- ``autoescape=True``: Excel/sidebar values are XML-escaped before they land in
  WordprocessingML (``<0.005`` stays ``<0.005``; ``Smith & Sons`` keeps the ``&``;
  a cell cannot inject ``<w:r>`` markup). docxtpl ``RichText`` / ``Listing`` /
  ``InlineImage`` / ``Subdoc`` implement ``__html__`` and still render as XML.
- Resource limits: cumulative ``range()`` budget per render, capped string/list
  repetition and concatenation, capped ``**``, and a cap on rendered XML size.
"""

from __future__ import annotations

import math
import operator
from typing import Any

from jinja2 import StrictUndefined, Template, Undefined
from jinja2.sandbox import SandboxedEnvironment, SecurityError

# Total range() items a single render may create (all parts, nested loops included).
MAX_RANGE_BUDGET = 100_000
# Longest str/list/tuple a template expression may build via * or +.
MAX_SEQUENCE_LEN = 1_000_000
# Largest integer (in bits) a template may build via **.
MAX_POW_BITS = 4_096
# Rendered XML characters per docx part (mirrors MAX_ZIP_UNCOMPRESSED_BYTES).
MAX_RENDERED_PART_CHARS = 120 * 1024 * 1024

_SEQUENCE_TYPES = (str, list, tuple)


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

    intercepted_binops = frozenset({"*", "+", "**"})
    template_class = _CappedTemplate

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._range_used = 0
        self.globals["range"] = self._budgeted_range

    def _budgeted_range(self, *args: int) -> range:
        rng = range(*args)
        self._range_used += len(rng)
        if self._range_used > MAX_RANGE_BUDGET:
            raise SecurityError(
                f"Template loops too large (range() budget of {MAX_RANGE_BUDGET:,} items exceeded)."
            )
        return rng

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
    """New per-render environment (fresh range budget). ``strict`` → StrictUndefined."""
    return LimitedSandboxedEnvironment(
        undefined=StrictUndefined if strict else Undefined,
        autoescape=True,
    )
