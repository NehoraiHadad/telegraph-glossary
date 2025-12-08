"""Telegraph Glossary - Personal glossary with Telegraph integration."""

import streamlit as st

from services.config_manager import ConfigManager
from services.telegraph_service import TelegraphService
from components.glossary_manager import render_glossary_manager
from components.text_processor import render_text_processor
from components.settings_panel import render_settings
from components.ai_integration import render_ai_integration
from utils.helpers import inject_custom_css, show_toast


# Page configuration
st.set_page_config(
    page_title="Telegraph Glossary",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state() -> None:
    """Initialize session state variables."""
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
        st.session_state.glossary = {}
        st.session_state.config = None
        st.session_state.telegraph = None
        st.session_state.edit_term = None
        st.session_state.show_add_form = False


def load_app() -> None:
    """Load configuration and initialize services."""
    config_manager = ConfigManager()
    config = config_manager.load()
    st.session_state.config = config

    if config_manager.is_configured():
        access_token = config["telegraph"]["access_token"]
        telegraph = TelegraphService(access_token)
        st.session_state.telegraph = telegraph

        # Load glossary from Telegraph
        index_path = config["telegraph"].get("index_page_path")
        if index_path:
            try:
                glossary = telegraph.load_glossary_from_index(index_path)
                st.session_state.glossary = glossary
            except Exception as e:
                st.warning(f"Could not load glossary from Telegraph: {e}")
                st.session_state.glossary = {}
        else:
            st.session_state.glossary = {}

    st.session_state.initialized = True


def render_sidebar() -> None:
    """Render the sidebar with status and quick actions."""
    with st.sidebar:
        st.title("Telegraph Glossary")

        config = st.session_state.get("config", {})
        telegraph = st.session_state.get("telegraph")
        glossary = st.session_state.get("glossary", {})

        # Connection status
        if telegraph and config.get("telegraph", {}).get("access_token"):
            st.success("Connected to Telegraph")
        else:
            st.warning("Not connected")

        # Metrics
        st.metric("Terms", len(glossary))

        # Index page link
        index_path = config.get("telegraph", {}).get("index_page_path")
        if index_path:
            st.link_button(
                "View Index Page",
                f"https://telegra.ph/{index_path}",
                use_container_width=True,
            )

        st.divider()

        # Current syntax
        st.subheader("Current Syntax")
        settings = config.get("settings", {})
        syntax = settings.get("marking_syntax", "<?>")
        custom_prefix = settings.get("custom_prefix", "")
        custom_suffix = settings.get("custom_suffix", "")

        from services.text_parser import SYNTAX_PATTERNS, create_custom_syntax
        if syntax == "custom" and custom_prefix and custom_suffix:
            syntax_info = create_custom_syntax(custom_prefix, custom_suffix)
        else:
            syntax_info = SYNTAX_PATTERNS.get(syntax, {})
        st.code(syntax_info.get("display", syntax))

        st.divider()

        # Quick actions
        st.subheader("Quick Actions")

        if st.button("Sync from Telegraph", use_container_width=True):
            _sync_glossary()

        if glossary:
            import json
            export_data = json.dumps(glossary, indent=2, ensure_ascii=False)
            st.download_button(
                "Export Glossary",
                export_data,
                file_name="glossary.json",
                mime="application/json",
                use_container_width=True,
            )


def _sync_glossary() -> None:
    """Sync glossary from Telegraph."""
    telegraph = st.session_state.get("telegraph")
    config = st.session_state.get("config", {})

    if not telegraph:
        st.sidebar.error("Not connected to Telegraph")
        return

    index_path = config.get("telegraph", {}).get("index_page_path")
    if not index_path:
        st.sidebar.error("No index page configured")
        return

    try:
        with st.spinner("Syncing..."):
            glossary = telegraph.load_glossary_from_index(index_path)
            st.session_state.glossary = glossary
            show_toast(f"Synced {len(glossary)} terms!", "")
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Sync failed: {e}")


def render_setup_wizard() -> None:
    """Render first-time setup wizard."""
    st.title("Welcome to Telegraph Glossary")
    st.markdown(
        "Create and manage your personal glossary with Telegraph integration. "
        "Let's set up your account!"
    )

    with st.form("setup_form"):
        st.subheader("Create Telegraph Account")

        short_name = st.text_input(
            "Account Name",
            value="MyGlossary",
            help="A short name for your Telegraph account (will appear in URLs)",
        )

        author_name = st.text_input(
            "Author Name (optional)",
            help="Your name to display on glossary pages",
        )

        st.markdown("---")

        submitted = st.form_submit_button("Create Account & Get Started", type="primary")

        if submitted:
            if not short_name:
                st.error("Please enter an account name.")
            else:
                _setup_account(short_name, author_name)


def _setup_account(short_name: str, author_name: str) -> None:
    """Set up new Telegraph account."""
    try:
        with st.spinner("Setting up your account..."):
            telegraph = TelegraphService()
            account = telegraph.create_account(short_name, author_name)
            index_result = telegraph.create_index_page({})

            config_manager = ConfigManager()
            config_manager.load()
            config_manager.set("telegraph.access_token", account["access_token"])
            config_manager.set("telegraph.short_name", short_name)
            config_manager.set("telegraph.author_name", author_name)
            config_manager.set("telegraph.index_page_path", index_result["path"])

            st.session_state.telegraph = telegraph
            st.session_state.config = config_manager.get_config()
            st.session_state.glossary = {}
            st.session_state.initialized = True

            st.success("Account created successfully!")
            st.balloons()
            st.rerun()

    except Exception as e:
        st.error(f"Setup failed: {e}")


def main() -> None:
    """Main application entry point."""
    inject_custom_css()
    init_session_state()

    if not st.session_state.initialized:
        load_app()

    config_manager = ConfigManager()
    config_manager.load()

    if not config_manager.is_configured():
        render_setup_wizard()
        return

    render_sidebar()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Glossary",
        "Process Text",
        "Settings",
        "AI Integration",
    ])

    with tab1:
        render_glossary_manager()
    with tab2:
        render_text_processor()
    with tab3:
        render_settings()
    with tab4:
        render_ai_integration()


if __name__ == "__main__":
    main()
