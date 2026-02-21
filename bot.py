import json
import os
import re
import asyncio
import time
from collections import defaultdict, deque
from datetime import timedelta
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "&")

def env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int, minimum: int) -> int:
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return max(int(raw), minimum)
    except ValueError:
        return default


AUTO_MOD_ENABLED = env_bool("AUTOMOD_ENABLED", True)
BLOCK_LINKS = env_bool("AUTOMOD_BLOCK_LINKS", True)
SPAM_MSG_THRESHOLD = env_int("AUTOMOD_SPAM_MSG_THRESHOLD", 6, 2)
SPAM_INTERVAL_SECONDS = env_int("AUTOMOD_SPAM_INTERVAL_SECONDS", 8, 1)
SPAM_TIMEOUT_MINUTES = env_int("AUTOMOD_SPAM_TIMEOUT_MINUTES", 5, 1)

env_mod_log_channel = os.getenv("MOD_LOG_CHANNEL_ID", "").strip()
ENV_MOD_LOG_CHANNEL_ID = int(env_mod_log_channel) if env_mod_log_channel.isdigit() else None

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-3-4b-it:free").strip()
OPENROUTER_API_URL = os.getenv(
    "OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions"
).strip()
OPENROUTER_MODELS_URL = os.getenv("OPENROUTER_MODELS_URL", "https://openrouter.ai/api/v1/models").strip()
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "Discord Mod Bot").strip()
OPENROUTER_HTTP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "").strip()
AI_MAX_HISTORY = env_int("AI_MAX_HISTORY", 4, 2)
AI_MAX_TOKENS = env_int("AI_MAX_TOKENS", 260, 80)
AI_SUMMARY_MAX_TOKENS = env_int("AI_SUMMARY_MAX_TOKENS", 320, 120)
AI_TIMEOUT_SECONDS = env_int("AI_TIMEOUT_SECONDS", 45, 10)
OPENROUTER_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "OPENROUTER_FALLBACK_MODELS",
        "google/gemma-3-4b-it:free,qwen/qwen3-4b:free,deepseek/deepseek-r1-0528:free",
    ).split(",")
    if model.strip()
]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

DATA_DIR = Path("data")
WARNINGS_FILE = DATA_DIR / "warnings.json"
MOD_CONFIG_FILE = DATA_DIR / "mod_config.json"
BAD_WORDS_FILE = DATA_DIR / "bad_words.txt"

LINK_PATTERN = re.compile(r"(https?://|www\.|discord\.gg/)", re.IGNORECASE)
WORD_PATTERN = re.compile(r"\b[\w']+\b")
POLL_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# (guild_id, user_id) -> message timestamps for spam detection.
SPAM_CACHE: dict[tuple[int, int], deque[float]] = defaultdict(lambda: deque(maxlen=20))
BAD_WORDS: set[str] = set()
SNIPE_CACHE: dict[int, dict[str, str]] = {}
AI_CHAT_CACHE: dict[int, list[dict[str, str]]] = defaultdict(list)
AI_SYSTEM_PROMPT = (
    "You are a helpful Discord assistant for a community server. "
    "Answer clearly in <=120 words unless the user asks for a long response, "
    "and avoid unsafe or illegal instructions."
)
MODEL_CACHE: set[str] = set()
MODEL_CACHE_TS = 0.0
MODEL_CACHE_TTL_SECONDS = 600


def ensure_data_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not WARNINGS_FILE.exists():
        WARNINGS_FILE.write_text("{}", encoding="utf-8")
    if not MOD_CONFIG_FILE.exists():
        MOD_CONFIG_FILE.write_text("{}", encoding="utf-8")
    if not BAD_WORDS_FILE.exists():
        BAD_WORDS_FILE.write_text(
            "# Add one blocked word per line.\n# Lines starting with # are ignored.\n",
            encoding="utf-8",
        )


def read_json(path: Path) -> dict:
    ensure_data_files()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: dict) -> None:
    ensure_data_files()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_warnings() -> dict:
    return read_json(WARNINGS_FILE)


def save_warnings(payload: dict) -> None:
    write_json(WARNINGS_FILE, payload)


def load_mod_config() -> dict:
    return read_json(MOD_CONFIG_FILE)


def save_mod_config(payload: dict) -> None:
    write_json(MOD_CONFIG_FILE, payload)


def reload_bad_words() -> int:
    ensure_data_files()
    global BAD_WORDS
    words: set[str] = set()
    for line in BAD_WORDS_FILE.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip().lower()
        if cleaned and not cleaned.startswith("#"):
            words.add(cleaned)
    BAD_WORDS = words
    return len(BAD_WORDS)


def get_guild_mod_log_channel_id(guild_id: int) -> int | None:
    config = load_mod_config()
    guild_config = config.get(str(guild_id), {})
    channel_id = guild_config.get("mod_log_channel_id")
    if isinstance(channel_id, int):
        return channel_id
    if isinstance(channel_id, str) and channel_id.isdigit():
        return int(channel_id)
    return ENV_MOD_LOG_CHANNEL_ID


def matches_bad_word(content: str) -> str | None:
    if not BAD_WORDS:
        return None
    words = WORD_PATTERN.findall(content.lower())
    for word in words:
        if word in BAD_WORDS:
            return word
    return None


async def send_mod_log(
    guild: discord.Guild,
    action: str,
    *,
    target: discord.abc.User | None = None,
    moderator: discord.abc.User | None = None,
    reason: str | None = None,
    channel: discord.abc.GuildChannel | None = None,
    details: str | None = None,
) -> None:
    channel_id = get_guild_mod_log_channel_id(guild.id)
    if not channel_id:
        return

    log_channel = guild.get_channel(channel_id)
    if not isinstance(log_channel, discord.TextChannel):
        return

    embed = discord.Embed(
        title="Moderation Log",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow(),
    )
    embed.add_field(name="Action", value=action, inline=False)
    if target is not None:
        embed.add_field(name="Target", value=f"{target} (`{target.id}`)", inline=False)
    if moderator is not None:
        embed.add_field(name="Moderator", value=f"{moderator} (`{moderator.id}`)", inline=False)
    if channel is not None:
        embed.add_field(name="Channel", value=channel.mention, inline=False)
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    if details:
        embed.add_field(name="Details", value=details, inline=False)

    try:
        await log_channel.send(embed=embed)
    except discord.HTTPException:
        pass


def split_message(content: str, max_len: int = 1900) -> list[str]:
    text = content.strip()
    if not text:
        return ["(empty response)"]
    parts: list[str] = []
    while len(text) > max_len:
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        parts.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        parts.append(text)
    return parts


async def send_chunked(channel: discord.abc.Messageable, content: str) -> None:
    for chunk in split_message(content):
        await channel.send(chunk)


async def fetch_openrouter_models(session: aiohttp.ClientSession) -> set[str]:
    global MODEL_CACHE_TS, MODEL_CACHE
    now = time.monotonic()
    if MODEL_CACHE and now - MODEL_CACHE_TS < MODEL_CACHE_TTL_SECONDS:
        return MODEL_CACHE

    async with session.get(OPENROUTER_MODELS_URL) as response:
        text = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"Could not fetch models (`{response.status}`): {text[:200]}")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Model list response is not valid JSON.") from exc

    models = {
        item.get("id", "")
        for item in payload.get("data", [])
        if isinstance(item, dict) and item.get("id")
    }
    if models:
        MODEL_CACHE = models
        MODEL_CACHE_TS = now
    return models


def get_model_try_order() -> list[str]:
    models: list[str] = []
    seen: set[str] = set()
    for model in [OPENROUTER_MODEL, *OPENROUTER_FALLBACK_MODELS]:
        cleaned = model.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        models.append(cleaned)
    return models


def should_try_fallback(status: int, raw_text: str) -> bool:
    body = raw_text.lower()
    if status in {404, 429, 500, 502, 503, 504}:
        return True
    return (
        "no endpoints found" in body
        or "temporarily unavailable" in body
        or "provider returned error" in body
    )


def friendly_ai_error(error: Exception | str) -> str:
    text = str(error).lower()
    if "429" in text or "rate-limit" in text or "provider returned error" in text:
        return "AI providers are busy right now (rate-limited). Try again in 10-20 seconds."
    if "timeout" in text:
        return "AI provider timed out. Try again in a few seconds."
    if "data policy" in text:
        return "Model blocked by OpenRouter data policy. Use `&aimodels` and choose another free model."
    if "401" in text or "unauthorized" in text or "invalid api key" in text:
        return "OpenRouter API key looks invalid. Update `OPENROUTER_API_KEY` in `.env` and restart."
    return "AI request failed temporarily. Please try again in a few seconds."


async def request_openrouter_completion(
    messages: list[dict[str, str]], *, max_tokens: int = 260, temperature: float = 0.6
) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is missing in .env")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": OPENROUTER_APP_NAME or "Discord Mod Bot",
    }
    if OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = OPENROUTER_HTTP_REFERER

    timeout = aiohttp.ClientTimeout(total=AI_TIMEOUT_SECONDS)
    models_to_try = get_model_try_order()
    last_error = "OpenRouter request failed."
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for index, model_to_use in enumerate(models_to_try):
            payload = {
                "model": model_to_use,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            try:
                async with session.post(
                    OPENROUTER_API_URL, headers=headers, json=payload
                ) as response:
                    raw_text = await response.text()
                    if response.status >= 400:
                        last_error = (
                            f"OpenRouter API error `{response.status}` for `{model_to_use}`: "
                            f"{raw_text[:220]}"
                        )
                        if index < len(models_to_try) - 1 and should_try_fallback(
                            response.status, raw_text
                        ):
                            continue
                        raise RuntimeError(last_error)
                    try:
                        data = json.loads(raw_text)
                    except json.JSONDecodeError:
                        last_error = f"Invalid JSON response from `{model_to_use}`."
                        if index < len(models_to_try) - 1:
                            continue
                        raise RuntimeError(last_error)
            except asyncio.TimeoutError:
                last_error = f"Timeout from `{model_to_use}`."
                if index < len(models_to_try) - 1:
                    continue
                raise RuntimeError(last_error)
            except aiohttp.ClientError as exc:
                last_error = f"Network error from `{model_to_use}`: {exc}"
                if index < len(models_to_try) - 1:
                    continue
                raise RuntimeError(last_error)

            choices = data.get("choices", [])
            if not choices:
                last_error = f"No choices returned from `{model_to_use}`."
                if index < len(models_to_try) - 1:
                    continue
                raise RuntimeError(last_error)

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if isinstance(content, list):
                text_parts: list[str] = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text_parts.append(part.get("text", ""))
                content = "\n".join(part for part in text_parts if part).strip()
            elif not isinstance(content, str):
                content = str(content)

            if not content:
                last_error = f"Empty text response from `{model_to_use}`."
                if index < len(models_to_try) - 1:
                    continue
                raise RuntimeError(last_error)

            if model_to_use != OPENROUTER_MODEL:
                return f"[Fallback model: `{model_to_use}`]\n\n{content.strip()}"
            return content.strip()

    raise RuntimeError(last_error)


def append_ai_history(channel_id: int, user_prompt: str, assistant_reply: str) -> None:
    history = AI_CHAT_CACHE[channel_id]
    history.append({"role": "user", "content": user_prompt})
    history.append({"role": "assistant", "content": assistant_reply})
    max_entries = max(2, AI_MAX_HISTORY * 2)
    if len(history) > max_entries:
        AI_CHAT_CACHE[channel_id] = history[-max_entries:]


async def delete_recent_user_messages(
    channel: discord.TextChannel, user_id: int, limit: int
) -> int:
    deleted = 0
    async for msg in channel.history(limit=120):
        if msg.author.id != user_id:
            continue
        try:
            await msg.delete()
            deleted += 1
        except (discord.NotFound, discord.HTTPException):
            continue
        if deleted >= limit:
            break
    return deleted


async def apply_automod_action(
    message: discord.Message,
    action: str,
    reason: str,
    *,
    timeout_minutes: int = 0,
    delete_count: int = 1,
) -> None:
    deleted_count = await delete_recent_user_messages(
        message.channel, message.author.id, max(delete_count, 1)
    )
    timeout_applied = False

    if timeout_minutes > 0 and isinstance(message.author, discord.Member):
        me = message.guild.me
        if me and me.guild_permissions.moderate_members:
            can_timeout = (
                message.author != message.guild.owner
                and message.author.top_role < me.top_role
                and not message.author.guild_permissions.administrator
            )
            if can_timeout:
                try:
                    until = discord.utils.utcnow() + timedelta(minutes=timeout_minutes)
                    await message.author.timeout(until, reason=f"AutoMod: {reason}")
                    timeout_applied = True
                except discord.HTTPException:
                    timeout_applied = False

    reply = f"{message.author.mention}, your message was removed: {reason}"
    if timeout_applied:
        reply += f" You were timed out for `{timeout_minutes}` minute(s)."

    try:
        await message.channel.send(reply, delete_after=8)
    except discord.HTTPException:
        pass

    details = f"Deleted messages: `{deleted_count}`."
    if timeout_applied:
        details += f" Timeout: `{timeout_minutes}` minute(s)."
    await send_mod_log(
        message.guild,
        action,
        target=message.author,
        moderator=bot.user,
        reason=reason,
        channel=message.channel,
        details=details,
    )


@bot.event
async def on_ready() -> None:
    count = reload_bad_words()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Bot is online. Loaded {count} blocked words.")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.TextChannel) or message.guild is None:
        await bot.process_commands(message)
        return

    if message.content.startswith(PREFIX):
        await bot.process_commands(message)
        return

    if not AUTO_MOD_ENABLED:
        await bot.process_commands(message)
        return

    member = message.author
    if isinstance(member, discord.Member):
        if member.guild_permissions.administrator or member.guild_permissions.manage_messages:
            await bot.process_commands(message)
            return

    bad_word = matches_bad_word(message.content)
    if bad_word:
        await apply_automod_action(
            message,
            "AutoMod: Blocked Word",
            f"Blocked word detected: `{bad_word}`.",
        )
        return

    if BLOCK_LINKS and LINK_PATTERN.search(message.content):
        await apply_automod_action(
            message,
            "AutoMod: Blocked Link",
            "Links are not allowed in this server.",
        )
        return

    key = (message.guild.id, message.author.id)
    queue = SPAM_CACHE[key]
    queue.append(message.created_at.timestamp())
    if (
        len(queue) >= SPAM_MSG_THRESHOLD
        and queue[-1] - queue[-SPAM_MSG_THRESHOLD] <= SPAM_INTERVAL_SECONDS
    ):
        queue.clear()
        await apply_automod_action(
            message,
            "AutoMod: Spam",
            "Spam detected.",
            timeout_minutes=SPAM_TIMEOUT_MINUTES,
            delete_count=SPAM_MSG_THRESHOLD,
        )
        return

    await bot.process_commands(message)


@bot.event
async def on_message_delete(message: discord.Message) -> None:
    if message.guild is None or message.author.bot:
        return

    content = message.content.strip() if message.content else ""
    if not content and message.attachments:
        content = "[Attachment only]"
    if not content:
        return

    SNIPE_CACHE[message.channel.id] = {
        "author": str(message.author),
        "author_id": str(message.author.id),
        "content": content[:1800],
        "created_at": message.created_at.isoformat(),
    }


@bot.command(name="help")
async def help_command(ctx: commands.Context) -> None:
    text = (
        f"**Prefix:** `{PREFIX}`\n"
        "**Moderation Commands**\n"
        f"`{PREFIX}pb [scan_limit]` - Delete bot/webhook messages from this channel (`0` = scan all).\n"
        f"`{PREFIX}clear <amount>` - Delete recent messages.\n"
        f"`{PREFIX}kick <@member> [reason]`\n"
        f"`{PREFIX}ban <@member> [reason]`\n"
        f"`{PREFIX}unban <user_id> [reason]`\n"
        f"`{PREFIX}mute <@member> <minutes> [reason]` - Timeout a member.\n"
        f"`{PREFIX}unmute <@member> [reason]`\n"
        f"`{PREFIX}lock [reason]` / `{PREFIX}unlock [reason]`\n"
        f"`{PREFIX}slowmode <seconds>` - `0` disables.\n"
        f"`{PREFIX}warn <@member> <reason>`\n"
        f"`{PREFIX}warnings <@member>`\n"
        f"`{PREFIX}clearwarns <@member>`\n"
        f"`{PREFIX}setmodlog [#channel]` - Set mod-log channel (defaults to current channel).\n"
        f"`{PREFIX}clearmodlog` - Disable mod-log for this server.\n"
        f"`{PREFIX}reloadbadwords` - Reload `data/bad_words.txt`.\n"
        "\n"
        "**Utility/Fun Commands**\n"
        f"`{PREFIX}ping`\n"
        f"`{PREFIX}avatar [@member]`\n"
        f"`{PREFIX}userinfo [@member]`\n"
        f"`{PREFIX}serverinfo`\n"
        f"`{PREFIX}poll <question | option1 | option2 ...>` (2-10 options)\n"
        f"`{PREFIX}snipe` - Show last deleted non-bot message in this channel.\n"
        f"`{PREFIX}remind <minutes> <text>` - Sends you a DM reminder.\n"
        "\n"
        "**AI Commands (OpenRouter)**\n"
        f"`{PREFIX}ai <prompt>` - Ask AI with per-channel memory.\n"
        f"`{PREFIX}aireset` - Clear AI memory for this channel.\n"
        f"`{PREFIX}aimodel` - Show active OpenRouter model.\n"
        f"`{PREFIX}aimodels [limit]` - List currently available free models.\n"
        f"`{PREFIX}aisummary [count]` - Summarize recent channel messages.\n"
    )
    await ctx.send(text)


@bot.command(name="setmodlog")
@commands.has_permissions(manage_guild=True)
async def set_modlog_channel(
    ctx: commands.Context, channel: discord.TextChannel | None = None
) -> None:
    target_channel = channel or ctx.channel
    config = load_mod_config()
    guild_key = str(ctx.guild.id)
    config.setdefault(guild_key, {})
    config[guild_key]["mod_log_channel_id"] = target_channel.id
    save_mod_config(config)

    await ctx.send(f"Mod-log channel set to {target_channel.mention}.")
    await send_mod_log(
        ctx.guild,
        "Config: Mod Log Set",
        moderator=ctx.author,
        channel=target_channel,
        details=f"Channel ID: `{target_channel.id}`",
    )


@bot.command(name="clearmodlog")
@commands.has_permissions(manage_guild=True)
async def clear_modlog_channel(ctx: commands.Context) -> None:
    config = load_mod_config()
    guild_key = str(ctx.guild.id)
    if guild_key in config and "mod_log_channel_id" in config[guild_key]:
        del config[guild_key]["mod_log_channel_id"]
        save_mod_config(config)
    await ctx.send("Mod-log channel disabled for this server.")


@bot.command(name="reloadbadwords")
@commands.has_permissions(manage_guild=True)
async def reload_bad_words_command(ctx: commands.Context) -> None:
    count = reload_bad_words()
    await ctx.send(f"Reloaded blocked words. Active entries: `{count}`.")


@bot.command(name="ping")
async def ping_command(ctx: commands.Context) -> None:
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"Pong! `{latency_ms}ms`")


@bot.command(name="avatar")
async def avatar_command(
    ctx: commands.Context, member: discord.Member | None = None
) -> None:
    target = member or ctx.author
    embed = discord.Embed(
        title=f"{target.display_name}'s Avatar",
        color=discord.Color.blurple(),
    )
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="userinfo")
async def userinfo_command(
    ctx: commands.Context, member: discord.Member | None = None
) -> None:
    target = member or ctx.author
    embed = discord.Embed(
        title="User Info",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="User", value=f"{target} (`{target.id}`)", inline=False)
    embed.add_field(
        name="Created",
        value=discord.utils.format_dt(target.created_at, style="F"),
        inline=False,
    )
    if target.joined_at:
        embed.add_field(
            name="Joined Server",
            value=discord.utils.format_dt(target.joined_at, style="F"),
            inline=False,
        )
    roles = [role.mention for role in target.roles[1:][-8:]]
    embed.add_field(name="Top Role", value=target.top_role.mention, inline=True)
    embed.add_field(name="Roles (max 8)", value=", ".join(roles) if roles else "None", inline=False)
    await ctx.send(embed=embed)


@bot.command(name="serverinfo")
async def serverinfo_command(ctx: commands.Context) -> None:
    guild = ctx.guild
    embed = discord.Embed(
        title="Server Info",
        color=discord.Color.teal(),
        timestamp=discord.utils.utcnow(),
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Server", value=f"{guild.name} (`{guild.id}`)", inline=False)
    embed.add_field(name="Owner", value=str(guild.owner), inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, style="F"), inline=False)
    await ctx.send(embed=embed)


@bot.command(name="poll")
async def poll_command(ctx: commands.Context, *, text: str) -> None:
    parts = [part.strip() for part in text.split("|") if part.strip()]
    if len(parts) < 3:
        await ctx.send(
            f"Usage: `{PREFIX}poll Question | Option 1 | Option 2` (2-10 options)."
        )
        return

    question = parts[0]
    options = parts[1:]
    if len(options) > 10:
        await ctx.send("You can add a maximum of `10` options.")
        return

    lines = [f"{POLL_EMOJIS[i]} {opt}" for i, opt in enumerate(options)]
    embed = discord.Embed(
        title="Poll",
        description=f"**{question}**\n\n" + "\n".join(lines),
        color=discord.Color.gold(),
    )
    embed.set_footer(text=f"Poll by {ctx.author}")

    poll_message = await ctx.send(embed=embed)
    for i in range(len(options)):
        await poll_message.add_reaction(POLL_EMOJIS[i])


@bot.command(name="snipe")
async def snipe_command(ctx: commands.Context) -> None:
    payload = SNIPE_CACHE.get(ctx.channel.id)
    if not payload:
        await ctx.send("Nothing to snipe in this channel.")
        return

    embed = discord.Embed(
        title="Sniped Message",
        description=payload["content"],
        color=discord.Color.dark_teal(),
    )
    embed.set_author(name=f"{payload['author']} ({payload['author_id']})")
    await ctx.send(embed=embed)


@bot.command(name="remind")
async def remind_command(ctx: commands.Context, minutes: int, *, reminder_text: str) -> None:
    if minutes < 1 or minutes > 10080:
        await ctx.send("Minutes must be between `1` and `10080`.")
        return

    await ctx.send(f"Reminder set. I will DM you in `{minutes}` minute(s).")

    async def fire_reminder() -> None:
        await asyncio.sleep(minutes * 60)
        try:
            await ctx.author.send(f"Reminder from **{ctx.guild.name}**: {reminder_text}")
        except discord.HTTPException:
            try:
                await ctx.send(
                    f"{ctx.author.mention} reminder: {reminder_text}",
                    delete_after=20,
                )
            except discord.HTTPException:
                pass

    asyncio.create_task(fire_reminder())


@bot.command(name="aimodel")
async def aimodel_command(ctx: commands.Context) -> None:
    model_text = OPENROUTER_MODEL if OPENROUTER_MODEL else "(not set)"
    await ctx.send(
        f"Configured model: `{model_text}`\n"
        f"Fallbacks: `{', '.join(OPENROUTER_FALLBACK_MODELS)}`"
    )


@bot.command(name="aimodels")
async def aimodels_command(ctx: commands.Context, limit: int = 15) -> None:
    if limit < 1 or limit > 40:
        await ctx.send("`limit` must be between `1` and `40`.")
        return

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            available = await fetch_openrouter_models(session)
        except Exception as error:
            await ctx.send(f"Failed to fetch models: `{error}`")
            return

    free_models = sorted(model for model in available if model.endswith(":free"))
    if not free_models:
        await ctx.send("No `:free` models found right now.")
        return

    shown = free_models[:limit]
    text = "Available free models:\n" + "\n".join(f"- `{model}`" for model in shown)
    if len(free_models) > limit:
        text += f"\n...and `{len(free_models) - limit}` more."
    await send_chunked(ctx.channel, text)


@bot.command(name="aireset")
async def aireset_command(ctx: commands.Context) -> None:
    AI_CHAT_CACHE.pop(ctx.channel.id, None)
    await ctx.send("AI memory has been cleared for this channel.", delete_after=6)


@bot.command(name="ai", aliases=["ask"])
@commands.cooldown(3, 30, commands.BucketType.user)
async def ai_command(ctx: commands.Context, *, prompt: str | None = None) -> None:
    if not OPENROUTER_API_KEY:
        await ctx.send(
            "OpenRouter is not configured. Add `OPENROUTER_API_KEY` in `.env`, then restart the bot."
        )
        return

    prompt = (prompt or "").strip()
    if not prompt:
        await ctx.send(f"Usage: `{PREFIX}ai <prompt>` or `{PREFIX}aisummary 25`")
        return

    history = AI_CHAT_CACHE.get(ctx.channel.id, [])[-(AI_MAX_HISTORY * 2) :]
    messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}, *history]
    messages.append({"role": "user", "content": prompt})

    async with ctx.typing():
        try:
            reply = await request_openrouter_completion(
                messages,
                max_tokens=AI_MAX_TOKENS,
                temperature=0.5,
            )
        except Exception as error:
            print(f"[AI ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return

    append_ai_history(ctx.channel.id, prompt, reply)
    await send_chunked(ctx.channel, reply)


@bot.command(name="aisummary", aliases=["aisummarise", "summary"])
@commands.cooldown(2, 45, commands.BucketType.user)
async def aisummary_command(ctx: commands.Context, count: int = 25) -> None:
    if not OPENROUTER_API_KEY:
        await ctx.send(
            "OpenRouter is not configured. Add `OPENROUTER_API_KEY` in `.env`, then restart the bot."
        )
        return

    if count < 5 or count > 100:
        await ctx.send("`count` must be between `5` and `100`.")
        return

    transcript: list[str] = []
    async for msg in ctx.channel.history(limit=count):
        if msg.author.bot:
            continue
        content = msg.clean_content.strip()
        if not content:
            continue
        transcript.append(f"{msg.author.display_name}: {content[:280]}")

    if not transcript:
        await ctx.send("Not enough recent user messages to summarize.")
        return

    transcript.reverse()
    summary_prompt = (
        "Summarize this Discord chat in short bullet points.\n"
        "Include: key topics, decisions, and any action items.\n\n"
        + "\n".join(transcript)
    )
    messages = [
        {"role": "system", "content": AI_SYSTEM_PROMPT},
        {"role": "user", "content": summary_prompt},
    ]

    async with ctx.typing():
        try:
            summary = await request_openrouter_completion(
                messages,
                max_tokens=AI_SUMMARY_MAX_TOKENS,
                temperature=0.2,
            )
        except Exception as error:
            print(f"[AI SUMMARY ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return

    await send_chunked(ctx.channel, f"Summary of last `{len(transcript)}` messages:\n{summary}")


@bot.command(name="pb")
@commands.has_permissions(manage_messages=True)
async def purge_bot_messages(ctx: commands.Context, scan_limit: int = 0) -> None:
    if scan_limit < 0 or scan_limit > 50000:
        await ctx.send("`scan_limit` must be between `0` and `50000`.", delete_after=3)
        return

    limit = None if scan_limit == 0 else scan_limit
    deleted_messages = await ctx.channel.purge(
        limit=limit,
        check=lambda m: m.author.bot or m.webhook_id is not None,
        bulk=False,
    )
    deleted = len(deleted_messages)

    await ctx.send(f"`{deleted}` messages have been deleted.", delete_after=3)
    await send_mod_log(
        ctx.guild,
        "Purge Bot Messages",
        moderator=ctx.author,
        channel=ctx.channel,
        details=f"Deleted: `{deleted}`",
    )


@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear_messages(ctx: commands.Context, amount: int) -> None:
    if amount < 1 or amount > 500:
        await ctx.send("Amount must be between `1` and `500`.")
        return
    deleted = await ctx.channel.purge(limit=amount + 1)
    total_deleted = max(len(deleted) - 1, 0)
    await ctx.send(f"Deleted `{total_deleted}` messages.", delete_after=6)
    await send_mod_log(
        ctx.guild,
        "Clear Messages",
        moderator=ctx.author,
        channel=ctx.channel,
        details=f"Deleted: `{total_deleted}`",
    )


@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick_member(
    ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided."
) -> None:
    await member.kick(reason=reason)
    await ctx.send(f"Kicked {member.mention}. Reason: {reason}")
    await send_mod_log(
        ctx.guild,
        "Kick",
        target=member,
        moderator=ctx.author,
        reason=reason,
        channel=ctx.channel,
    )


@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban_member(
    ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided."
) -> None:
    await member.ban(reason=reason)
    await ctx.send(f"Banned {member.mention}. Reason: {reason}")
    await send_mod_log(
        ctx.guild,
        "Ban",
        target=member,
        moderator=ctx.author,
        reason=reason,
        channel=ctx.channel,
    )


@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban_member(
    ctx: commands.Context, user_id: int, *, reason: str = "No reason provided."
) -> None:
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user, reason=reason)
    await ctx.send(f"Unbanned `{user}`. Reason: {reason}")
    await send_mod_log(
        ctx.guild,
        "Unban",
        target=user,
        moderator=ctx.author,
        reason=reason,
        channel=ctx.channel,
    )


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute_member(
    ctx: commands.Context,
    member: discord.Member,
    minutes: int,
    *,
    reason: str = "No reason provided.",
) -> None:
    if minutes < 1 or minutes > 40320:
        await ctx.send("Minutes must be between `1` and `40320` (28 days).")
        return
    until = discord.utils.utcnow() + timedelta(minutes=minutes)
    await member.timeout(until, reason=reason)
    await ctx.send(f"Muted {member.mention} for `{minutes}` minute(s). Reason: {reason}")
    await send_mod_log(
        ctx.guild,
        "Mute",
        target=member,
        moderator=ctx.author,
        reason=reason,
        channel=ctx.channel,
        details=f"Duration: `{minutes}` minute(s)",
    )


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute_member(
    ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided."
) -> None:
    await member.timeout(None, reason=reason)
    await ctx.send(f"Unmuted {member.mention}. Reason: {reason}")
    await send_mod_log(
        ctx.guild,
        "Unmute",
        target=member,
        moderator=ctx.author,
        reason=reason,
        channel=ctx.channel,
    )


@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock_channel(ctx: commands.Context, *, reason: str = "No reason provided.") -> None:
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)
    await ctx.send(f"Locked {ctx.channel.mention}. Reason: {reason}")
    await send_mod_log(
        ctx.guild,
        "Lock Channel",
        moderator=ctx.author,
        reason=reason,
        channel=ctx.channel,
    )


@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock_channel(ctx: commands.Context, *, reason: str = "No reason provided.") -> None:
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = None
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)
    await ctx.send(f"Unlocked {ctx.channel.mention}. Reason: {reason}")
    await send_mod_log(
        ctx.guild,
        "Unlock Channel",
        moderator=ctx.author,
        reason=reason,
        channel=ctx.channel,
    )


@bot.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode_channel(ctx: commands.Context, seconds: int) -> None:
    if seconds < 0 or seconds > 21600:
        await ctx.send("Seconds must be between `0` and `21600`.")
        return
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(f"Set slowmode in {ctx.channel.mention} to `{seconds}` second(s).")
    await send_mod_log(
        ctx.guild,
        "Slowmode",
        moderator=ctx.author,
        channel=ctx.channel,
        details=f"Delay: `{seconds}` second(s)",
    )


@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def warn_member(
    ctx: commands.Context, member: discord.Member, *, reason: str
) -> None:
    warnings = load_warnings()
    guild_key = str(ctx.guild.id)
    user_key = str(member.id)

    warnings.setdefault(guild_key, {}).setdefault(user_key, [])
    warnings[guild_key][user_key].append(
        {
            "reason": reason,
            "moderator_id": ctx.author.id,
            "timestamp": discord.utils.utcnow().isoformat(),
        }
    )
    save_warnings(warnings)

    total = len(warnings[guild_key][user_key])
    await ctx.send(f"Warned {member.mention}. Total warnings: `{total}`.")
    await send_mod_log(
        ctx.guild,
        "Warn",
        target=member,
        moderator=ctx.author,
        reason=reason,
        channel=ctx.channel,
        details=f"Total warnings: `{total}`",
    )


@bot.command(name="warnings")
@commands.has_permissions(manage_messages=True)
async def list_warnings(ctx: commands.Context, member: discord.Member) -> None:
    warnings = load_warnings()
    guild_key = str(ctx.guild.id)
    user_key = str(member.id)
    user_warnings = warnings.get(guild_key, {}).get(user_key, [])

    if not user_warnings:
        await ctx.send(f"{member.mention} has no warnings.")
        return

    lines = []
    for i, entry in enumerate(user_warnings[-10:], start=max(1, len(user_warnings) - 9)):
        lines.append(
            f"{i}. Reason: {entry['reason']} | Mod ID: {entry['moderator_id']} | Time: {entry['timestamp']}"
        )
    await ctx.send(
        f"Warnings for {member.mention} (`{len(user_warnings)}` total):\n" + "\n".join(lines)
    )


@bot.command(name="clearwarns")
@commands.has_permissions(manage_messages=True)
async def clear_warnings(ctx: commands.Context, member: discord.Member) -> None:
    warnings = load_warnings()
    guild_key = str(ctx.guild.id)
    user_key = str(member.id)

    if guild_key in warnings and user_key in warnings[guild_key]:
        del warnings[guild_key][user_key]
        save_warnings(warnings)
        await ctx.send(f"Cleared all warnings for {member.mention}.")
        await send_mod_log(
            ctx.guild,
            "Clear Warnings",
            target=member,
            moderator=ctx.author,
            channel=ctx.channel,
        )
        return

    await ctx.send(f"{member.mention} has no warnings.")


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Command cooldown active. Try again in `{error.retry_after:.1f}`s.")
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`. Use `{PREFIX}help`.")
        return
    if isinstance(error, (commands.BadArgument, commands.MemberNotFound, commands.UserNotFound)):
        await ctx.send("Invalid argument. Use the correct mention/id format.")
        return
    await ctx.send(f"Error: `{error}`")


def main() -> None:
    if not TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is missing. Put it in your .env file.")
    ensure_data_files()
    reload_bad_words()
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
