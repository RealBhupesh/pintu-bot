# Discord Moderation Bot

Discord moderation bot with prefix commands (default: `&`).

## Features

- `&pb`: deletes bot/webhook messages from the most recent 20 messages in the current channel.
- `&pba`: deletes all bot/webhook messages from the current channel.
- `&clear <amount>`: bulk deletes recent messages.
- `&bulkdelete <#channel> <amount>`: bulk deletes messages in a specific channel.
- `&kick`, `&ban`, `&unban`
- `&mute`, `&unmute` (Discord timeout based)
- `&lock`, `&unlock`, `&slowmode`
- `&warn`, `&warnings`, `&clearwarns` (stored in `data/warnings.json`)
- `&automod <on|off|toggle|status>` (moderators can control AutoMod per server)
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
  - DM the bot with `remove timeout` to remove your active timeout (if bot has permission)
- AI commands:
  - `&ai <prompt>` or `&ask <prompt>`
  - `&aisummary [count]`
  - `&aireset`
  - `&aimodel`
  - `&aimodels [limit]`
  - `&roast @user [soft|friendly|brutal]`
  - `&serverlore`
  - `&aicrush @user`
  - `&analyze @user`
  - `&lie_detector @user <message>`
  - `&futureme`
  - `&rizzcoach [smooth|funny|mysterious] <message>`
  - `&argument <topic>`
  - `&debate @user <topic>`
- Vibe commands:
  - `&myvibe [count]`
  - `&vibe @user [count]`
  - `&vibecheck @user`
- Music commands:
  - `&join`, `&leave`
  - `&play <youtube/spotify link or search>`
  - `&skip`, `&pause`, `&resume`, `&stop`
  - `&queue`, `&nowplaying`
  - Spotify playlist links are supported
- `&help`

Most new AI fun commands are hybrid, so you can use both prefix (`&...`) and slash (`/...`) after command sync.

## Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and set `DISCORD_BOT_TOKEN`.
4. If using AI features, set one provider:
   - OpenRouter:
     - `AI_PROVIDER=openrouter`
     - `OPENROUTER_API_KEY=...`
   - Groq:
     - `AI_PROVIDER=groq`
     - `GROQ_API_KEY=...`
5. If using music features:
   - Make sure `ffmpeg` is installed on your host.
   - For Spotify links/playlists, set:
     - `SPOTIFY_CLIENT_ID=...`
     - `SPOTIFY_CLIENT_SECRET=...`
6. Enable bot intents in Discord Developer Portal:
   - `MESSAGE CONTENT INTENT`
   - `SERVER MEMBERS INTENT`
7. Run:
   ```bash
   python bot.py
   ```

## Optional Environment Variables

- `MOD_LOG_CHANNEL_ID=` fallback mod-log channel id if `&setmodlog` is not used.
- `BOT_ACTIVITY_TEXT=with your crush`
- `AUTOMOD_ENABLED=false`
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
- `AI_PROVIDER=openrouter`
- `GROQ_API_KEY=`
- `GROQ_MODEL=llama-3.1-8b-instant`
- `GROQ_API_URL=https://api.groq.com/openai/v1/chat/completions`
- `GROQ_MODELS_URL=https://api.groq.com/openai/v1/models`
- `AI_MAX_HISTORY=4`
- `AI_MAX_TOKENS=260`
- `AI_SUMMARY_MAX_TOKENS=320`
- `AI_TIMEOUT_SECONDS=45`
- `SYNC_SLASH_COMMANDS=true`
- `VIBE_DEFAULT_MESSAGE_COUNT=200`
- `VIBE_MAX_MESSAGE_COUNT=800`
- `VIBE_MIN_REQUIRED_MESSAGES=25`
- `VIBE_MAX_PROMPT_MESSAGES=80`
- `VIBE_MAX_PROMPT_CHARS=12000`
- `VOICE_CONNECT_RETRIES=4`
- `VOICE_CONNECT_TIMEOUT=25`
- `VOICE_INTERNAL_RECONNECT=false`
- `OPENROUTER_FALLBACK_MODELS=google/gemma-3-4b-it:free,qwen/qwen3-4b:free,deepseek/deepseek-r1-0528:free`
- `GROQ_FALLBACK_MODELS=llama-3.1-8b-instant,gemma2-9b-it`
- `FFMPEG_PATH=ffmpeg`
- `MUSIC_MAX_PLAYLIST_ITEMS=50`
- `SPOTIFY_CLIENT_ID=`
- `SPOTIFY_CLIENT_SECRET=`

## Required Bot Permissions

Depending on which commands you use:
- Manage Messages
- Kick Members
- Ban Members
- Moderate Members
- Manage Channels
- Read Message History

## Notes

- `&pb` checks only the latest 20 messages and removes bot/webhook messages there.
- `&pba` scans full channel history and may take time on very large channels due to API rate limits.
- `data/bad_words.txt` is auto-created at first run; add one blocked word per line.
- AI commands work after provider key is set (`OPENROUTER_API_KEY` or `GROQ_API_KEY`).
- If your selected model becomes unavailable, bot auto-falls back to another free model.
- For fastest replies, use smaller models and lower `AI_MAX_TOKENS`.
- Spotify links require Spotify API credentials; otherwise only YouTube/search playback works.
- Spotify playlists must be Public when using client credentials (`SPOTIFY_CLIENT_ID/SECRET`).
- If hosted voice keeps failing with websocket `4006`, this is usually host/node UDP/network routing. Try another node/provider.
- Vibe reports are fun-only and may be inaccurate.
- Vibe output is paragraph-style and considers both the user’s messages and replies they receive (in the same channel window).
- Vibe analysis reads recent messages on-demand in the current channel; it does not store long-term message archives.
- If vibe AI times out, the bot falls back to a local heuristic narrative summary.
