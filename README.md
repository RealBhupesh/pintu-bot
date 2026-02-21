# Discord Moderation Bot

Discord moderation bot with prefix commands (default: `&`).

## Features

- `&pb [scan_limit]`: deletes bot/webhook messages from the current channel (`0` means scan full history).
- `&clear <amount>`: bulk deletes recent messages.
- `&kick`, `&ban`, `&unban`
- `&mute`, `&unmute` (Discord timeout based)
- `&lock`, `&unlock`, `&slowmode`
- `&warn`, `&warnings`, `&clearwarns` (stored in `data/warnings.json`)
- Auto moderation:
  - blocked words from `data/bad_words.txt`
  - link blocking
  - spam detection + automatic timeout
- Mod-log channel support:
  - `&setmodlog [#channel]`
  - `&clearmodlog`
  - logs both manual moderation actions and automod actions
- `&reloadbadwords` to reload bad word entries without restarting the bot
- Utility/fun commands:
  - `&ping`
  - `&avatar [@member]`
  - `&userinfo [@member]`
  - `&serverinfo`
  - `&poll Question | Option 1 | Option 2`
  - `&snipe`
  - `&remind <minutes> <text>`
- AI commands (OpenRouter):
  - `&ai <prompt>` or `&ask <prompt>`
  - `&aisummary [count]`
  - `&aireset`
  - `&aimodel`
  - `&aimodels [limit]`
- `&help`

## Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and set `DISCORD_BOT_TOKEN`.
4. If using AI features, create an OpenRouter API key and set:
   - `OPENROUTER_API_KEY=...`
   - Optional fast free model: `OPENROUTER_MODEL=google/gemma-3-4b-it:free`
5. Enable bot intents in Discord Developer Portal:
   - `MESSAGE CONTENT INTENT`
   - `SERVER MEMBERS INTENT`
6. Run:
   ```bash
   python bot.py
   ```

## Optional Environment Variables

- `MOD_LOG_CHANNEL_ID=` fallback mod-log channel id if `&setmodlog` is not used.
- `AUTOMOD_ENABLED=true`
- `AUTOMOD_BLOCK_LINKS=true`
- `AUTOMOD_SPAM_MSG_THRESHOLD=6`
- `AUTOMOD_SPAM_INTERVAL_SECONDS=8`
- `AUTOMOD_SPAM_TIMEOUT_MINUTES=5`
- `OPENROUTER_API_KEY=`
- `OPENROUTER_MODEL=google/gemma-3-4b-it:free`
- `OPENROUTER_API_URL=https://openrouter.ai/api/v1/chat/completions`
- `OPENROUTER_MODELS_URL=https://openrouter.ai/api/v1/models`
- `OPENROUTER_APP_NAME=Discord Mod Bot`
- `OPENROUTER_HTTP_REFERER=`
- `AI_MAX_HISTORY=4`
- `AI_MAX_TOKENS=260`
- `AI_SUMMARY_MAX_TOKENS=320`
- `AI_TIMEOUT_SECONDS=45`
- `OPENROUTER_FALLBACK_MODELS=google/gemma-3-4b-it:free,qwen/qwen3-4b:free,deepseek/deepseek-r1-0528:free`

## Required Bot Permissions

Depending on which commands you use:
- Manage Messages
- Kick Members
- Ban Members
- Moderate Members
- Manage Channels
- Read Message History

## Notes

- `&pb` removes only bot/webhook messages in the channel where you run it.
- For very large channels, `&pb` may take time due to API rate limits.
- `data/bad_words.txt` is auto-created at first run; add one blocked word per line.
- AI commands work only after `OPENROUTER_API_KEY` is set.
- If your selected model becomes unavailable, bot auto-falls back to another free model.
- For fastest replies, use smaller models and lower `AI_MAX_TOKENS`.
