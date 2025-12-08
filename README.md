# Telegraph Glossary

Personal glossary app with Telegraph integration - Built with Streamlit

## Features

- Create and manage glossary terms with Telegraph pages
- Process text with marked terms (e.g., `term<?>`) and convert to links
- Send formatted messages directly to Telegram
- Multiple syntax options for marking terms

## Deploy to Streamlit Cloud

1. Fork this repository
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub account
4. Select this repo and `app.py`
5. Add your secrets in Advanced Settings (see below)

## Secrets Configuration

For Streamlit Cloud, add these secrets in your app settings:

```toml
[telegraph]
access_token = "your-telegraph-access-token"
short_name = "MyGlossary"
author_name = "Your Name"
index_page_path = "your-index-page-path"

[telegram]
bot_token = "your-telegram-bot-token"
```

To get Telegraph credentials:
- Run the app locally first (it will create an account automatically), or
- Create an account at [telegra.ph](https://telegra.ph) using their API

## Local Development

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-bot-token"
streamlit run app.py
```

On first run, the app will guide you through creating a Telegraph account.

## User Settings

User-specific settings (Chat ID, marking syntax) are stored in URL query parameters.
This means:

- **Each user has isolated settings** - no conflicts between users
- **Settings survive deployments** - they're in the URL, not on the server
- **Bookmark to save** - users should bookmark the page after configuring their Chat ID

Example URL with settings:
```
https://your-app.streamlit.app/?cid=@yourchannel&syn=%3C%3F%3E
```

## Telegram Integration

To send messages with clickable links to Telegram:

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Add the bot to your channel/group as admin
3. Set the bot token in secrets
4. In the app, go to Settings and enter your Chat ID
5. **Bookmark the page** to save your Chat ID

### Finding Your Chat ID

**Public channels:** Use `@yourchannel` (with @ symbol)

**Private channels/groups:**
1. Open [web.telegram.org](https://web.telegram.org)
2. Go to your channel/group
3. Look at the URL: `web.telegram.org/a/#-1001234567890`
4. Your Chat ID is `-1001234567890` (including the minus)

## Architecture

```
Admin Settings (st.secrets)     User Settings (URL params)
        |                               |
        v                               v
   ConfigManager              UserSettingsManager
        |                               |
        +---------------+---------------+
                        |
                        v
                st.session_state.config
```
