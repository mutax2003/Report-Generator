"""Load Alberta standard prompt library (schemas/alberta_prompt_library.json).

Prompts are advisory for LLM narrative drafts and external agents (Cursor / Codex /
Claude Cowork). Never imported by ReportEngine.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_PATH = ROOT / "schemas" / "alberta_prompt_library.json"

# Keep library small (prompt text only).
MAX_LIBRARY_BYTES = 512 * 1024
MAX_ID_LEN = 64
_SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")

REQUIRED_TOP_KEYS = ("version", "profiles")
REQUIRED_PROFILE_KEYS = ("label", "report_types", "sections", "system_addon")

logger = logging.getLogger(__name__)

# report_type → profile key in library
_REPORT_TYPE_TO_PROFILE: dict[str, str] = {
    "phase1_alberta": "phase1_alberta",
    "phase1_devon": "phase1_alberta",
    "phase2_esa": "phase2_esa",
    "groundwater_monitoring": "groundwater_monitoring",
    "reclamation_certificate": "reclamation_certificate",
    "phase3_remediation": "phase3_remediation",
    "template_driven": "template_driven",
}

_FALLBACK_SYSTEM = (
    "You draft professional ESA report prose for Ecoventure Inc. (Alberta oil and gas). "
    "Use only facts from the JSON context and reference snippets. "
    "Do not invent regulatory citations or sample results. "
    "Mark uncertainty. 2-4 short paragraphs max."
)


class PromptLibraryError(ValueError):
    """Invalid or unreadable Alberta prompt library."""


def _sanitize_id(value: str, *, what: str = "id") -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) > MAX_ID_LEN or not _SAFE_ID.match(text):
        raise PromptLibraryError(f"Invalid {what}: {text[:80]!r}")
    return text


def validate_library_payload(data: Any) -> dict[str, Any]:
    """Raise PromptLibraryError if structure is unsafe or incomplete."""
    if not isinstance(data, dict):
        raise PromptLibraryError("Prompt library root must be a JSON object.")
    for key in REQUIRED_TOP_KEYS:
        if key not in data:
            raise PromptLibraryError(f"Prompt library missing required key: {key}")
    profiles = data.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise PromptLibraryError("Prompt library 'profiles' must be a non-empty object.")
    for name, profile in profiles.items():
        _sanitize_id(str(name), what="profile key")
        if not isinstance(profile, dict):
            raise PromptLibraryError(f"Profile {name!r} must be an object.")
        for key in REQUIRED_PROFILE_KEYS:
            if key not in profile:
                raise PromptLibraryError(f"Profile {name!r} missing key: {key}")
        types = profile.get("report_types")
        if not isinstance(types, list) or not all(isinstance(t, str) for t in types):
            raise PromptLibraryError(f"Profile {name!r} report_types must be a string list.")
        sections = profile.get("sections")
        if not isinstance(sections, list) or not all(isinstance(s, str) for s in sections):
            raise PromptLibraryError(f"Profile {name!r} sections must be a string list.")
        instr = profile.get("section_instructions")
        if instr is not None and not isinstance(instr, dict):
            raise PromptLibraryError(
                f"Profile {name!r} section_instructions must be an object."
            )
    tasks = data.get("agent_tasks")
    if tasks is not None:
        if not isinstance(tasks, dict):
            raise PromptLibraryError("'agent_tasks' must be an object.")
        for tid, task in tasks.items():
            _sanitize_id(str(tid), what="agent task id")
            if not isinstance(task, dict):
                raise PromptLibraryError(f"Agent task {tid!r} must be an object.")
            if "prompt" in task and not isinstance(task.get("prompt"), str):
                raise PromptLibraryError(f"Agent task {tid!r} prompt must be a string.")
    return data


@lru_cache(maxsize=1)
def _load_prompt_library_cached() -> dict[str, Any]:
    """Cached soft load (never raises)."""
    try:
        if not LIBRARY_PATH.is_file():
            logger.warning("Prompt library not found: %s", LIBRARY_PATH)
            return {}
        size = LIBRARY_PATH.stat().st_size
        if size <= 0:
            raise PromptLibraryError("Prompt library file is empty.")
        if size > MAX_LIBRARY_BYTES:
            raise PromptLibraryError(
                f"Prompt library too large ({size} bytes; max {MAX_LIBRARY_BYTES})."
            )
        raw = LIBRARY_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        return validate_library_payload(data)
    except (PromptLibraryError, OSError, UnicodeError, json.JSONDecodeError) as e:
        logger.warning("Prompt library load failed (%s); using empty fallback", e)
        return {}


def load_prompt_library(*, strict: bool = False) -> dict[str, Any]:
    """Load and validate the library. Soft-fails to {} unless strict=True."""
    if not strict:
        return _load_prompt_library_cached()
    if not LIBRARY_PATH.is_file():
        raise PromptLibraryError(f"Prompt library not found: {LIBRARY_PATH}")
    size = LIBRARY_PATH.stat().st_size
    if size <= 0:
        raise PromptLibraryError("Prompt library file is empty.")
    if size > MAX_LIBRARY_BYTES:
        raise PromptLibraryError(
            f"Prompt library too large ({size} bytes; max {MAX_LIBRARY_BYTES})."
        )
    try:
        raw = LIBRARY_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        raise PromptLibraryError(f"Could not read prompt library: {e}") from e
    return validate_library_payload(data)


def clear_prompt_library_cache() -> None:
    _load_prompt_library_cached.cache_clear()


def profile_key_for_report_type(report_type: str) -> str:
    try:
        rt = _sanitize_id(str(report_type or "").strip(), what="report_type")
    except PromptLibraryError:
        rt = ""
    if not rt:
        return "phase1_alberta"
    if rt in _REPORT_TYPE_TO_PROFILE:
        return _REPORT_TYPE_TO_PROFILE[rt]
    lib = load_prompt_library()
    for key, profile in (lib.get("profiles") or {}).items():
        types = profile.get("report_types") or []
        if rt in types:
            return str(key)
    return "template_driven"


def get_profile(report_type: str) -> dict[str, Any]:
    lib = load_prompt_library()
    key = profile_key_for_report_type(report_type)
    profiles = lib.get("profiles") or {}
    profile = profiles.get(key) or profiles.get("template_driven") or {}
    return dict(profile) if isinstance(profile, dict) else {}


def sections_for_report_type(report_type: str) -> list[str]:
    profile = get_profile(report_type)
    sections = profile.get("sections")
    if isinstance(sections, list) and sections:
        return [str(s) for s in sections if str(s).strip()]
    return []


def system_prompt_for(report_type: str) -> str:
    """Full system message: global + profile addon."""
    lib = load_prompt_library()
    global_sys = str(lib.get("global_system") or "").strip()
    profile = get_profile(report_type)
    addon = str(profile.get("system_addon") or "").strip()
    parts = [p for p in (global_sys, addon) if p]
    return "\n\n".join(parts) if parts else _FALLBACK_SYSTEM


def section_instruction(report_type: str, section: str) -> str:
    try:
        sec = _sanitize_id(section, what="section")
    except PromptLibraryError:
        sec = "section"
    profile = get_profile(report_type)
    instructions = profile.get("section_instructions") or {}
    if isinstance(instructions, dict):
        text = instructions.get(sec)
        if text:
            return str(text).strip()
    return (
        f"Draft the '{sec}' section using only supplied context. "
        "Mark uncertainty. 2-4 short paragraphs max."
    )


def agent_brief(report_type: str) -> str:
    profile = get_profile(report_type)
    brief = str(profile.get("agent_brief") or "").strip()
    if brief:
        return brief
    return str(load_prompt_library().get("tone") or "")


def agent_task_prompt(task_id: str) -> str:
    try:
        tid = _sanitize_id(task_id, what="agent task id")
    except PromptLibraryError:
        return ""
    if not tid:
        return ""
    lib = load_prompt_library()
    tasks = lib.get("agent_tasks") or {}
    task = tasks.get(tid) or {}
    if not isinstance(task, dict):
        return ""
    return str(task.get("prompt") or "").strip()


def list_profile_keys() -> list[str]:
    lib = load_prompt_library()
    return sorted(str(k) for k in (lib.get("profiles") or {}).keys())


def list_agent_task_ids() -> list[str]:
    lib = load_prompt_library()
    return sorted(str(k) for k in (lib.get("agent_tasks") or {}).keys())
