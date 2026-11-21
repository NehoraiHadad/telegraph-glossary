"""Help Guide component - User guide with all app features explained."""

import streamlit as st


def render_help_guide() -> None:
    """Render the help guide with tabs for each section."""

    tabs = st.tabs([
        "Quick Start",
        "Glossary",
        "Syntax",
        "Process",
        "Telegram",
        "Settings",
        "AI",
    ])

    with tabs[0]:
        _render_quick_start()
    with tabs[1]:
        _render_glossary_help()
    with tabs[2]:
        _render_syntax_help()
    with tabs[3]:
        _render_process_help()
    with tabs[4]:
        _render_telegram_help()
    with tabs[5]:
        _render_settings_help()
    with tabs[6]:
        _render_ai_help()


def _render_quick_start() -> None:
    """Quick Start section - 60 second overview."""
    st.markdown("""
    ### How It Works - 60 Seconds Overview

    **The Flow:**
    """)

    # Visual flow diagram
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info("**1. Create Terms**\n\nAdd terms with definitions to your glossary")
    with col2:
        st.info("**2. Mark in Text**\n\nUse syntax like `term<?>` in your content")
    with col3:
        st.info("**3. Process**\n\nConvert marked terms to clickable links")
    with col4:
        st.info("**4. Send**\n\nShare to Telegram with linked terms")

    st.markdown("""
    ---

    **Basic Steps:**

    1. **Create a term** - Go to "Glossary" tab and click "+ Add New Term"
    2. **Mark in your text** - Write `term<?>` where you want links (e.g., `CPU<?>`)
    3. **Process text** - Paste text in "Process Text" tab and click "Process"
    4. **Send to Telegram** - Click "Send to Telegram" button

    That's it! Your terms become clickable links to Telegraph pages.

    ---

    **Important:** Your settings are saved in the URL. **Bookmark the page** to keep your glossary!
    """)


def _render_glossary_help() -> None:
    """Glossary management help."""
    st.markdown("""
    ### Creating & Managing Terms

    **Adding a New Term:**

    1. Go to the **Glossary** tab
    2. Click **"+ Add New Term"** button
    3. Enter the term name (e.g., "API", "CPU", "Machine Learning")
    4. Write the definition using the rich editor
    5. Click **Add Term**

    Each term automatically gets its own Telegraph page with a unique URL.

    ---

    **Rich Editor Features:**

    The definition editor supports:
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        - **Bold** and *Italic* text
        - [Links](https://example.com)
        - Images
        - Bullet lists
        - Numbered lists
        """)
    with col2:
        st.markdown("""
        - Block quotes
        - Code blocks
        - Headings (H3, H4)
        - Horizontal lines
        - Inline code
        """)

    st.markdown("""
    ---

    **Managing Terms:**

    - **Search** - Use the search bar to filter by name or definition
    - **Edit** - Click "Edit" on any term card to update it
    - **Delete** - Click "Delete" to remove a term
    - **Open** - Click the link to view the Telegraph page

    ---

    **Tip:** Use the "Sync from Telegraph" button in the sidebar to refresh your glossary from Telegraph.
    """)


def _render_syntax_help() -> None:
    """Marking syntax help."""
    st.markdown("""
    ### Marking Syntax - How to Mark Terms in Text

    When writing content, you mark terms using a special syntax. The app will recognize these marks and convert them to clickable links.

    **Available Syntaxes:**
    """)

    syntax_data = [
        ("term<?>", "CPU<?> processes data", "Default"),
        ("[[term]]", "[[CPU]] processes data", "Wiki-style"),
        ("{{term}}", "{{CPU}} processes data", "Template-style"),
        ("<<term>>", "<<CPU>> processes data", "Angle brackets"),
        ("Custom", "~[CPU]~ processes data", "Define your own"),
    ]

    for syntax, example, desc in syntax_data:
        col1, col2, col3 = st.columns([2, 4, 2])
        with col1:
            st.code(syntax)
        with col2:
            st.text(example)
        with col3:
            st.caption(desc)

    st.markdown("""
    ---

    **Changing Syntax:**

    1. Go to **Settings** tab
    2. Find **Marking Syntax** section
    3. Select your preferred syntax
    4. For custom syntax, enter your own prefix and suffix

    **Important:** After changing syntax, **bookmark the URL** to save your preference!

    ---

    **Custom Syntax:**

    You can define your own marking syntax:
    - Enter a **Prefix** (e.g., `~[`)
    - Enter a **Suffix** (e.g., `]~`)
    - Maximum 10 characters each
    - Result: `~[term]~`
    """)


def _render_process_help() -> None:
    """Text processing help."""
    st.markdown("""
    ### Processing Text - Converting Marks to Links

    The Process Text feature converts your marked terms into clickable links.

    **How to Use:**

    1. Go to **Process Text** tab
    2. Paste your text with marked terms
    3. Select output format:
       - **Telegram** - For sending to Telegram channels
       - **Markdown** - For documentation and files
       - **HTML** - For websites
    4. Click **Process Text**

    ---

    **Example:**
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Input:**")
        st.code('The {{CPU}} and {{RAM}} work together to process data.')
    with col2:
        st.markdown("**Output (Telegram):**")
        st.code('The CPU and RAM work together to process data.\n\n+ Clickable links to Telegraph pages')

    st.markdown("""
    ---

    **Results Display:**

    After processing, you'll see:
    - **Processed text** - Ready to copy or send
    - **Statistics** - How many terms found vs. missing
    - **Term list** - All recognized terms with their URLs
    - **Missing terms** - Terms that aren't in your glossary

    ---

    **Tips:**

    - Terms are matched **case-insensitively** (CPU matches cpu, Cpu, etc.)
    - Missing terms are highlighted so you can add them to your glossary
    - Use the **Copy** button to copy processed text to clipboard
    """)


def _render_telegram_help() -> None:
    """Telegram integration help."""
    st.markdown("""
    ### Telegram Integration - Setup & Usage

    Send processed text directly to your Telegram channel or group.

    ---

    **Setup Steps:**

    **Step 1: Add the Bot to Your Channel**

    1. Open your Telegram channel/group
    2. Go to channel settings -> Administrators
    3. Click "Add Administrator"
    4. Search for `@TelegraphGlossaryBot`
    5. Give it permission to **post messages**

    ---

    **Step 2: Find Your Chat ID**
    """)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Public Channel:**

        Use the channel username:
        ```
        @channelname
        ```
        """)
    with col2:
        st.markdown("""
        **Private Channel:**

        1. Open `web.telegram.org`
        2. Go to your channel
        3. Look at the URL: `web.telegram.org/a/#-1001234567890`
        4. The Chat ID is: `-1001234567890`
        """)

    st.markdown("""
    ---

    **Step 3: Configure in App**

    1. Go to **Settings** tab
    2. Find **Telegram Bot Settings**
    3. Enter your Chat ID
    4. Click **Test Connection** to verify
    5. **Bookmark the URL** to save your Chat ID!

    ---

    **Sending Messages:**

    1. Process your text in **Process Text** tab
    2. Click **Send to Telegram** button
    3. Message appears in your channel with clickable term links!

    ---

    **Note:** The bot must have posting permissions in your channel/group.
    """)


def _render_settings_help() -> None:
    """Settings and persistence help."""
    st.markdown("""
    ### Settings - How Your Data is Saved

    **Important Concept:** All your settings are stored in the URL!

    ---

    **What's Saved in the URL:**

    - Telegraph Access Token (your glossary identity)
    - Telegram Chat ID
    - Marking syntax preference
    - Custom prefix/suffix
    - Account name and author name

    ---

    **How to Keep Your Settings:**
    """)

    st.warning("""
    **After any settings change:**
    1. **Bookmark the current URL**
    2. The URL is your "password" to your glossary
    3. Sharing the URL = Sharing full access
    """)

    st.markdown("""
    ---

    **Why URL-based Storage?**

    - No server database needed
    - Each user has isolated settings
    - Works across devices via bookmark
    - Privacy - your data stays with you

    ---

    **Data Management:**

    - **Export Glossary** - Download your terms as JSON (sidebar)
    - **Sync from Telegraph** - Reload terms from Telegraph
    - Your actual content is stored on Telegraph.ph

    ---

    **Lost Your URL?**

    If you lose access:
    - Your Telegraph pages still exist
    - You'd need to create a new account
    - Consider saving your URL in a password manager
    """)


def _render_ai_help() -> None:
    """AI integration help."""
    st.markdown("""
    ### AI Integration - Chat with AI to Manage Your Glossary

    *This feature is optional and requires an API key.*

    ---

    **What Can AI Do?**

    - Create new terms via natural language
    - Update existing definitions
    - Delete terms
    - Answer questions about your glossary

    **Example Requests:**
    """)

    examples = [
        '"Add a term API - Application Programming Interface"',
        '"Update the CPU definition to include more details"',
        '"What terms do I have about networking?"',
        '"Delete the term XYZ"',
    ]
    for ex in examples:
        st.code(ex, language=None)

    st.markdown("""
    ---

    **Setup:**

    1. Go to **AI Integration** tab
    2. Select your AI provider (Claude, OpenAI, or Gemini)
    3. Enter your API key
    4. Start chatting!

    ---

    **Supported Providers:**

    | Provider | Model | Notes |
    |----------|-------|-------|
    | Claude | claude-sonnet | Recommended |
    | OpenAI | gpt-4o-mini | Fast & capable |
    | Gemini | gemini-flash | Google's model |

    ---

    **MCP Configuration:**

    For advanced users, you can configure the Telegraph MCP server for Claude Desktop:

    1. Go to AI Integration tab
    2. Find MCP Configuration section
    3. Copy the JSON config
    4. Add to your Claude Desktop settings

    This allows Claude Desktop to directly manage your glossary.
    """)


@st.dialog("User Guide", width="large")
def show_help_dialog() -> None:
    """Show help guide in a modal dialog."""
    render_help_guide()
