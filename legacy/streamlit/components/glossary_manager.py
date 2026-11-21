"""Glossary manager UI component."""

import streamlit as st
from datetime import datetime
from typing import Dict, Any

from services.telegraph_service import TelegraphService
from services.content_converter import ContentConverter
from components.rich_editor import render_rich_editor, inject_editor_rtl_css
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
        # Inject RTL CSS for Hebrew support
        inject_editor_rtl_css()

        new_term = st.text_input("Term", placeholder="e.g., API", key="add_term_input")

        st.markdown("**Definition**")
        telegraph_service = st.session_state.get("telegraph")
        html_content, raw_content = render_rich_editor(
            key="add_term_editor",
            initial_content="",
            initial_mode="markdown",
            height=250,
            telegraph_service=telegraph_service,
            show_preview=True
        )

        # Store content in session state for form submission
        st.session_state["add_term_html"] = html_content
        st.session_state["add_term_raw"] = raw_content

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Add Term", type="primary", key="add_term_submit"):
                if new_term and raw_content:
                    _add_term(new_term, html_content, raw_content)
                else:
                    st.warning("Please enter both term and definition.")
        with col2:
            if st.button("Cancel", key="add_term_cancel"):
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
    # Inject RTL CSS for Hebrew support
    inject_editor_rtl_css()

    new_term = st.text_input("Term", value=term, key=f"edit_term_input_{term}")

    st.markdown("**Definition**")
    telegraph_service = st.session_state.get("telegraph")

    # Get initial content - prefer HTML if available, otherwise use plain text
    initial_content = data.get("definition_html", data.get("definition", ""))

    html_content, raw_content = render_rich_editor(
        key=f"edit_term_editor_{term}",
        initial_content=initial_content,
        initial_mode="markdown",
        height=250,
        telegraph_service=telegraph_service,
        show_preview=True
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save", type="primary", key=f"edit_save_{term}"):
            if new_term and raw_content:
                _update_term(term, new_term, html_content, raw_content, data)
            else:
                st.warning("Please enter both term and definition.")
    with col2:
        if st.button("Cancel", key=f"edit_cancel_{term}"):
            st.session_state.edit_term = None
            st.rerun()


def _add_term(term: str, html_content: str, raw_content: str) -> None:
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
            # Use is_html=True to pass pre-formatted HTML content
            result = telegraph.create_term_page(term, html_content, is_html=True)
        now = datetime.now().isoformat()
        # Extract plain text for display/search
        plain_text = ContentConverter.extract_plain_text(html_content)
        glossary[term] = {
            "term": term,
            "definition": plain_text,  # Plain text for backward compatibility
            "definition_html": html_content,  # HTML for rich display
            "definition_format": "html",  # Mark as HTML format
            "telegraph_path": result["path"],
            "telegraph_url": result["url"],
            "created_at": now,
            "updated_at": now
        }
        st.session_state.glossary = glossary
        _update_index_page(glossary)
        st.session_state.show_add_form = False
        # Clear editor state
        for key in list(st.session_state.keys()):
            if key.startswith("add_term_editor"):
                del st.session_state[key]
        show_toast(f"Added '{term}'!")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to add term: {e}")


def _update_term(old_term: str, new_term: str, html_content: str, raw_content: str, data: Dict[str, Any]) -> None:
    glossary = st.session_state.get("glossary", {})
    telegraph = st.session_state.get("telegraph")
    if not telegraph:
        st.error("Telegraph service not initialized.")
        return
    try:
        with st.spinner("Updating Telegraph page..."):
            path = data.get("telegraph_path", "")
            if path:
                # Use is_html=True to pass pre-formatted HTML content
                result = telegraph.update_term_page(path, new_term, html_content, is_html=True)
            else:
                result = telegraph.create_term_page(new_term, html_content, is_html=True)
        if old_term != new_term:
            del glossary[old_term]
        now = datetime.now().isoformat()
        # Extract plain text for display/search
        plain_text = ContentConverter.extract_plain_text(html_content)
        glossary[new_term] = {
            "term": new_term,
            "definition": plain_text,  # Plain text for backward compatibility
            "definition_html": html_content,  # HTML for rich display
            "definition_format": "html",  # Mark as HTML format
            "telegraph_path": result["path"],
            "telegraph_url": result["url"],
            "created_at": data.get("created_at", now),
            "updated_at": now
        }
        st.session_state.glossary = glossary
        _update_index_page(glossary)
        st.session_state.edit_term = None
        # Clear editor state
        for key in list(st.session_state.keys()):
            if key.startswith(f"edit_term_editor_{old_term}"):
                del st.session_state[key]
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
