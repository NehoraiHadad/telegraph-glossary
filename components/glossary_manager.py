"""Glossary manager UI component."""

import streamlit as st
from datetime import datetime
from typing import Dict, Any

from services.telegraph_service import TelegraphService
from utils.helpers import show_toast, truncate_text


def render_glossary_manager() -> None:
    st.header("Glossary")
    if "edit_term" not in st.session_state:
        st.session_state.edit_term = None
    col1, col2 = st.columns([1, 2])
    with col1:
        add_new = st.button("+ Add New Term", type="primary", use_container_width=True)
    with col2:
        search_query = st.text_input("Search terms", placeholder="Filter glossary...", label_visibility="collapsed")
    if add_new or st.session_state.get("show_add_form"):
        st.session_state.show_add_form = True
        _render_add_form()
    st.divider()
    glossary = st.session_state.get("glossary", {})
    if not glossary:
        st.info("No terms in your glossary yet.")
        return
    filtered_terms = glossary
    if search_query:
        search_lower = search_query.lower()
        filtered_terms = {t: d for t, d in glossary.items() if search_lower in t.lower() or search_lower in d.get("definition", "").lower()}
    if not filtered_terms:
        st.warning(f"No terms matching '{search_query}'")
        return
    for term, data in sorted(filtered_terms.items()):
        _render_term_card(term, data)


def _render_add_form() -> None:
    with st.expander("Add New Term", expanded=True):
        with st.form("add_term_form"):
            new_term = st.text_input("Term", placeholder="e.g., API")
            new_definition = st.text_area("Definition", placeholder="Enter the definition...", height=100)
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Add Term", type="primary")
            with col2:
                cancel = st.form_submit_button("Cancel")
            if submit and new_term and new_definition:
                _add_term(new_term, new_definition)
            if cancel:
                st.session_state.show_add_form = False
                st.rerun()


def _render_term_card(term: str, data: Dict[str, Any]) -> None:
    definition = data.get("definition", "")
    url = data.get("telegraph_url", "")
    is_editing = st.session_state.edit_term == term
    if is_editing:
        _render_edit_form(term, data)
    else:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.markdown(f"**{term}**")
            with col2:
                if st.button("Edit", key=f"edit_{term}", use_container_width=True):
                    st.session_state.edit_term = term
                    st.rerun()
            with col3:
                if st.button("Delete", key=f"delete_{term}", use_container_width=True):
                    _delete_term(term)
            with col4:
                if url:
                    st.link_button("Open", url, use_container_width=True)
            st.markdown(f"<div class='rtl-text'>{truncate_text(definition, 200)}</div>", unsafe_allow_html=True)
            if url:
                st.code(url, language=None)
            st.divider()


def _render_edit_form(term: str, data: Dict[str, Any]) -> None:
    with st.form(f"edit_form_{term}"):
        new_term = st.text_input("Term", value=term)
        new_definition = st.text_area("Definition", value=data.get("definition", ""), height=150)
        col1, col2 = st.columns(2)
        with col1:
            save = st.form_submit_button("Save", type="primary")
        with col2:
            cancel = st.form_submit_button("Cancel")
        if save and new_term and new_definition:
            _update_term(term, new_term, new_definition, data)
        if cancel:
            st.session_state.edit_term = None
            st.rerun()


def _add_term(term: str, definition: str) -> None:
    glossary = st.session_state.get("glossary", {})
    if term in glossary:
        st.error(f"Term '{term}' already exists.")
        return
    telegraph = st.session_state.get("telegraph")
    if not telegraph:
        st.error("Telegraph service not initialized.")
        return
    try:
        with st.spinner("Creating Telegraph page..."):
            result = telegraph.create_term_page(term, definition)
        now = datetime.now().isoformat()
        glossary[term] = {"term": term, "definition": definition, "telegraph_path": result["path"], "telegraph_url": result["url"], "created_at": now, "updated_at": now}
        st.session_state.glossary = glossary
        _update_index_page(glossary)
        st.session_state.show_add_form = False
        show_toast(f"Added '{term}'!")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to add term: {e}")


def _update_term(old_term: str, new_term: str, new_definition: str, data: Dict[str, Any]) -> None:
    glossary = st.session_state.get("glossary", {})
    telegraph = st.session_state.get("telegraph")
    if not telegraph:
        st.error("Telegraph service not initialized.")
        return
    try:
        with st.spinner("Updating Telegraph page..."):
            path = data.get("telegraph_path", "")
            if path:
                result = telegraph.update_term_page(path, new_term, new_definition)
            else:
                result = telegraph.create_term_page(new_term, new_definition)
        if old_term != new_term:
            del glossary[old_term]
        now = datetime.now().isoformat()
        glossary[new_term] = {"term": new_term, "definition": new_definition, "telegraph_path": result["path"], "telegraph_url": result["url"], "created_at": data.get("created_at", now), "updated_at": now}
        st.session_state.glossary = glossary
        _update_index_page(glossary)
        st.session_state.edit_term = None
        show_toast(f"Updated '{new_term}'!")
        st.rerun()
    except ValueError as e:
        # Verification failed - Telegraph page was not actually updated
        st.error(f"Update verification failed: {e}")
        st.info("Tip: Try deleting this term and creating it again.")
    except Exception as e:
        st.error(f"Failed to update term: {e}")


def _delete_term(term: str) -> None:
    glossary = st.session_state.get("glossary", {})
    if term not in glossary:
        return
    del glossary[term]
    st.session_state.glossary = glossary
    _update_index_page(glossary)
    show_toast(f"Removed '{term}'")
    st.rerun()


def _update_index_page(glossary: Dict[str, Dict[str, Any]]) -> None:
    telegraph = st.session_state.get("telegraph")
    config = st.session_state.get("config", {})
    if not telegraph:
        return
    try:
        index_path = config.get("telegraph", {}).get("index_page_path")
        telegraph.create_index_page(glossary, index_path)
    except Exception as e:
        st.warning(f"Failed to update index page: {e}")
