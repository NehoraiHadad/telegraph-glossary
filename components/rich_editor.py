"""Rich text editor component for Telegraph Glossary with Markdown and WYSIWYG modes."""

from typing import Optional, Tuple
import streamlit as st
import streamlit.components.v1 as components

from services.content_converter import ContentConverter


def render_rich_editor(
    key: str,
    initial_content: str = "",
    initial_mode: str = "markdown",
    height: int = 300,
    telegraph_service=None,
    show_preview: bool = True
) -> Tuple[str, str]:
    """
    Render a rich text editor with Markdown and WYSIWYG modes.

    Args:
        key: Unique key for this editor instance (prevents conflicts in session_state)
        initial_content: Initial content to display (markdown or HTML)
        initial_mode: Initial editor mode - "markdown" or "wysiwyg"
        height: Height of the editor in pixels
        telegraph_service: Optional TelegraphService instance for image uploads
        show_preview: Whether to show the markdown preview pane

    Returns:
        Tuple of (html_content, raw_content)
        - html_content: Telegraph-ready HTML content
        - raw_content: Original markdown or HTML from the editor
    """
    # Initialize session state for this editor instance
    state_key_mode = f"{key}_editor_mode"
    state_key_content = f"{key}_editor_content"
    state_key_wysiwyg_content = f"{key}_wysiwyg_content"
    state_key_image_upload = f"{key}_image_upload"

    # Initialize state on first render
    if state_key_mode not in st.session_state:
        st.session_state[state_key_mode] = initial_mode
    if state_key_content not in st.session_state:
        st.session_state[state_key_content] = initial_content
    if state_key_wysiwyg_content not in st.session_state:
        # Convert markdown to HTML for WYSIWYG if needed
        if ContentConverter.is_html_content(initial_content):
            st.session_state[state_key_wysiwyg_content] = initial_content
        else:
            st.session_state[state_key_wysiwyg_content] = ContentConverter.markdown_to_html(initial_content)

    # Editor mode toggle
    st.markdown("**Editor Mode**")
    col_mode1, col_mode2 = st.columns(2)

    with col_mode1:
        if st.button(
            "📝 Markdown" + (" ✓" if st.session_state[state_key_mode] == "markdown" else ""),
            key=f"{key}_btn_markdown",
            use_container_width=True,
            type="primary" if st.session_state[state_key_mode] == "markdown" else "secondary"
        ):
            _switch_to_markdown(state_key_mode, state_key_content, state_key_wysiwyg_content)

    with col_mode2:
        if st.button(
            "✨ WYSIWYG" + (" ✓" if st.session_state[state_key_mode] == "wysiwyg" else ""),
            key=f"{key}_btn_wysiwyg",
            use_container_width=True,
            type="primary" if st.session_state[state_key_mode] == "wysiwyg" else "secondary"
        ):
            _switch_to_wysiwyg(state_key_mode, state_key_content, state_key_wysiwyg_content)

    st.divider()

    # Image upload section (available in both modes)
    if telegraph_service:
        _render_image_uploader(key, state_key_mode, state_key_content, state_key_wysiwyg_content, telegraph_service)

    # Render the appropriate editor
    current_mode = st.session_state[state_key_mode]

    if current_mode == "markdown":
        html_content, raw_content = _render_markdown_editor(
            key, state_key_content, height, show_preview
        )
    else:  # wysiwyg
        html_content, raw_content = _render_wysiwyg_editor(
            key, state_key_wysiwyg_content, height
        )

    return html_content, raw_content


def _switch_to_markdown(state_key_mode: str, state_key_content: str, state_key_wysiwyg_content: str) -> None:
    """Switch editor mode to Markdown, converting content if necessary."""
    if st.session_state[state_key_mode] != "markdown":
        # Convert WYSIWYG HTML content to Markdown
        wysiwyg_content = st.session_state.get(state_key_wysiwyg_content, "")
        if wysiwyg_content:
            markdown_content = ContentConverter.html_to_markdown(wysiwyg_content)
            st.session_state[state_key_content] = markdown_content
        st.session_state[state_key_mode] = "markdown"


def _switch_to_wysiwyg(state_key_mode: str, state_key_content: str, state_key_wysiwyg_content: str) -> None:
    """Switch editor mode to WYSIWYG, converting content if necessary."""
    if st.session_state[state_key_mode] != "wysiwyg":
        # Convert Markdown content to HTML for WYSIWYG
        markdown_content = st.session_state.get(state_key_content, "")
        if markdown_content:
            html_content = ContentConverter.markdown_to_html(markdown_content)
            st.session_state[state_key_wysiwyg_content] = html_content
        st.session_state[state_key_mode] = "wysiwyg"


def _render_markdown_editor(
    key: str,
    state_key_content: str,
    height: int,
    show_preview: bool
) -> Tuple[str, str]:
    """Render the Markdown editor with optional live preview."""
    if show_preview:
        col_edit, col_preview = st.columns(2)

        with col_edit:
            st.markdown("**✍️ Editor**")
            markdown_content = st.text_area(
                "Markdown Content",
                value=st.session_state[state_key_content],
                height=height,
                key=f"{key}_markdown_textarea",
                label_visibility="collapsed",
                placeholder="Enter your content in Markdown...\n\n**Bold** *Italic* ~~Strike~~\n[Link](url)\n![Image](url)"
            )

        with col_preview:
            st.markdown("**👁️ Preview**")
            if markdown_content:
                html_preview = ContentConverter.markdown_to_html(markdown_content)
                # Wrap in a styled container with scroll
                st.markdown(
                    f"""
                    <div style="
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        padding: 1rem;
                        height: {height}px;
                        overflow-y: auto;
                        background-color: #f9f9f9;
                    ">
                        {html_preview}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.info("Preview will appear here...")
    else:
        # No preview, full-width editor
        st.markdown("**✍️ Markdown Editor**")
        markdown_content = st.text_area(
            "Markdown Content",
            value=st.session_state[state_key_content],
            height=height,
            key=f"{key}_markdown_textarea_full",
            label_visibility="collapsed",
            placeholder="Enter your content in Markdown..."
        )

    # Update session state
    st.session_state[state_key_content] = markdown_content

    # Convert to HTML for Telegraph
    html_content = ContentConverter.markdown_to_html(markdown_content)
    html_content = ContentConverter.sanitize_for_telegraph(html_content)

    return html_content, markdown_content


def _render_wysiwyg_editor(
    key: str,
    state_key_wysiwyg_content: str,
    height: int
) -> Tuple[str, str]:
    """Render the WYSIWYG editor using streamlit-quill or fallback to HTML textarea."""
    st.markdown("**✨ Visual Editor**")

    # Try to import streamlit-quill for WYSIWYG editing
    try:
        from streamlit_quill import st_quill

        # Configure toolbar for Telegraph-supported features
        toolbar_options = [
            ['bold', 'italic', 'underline', 'strike'],
            ['blockquote', 'code-block'],
            [{'header': [3, 4, False]}],
            [{'list': 'ordered'}, {'list': 'bullet'}],
            ['link', 'image'],
            ['clean']
        ]

        # Render the Quill editor
        content = st_quill(
            value=st.session_state[state_key_wysiwyg_content],
            placeholder="Start typing your content...",
            html=True,
            toolbar=toolbar_options,
            key=f"{key}_quill_editor"
        )

        # Update session state
        if content:
            st.session_state[state_key_wysiwyg_content] = content

        # Sanitize for Telegraph
        html_content = ContentConverter.sanitize_for_telegraph(content or "")

        return html_content, content or ""

    except ImportError:
        # Fallback: Use regular HTML textarea with a helpful message
        st.info("📦 Install `streamlit-quill` for visual editing: `pip install streamlit-quill`")
        st.markdown("**HTML Editor (Fallback)**")

        html_content = st.text_area(
            "HTML Content",
            value=st.session_state[state_key_wysiwyg_content],
            height=height,
            key=f"{key}_html_textarea",
            label_visibility="collapsed",
            placeholder="<p>Enter HTML content...</p>\n<b>Bold</b> <i>Italic</i> <a href='url'>Link</a>"
        )

        # Update session state
        st.session_state[state_key_wysiwyg_content] = html_content

        # Show preview
        if html_content:
            st.markdown("**Preview:**")
            st.markdown(
                f"""
                <div style="
                    border: 1px solid #ddd;
                    border-radius: 4px;
                    padding: 1rem;
                    background-color: #f9f9f9;
                ">
                    {html_content}
                </div>
                """,
                unsafe_allow_html=True
            )

        # Sanitize for Telegraph
        sanitized_html = ContentConverter.sanitize_for_telegraph(html_content)

        return sanitized_html, html_content


def _render_image_uploader(
    key: str,
    state_key_mode: str,
    state_key_content: str,
    state_key_wysiwyg_content: str,
    telegraph_service
) -> None:
    """Render image uploader that inserts images into the editor."""
    with st.expander("📷 Upload Image", expanded=False):
        uploaded_file = st.file_uploader(
            "Choose an image",
            type=["jpg", "jpeg", "png", "gif"],
            key=f"{key}_image_uploader",
            help="Upload an image to insert into your content"
        )

        if uploaded_file is not None:
            # Show preview
            st.image(uploaded_file, caption="Image preview", use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                image_description = st.text_input(
                    "Image description (alt text)",
                    key=f"{key}_img_desc",
                    placeholder="Brief description..."
                )

            with col2:
                st.markdown("<br>", unsafe_allow_html=True)  # Spacing
                if st.button("Insert Image", key=f"{key}_insert_img", type="primary"):
                    _handle_image_insertion(
                        uploaded_file,
                        image_description,
                        state_key_mode,
                        state_key_content,
                        state_key_wysiwyg_content,
                        telegraph_service
                    )


def _handle_image_insertion(
    uploaded_file,
    description: str,
    state_key_mode: str,
    state_key_content: str,
    state_key_wysiwyg_content: str,
    telegraph_service
) -> None:
    """Handle the image upload and insertion into the editor."""
    try:
        with st.spinner("Uploading image to Telegraph..."):
            # Use ImageUploadService for reliable uploads
            from services.image_upload_service import ImageUploadService, ImageUploadError

            upload_service = ImageUploadService()
            image_url = upload_service.upload_from_streamlit(uploaded_file)

        # Insert into the appropriate editor
        current_mode = st.session_state[state_key_mode]
        alt_text = description or "image"

        if current_mode == "markdown":
            # Insert markdown syntax
            markdown_img = f"\n![{alt_text}]({image_url})\n"
            st.session_state[state_key_content] += markdown_img
            st.success("Image inserted into Markdown editor!")
        else:
            # Insert HTML figure
            html_img = f'\n<figure><img src="{image_url}" alt="{alt_text}"/></figure>\n'
            st.session_state[state_key_wysiwyg_content] += html_img
            st.success("Image inserted into WYSIWYG editor!")

        st.rerun()

    except ImageUploadError as e:
        st.error(f"Image upload failed: {str(e)}")
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")


# RTL Support CSS
def inject_editor_rtl_css() -> None:
    """Inject CSS for RTL text support in the editor."""
    st.markdown(
        """
        <style>
            /* RTL support for text areas */
            .rtl-text textarea,
            .rtl-text .stTextArea textarea {
                direction: rtl;
                text-align: right;
                unicode-bidi: plaintext;
            }

            /* RTL support for preview */
            .rtl-preview {
                direction: rtl;
                text-align: right;
            }

            /* Editor styling */
            .editor-container {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                padding: 1rem;
                background-color: #ffffff;
            }

            @media (prefers-color-scheme: dark) {
                .editor-container {
                    background-color: #262730;
                    border-color: #464646;
                }
            }

            /* Quill editor customization */
            .ql-container {
                min-height: 200px;
                font-family: inherit;
            }

            .ql-editor {
                min-height: 200px;
            }

            /* Telegraph-specific styling hints */
            .telegraph-hint {
                font-size: 0.85rem;
                color: #666;
                margin-top: 0.5rem;
            }
        </style>
        """,
        unsafe_allow_html=True
    )


# Example usage function for testing
def example_usage():
    """Example usage of the rich editor component."""
    st.title("Rich Text Editor Example")

    # Inject RTL CSS
    inject_editor_rtl_css()

    # Example with all features
    html_content, raw_content = render_rich_editor(
        key="example_editor",
        initial_content="# Welcome\n\nThis is **bold** and this is *italic*.",
        initial_mode="markdown",
        height=400,
        telegraph_service=None,  # Pass your TelegraphService instance here
        show_preview=True
    )

    # Display results
    st.divider()
    st.subheader("Results")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Raw Content:**")
        st.code(raw_content, language="markdown")

    with col2:
        st.markdown("**HTML Output:**")
        st.code(html_content, language="html")


if __name__ == "__main__":
    # Run example if executed directly
    example_usage()
