"""Simplified Markdown editor component for Telegraph Glossary.

This editor provides a clean Markdown editing experience with live preview,
optimized for Telegraph's supported HTML format.
"""

from typing import Optional, Tuple
import streamlit as st

from services.content_converter import ContentConverter


def render_rich_editor(
    key: str,
    initial_content: str = "",
    initial_mode: str = "markdown",  # kept for backward compatibility, always uses markdown
    height: int = 300,
    telegraph_service=None,  # kept for backward compatibility
    show_preview: bool = True
) -> Tuple[str, str]:
    """
    Render a Markdown editor with live preview.

    Args:
        key: Unique key for this editor instance
        initial_content: Initial content (markdown or HTML - HTML will be converted)
        initial_mode: Ignored - always uses markdown mode
        height: Height of the editor in pixels
        telegraph_service: Ignored - kept for backward compatibility
        show_preview: Whether to show the live preview pane

    Returns:
        Tuple of (html_content, raw_content)
        - html_content: Telegraph-ready HTML content
        - raw_content: Original markdown from the editor
    """
    # Initialize session state for this editor
    state_key_content = f"{key}_editor_content"

    # Initialize content - convert HTML to markdown if needed
    if state_key_content not in st.session_state:
        if initial_content and ContentConverter.is_html_content(initial_content):
            # Convert existing HTML to markdown for editing
            st.session_state[state_key_content] = ContentConverter.html_to_markdown(initial_content)
        else:
            st.session_state[state_key_content] = initial_content

    # Render image insertion section
    _render_image_inserter(key, state_key_content)

    # Render the markdown editor
    html_content, raw_content = _render_markdown_editor(
        key, state_key_content, height, show_preview
    )

    return html_content, raw_content


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
            st.markdown("**Markdown Editor**")
            markdown_content = st.text_area(
                "Markdown Content",
                value=st.session_state[state_key_content],
                height=height,
                key=f"{key}_markdown_textarea",
                label_visibility="collapsed",
                placeholder=_get_placeholder_text()
            )

        with col_preview:
            st.markdown("**Preview**")
            if markdown_content:
                html_preview = ContentConverter.markdown_to_html(markdown_content)
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
        st.markdown("**Markdown Editor**")
        markdown_content = st.text_area(
            "Markdown Content",
            value=st.session_state[state_key_content],
            height=height,
            key=f"{key}_markdown_textarea_full",
            label_visibility="collapsed",
            placeholder=_get_placeholder_text()
        )

    # Update session state
    st.session_state[state_key_content] = markdown_content

    # Convert to HTML for Telegraph
    html_content = ContentConverter.markdown_to_html(markdown_content)
    html_content = ContentConverter.sanitize_for_telegraph(html_content)

    return html_content, markdown_content


def _render_image_inserter(key: str, state_key_content: str) -> None:
    """Render image upload/insert section."""

    with st.expander("Add Image", expanded=False):
        # Check if imgbb is configured
        imgbb_key = st.session_state.get("imgbb_api_key", "")

        if imgbb_key:
            # Native upload available
            _render_native_upload(key, state_key_content, imgbb_key)
        else:
            # URL-only mode with setup hint
            _render_url_only_mode(key, state_key_content)


def _render_native_upload(key: str, state_key_content: str, api_key: str) -> None:
    """Render native image upload using imgbb."""

    tab_upload, tab_url = st.tabs(["Upload Image", "Paste URL"])

    with tab_upload:
        uploaded_file = st.file_uploader(
            "Choose an image",
            type=["jpg", "jpeg", "png", "gif", "webp"],
            key=f"{key}_image_uploader",
            help="Upload an image (max 32MB)"
        )

        if uploaded_file:
            # Show preview
            st.image(uploaded_file, caption="Preview", use_container_width=True)

            if st.button("Upload & Insert", key=f"{key}_upload_btn", type="primary"):
                _handle_imgbb_upload(uploaded_file, api_key, state_key_content)

    with tab_url:
        _render_url_input(key, state_key_content)


def _render_url_only_mode(key: str, state_key_content: str) -> None:
    """Render URL-only mode with setup hint."""

    st.info(
        "**Native upload available!** Add your imgbb API key in Settings to upload images directly. "
        "[Get free API key](https://api.imgbb.com/)"
    )

    st.markdown("**Or paste an image URL:**")
    _render_url_input(key, state_key_content)

    with st.expander("Manual upload options"):
        st.markdown("""
        Upload your image to one of these free services:
        - [imgbb.com](https://imgbb.com) - No signup required
        - [imgur.com](https://imgur.com)
        - [postimages.org](https://postimages.org)

        Then copy the direct image URL and paste it above.
        """)


def _render_url_input(key: str, state_key_content: str) -> None:
    """Render URL input field."""

    col1, col2 = st.columns([3, 1])

    with col1:
        image_url = st.text_input(
            "Image URL",
            key=f"{key}_image_url",
            placeholder="https://i.ibb.co/xxxxx/image.jpg",
            label_visibility="collapsed"
        )

    with col2:
        if st.button("Insert", key=f"{key}_insert_url_btn", type="primary", use_container_width=True):
            if image_url:
                if _is_valid_image_url(image_url):
                    _insert_image(image_url, state_key_content)
                else:
                    st.error("Invalid URL format")
            else:
                st.warning("Enter a URL")

    st.caption("Tip: `![description](image_url)` in the editor also works")


def _handle_imgbb_upload(uploaded_file, api_key: str, state_key_content: str) -> None:
    """Handle image upload to imgbb."""

    try:
        from services.imgbb_service import ImgbbService, ImgbbUploadError

        with st.spinner("Uploading image..."):
            service = ImgbbService(api_key)
            image_url = service.upload_from_streamlit(uploaded_file)

        _insert_image(image_url, state_key_content)

    except ImgbbUploadError as e:
        st.error(f"Upload failed: {str(e)}")
    except Exception as e:
        st.error(f"Error: {str(e)}")


def _insert_image(image_url: str, state_key_content: str) -> None:
    """Insert an image markdown into the editor content."""
    markdown_img = f"\n![image]({image_url})\n"
    current_content = st.session_state.get(state_key_content, "")
    st.session_state[state_key_content] = current_content + markdown_img
    st.success("Image inserted!")
    st.rerun()


def _is_valid_image_url(url: str) -> bool:
    """Check if a URL looks like a valid image URL."""
    if not url:
        return False
    url_lower = url.lower()
    return url_lower.startswith(('http://', 'https://'))


def _get_placeholder_text() -> str:
    """Return placeholder text for the markdown editor."""
    return """Enter your content in Markdown...

**Bold** *Italic* ~~Strikethrough~~
[Link text](url)
![Image description](image_url)

### Heading 3
#### Heading 4

- Bullet list
- Item 2

1. Numbered list
2. Item 2

> Blockquote

`inline code`

```
code block
```"""


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
        </style>
        """,
        unsafe_allow_html=True
    )
