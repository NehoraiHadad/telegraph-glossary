# Telegraph Glossary

Personal glossary app with Telegraph integration - Built with Streamlit

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

[telegram]
bot_token = "your-telegram-bot-token"
```

For local development, create `.streamlit/secrets.toml` or set environment variables:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token

## Local Development

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-bot-token"
streamlit run app.py
```

## Telegram Integration

To send messages with clickable links to Telegram:
1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Add the bot to your channel/group as admin
3. Set the bot token in secrets/environment
4. Enter your Chat ID in Settings
