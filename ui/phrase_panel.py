"""Streamlit UI for multiple-choice standard phrases."""

from __future__ import annotations

from typing import Any

import streamlit as st

from phrase_resolver import SELECTED_SUFFIX, list_phrase_definitions


def _init_phrase_state() -> None:
    if "phrase_selections" not in st.session_state:
        st.session_state.phrase_selections = {}
    if "phrase_option_ids" not in st.session_state:
        st.session_state.phrase_option_ids = {}


def render_phrase_panel(*, compact: bool = False) -> dict[str, str]:
    """
    Show selectboxes for each phrase in phrase_catalog.json.
    Returns meta fields to merge (phrase_key -> text, phrase_key_option_id -> id).
    """
    _init_phrase_state()
    phrases = list_phrase_definitions()
    if not phrases:
        return {}

    if not compact:
        st.subheader("Standard phrases (optional)")
        st.caption(
            "Choose wording for tagged template fields. Selections override Excel "
            f"when the template uses `{{{{ phrase_key }}}}` or `{{phrase_key}}_selected` in ProjectData."
        )

    meta_out: dict[str, str] = {}
    selections: dict[str, str] = st.session_state.phrase_selections
    option_ids: dict[str, str] = st.session_state.phrase_option_ids

    for phrase_key in sorted(phrases):
        spec = phrases[phrase_key]
        label = str(spec.get("label", phrase_key))
        options = list(spec.get("options", []))
        if not options:
            continue

        labels = ["— Use Excel / template default —"] + [
            str(o.get("label", o.get("id", ""))) for o in options
        ]
        ids = [""] + [str(o.get("id", "")) for o in options]

        prev_id = option_ids.get(phrase_key, "")
        try:
            default_index = ids.index(prev_id) if prev_id in ids else 0
        except ValueError:
            default_index = 0

        choice = st.selectbox(
            label,
            options=range(len(labels)),
            format_func=lambda i: labels[i],
            index=default_index,
            key=f"phrase_sel_{phrase_key}",
        )

        if choice == 0:
            selections.pop(phrase_key, None)
            option_ids.pop(phrase_key, None)
            continue

        opt_id = ids[choice]
        text = str(options[choice - 1].get("text", "")).strip()
        selections[phrase_key] = text
        option_ids[phrase_key] = opt_id
        meta_out[phrase_key] = text
        meta_out[f"{phrase_key}_option_id"] = opt_id

    st.session_state.phrase_selections = selections
    st.session_state.phrase_option_ids = option_ids
    return meta_out


def phrase_meta_for_render() -> dict[str, str]:
    """Call once per run; returns keys to merge into render meta."""
    return render_phrase_panel()
