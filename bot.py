import json
import os
import re
import asyncio
import time
import shutil
import random
from typing import Literal
from dataclasses import dataclass
from collections import Counter, defaultdict, deque
from datetime import timedelta
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

try:
    import yt_dlp
except Exception:
    yt_dlp = None

try:
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials
except Exception:
    spotipy = None
    SpotifyClientCredentials = None

try:
    import imageio_ffmpeg
except Exception:
    imageio_ffmpeg = None


load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PREFIX = os.getenv("BOT_PREFIX", "&")
BOT_ACTIVITY_TEXT = os.getenv("BOT_ACTIVITY_TEXT", "with your crush").strip()

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


AUTO_MOD_ENABLED = env_bool("AUTOMOD_ENABLED", False)
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
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()
GROQ_API_URL = os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions").strip()
GROQ_MODELS_URL = os.getenv("GROQ_MODELS_URL", "https://api.groq.com/openai/v1/models").strip()
AI_MAX_HISTORY = env_int("AI_MAX_HISTORY", 4, 2)
AI_MAX_TOKENS = env_int("AI_MAX_TOKENS", 260, 80)
AI_SUMMARY_MAX_TOKENS = env_int("AI_SUMMARY_MAX_TOKENS", 320, 120)
AI_TIMEOUT_SECONDS = env_int("AI_TIMEOUT_SECONDS", 45, 10)
SYNC_SLASH_COMMANDS = env_bool("SYNC_SLASH_COMMANDS", True)
VIBE_DEFAULT_MESSAGE_COUNT = env_int("VIBE_DEFAULT_MESSAGE_COUNT", 200, 20)
VIBE_MAX_MESSAGE_COUNT = env_int("VIBE_MAX_MESSAGE_COUNT", 800, 50)
VIBE_MIN_REQUIRED_MESSAGES = env_int("VIBE_MIN_REQUIRED_MESSAGES", 25, 5)
VIBE_MAX_PROMPT_MESSAGES = env_int("VIBE_MAX_PROMPT_MESSAGES", 80, 20)
VIBE_MAX_PROMPT_CHARS = env_int("VIBE_MAX_PROMPT_CHARS", 12000, 2000)
VOICE_CONNECT_RETRIES = env_int("VOICE_CONNECT_RETRIES", 4, 1)
VOICE_CONNECT_TIMEOUT = env_int("VOICE_CONNECT_TIMEOUT", 25, 10)
VOICE_INTERNAL_RECONNECT = env_bool("VOICE_INTERNAL_RECONNECT", False)
_AI_PROVIDER_RAW = os.getenv("AI_PROVIDER", "").strip().lower()
if _AI_PROVIDER_RAW in {"openrouter", "groq"}:
    AI_PROVIDER = _AI_PROVIDER_RAW
elif GROQ_API_KEY and not OPENROUTER_API_KEY:
    AI_PROVIDER = "groq"
else:
    AI_PROVIDER = "openrouter"
OPENROUTER_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "OPENROUTER_FALLBACK_MODELS",
        "google/gemma-3-4b-it:free,qwen/qwen3-4b:free,deepseek/deepseek-r1-0528:free",
    ).split(",")
    if model.strip()
]
GROQ_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GROQ_FALLBACK_MODELS",
        "llama-3.1-8b-instant,gemma2-9b-it",
    ).split(",")
    if model.strip()
]

FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg").strip() or "ffmpeg"
MUSIC_MAX_PLAYLIST_ITEMS = env_int("MUSIC_MAX_PLAYLIST_ITEMS", 50, 1)
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
CAT_API_URL = os.getenv("CAT_API_URL", "https://api.thecatapi.com/v1/images/search").strip()
MEALDB_BASE_URL = os.getenv(
    "MEALDB_BASE_URL", "https://www.themealdb.com/api/json/v1/1"
).strip().rstrip("/")
MEAL_CACHE_TTL_SECONDS = env_int("MEAL_CACHE_TTL_SECONDS", 1800, 60)

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
EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
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
VIBE_SYSTEM_PROMPT = (
    "You are generating a playful Discord 'vibe report' from chat messages. "
    "Keep it fun, non-judgmental, and privacy-respecting. "
    "Do not diagnose mental/medical conditions, do not infer protected traits, "
    "and avoid harsh labels. Mention uncertainty explicitly."
)
MODEL_CACHE: set[str] = set()
MODEL_CACHE_TS = 0.0
MODEL_CACHE_TTL_SECONDS = 600
SPOTIFY_CLIENT = None
FFMPEG_EXECUTABLE: str | None = None
INDIAN_VEG_MEALS_CACHE: list[dict[str, str]] = []
INDIAN_VEG_MEALS_CACHE_TS = 0.0

SPOTIFY_TRACK_RE = re.compile(
    r"(?:https?://open\.spotify\.com/track/|spotify:track:)([A-Za-z0-9]+)",
    re.IGNORECASE,
)
SPOTIFY_PLAYLIST_RE = re.compile(
    r"(?:https?://open\.spotify\.com/playlist/|spotify:playlist:)([A-Za-z0-9]+)",
    re.IGNORECASE,
)

YTDL_BASE_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": False,
    "source_address": "0.0.0.0",
}
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -loglevel warning",
}
TIMEOUT_DURATION_RE = re.compile(
    r"\b(\d{1,4})\s*(m|min|mins|minute|minutes)\b",
    re.IGNORECASE,
)


@dataclass
class MusicTrack:
    title: str
    webpage_url: str
    requested_by: int


MUSIC_QUEUES: dict[int, deque[MusicTrack]] = defaultdict(deque)
MUSIC_NOW_PLAYING: dict[int, MusicTrack] = {}
MUSIC_TEXT_CHANNELS: dict[int, int] = {}
MUSIC_LOCKS: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
APP_COMMANDS_SYNCED = False


def resolve_ffmpeg_executable() -> str | None:
    configured = (FFMPEG_PATH or "").strip()
    if configured:
        if os.path.isfile(configured):
            return configured
        found_configured = shutil.which(configured)
        if found_configured:
            return found_configured

    found_default = shutil.which("ffmpeg")
    if found_default:
        return found_default

    if imageio_ffmpeg is not None:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None
    return None


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


def get_guild_automod_enabled(guild_id: int) -> bool:
    config = load_mod_config()
    guild_config = config.get(str(guild_id), {})
    value = guild_config.get("automod_enabled")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on", "enabled"}:
            return True
        if lowered in {"0", "false", "no", "off", "disabled"}:
            return False
    return AUTO_MOD_ENABLED


def set_guild_automod_enabled(guild_id: int, enabled: bool) -> None:
    config = load_mod_config()
    guild_key = str(guild_id)
    config.setdefault(guild_key, {})
    config[guild_key]["automod_enabled"] = bool(enabled)
    save_mod_config(config)


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


async def fetch_json_response(session: aiohttp.ClientSession, url: str) -> dict | list:
    async with session.get(url) as response:
        raw = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"API error `{response.status}` from `{url}`.")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON response from `{url}`.") from exc


async def fetch_random_cat_image_url() -> str:
    timeout = aiohttp.ClientTimeout(total=18)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        payload = await fetch_json_response(session, CAT_API_URL)

    if not isinstance(payload, list) or not payload:
        raise RuntimeError("No cat images returned from API.")
    first = payload[0]
    if not isinstance(first, dict):
        raise RuntimeError("Unexpected cat API payload format.")
    url = first.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise RuntimeError("Cat API did not return a usable image URL.")
    return url


async def get_indian_veg_meals() -> list[dict[str, str]]:
    global INDIAN_VEG_MEALS_CACHE_TS, INDIAN_VEG_MEALS_CACHE
    now = time.monotonic()
    if INDIAN_VEG_MEALS_CACHE and now - INDIAN_VEG_MEALS_CACHE_TS < MEAL_CACHE_TTL_SECONDS:
        return INDIAN_VEG_MEALS_CACHE

    indian_url = f"{MEALDB_BASE_URL}/filter.php?a=Indian"
    vegetarian_url = f"{MEALDB_BASE_URL}/filter.php?c=Vegetarian"

    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        indian_payload, vegetarian_payload = await asyncio.gather(
            fetch_json_response(session, indian_url),
            fetch_json_response(session, vegetarian_url),
        )

    indian_meals = indian_payload.get("meals") if isinstance(indian_payload, dict) else None
    vegetarian_meals = (
        vegetarian_payload.get("meals") if isinstance(vegetarian_payload, dict) else None
    )
    if not isinstance(indian_meals, list) or not isinstance(vegetarian_meals, list):
        raise RuntimeError("Food API returned invalid data.")

    vegetarian_by_id: dict[str, dict] = {}
    for meal in vegetarian_meals:
        if not isinstance(meal, dict):
            continue
        meal_id = str(meal.get("idMeal") or "").strip()
        if meal_id:
            vegetarian_by_id[meal_id] = meal

    merged: list[dict[str, str]] = []
    for meal in indian_meals:
        if not isinstance(meal, dict):
            continue
        meal_id = str(meal.get("idMeal") or "").strip()
        if not meal_id or meal_id not in vegetarian_by_id:
            continue

        backup = vegetarian_by_id[meal_id]
        name = str(meal.get("strMeal") or backup.get("strMeal") or "Unknown dish").strip()
        thumb = str(meal.get("strMealThumb") or backup.get("strMealThumb") or "").strip()
        if not thumb.startswith(("http://", "https://")):
            continue
        merged.append({"id": meal_id, "name": name, "thumb": thumb})

    if not merged:
        raise RuntimeError("No Indian vegetarian meals found in API response.")

    INDIAN_VEG_MEALS_CACHE = merged
    INDIAN_VEG_MEALS_CACHE_TS = now
    return INDIAN_VEG_MEALS_CACHE


async def send_random_cat_image(channel: discord.abc.Messageable) -> None:
    try:
        image_url = await fetch_random_cat_image_url()
    except Exception:
        await channel.send("Could not fetch a cat image right now. Try again in a few seconds.")
        return

    embed = discord.Embed(title="Cute Random Cat", color=discord.Color.magenta())
    embed.set_image(url=image_url)
    await channel.send(embed=embed)


async def send_random_indian_veg_food(channel: discord.abc.Messageable) -> None:
    try:
        meals = await get_indian_veg_meals()
    except Exception:
        await channel.send("Could not fetch Indian veg food images right now. Try again in a few seconds.")
        return

    meal = random.choice(meals)
    embed = discord.Embed(
        title=f"Indian Veg Pick: {meal['name']}",
        color=discord.Color.orange(),
    )
    embed.set_image(url=meal["thumb"])
    await channel.send(embed=embed)


def has_active_timeout(member: discord.Member) -> bool:
    if hasattr(member, "is_timed_out"):
        try:
            return bool(member.is_timed_out())
        except Exception:
            pass
    until = getattr(member, "timed_out_until", None)
    return bool(until and until > discord.utils.utcnow())


async def remove_timeout_from_dm_request(user_id: int) -> tuple[int, int, int]:
    removed = 0
    active_found = 0
    failed = 0

    for guild in bot.guilds:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
        if not isinstance(member, discord.Member):
            continue
        if not has_active_timeout(member):
            continue

        active_found += 1
        me = guild.me
        if me is None and bot.user is not None:
            try:
                me = await guild.fetch_member(bot.user.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                me = None

        if me is None or not me.guild_permissions.moderate_members:
            failed += 1
            continue
        if member == guild.owner or member.top_role >= me.top_role:
            failed += 1
            continue

        try:
            await member.timeout(None, reason="User requested timeout removal via DM.")
            removed += 1
            await send_mod_log(
                guild,
                "Self Unmute via DM",
                target=member,
                moderator=bot.user,
                reason="User DMed `remove timeout`.",
                details="Timeout removed by DM self-service flow.",
            )
        except discord.HTTPException:
            failed += 1

    return removed, active_found, failed


def is_moderator(member: discord.Member) -> bool:
    perms = member.guild_permissions
    return (
        perms.administrator
        or perms.manage_messages
        or perms.moderate_members
        or perms.kick_members
        or perms.ban_members
        or perms.manage_channels
    )


def strip_bot_address_prefix(message: discord.Message) -> str | None:
    if bot.user is None:
        return None

    raw = message.content.strip()
    if not raw:
        return None

    mention_pattern = rf"^<@!?{bot.user.id}>\s*[:,\-]?\s*(.*)$"
    mention_match = re.match(mention_pattern, raw, flags=re.IGNORECASE)
    if mention_match:
        remainder = mention_match.group(1).strip()
        return remainder if remainder else None

    names: set[str] = {"bell", bot.user.name.lower()}
    if isinstance(message.guild, discord.Guild):
        me = message.guild.me
        if me and me.display_name:
            names.add(me.display_name.lower())

    lowered = raw.lower()
    for name in sorted(names, key=len, reverse=True):
        name_match = re.match(rf"^{re.escape(name)}\b\s*[:,\-]?\s*(.*)$", lowered)
        if name_match:
            remainder = name_match.group(1).strip()
            return remainder if remainder else None
    return None


def find_member_by_name(guild: discord.Guild, query: str) -> discord.Member | None:
    cleaned = re.sub(r"[^\w\s.\-]", " ", query).strip().lower()
    if not cleaned:
        return None

    words = cleaned.split()
    noise = {
        "avatar",
        "pfp",
        "profile",
        "pic",
        "picture",
        "timeout",
        "mute",
        "remove",
        "show",
        "give",
        "please",
        "to",
        "for",
        "of",
    }
    candidate = " ".join(w for w in words if w not in noise).strip()
    if not candidate:
        return None

    exact = discord.utils.find(
        lambda m: m.display_name.lower() == candidate or m.name.lower() == candidate,
        guild.members,
    )
    if exact:
        return exact

    starts = discord.utils.find(
        lambda m: m.display_name.lower().startswith(candidate) or m.name.lower().startswith(candidate),
        guild.members,
    )
    if starts:
        return starts
    return None


def extract_conversation_target(
    message: discord.Message, text: str, *, allow_self_avatar: bool = False
) -> discord.Member | None:
    for member in message.mentions:
        if bot.user is None or member.id != bot.user.id:
            return member

    lowered = text.lower()
    if allow_self_avatar and ("my avatar" in lowered or "my pfp" in lowered):
        return message.author if isinstance(message.author, discord.Member) else None

    if not isinstance(message.guild, discord.Guild):
        return None

    avatar_match = re.search(r"show\s+(.+?)'?s\s+avatar\b", text, flags=re.IGNORECASE)
    if avatar_match:
        found = find_member_by_name(message.guild, avatar_match.group(1))
        if found:
            return found

    pfp_possessive_match = re.search(r"show\s+(.+?)'?s\s+pfp\b", text, flags=re.IGNORECASE)
    if pfp_possessive_match:
        found = find_member_by_name(message.guild, pfp_possessive_match.group(1))
        if found:
            return found

    avatar_of_match = re.search(r"avatar\s+of\s+(.+)$", text, flags=re.IGNORECASE)
    if avatar_of_match:
        found = find_member_by_name(message.guild, avatar_of_match.group(1))
        if found:
            return found

    pfp_of_match = re.search(r"pfp\s+of\s+(.+)$", text, flags=re.IGNORECASE)
    if pfp_of_match:
        found = find_member_by_name(message.guild, pfp_of_match.group(1))
        if found:
            return found

    return find_member_by_name(message.guild, text)


async def send_avatar_for_member(channel: discord.abc.Messageable, target: discord.Member) -> None:
    embed = discord.Embed(
        title=f"{target.display_name}'s Avatar",
        color=discord.Color.blurple(),
    )
    embed.set_image(url=target.display_avatar.url)
    await channel.send(embed=embed)


async def send_server_info_embed(channel: discord.abc.Messageable, guild: discord.Guild) -> None:
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
    await channel.send(embed=embed)


async def purge_recent_bot_webhook_messages(
    channel: discord.TextChannel, trigger_message: discord.Message | None = None
) -> int:
    if trigger_message is not None:
        try:
            await trigger_message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    deleted_messages = await channel.purge(
        limit=20,
        check=lambda m: m.author.bot or m.webhook_id is not None,
        bulk=False,
    )
    return len(deleted_messages)


async def handle_conversational_request(message: discord.Message) -> bool:
    if message.guild is None or not isinstance(message.author, discord.Member):
        return False

    text = strip_bot_address_prefix(message)
    if not text:
        return False

    lowered = text.lower()

    if re.search(r"\bcats?\b", lowered):
        await send_random_cat_image(message.channel)
        return True

    if re.search(r"\bfood\b", lowered):
        await send_random_indian_veg_food(message.channel)
        return True

    if "automod" in lowered:
        if not is_moderator(message.author):
            await message.channel.send("Only moderators can use moderation actions in conversational mode.")
            return True

        if re.search(r"\b(on|enable|enabled|start)\b", lowered) or "turn on" in lowered:
            enabled = True
        elif re.search(r"\b(off|disable|disabled|stop)\b", lowered) or "turn off" in lowered:
            enabled = False
        else:
            enabled = not get_guild_automod_enabled(message.guild.id)

        set_guild_automod_enabled(message.guild.id, enabled)
        state_text = "enabled" if enabled else "disabled"
        await message.channel.send(f"Auto moderation is now **{state_text}** in this server.")
        await send_mod_log(
            message.guild,
            "Config: AutoMod Updated (Conversational)",
            moderator=message.author,
            channel=message.channel,
            details=f"New state: `{state_text}`",
        )
        return True

    if "ping" in lowered:
        latency_ms = round(bot.latency * 1000)
        await message.channel.send(f"Pong! `{latency_ms}ms`")
        return True

    if "server info" in lowered or "serverinfo" in lowered or "show server details" in lowered:
        await send_server_info_embed(message.channel, message.guild)
        return True

    clear_match = re.search(r"\bclear\b.*?\b(\d{1,3})\b.*\bmessages?\b", lowered)
    if clear_match:
        if not is_moderator(message.author):
            await message.channel.send("Only moderators can use moderation actions in conversational mode.")
            return True
        amount = int(clear_match.group(1))
        if amount < 1 or amount > 500:
            await message.channel.send("Amount must be between `1` and `500`.")
            return True
        deleted = await message.channel.purge(limit=amount + 1)
        total_deleted = max(len(deleted) - 1, 0)
        await message.channel.send(f"Deleted `{total_deleted}` messages.", delete_after=6)
        await send_mod_log(
            message.guild,
            "Clear Messages (Conversational)",
            moderator=message.author,
            channel=message.channel,
            details=f"Deleted: `{total_deleted}`",
        )
        return True

    clean_chat_requested = (
        re.search(r"\b(clean|clear)\b", lowered) is not None
        and (
            re.search(r"\b(chat|msgs?|messages?|mess)\b", lowered) is not None
            or lowered in {"clean", "clear"}
        )
    )
    if clean_chat_requested:
        if not is_moderator(message.author):
            await message.channel.send("Only moderators can use moderation actions in conversational mode.")
            return True
        deleted = await purge_recent_bot_webhook_messages(message.channel, trigger_message=message)
        await message.channel.send(f"`{deleted}` messages have been deleted.", delete_after=3)
        await send_mod_log(
            message.guild,
            "Purge Bot Messages (Conversational)",
            moderator=message.author,
            channel=message.channel,
            details=f"Deleted: `{deleted}`",
        )
        return True

    if re.search(r"\b(avatar|pfp)\b", lowered):
        target = extract_conversation_target(message, text, allow_self_avatar=True)
        if target is None:
            await message.channel.send("I could not find that user. Mention them or use an exact name.")
            return True
        await send_avatar_for_member(message.channel, target)
        return True

    is_timeout_action = (
        "timeout" in lowered
        or "mute" in lowered
        or "unmute" in lowered
        or "untimeout" in lowered
    )
    if is_timeout_action:
        if not is_moderator(message.author):
            await message.channel.send("Only moderators can use moderation actions in conversational mode.")
            return True

        target = extract_conversation_target(message, text)
        if target is None:
            await message.channel.send("Mention the user for timeout actions.")
            return True
        if target.bot:
            await message.channel.send("I will not apply timeout actions to bot accounts.")
            return True

        me = message.guild.me
        if me is None:
            await message.channel.send("Could not verify my permissions right now.")
            return True
        if not me.guild_permissions.moderate_members:
            await message.channel.send("I need `Moderate Members` permission to manage timeouts.")
            return True
        if target == message.guild.owner or target.top_role >= me.top_role:
            await message.channel.send("I cannot manage timeout for that member due to role hierarchy.")
            return True

        is_remove = (
            "remove" in lowered
            or "unmute" in lowered
            or "untimeout" in lowered
        )
        if is_remove:
            try:
                await target.timeout(None, reason=f"Conversational unmute by {message.author}")
            except discord.HTTPException:
                await message.channel.send("Failed to remove timeout for that user.")
                return True
            await message.channel.send(f"Removed timeout for {target.mention}.")
            await send_mod_log(
                message.guild,
                "Unmute (Conversational)",
                target=target,
                moderator=message.author,
                channel=message.channel,
                reason="Natural language request",
            )
            return True

        duration_match = TIMEOUT_DURATION_RE.search(lowered)
        if duration_match is None:
            await message.channel.send("Please include timeout duration, e.g. `20 mins`.")
            return True

        minutes = int(duration_match.group(1))
        if minutes < 1 or minutes > 40320:
            await message.channel.send("Minutes must be between `1` and `40320`.")
            return True

        until = discord.utils.utcnow() + timedelta(minutes=minutes)
        try:
            await target.timeout(until, reason=f"Conversational mute by {message.author}")
        except discord.HTTPException:
            await message.channel.send("Failed to apply timeout for that user.")
            return True

        await message.channel.send(f"Timed out {target.mention} for `{minutes}` minute(s).")
        await send_mod_log(
            message.guild,
            "Mute (Conversational)",
            target=target,
            moderator=message.author,
            channel=message.channel,
            reason="Natural language request",
            details=f"Duration: `{minutes}` minute(s)",
        )
        return True

    if not is_ai_configured():
        await message.channel.send(ai_setup_message())
        return True

    history = AI_CHAT_CACHE.get(message.channel.id, [])[-(AI_MAX_HISTORY * 2) :]
    ai_messages = [{"role": "system", "content": AI_SYSTEM_PROMPT}, *history]
    ai_messages.append({"role": "user", "content": text})
    async with message.channel.typing():
        try:
            reply = await request_ai_completion(
                ai_messages,
                max_tokens=AI_MAX_TOKENS,
                temperature=0.5,
            )
        except Exception as error:
            print(f"[CONVERSATIONAL AI ERROR] {error}")
            await message.channel.send(friendly_ai_error(error))
            return True

    append_ai_history(message.channel.id, text, reply)
    await send_chunked(message.channel, reply)
    return True


def get_spotify_client():
    global SPOTIFY_CLIENT
    if SPOTIFY_CLIENT is not None:
        return SPOTIFY_CLIENT
    if (
        spotipy is None
        or SpotifyClientCredentials is None
        or not SPOTIFY_CLIENT_ID
        or not SPOTIFY_CLIENT_SECRET
    ):
        return None
    SPOTIFY_CLIENT = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=SPOTIFY_CLIENT_ID,
            client_secret=SPOTIFY_CLIENT_SECRET,
        )
    )
    return SPOTIFY_CLIENT


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


async def ytdlp_extract(query: str) -> dict:
    if yt_dlp is None:
        raise RuntimeError("`yt-dlp` is not installed. Install requirements first.")

    options = dict(YTDL_BASE_OPTIONS)

    def _extract() -> dict:
        with yt_dlp.YoutubeDL(options) as ydl:
            return ydl.extract_info(query, download=False)

    return await asyncio.to_thread(_extract)


async def ytdlp_extract_stream(query: str) -> dict:
    if yt_dlp is None:
        raise RuntimeError("`yt-dlp` is not installed. Install requirements first.")

    option_sets = [
        {
            **YTDL_BASE_OPTIONS,
            "format": "bestaudio/best",
            "noplaylist": True,
            "extractor_args": {"youtube": {"player_client": ["web"]}},
        },
        {
            **YTDL_BASE_OPTIONS,
            "format": "bestaudio/best",
            "noplaylist": True,
            "extractor_args": {"youtube": {"player_client": ["ios"]}},
        },
        {
            **YTDL_BASE_OPTIONS,
            "format": "best",
            "noplaylist": True,
        },
    ]

    last_error: Exception | None = None
    for options in option_sets:
        try:
            def _extract() -> dict:
                with yt_dlp.YoutubeDL(options) as ydl:
                    return ydl.extract_info(query, download=False)

            return await asyncio.to_thread(_extract)
        except Exception as error:
            last_error = error
            continue

    raise RuntimeError(last_error or "yt-dlp could not extract stream data.")


def track_from_ytdlp_entry(entry: dict, requester_id: int) -> MusicTrack | None:
    if not entry:
        return None
    title = entry.get("title") or "Unknown title"
    webpage_url = entry.get("webpage_url") or entry.get("url") or ""

    if webpage_url and not str(webpage_url).startswith("http"):
        video_id = entry.get("id")
        if video_id:
            webpage_url = f"https://www.youtube.com/watch?v={video_id}"
    if not webpage_url:
        return None

    return MusicTrack(
        title=title[:200],
        webpage_url=str(webpage_url),
        requested_by=requester_id,
    )


async def youtube_query_to_tracks(query: str, requester_id: int) -> list[MusicTrack]:
    info = await ytdlp_extract(query)
    entries = info.get("entries")
    tracks: list[MusicTrack] = []

    if isinstance(entries, list):
        for entry in entries:
            track = track_from_ytdlp_entry(entry, requester_id)
            if track is None:
                continue
            tracks.append(track)
            if len(tracks) >= MUSIC_MAX_PLAYLIST_ITEMS:
                break
    else:
        track = track_from_ytdlp_entry(info, requester_id)
        if track is not None:
            tracks.append(track)

    if not tracks:
        raise RuntimeError("No playable results found for that query.")
    return tracks


async def spotify_url_to_search_queries(url: str) -> tuple[list[str], str]:
    client = get_spotify_client()
    if client is None:
        raise RuntimeError(
            "Spotify is not configured. Set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env`."
        )

    track_match = SPOTIFY_TRACK_RE.search(url)
    if track_match:
        track_id = track_match.group(1)

        def _fetch_track():
            return client.track(track_id)

        track_obj = await asyncio.to_thread(_fetch_track)
        name = (track_obj or {}).get("name", "Unknown track")
        artists = ", ".join(a.get("name", "") for a in (track_obj or {}).get("artists", []) if a)
        query = f"{name} {artists} audio".strip()
        return [query], f"Spotify track: {name}"

    playlist_match = SPOTIFY_PLAYLIST_RE.search(url)
    if playlist_match:
        playlist_id = playlist_match.group(1)

        def _fetch_playlist_queries():
            queries: list[str] = []
            offset = 0
            playlist_name = f"Spotify playlist {playlist_id}"
            while True:
                try:
                    payload = client.playlist_items(
                        playlist_id,
                        offset=offset,
                        limit=100,
                        fields="items(track(name,artists(name))),next",
                        additional_types=("track",),
                    )
                except Exception as error:
                    message = str(error).lower()
                    if "http status: 403" in message or "forbidden" in message:
                        raise RuntimeError(
                            "Spotify playlist is not accessible (403). Make it Public and try again."
                        ) from error
                    raise RuntimeError(f"Spotify API error while reading playlist: {error}") from error
                if offset == 0:
                    playlist_meta = client.playlist(playlist_id, fields="name")
                    if playlist_meta and playlist_meta.get("name"):
                        playlist_name = playlist_meta["name"]
                items = payload.get("items", [])
                for item in items:
                    track_obj = (item or {}).get("track")
                    if not track_obj:
                        continue
                    name = track_obj.get("name")
                    if not name:
                        continue
                    artists = ", ".join(
                        a.get("name", "") for a in track_obj.get("artists", []) if a
                    )
                    queries.append(f"{name} {artists} audio".strip())
                    if len(queries) >= MUSIC_MAX_PLAYLIST_ITEMS:
                        return queries, playlist_name
                if not payload.get("next"):
                    break
                offset += len(items)
            return queries, playlist_name

        queries, playlist_name = await asyncio.to_thread(_fetch_playlist_queries)
        if not queries:
            raise RuntimeError("Spotify playlist has no playable tracks.")
        return queries, f"Spotify playlist: {playlist_name}"

    raise RuntimeError("Only Spotify track/playlist links are supported.")


async def source_to_tracks(source: str, requester_id: int) -> tuple[list[MusicTrack], str | None]:
    if SPOTIFY_TRACK_RE.search(source) or SPOTIFY_PLAYLIST_RE.search(source):
        queries, label = await spotify_url_to_search_queries(source)
        tracks: list[MusicTrack] = []
        for q in queries:
            result = await youtube_query_to_tracks(f"ytsearch1:{q}", requester_id)
            if result:
                tracks.append(result[0])
        if not tracks:
            raise RuntimeError("Could not map Spotify tracks to YouTube sources.")
        return tracks, label

    query = source if is_url(source) else f"ytsearch1:{source}"
    tracks = await youtube_query_to_tracks(query, requester_id)
    return tracks, None


def extract_stream_url(info: dict) -> str | None:
    direct_url = info.get("url")
    if isinstance(direct_url, str) and direct_url.startswith(("http://", "https://")):
        return direct_url

    requested_formats = info.get("requested_formats") or []
    for fmt in requested_formats:
        fmt_url = (fmt or {}).get("url")
        if not fmt_url:
            continue
        if (fmt or {}).get("acodec") not in (None, "none"):
            return str(fmt_url)

    formats = info.get("formats") or []
    best_url = None
    best_score = None
    for fmt in formats:
        if not isinstance(fmt, dict):
            continue
        fmt_url = fmt.get("url")
        if not fmt_url:
            continue
        acodec = fmt.get("acodec")
        if acodec in (None, "none"):
            continue
        audio_only = 1 if fmt.get("vcodec") in (None, "none") else 0
        score = (
            audio_only,
            float(fmt.get("abr") or 0),
            float(fmt.get("tbr") or 0),
            float(fmt.get("asr") or 0),
        )
        if best_score is None or score > best_score:
            best_score = score
            best_url = str(fmt_url)
    return best_url


async def resolve_stream(track: MusicTrack) -> tuple[str, str, str]:
    current_url = track.webpage_url
    info: dict | None = None

    for _ in range(3):
        info = await ytdlp_extract_stream(current_url)
        entries = info.get("entries")
        if isinstance(entries, list) and entries:
            info = entries[0]

        stream_url = extract_stream_url(info)
        title = info.get("title") or track.title
        webpage_url = info.get("webpage_url") or current_url
        if stream_url:
            return str(stream_url), str(title), str(webpage_url)

        fallback_url = info.get("webpage_url") or info.get("url")
        if (
            isinstance(fallback_url, str)
            and fallback_url.startswith(("http://", "https://"))
            and fallback_url != current_url
        ):
            current_url = fallback_url
            continue
        break

    raise RuntimeError(
        "Could not resolve a stream URL for this track. Try another source/query "
        "or update yt-dlp on the host."
    )


async def ensure_voice_connection(ctx: commands.Context) -> discord.VoiceClient | None:
    if not isinstance(ctx.author, discord.Member) or not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.send("Join a voice channel first.")
        return None

    target_channel = ctx.author.voice.channel
    last_error: Exception | None = None

    for attempt in range(1, VOICE_CONNECT_RETRIES + 1):
        vc = ctx.guild.voice_client
        try:
            if vc is not None and not vc.is_connected():
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass
                vc = None
                await asyncio.sleep(0.35)

            if vc is None:
                vc = await asyncio.wait_for(
                    target_channel.connect(
                        timeout=VOICE_CONNECT_TIMEOUT,
                        reconnect=VOICE_INTERNAL_RECONNECT,
                    ),
                    timeout=VOICE_CONNECT_TIMEOUT + 5,
                )
            elif vc.channel != target_channel:
                await asyncio.wait_for(
                    vc.move_to(target_channel),
                    timeout=VOICE_CONNECT_TIMEOUT,
                )

            if vc is not None and vc.is_connected():
                return vc
            raise RuntimeError("Voice client did not stay connected after handshake.")
        except Exception as error:
            last_error = error
            print(
                f"[VOICE CONNECT] attempt {attempt}/{VOICE_CONNECT_RETRIES} failed in guild "
                f"{ctx.guild.id}: {error!r}"
            )
            stale = ctx.guild.voice_client
            if stale is not None:
                try:
                    await stale.disconnect(force=True)
                except Exception:
                    pass
            if attempt < VOICE_CONNECT_RETRIES:
                await asyncio.sleep(min(2.5, 0.75 * attempt))

    error_text = str(last_error).lower() if last_error else ""
    if "4006" in error_text or "voice handshake" in error_text:
        await ctx.send(
            "Voice connect failed (`4006`). This is usually a hosting/network issue (Discord voice UDP). "
            "Try again once; if it keeps failing, switch node/provider."
        )
    else:
        await ctx.send(
            f"Could not join/move voice channel after `{VOICE_CONNECT_RETRIES}` tries: "
            f"`{last_error or 'unknown error'}`"
        )
    return None


def in_same_voice_channel(ctx: commands.Context) -> bool:
    vc = ctx.guild.voice_client
    if vc is None:
        return False
    author = ctx.author
    return isinstance(author, discord.Member) and author.voice and author.voice.channel == vc.channel


def get_music_text_channel(guild: discord.Guild) -> discord.TextChannel | None:
    channel_id = MUSIC_TEXT_CHANNELS.get(guild.id)
    if channel_id is None:
        return None
    channel = guild.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return channel
    return None


def music_after_playback(guild: discord.Guild, error: Exception | None) -> None:
    if error is not None:
        print(f"[MUSIC PLAYBACK ERROR] {error}")
    future = asyncio.run_coroutine_threadsafe(play_next_track(guild), bot.loop)
    try:
        future.result()
    except Exception as follow_err:
        print(f"[MUSIC FOLLOWUP ERROR] {follow_err}")


async def play_next_track(guild: discord.Guild) -> None:
    global FFMPEG_EXECUTABLE
    lock = MUSIC_LOCKS[guild.id]
    async with lock:
        vc = guild.voice_client
        if vc is None or not vc.is_connected():
            MUSIC_NOW_PLAYING.pop(guild.id, None)
            return
        if vc.is_playing() or vc.is_paused():
            return

        if not FFMPEG_EXECUTABLE:
            FFMPEG_EXECUTABLE = resolve_ffmpeg_executable()
        if not FFMPEG_EXECUTABLE:
            channel = get_music_text_channel(guild)
            if channel is not None:
                await channel.send(
                    "Playback failed: ffmpeg not found on host. "
                    "Install ffmpeg or add `imageio-ffmpeg` dependency."
                )
            return

        queue = MUSIC_QUEUES[guild.id]
        while queue:
            track = queue.popleft()
            try:
                stream_url, title, webpage_url = await resolve_stream(track)
            except Exception as error:
                channel = get_music_text_channel(guild)
                if channel is not None:
                    await channel.send(f"Skipping `{track.title}`: {error}")
                continue

            track.title = title[:200]
            track.webpage_url = webpage_url
            channel = get_music_text_channel(guild)
            try:
                source = discord.FFmpegPCMAudio(
                    stream_url,
                    executable=FFMPEG_EXECUTABLE,
                    **FFMPEG_OPTIONS,
                )
                vc.play(source, after=lambda e: music_after_playback(guild, e))
                MUSIC_NOW_PLAYING[guild.id] = track
                if channel is not None:
                    await channel.send(f"Now playing: **{track.title}**")
                return
            except Exception as error:
                if channel is not None:
                    await channel.send(f"Playback failed for `{track.title}`: {error}")
                continue

        MUSIC_NOW_PLAYING.pop(guild.id, None)


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


async def fetch_groq_models(session: aiohttp.ClientSession) -> set[str]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing in .env")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    async with session.get(GROQ_MODELS_URL, headers=headers) as response:
        text = await response.text()
        if response.status >= 400:
            raise RuntimeError(f"Could not fetch Groq models (`{response.status}`): {text[:200]}")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Groq model list response is not valid JSON.") from exc

    return {
        item.get("id", "")
        for item in payload.get("data", [])
        if isinstance(item, dict) and item.get("id")
    }


def get_model_try_order(provider: str) -> list[str]:
    models: list[str] = []
    seen: set[str] = set()
    if provider == "groq":
        ordered = [GROQ_MODEL, *GROQ_FALLBACK_MODELS]
    else:
        ordered = [OPENROUTER_MODEL, *OPENROUTER_FALLBACK_MODELS]
    for model in ordered:
        cleaned = model.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        models.append(cleaned)
    return models


def should_try_fallback(status: int, raw_text: str, provider: str) -> bool:
    body = raw_text.lower()
    if status in {404, 429, 500, 502, 503, 504}:
        return True
    if provider == "groq":
        return "rate limit" in body or "model_decommissioned" in body or "unavailable" in body
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
        if AI_PROVIDER == "groq":
            return "Model blocked by provider policy. Try `&aimodel` or switch model."
        return "Model blocked by OpenRouter data policy. Use `&aimodels` and choose another free model."
    if "401" in text or "unauthorized" in text or "invalid api key" in text:
        if AI_PROVIDER == "groq":
            return "Groq API key looks invalid. Update `GROQ_API_KEY` in `.env` and restart."
        return "OpenRouter API key looks invalid. Update `OPENROUTER_API_KEY` in `.env` and restart."
    return "AI request failed temporarily. Please try again in a few seconds."


def is_ai_configured() -> bool:
    if AI_PROVIDER == "groq":
        return bool(GROQ_API_KEY)
    return bool(OPENROUTER_API_KEY)


def ai_setup_message() -> str:
    if AI_PROVIDER == "groq":
        return "Groq is not configured. Add `GROQ_API_KEY` in `.env`, then restart the bot."
    return "OpenRouter is not configured. Add `OPENROUTER_API_KEY` in `.env`, then restart the bot."


def current_ai_model() -> str:
    return GROQ_MODEL if AI_PROVIDER == "groq" else OPENROUTER_MODEL


def current_ai_fallback_models() -> list[str]:
    return GROQ_FALLBACK_MODELS if AI_PROVIDER == "groq" else OPENROUTER_FALLBACK_MODELS


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
    models_to_try = get_model_try_order("openrouter")
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
                            response.status, raw_text, "openrouter"
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


async def request_groq_completion(
    messages: list[dict[str, str]], *, max_tokens: int = 260, temperature: float = 0.6
) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing in .env")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=AI_TIMEOUT_SECONDS)
    models_to_try = get_model_try_order("groq")
    last_error = "Groq request failed."
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for index, model_to_use in enumerate(models_to_try):
            payload = {
                "model": model_to_use,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            try:
                async with session.post(GROQ_API_URL, headers=headers, json=payload) as response:
                    raw_text = await response.text()
                    if response.status >= 400:
                        last_error = (
                            f"Groq API error `{response.status}` for `{model_to_use}`: "
                            f"{raw_text[:220]}"
                        )
                        if index < len(models_to_try) - 1 and should_try_fallback(
                            response.status, raw_text, "groq"
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

            if model_to_use != GROQ_MODEL:
                return f"[Fallback model: `{model_to_use}`]\n\n{content.strip()}"
            return content.strip()

    raise RuntimeError(last_error)


async def request_ai_completion(
    messages: list[dict[str, str]], *, max_tokens: int = 260, temperature: float = 0.6
) -> str:
    if AI_PROVIDER == "groq":
        return await request_groq_completion(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    return await request_openrouter_completion(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def append_ai_history(channel_id: int, user_prompt: str, assistant_reply: str) -> None:
    history = AI_CHAT_CACHE[channel_id]
    history.append({"role": "user", "content": user_prompt})
    history.append({"role": "assistant", "content": assistant_reply})
    max_entries = max(2, AI_MAX_HISTORY * 2)
    if len(history) > max_entries:
        AI_CHAT_CACHE[channel_id] = history[-max_entries:]


async def collect_vibe_context(
    channel: discord.TextChannel,
    user_id: int,
    target_messages: int,
) -> tuple[list[str], list[str]]:
    desired = max(1, target_messages)
    scan_limit = min(max(desired * 12, desired + 160), 7000)

    user_messages: list[str] = []
    replies_received: list[str] = []
    target_message_ids: set[int] = set()

    async for msg in channel.history(limit=scan_limit, oldest_first=True):
        if msg.author.bot:
            continue
        content = msg.clean_content.strip()
        if not content:
            continue
        content = content[:420]

        if msg.author.id == user_id:
            user_messages.append(content)
            target_message_ids.add(msg.id)
            continue

        is_reply_to_target = False
        if msg.reference and msg.reference.message_id in target_message_ids:
            is_reply_to_target = True
        elif any(getattr(m, "id", None) == user_id for m in msg.mentions):
            is_reply_to_target = True

        if is_reply_to_target:
            replies_received.append(content)

    user_messages = user_messages[-desired:]
    max_replies = min(max(desired, 30), desired * 2)
    replies_received = replies_received[-max_replies:]
    return user_messages, replies_received


def trim_context_lines(source: list[str], max_lines: int, max_chars: int) -> list[str]:
    selected: list[str] = []
    total = 0
    for raw in reversed(source[-max_lines:]):
        line = " ".join(raw.split()).strip()
        if not line:
            continue
        if len(line) > 220:
            line = line[:220].rstrip() + "..."
        projected = total + len(line) + 4
        if projected > max_chars:
            break
        selected.append(line)
        total = projected
    selected.reverse()
    return selected


def build_vibe_prompt_lines(
    user_messages: list[str], replies_received: list[str]
) -> tuple[list[str], list[str]]:
    total_budget = max(VIBE_MAX_PROMPT_CHARS, 2000)
    user_budget = int(total_budget * 0.62)
    reply_budget = total_budget - user_budget
    user_lines = trim_context_lines(user_messages, VIBE_MAX_PROMPT_MESSAGES, user_budget)
    reply_lines = trim_context_lines(replies_received, VIBE_MAX_PROMPT_MESSAGES, reply_budget)
    return user_lines, reply_lines


def generate_vibe_report_local(
    member: discord.Member, user_messages: list[str], replies_received: list[str]
) -> str:
    msg_count = len(user_messages)
    joined = " ".join(user_messages).lower()
    words = [w for w in WORD_PATTERN.findall(joined) if len(w) > 2]
    stop = {
        "the", "and", "for", "that", "with", "this", "you", "are", "was", "have", "not", "but",
        "just", "your", "from", "what", "when", "where", "will", "would", "they", "them", "their",
        "about", "there", "then", "than", "into", "also", "been", "can", "could", "should",
    }
    filtered = [w for w in words if w not in stop]
    common = [w for w, _ in Counter(filtered).most_common(6)]
    topic_text = ", ".join(common[:5]) if common else "general chat"

    question_ratio = sum(1 for m in user_messages if "?" in m) / max(msg_count, 1)
    exclaim_ratio = sum(1 for m in user_messages if "!" in m) / max(msg_count, 1)

    reply_text = " ".join(replies_received).lower()
    pos_markers = ["thanks", "thank", "love", "nice", "great", "good", "haha", "lol", "bro", "best"]
    neg_markers = ["stupid", "idiot", "hate", "shut", "noob", "trash", "bad", "annoying", "toxic", "loser"]
    pos_hits = sum(reply_text.count(w) for w in pos_markers)
    neg_hits = sum(reply_text.count(w) for w in neg_markers)

    style_bits = []
    if exclaim_ratio > 0.18:
        style_bits.append("high-energy and expressive")
    if question_ratio > 0.22:
        style_bits.append("question-driven and curious")
    if not style_bits:
        style_bits.append("casual and conversational")

    if not replies_received:
        response_read = "There is limited visible reply context in this channel snapshot."
    elif pos_hits > neg_hits * 1.3:
        response_read = "People mostly respond with positive and engaged reactions."
    elif neg_hits > pos_hits * 1.3:
        response_read = "Replies show noticeable pushback or teasing around their messages."
    else:
        response_read = "Replies are mixed, with both positive engagement and occasional friction."

    return (
        f"Behavior Snapshot: {member.display_name} tends to communicate in a {style_bits[0]} way, "
        f"and their recent messages revolve around topics like {topic_text}. Their wording suggests a "
        "social, active presence in chat, with tone shifting based on context.\n\n"
        f"How Others Respond: {response_read} This read is based on recent direct replies/mentions in the "
        "same channel and can vary heavily across different channels or days.\n\n"
        "Balanced Take: They come across as engaged and visible in conversation, and depending on the moment, "
        "their style may feel either fun/hyped or sharp/blunt to others. This is a lightweight estimate from "
        "recent chat behavior, not a factual judgment."
    )


def generate_vibecheck_local(user_messages: list[str], replies_received: list[str]) -> str:
    message_count = max(1, len(user_messages))
    text = " ".join(user_messages).lower()
    replies_text = " ".join(replies_received).lower()

    exclaim_ratio = sum(1 for m in user_messages if "!" in m) / message_count
    question_ratio = sum(1 for m in user_messages if "?" in m) / message_count

    chaos_percent = int(min(95, max(15, 30 + exclaim_ratio * 280 + question_ratio * 120)))
    if chaos_percent >= 75:
        mood_label = "chaotic"
    elif chaos_percent >= 55:
        mood_label = "hyped"
    elif chaos_percent >= 35:
        mood_label = "balanced"
    else:
        mood_label = "calm"

    supportive_hits = sum(text.count(w) for w in ["thanks", "love", "bro", "help", "nice", "great"])
    roast_hits = sum(text.count(w) for w in ["noob", "stupid", "idiot", "trash", "roast", "shut"])
    question_hits = sum(m.count("?") for m in user_messages)
    mention_hits = sum(m.count("@") for m in user_messages) + replies_text.count("@")

    if supportive_hits > roast_hits and supportive_hits > question_hits:
        dominant_trait = "supportive hype friend"
    elif question_hits > supportive_hits and question_hits > roast_hits:
        dominant_trait = "curious conversation starter"
    elif roast_hits >= 3:
        dominant_trait = "playful instigator"
    else:
        dominant_trait = "social chatter spark"

    roast_score = roast_hits + int(exclaim_ratio * 6)
    if roast_score >= 7:
        roast_level = "unhinged roast machine"
    elif roast_score >= 4:
        roast_level = "medium spice"
    elif roast_score >= 2:
        roast_level = "light teasing"
    else:
        roast_level = "mostly wholesome"

    energy_score = exclaim_ratio * 5 + question_ratio * 3 + (mention_hits / max(message_count, 1))
    if energy_score >= 3.8:
        social_energy = "main character mode"
    elif energy_score >= 2.3:
        social_energy = "active and loud"
    elif energy_score >= 1.2:
        social_energy = "steady participant"
    else:
        social_energy = "low-key presence"

    return (
        "🔥 Vibe Check Result\n"
        f"Mood: {chaos_percent}% {mood_label}\n"
        f"Dominant trait: {dominant_trait}\n"
        f"Roast level: {roast_level}\n"
        f"Social energy: {social_energy}\n\n"
        "⚠️ For fun only."
    )


def normalize_vibecheck_output(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        text = "🔥 Vibe Check Result"
    if "vibe check result" not in text.lower():
        text = "🔥 Vibe Check Result\n" + text
    if "for fun only" not in text.lower():
        text = text.rstrip() + "\n\n⚠️ For fun only."
    return text


async def generate_vibecheck_report(
    member: discord.Member, user_messages: list[str], replies_received: list[str]
) -> str:
    user_lines, reply_lines = build_vibe_prompt_lines(user_messages, replies_received)
    user_transcript = "\n".join(f"- {line}" for line in user_lines) or "- (none)"
    reply_transcript = "\n".join(f"- {line}" for line in reply_lines) if reply_lines else "- (none)"
    prompt = (
        "Create a short playful Discord vibe check.\n"
        "Rules:\n"
        "1) Fun only, do not diagnose.\n"
        "2) No slurs, no hate, no protected-trait inferences.\n"
        "3) Keep each value concise (2-6 words).\n"
        "4) Return EXACTLY this format:\n"
        "🔥 Vibe Check Result\n"
        "Mood: <0-100>% <descriptor>\n"
        "Dominant trait: <descriptor>\n"
        "Roast level: <descriptor>\n"
        "Social energy: <descriptor>\n"
        "⚠️ For fun only.\n\n"
        f"Target user: {member.display_name}\n"
        f"User messages analyzed: {len(user_messages)}\n"
        f"Replies considered: {len(replies_received)}\n\n"
        "User message sample:\n"
        f"{user_transcript}\n\n"
        "Replies from others sample:\n"
        f"{reply_transcript}"
    )
    ai_messages = [
        {"role": "system", "content": VIBE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    output = await request_ai_completion(
        ai_messages,
        max_tokens=180,
        temperature=0.45,
    )
    return normalize_vibecheck_output(output)


async def collect_recent_channel_transcript(
    channel: discord.TextChannel, limit: int
) -> list[str]:
    lines: list[str] = []
    async for msg in channel.history(limit=limit):
        if msg.author.bot:
            continue
        content = msg.clean_content.strip()
        if not content:
            continue
        lines.append(f"{msg.author.display_name}: {content[:260]}")
    lines.reverse()
    return lines


async def collect_recent_user_messages(
    channel: discord.TextChannel, user_id: int, limit: int
) -> list[str]:
    messages: list[str] = []
    async for msg in channel.history(limit=min(5000, max(limit * 8, limit + 120))):
        if msg.author.bot or msg.author.id != user_id:
            continue
        content = msg.clean_content.strip()
        if not content:
            continue
        messages.append(content[:260])
        if len(messages) >= limit:
            break
    messages.reverse()
    return messages


def user_style_stats(user_messages: list[str]) -> dict[str, str]:
    if not user_messages:
        return {
            "avg_len": "0",
            "question_ratio": "0%",
            "exclaim_ratio": "0%",
            "emoji_per_msg": "0.00",
            "top_words": "none",
        }

    joined = " ".join(user_messages).lower()
    words = [w for w in WORD_PATTERN.findall(joined) if len(w) > 2]
    stop = {
        "the", "and", "for", "that", "with", "this", "you", "are", "was", "have", "not", "but",
        "just", "your", "from", "what", "when", "where", "will", "would", "they", "them", "their",
        "about", "there", "then", "than", "into", "also", "been", "can", "could", "should",
    }
    filtered = [w for w in words if w not in stop]
    common = [w for w, _ in Counter(filtered).most_common(5)]
    avg_len = sum(len(m) for m in user_messages) / max(1, len(user_messages))
    question_ratio = sum(1 for m in user_messages if "?" in m) / max(1, len(user_messages))
    exclaim_ratio = sum(1 for m in user_messages if "!" in m) / max(1, len(user_messages))
    emoji_count = sum(len(EMOJI_PATTERN.findall(m)) for m in user_messages)
    emoji_per_msg = emoji_count / max(1, len(user_messages))
    return {
        "avg_len": f"{avg_len:.1f}",
        "question_ratio": f"{question_ratio * 100:.0f}%",
        "exclaim_ratio": f"{exclaim_ratio * 100:.0f}%",
        "emoji_per_msg": f"{emoji_per_msg:.2f}",
        "top_words": ", ".join(common) if common else "none",
    }


async def request_fun_ai(
    user_prompt: str,
    *,
    max_tokens: int = 220,
    temperature: float = 0.8,
) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a witty Discord assistant for fun community features. "
                "Keep outputs entertaining but avoid hate speech, slurs, sexual content about minors, "
                "or severe harassment. Keep responses compact and readable."
            ),
        },
        {"role": "user", "content": user_prompt},
    ]
    return await request_ai_completion(
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def generate_vibe_report(
    member: discord.Member, user_messages: list[str], replies_received: list[str]
) -> str:
    user_lines, reply_lines = build_vibe_prompt_lines(user_messages, replies_received)
    user_transcript = "\n".join(f"- {line}" for line in user_lines)
    replies_transcript = "\n".join(f"- {line}" for line in reply_lines) if reply_lines else "- (No clear replies found in range)"
    prompt = (
        "Create a Discord behavior snapshot in a paragraph format.\n"
        "Rules:\n"
        "1) Fun-only, non-diagnostic.\n"
        "2) No mental health or medical labels.\n"
        "3) Include balanced positives and rough edges only if observable.\n"
        "4) Use hedge words (e.g., seems, appears) for uncertain claims.\n"
        "5) No direct quotes from messages.\n"
        "6) Keep output under 240 words.\n\n"
        "Output format (exact headings, paragraph under each):\n"
        "Behavior Snapshot:\n"
        "How Others Respond:\n"
        "Balanced Take:\n"
        "Disclaimer:\n\n"
        f"User: {member.display_name}\n"
        f"Total user messages analyzed: {len(user_messages)}\n"
        f"Messages included in prompt: {len(user_lines)}\n"
        f"Replies included in prompt: {len(reply_lines)}\n\n"
        "User messages:\n"
        f"{user_transcript}\n\n"
        "Replies from others to this user:\n"
        f"{replies_transcript}"
    )
    ai_messages = [
        {"role": "system", "content": VIBE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    return await request_ai_completion(
        ai_messages,
        max_tokens=260,
        temperature=0.35,
    )


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
    global FFMPEG_EXECUTABLE, APP_COMMANDS_SYNCED
    count = reload_bad_words()
    FFMPEG_EXECUTABLE = resolve_ffmpeg_executable()
    if BOT_ACTIVITY_TEXT:
        try:
            await bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.playing,
                    name=BOT_ACTIVITY_TEXT,
                )
            )
        except discord.HTTPException:
            pass
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Bot is online. Loaded {count} blocked words.")
    if FFMPEG_EXECUTABLE:
        print(f"FFmpeg executable: {FFMPEG_EXECUTABLE}")
    else:
        print("FFmpeg executable not found. Music playback commands will fail.")
    if SYNC_SLASH_COMMANDS and not APP_COMMANDS_SYNCED:
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} slash commands.")
        except Exception as error:
            print(f"[SLASH SYNC ERROR] {error}")
        APP_COMMANDS_SYNCED = True


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    if not isinstance(message.channel, discord.TextChannel) or message.guild is None:
        normalized_dm = " ".join(message.content.strip().lower().split())
        if message.guild is None and normalized_dm == "remove timeout":
            removed, active_found, failed = await remove_timeout_from_dm_request(message.author.id)
            if removed > 0:
                await message.channel.send(
                    f"Done. Your timeout was removed in `{removed}` server(s)."
                )
            elif active_found > 0 and failed > 0:
                await message.channel.send(
                    "I found your timeout, but I couldn't remove it due to role/permission limits."
                )
            else:
                await message.channel.send("You do not currently have an active timeout.")
            return
        await bot.process_commands(message)
        return

    if message.content.startswith(PREFIX):
        await bot.process_commands(message)
        return

    try:
        if await handle_conversational_request(message):
            return
    except Exception as error:
        print(f"[CONVERSATIONAL COMMAND ERROR] {error}")

    if not get_guild_automod_enabled(message.guild.id):
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
        f"`{PREFIX}pb` - Delete bot/webhook messages from the most recent 20 messages in this channel.\n"
        f"`{PREFIX}pba` - Delete all bot/webhook messages from this channel.\n"
        f"`{PREFIX}clear <amount>` - Delete recent messages.\n"
        f"`{PREFIX}bulkdelete <#channel> <amount>` - Bulk delete from a specific channel.\n"
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
        f"`{PREFIX}automod <on|off|toggle|status>` - Enable or disable AutoMod in this server.\n"
        f"`{PREFIX}reloadbadwords` - Reload `data/bad_words.txt`.\n"
        f"`{PREFIX}say <message>` - Moderator echo command (deletes your command message).\n"
        "\n"
        "**Utility/Fun Commands**\n"
        f"`{PREFIX}ping`\n"
        f"`{PREFIX}avatar [@member]`\n"
        f"`{PREFIX}userinfo [@member]`\n"
        f"`{PREFIX}serverinfo`\n"
        f"`{PREFIX}poll <question | option1 | option2 ...>` (2-10 options)\n"
        f"`{PREFIX}snipe` - Show last deleted non-bot message in this channel.\n"
        f"`{PREFIX}remind <minutes> <text>` - Sends you a DM reminder.\n"
        f"`{PREFIX}cat` / `{PREFIX}food` - Send random cat or Indian veg food image.\n"
        "\n"
        "**AI Commands**\n"
        f"`{PREFIX}ai <prompt>` - Ask AI with per-channel memory.\n"
        f"`{PREFIX}aireset` - Clear AI memory for this channel.\n"
        f"`{PREFIX}aimodel` - Show active AI provider/model.\n"
        f"`{PREFIX}aimodels [limit]` - List currently available models from active provider.\n"
        f"`{PREFIX}aisummary [count]` - Summarize recent channel messages.\n"
        f"`{PREFIX}roast <@user> [soft|friendly|brutal]`\n"
        f"`{PREFIX}serverlore`, `{PREFIX}aicrush <@user>`, `{PREFIX}analyze <@user>`\n"
        f"`{PREFIX}lie_detector <@user> <message>`, `{PREFIX}futureme`\n"
        f"`{PREFIX}rizzcoach [smooth|funny|mysterious] <message>`\n"
        f"`{PREFIX}argument <topic>`, `{PREFIX}debate <@user> <topic>`\n"
        "\n"
        "**Vibe Commands**\n"
        f"`{PREFIX}myvibe [count]` - Analyze your own recent messages in this channel.\n"
        f"`{PREFIX}vibe <@user> [count]` - Analyze user messages in this channel.\n"
        f"`{PREFIX}vibecheck <@user>` - Fun short vibe stats from last 200 messages.\n"
        "\n"
        "**Music Commands**\n"
        f"`{PREFIX}join` / `{PREFIX}leave`\n"
        f"`{PREFIX}play <youtube/spotify link or search>`\n"
        f"`{PREFIX}skip`, `{PREFIX}pause`, `{PREFIX}resume`, `{PREFIX}stop`\n"
        f"`{PREFIX}queue`, `{PREFIX}nowplaying`\n"
    )
    await send_chunked(ctx.channel, text)


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


@bot.command(name="automod")
@commands.guild_only()
async def automod_command(ctx: commands.Context, mode: str | None = None) -> None:
    if not isinstance(ctx.author, discord.Member) or not is_moderator(ctx.author):
        await ctx.send("Only moderators can change AutoMod settings.")
        return

    current = get_guild_automod_enabled(ctx.guild.id)
    normalized = (mode or "").strip().lower()

    if normalized in {"", "toggle"}:
        new_state = not current
    elif normalized in {"on", "enable", "enabled", "true", "1"}:
        new_state = True
    elif normalized in {"off", "disable", "disabled", "false", "0"}:
        new_state = False
    elif normalized in {"status", "state"}:
        state_text = "enabled" if current else "disabled"
        await ctx.send(f"Auto moderation is currently **{state_text}** in this server.")
        return
    else:
        await ctx.send(f"Usage: `{PREFIX}automod <on|off|toggle|status>`")
        return

    set_guild_automod_enabled(ctx.guild.id, new_state)
    state_text = "enabled" if new_state else "disabled"
    await ctx.send(f"Auto moderation is now **{state_text}** in this server.")
    await send_mod_log(
        ctx.guild,
        "Config: AutoMod Updated",
        moderator=ctx.author,
        channel=ctx.channel,
        details=f"New state: `{state_text}`",
    )


@bot.command(name="say")
@commands.guild_only()
async def say_command(ctx: commands.Context, *, text: str | None = None) -> None:
    if not isinstance(ctx.author, discord.Member) or not is_moderator(ctx.author):
        await ctx.send("Only moderators can use this command.")
        return

    message_text = (text or "").strip()
    if not message_text:
        await ctx.send(f"Usage: `{PREFIX}say <message>`")
        return

    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass

    await ctx.send(message_text)


@bot.command(name="cat", aliases=["cats"])
async def cat_command(ctx: commands.Context) -> None:
    await send_random_cat_image(ctx.channel)


@bot.command(name="food")
async def food_command(ctx: commands.Context) -> None:
    await send_random_indian_veg_food(ctx.channel)


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


@bot.command(name="join")
async def join_voice(ctx: commands.Context) -> None:
    vc = await ensure_voice_connection(ctx)
    if vc is None:
        return
    MUSIC_TEXT_CHANNELS[ctx.guild.id] = ctx.channel.id
    await ctx.send(f"Joined voice channel: {vc.channel.mention}")


@bot.command(name="leave", aliases=["dc", "disconnect"])
async def leave_voice(ctx: commands.Context) -> None:
    vc = ctx.guild.voice_client
    if vc is None:
        await ctx.send("I am not in a voice channel.")
        return
    if not in_same_voice_channel(ctx):
        await ctx.send("You must be in my voice channel to use this command.")
        return

    MUSIC_QUEUES[ctx.guild.id].clear()
    MUSIC_NOW_PLAYING.pop(ctx.guild.id, None)
    MUSIC_TEXT_CHANNELS.pop(ctx.guild.id, None)
    await vc.disconnect(force=True)
    await ctx.send("Disconnected and cleared music queue.")


@bot.command(name="play", aliases=["p"])
async def play_music(ctx: commands.Context, *, source: str) -> None:
    global FFMPEG_EXECUTABLE
    vc = await ensure_voice_connection(ctx)
    if vc is None:
        return
    if yt_dlp is None:
        await ctx.send("Music features require `yt-dlp`. Install dependencies first.")
        return
    if not FFMPEG_EXECUTABLE:
        FFMPEG_EXECUTABLE = resolve_ffmpeg_executable()
    if not FFMPEG_EXECUTABLE:
        await ctx.send(
            "ffmpeg was not found. Install ffmpeg on host, or install `imageio-ffmpeg` in requirements and restart."
        )
        return

    source = source.strip()
    if not source:
        await ctx.send(f"Usage: `{PREFIX}play <youtube/spotify link or search>`")
        return

    MUSIC_TEXT_CHANNELS[ctx.guild.id] = ctx.channel.id

    async with ctx.typing():
        try:
            tracks, label = await source_to_tracks(source, ctx.author.id)
        except Exception as error:
            await ctx.send(f"Could not queue track(s): `{error}`")
            return

    queue = MUSIC_QUEUES[ctx.guild.id]
    queue.extend(tracks)

    if len(tracks) == 1:
        await ctx.send(f"Queued: **{tracks[0].title}**")
    else:
        extra = f" from **{label}**" if label else ""
        await ctx.send(f"Queued `{len(tracks)}` tracks{extra}.")

    if not vc.is_playing() and not vc.is_paused():
        await play_next_track(ctx.guild)


@bot.command(name="skip")
async def skip_music(ctx: commands.Context) -> None:
    vc = ctx.guild.voice_client
    if vc is None or not vc.is_connected():
        await ctx.send("I am not in a voice channel.")
        return
    if not in_same_voice_channel(ctx):
        await ctx.send("You must be in my voice channel to use this command.")
        return
    if not vc.is_playing() and not vc.is_paused():
        await ctx.send("Nothing is currently playing.")
        return
    vc.stop()
    await ctx.send("Skipped current track.")


@bot.command(name="pause")
async def pause_music(ctx: commands.Context) -> None:
    vc = ctx.guild.voice_client
    if vc is None or not vc.is_playing():
        await ctx.send("Nothing is currently playing.")
        return
    if not in_same_voice_channel(ctx):
        await ctx.send("You must be in my voice channel to use this command.")
        return
    vc.pause()
    await ctx.send("Paused playback.")


@bot.command(name="resume")
async def resume_music(ctx: commands.Context) -> None:
    vc = ctx.guild.voice_client
    if vc is None or not vc.is_paused():
        await ctx.send("Playback is not paused.")
        return
    if not in_same_voice_channel(ctx):
        await ctx.send("You must be in my voice channel to use this command.")
        return
    vc.resume()
    await ctx.send("Resumed playback.")


@bot.command(name="stop")
async def stop_music(ctx: commands.Context) -> None:
    vc = ctx.guild.voice_client
    if vc is None or not vc.is_connected():
        await ctx.send("I am not in a voice channel.")
        return
    if not in_same_voice_channel(ctx):
        await ctx.send("You must be in my voice channel to use this command.")
        return
    MUSIC_QUEUES[ctx.guild.id].clear()
    MUSIC_NOW_PLAYING.pop(ctx.guild.id, None)
    if vc.is_playing() or vc.is_paused():
        vc.stop()
    await ctx.send("Stopped playback and cleared queue.")


@bot.command(name="queue", aliases=["q"])
async def queue_music(ctx: commands.Context) -> None:
    now_playing = MUSIC_NOW_PLAYING.get(ctx.guild.id)
    queue = MUSIC_QUEUES.get(ctx.guild.id, deque())
    if not now_playing and not queue:
        await ctx.send("Queue is empty.")
        return

    lines: list[str] = []
    if now_playing:
        lines.append(f"Now: **{now_playing.title}**")
    if queue:
        for i, track in enumerate(list(queue)[:10], start=1):
            lines.append(f"{i}. {track.title}")
        if len(queue) > 10:
            lines.append(f"...and {len(queue) - 10} more.")
    await ctx.send("\n".join(lines))


@bot.command(name="nowplaying", aliases=["np"])
async def now_playing_music(ctx: commands.Context) -> None:
    current = MUSIC_NOW_PLAYING.get(ctx.guild.id)
    if current is None:
        await ctx.send("Nothing is currently playing.")
        return
    await ctx.send(f"Now playing: **{current.title}**\n{current.webpage_url}")


@bot.command(name="aimodel")
async def aimodel_command(ctx: commands.Context) -> None:
    provider = "Groq" if AI_PROVIDER == "groq" else "OpenRouter"
    model_text = current_ai_model() or "(not set)"
    fallbacks = current_ai_fallback_models()
    fallback_text = ", ".join(fallbacks) if fallbacks else "(none)"
    await ctx.send(
        f"Provider: `{provider}`\n"
        f"Configured model: `{model_text}`\n"
        f"Fallbacks: `{fallback_text}`"
    )


@bot.command(name="aimodels")
async def aimodels_command(ctx: commands.Context, limit: int = 15) -> None:
    if limit < 1 or limit > 40:
        await ctx.send("`limit` must be between `1` and `40`.")
        return
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            if AI_PROVIDER == "groq":
                available = await fetch_groq_models(session)
            else:
                available = await fetch_openrouter_models(session)
        except Exception as error:
            await ctx.send(f"Failed to fetch models: `{error}`")
            return

    listed = sorted(available)
    if AI_PROVIDER == "openrouter":
        listed = [model for model in listed if model.endswith(":free")]
        if not listed:
            await ctx.send("No `:free` OpenRouter models found right now.")
            return

    if not listed:
        await ctx.send("No models found right now.")
        return

    shown = listed[:limit]
    provider_label = "Groq" if AI_PROVIDER == "groq" else "OpenRouter free"
    text = f"Available {provider_label} models:\n" + "\n".join(f"- `{model}`" for model in shown)
    if len(listed) > limit:
        text += f"\n...and `{len(listed) - limit}` more."
    await send_chunked(ctx.channel, text)


@bot.command(name="aireset")
async def aireset_command(ctx: commands.Context) -> None:
    AI_CHAT_CACHE.pop(ctx.channel.id, None)
    await ctx.send("AI memory has been cleared for this channel.", delete_after=6)


@bot.command(name="myvibe")
@commands.cooldown(2, 60, commands.BucketType.user)
@commands.guild_only()
async def my_vibe_command(ctx: commands.Context, count: int = VIBE_DEFAULT_MESSAGE_COUNT) -> None:
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return
    if count < VIBE_MIN_REQUIRED_MESSAGES or count > VIBE_MAX_MESSAGE_COUNT:
        await ctx.send(
            f"`count` must be between `{VIBE_MIN_REQUIRED_MESSAGES}` and `{VIBE_MAX_MESSAGE_COUNT}`."
        )
        return

    async with ctx.typing():
        user_messages, replies_received = await collect_vibe_context(ctx.channel, ctx.author.id, count)
        if len(user_messages) < VIBE_MIN_REQUIRED_MESSAGES:
            await ctx.send(
                f"Need at least `{VIBE_MIN_REQUIRED_MESSAGES}` of your recent messages in this channel."
            )
            return
        try:
            report = await generate_vibe_report(ctx.author, user_messages, replies_received)
        except Exception as error:
            print(f"[VIBE ERROR] {error}")
            report = generate_vibe_report_local(ctx.author, user_messages, replies_received)
            report = (
                f"{report}\n\n"
                "_AI model timed out, so this report is from local heuristics._"
            )

    await send_chunked(
        ctx.channel,
        (
            f"**Vibe Report for {ctx.author.display_name}**\n"
            f"(Fun feature, may be inaccurate. Based on `{len(user_messages)}` user messages "
            f"and `{len(replies_received)}` replies in this channel.)\n\n"
            f"{report}"
        ),
    )


@bot.command(name="vibe")
@commands.cooldown(2, 60, commands.BucketType.user)
@commands.guild_only()
async def vibe_command(
    ctx: commands.Context, member: discord.Member, count: int = VIBE_DEFAULT_MESSAGE_COUNT
) -> None:
    if member.bot:
        await ctx.send("Bot accounts are not supported for vibe reports.")
        return
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return
    if count < VIBE_MIN_REQUIRED_MESSAGES or count > VIBE_MAX_MESSAGE_COUNT:
        await ctx.send(
            f"`count` must be between `{VIBE_MIN_REQUIRED_MESSAGES}` and `{VIBE_MAX_MESSAGE_COUNT}`."
        )
        return

    async with ctx.typing():
        user_messages, replies_received = await collect_vibe_context(ctx.channel, member.id, count)
        if len(user_messages) < VIBE_MIN_REQUIRED_MESSAGES:
            await ctx.send(
                f"Need at least `{VIBE_MIN_REQUIRED_MESSAGES}` recent messages from {member.mention} "
                "in this channel."
            )
            return
        try:
            report = await generate_vibe_report(member, user_messages, replies_received)
        except Exception as error:
            print(f"[VIBE ERROR] {error}")
            report = generate_vibe_report_local(member, user_messages, replies_received)
            report = (
                f"{report}\n\n"
                "_AI model timed out, so this report is from local heuristics._"
            )

    await send_chunked(
        ctx.channel,
        (
            f"**Vibe Report for {member.display_name}**\n"
            f"(Fun feature, may be inaccurate. Based on `{len(user_messages)}` user messages "
            f"and `{len(replies_received)}` replies in this channel.)\n\n"
            f"{report}"
        ),
    )


@bot.command(name="vibecheck")
@commands.cooldown(2, 60, commands.BucketType.user)
@commands.guild_only()
async def vibecheck_command(ctx: commands.Context, member: discord.Member) -> None:
    if member.bot:
        await ctx.send("Bot accounts are not supported for vibe checks.")
        return
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return

    target_count = 200
    async with ctx.typing():
        user_messages, replies_received = await collect_vibe_context(ctx.channel, member.id, target_count)
        if len(user_messages) < VIBE_MIN_REQUIRED_MESSAGES:
            await ctx.send(
                f"Need at least `{VIBE_MIN_REQUIRED_MESSAGES}` recent messages from {member.mention} "
                "in this channel."
            )
            return

        try:
            report = await generate_vibecheck_report(member, user_messages, replies_received)
        except Exception as error:
            print(f"[VIBECHECK ERROR] {error}")
            report = generate_vibecheck_local(user_messages, replies_received)
            report = normalize_vibecheck_output(report)

    await send_chunked(ctx.channel, report)


@bot.hybrid_command(name="roast")
@commands.cooldown(2, 45, commands.BucketType.user)
@commands.guild_only()
async def roast_command(
    ctx: commands.Context,
    member: discord.Member,
    style: Literal["soft", "friendly", "brutal"] = "friendly",
) -> None:
    if member.bot:
        await ctx.send("I do not roast bot accounts.")
        return
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return

    async with ctx.typing():
        user_messages, replies_received = await collect_vibe_context(ctx.channel, member.id, 140)
        if not user_messages:
            await ctx.send(f"I need some recent messages from {member.mention} in this channel first.")
            return
        prompt = (
            f"Create a {style} playful roast for this Discord user.\n"
            "Use only playful humor. No slurs, no hate speech, no protected-trait insults, no real harm.\n"
            "Output 4-8 short lines, punchy and readable.\n\n"
            f"Username: {member.name}\n"
            f"Display name: {member.display_name}\n"
            f"Avatar URL: {member.display_avatar.url}\n"
            f"Recent messages sample:\n" + "\n".join(f"- {m}" for m in user_messages[-20:]) + "\n\n"
            f"How others replied sample:\n" + "\n".join(f"- {m}" for m in replies_received[-12:])
        )
        try:
            roast = await request_fun_ai(prompt, max_tokens=220, temperature=0.9)
        except Exception as error:
            print(f"[ROAST ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return

    await send_chunked(
        ctx.channel,
        f"🔥 Roast mode: **{style}** for {member.mention}\n{roast}\n\n⚠️ For fun only.",
    )


@bot.hybrid_command(name="serverlore")
@commands.cooldown(2, 60, commands.BucketType.user)
@commands.guild_only()
async def serverlore_command(ctx: commands.Context) -> None:
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return

    async with ctx.typing():
        transcript = await collect_recent_channel_transcript(ctx.channel, 140)
        if len(transcript) < 12:
            await ctx.send("Need more recent chat context in this channel for server lore.")
            return
        prompt = (
            "Write a dramatic fake mythology story for this Discord server.\n"
            "Include title, a rise/fall arc, and 3 mythic events. Make it addictive and funny.\n"
            "Keep it under 260 words.\n\n"
            f"Server: {ctx.guild.name}\n"
            "Recent chat context:\n"
            + "\n".join(transcript[-90:])
        )
        try:
            lore = await request_fun_ai(prompt, max_tokens=320, temperature=0.95)
        except Exception as error:
            print(f"[SERVERLORE ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return
    await send_chunked(ctx.channel, f"📜 **Server Lore**\n{lore}\n\n⚠️ For fun only.")


@bot.hybrid_command(name="aicrush")
@commands.cooldown(2, 60, commands.BucketType.user)
@commands.guild_only()
async def aicrush_command(ctx: commands.Context, member: discord.Member) -> None:
    if member.bot:
        await ctx.send("This command is for server members only.")
        return
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return

    async with ctx.typing():
        user_messages, replies_received = await collect_vibe_context(ctx.channel, member.id, 120)
        if len(user_messages) < 15:
            await ctx.send(f"Need more recent messages from {member.mention} in this channel.")
            return
        prompt = (
            "Create a playful 'AI Crush Prediction' for a Discord user.\n"
            "No real accusations, no doxxing, no sexual content. Keep it funny and safe.\n"
            "Output exactly:\n"
            "AI Crush Guess: <name-like hint or archetype>\n"
            "Love Compatibility: <0-100>%\n"
            "Drama Rating: <0-10>/10\n"
            "Reason: <1 short paragraph>\n\n"
            f"Target user: {member.display_name}\n"
            "Recent user messages:\n"
            + "\n".join(f"- {m}" for m in user_messages[-22:])
            + "\n\nRecent replies:\n"
            + "\n".join(f"- {m}" for m in replies_received[-16:])
        )
        try:
            result = await request_fun_ai(prompt, max_tokens=220, temperature=0.9)
        except Exception as error:
            print(f"[AICRUSH ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return
    await send_chunked(ctx.channel, f"💘 **AI Crush for {member.display_name}**\n{result}\n\n⚠️ For fun only.")


@bot.hybrid_command(name="analyze")
@commands.cooldown(2, 60, commands.BucketType.user)
@commands.guild_only()
async def analyze_command(ctx: commands.Context, member: discord.Member) -> None:
    if member.bot:
        await ctx.send("Bot accounts are not supported for analysis.")
        return
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return

    async with ctx.typing():
        user_messages = await collect_recent_user_messages(ctx.channel, member.id, 200)
        if len(user_messages) < 20:
            await ctx.send(f"Need more recent messages from {member.mention} in this channel.")
            return
        stats = user_style_stats(user_messages)
        prompt = (
            "Analyze this Discord user's communication style in a fun, non-clinical way.\n"
            "No medical or mental-health diagnosis.\n"
            "Return exactly:\n"
            "Communication style: ...\n"
            "Confidence level: ...\n"
            "Hidden trait: ...\n"
            "Emoji frequency: ...\n"
            "Word-usage signature: ...\n\n"
            f"User: {member.display_name}\n"
            f"Average message length: {stats['avg_len']}\n"
            f"Question ratio: {stats['question_ratio']}\n"
            f"Exclaim ratio: {stats['exclaim_ratio']}\n"
            f"Emoji per message: {stats['emoji_per_msg']}\n"
            f"Top words: {stats['top_words']}\n"
            "Recent message sample:\n"
            + "\n".join(f"- {m}" for m in user_messages[-30:])
        )
        try:
            result = await request_fun_ai(prompt, max_tokens=230, temperature=0.55)
        except Exception as error:
            print(f"[ANALYZE ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return
    await send_chunked(ctx.channel, f"🧠 **Analysis for {member.display_name}**\n{result}\n\n⚠️ For fun only.")


@bot.hybrid_command(name="lie_detector")
@commands.cooldown(3, 45, commands.BucketType.user)
@commands.guild_only()
async def lie_detector_command(
    ctx: commands.Context, member: discord.Member, *, statement: str
) -> None:
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return
    statement = statement.strip()
    if len(statement) < 5:
        await ctx.send(f"Usage: `{PREFIX}lie_detector @user <message>`")
        return

    async with ctx.typing():
        prompt = (
            "Act as a playful lie detector for Discord.\n"
            "No factual certainty claims; this is entertainment only.\n"
            "Return exactly:\n"
            "Truth probability: <0-100>%\n"
            "Suspicious phrases detected: <comma-separated>\n"
            "Read: <one-line playful verdict>\n\n"
            f"User: {member.display_name}\n"
            f"Statement: {statement[:350]}"
        )
        try:
            result = await request_fun_ai(prompt, max_tokens=160, temperature=0.6)
        except Exception as error:
            print(f"[LIE_DETECTOR ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return
    await send_chunked(ctx.channel, f"🕵️ **Lie Detector for {member.display_name}**\n{result}\n\n⚠️ For fun only.")


@bot.hybrid_command(name="futureme")
@commands.cooldown(2, 60, commands.BucketType.user)
@commands.guild_only()
async def futureme_command(ctx: commands.Context) -> None:
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return

    async with ctx.typing():
        user_messages = await collect_recent_user_messages(ctx.channel, ctx.author.id, 120)
        prompt = (
            "Predict a playful 5-year future snapshot for this user.\n"
            "Must include these headings:\n"
            "Career path:\n"
            "Drama level:\n"
            "Wealth potential:\n"
            "Main plot twist:\n"
            "Keep it witty and under 170 words.\n\n"
            f"User: {ctx.author.display_name}\n"
            "Recent message sample:\n"
            + "\n".join(f"- {m}" for m in user_messages[-24:])
        )
        try:
            result = await request_fun_ai(prompt, max_tokens=220, temperature=0.85)
        except Exception as error:
            print(f"[FUTUREME ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return
    await send_chunked(ctx.channel, f"🔮 **FutureMe for {ctx.author.display_name}**\n{result}\n\n⚠️ For fun only.")


@bot.hybrid_command(name="rizzcoach")
@commands.cooldown(3, 45, commands.BucketType.user)
@commands.guild_only()
async def rizzcoach_command(
    ctx: commands.Context,
    style: str = "smooth",
    *,
    draft: str | None = None,
) -> None:
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return

    normalized_style = style.strip().lower()
    if draft is None:
        draft_text = style
        normalized_style = "smooth"
    elif normalized_style in {"smooth", "funny", "mysterious"}:
        draft_text = draft
    else:
        draft_text = f"{style} {draft}".strip()
        normalized_style = "smooth"

    draft_text = draft_text.strip()
    if len(draft_text) < 4:
        await ctx.send(f"Usage: `{PREFIX}rizzcoach [smooth|funny|mysterious] <message>`")
        return

    async with ctx.typing():
        prompt = (
            "You are a rizz coach for Discord.\n"
            "Rewrite the user's draft into 3 alternatives:\n"
            "1) smooth\n"
            "2) funny\n"
            "3) mysterious\n"
            "Then recommend one best option based on requested style.\n"
            "Keep it clean and non-explicit.\n\n"
            f"Requested style: {normalized_style}\n"
            f"Original draft: {draft_text[:350]}"
        )
        try:
            result = await request_fun_ai(prompt, max_tokens=260, temperature=0.85)
        except Exception as error:
            print(f"[RIZZCOACH ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return
    await send_chunked(ctx.channel, f"💬 **RizzCoach ({normalized_style})**\n{result}")


@bot.hybrid_command(name="argument")
@commands.cooldown(3, 45, commands.BucketType.user)
@commands.guild_only()
async def argument_command(ctx: commands.Context, *, topic: str) -> None:
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return
    topic = topic.strip()
    if len(topic) < 3:
        await ctx.send(f"Usage: `{PREFIX}argument <topic>`")
        return

    side = random.choice(["PRO", "ANTI"])
    async with ctx.typing():
        prompt = (
            "Argue aggressively but playfully for a Discord debate topic.\n"
            "No hate speech or threats.\n"
            "Output: a short opening statement + 4 bullet arguments + one savage closer.\n\n"
            f"Topic: {topic}\n"
            f"Side: {side}"
        )
        try:
            result = await request_fun_ai(prompt, max_tokens=260, temperature=0.85)
        except Exception as error:
            print(f"[ARGUMENT ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return
    await send_chunked(ctx.channel, f"⚔️ **Argument Mode** ({side}) on **{topic}**\n{result}")


@bot.hybrid_command(name="debate")
@commands.cooldown(2, 75, commands.BucketType.user)
@commands.guild_only()
async def debate_command(ctx: commands.Context, member: discord.Member, *, topic: str) -> None:
    if member.bot or member.id == ctx.author.id:
        await ctx.send("Pick another non-bot member for debate.")
        return
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
        return
    topic = topic.strip()
    if len(topic) < 3:
        await ctx.send(f"Usage: `{PREFIX}debate @user <topic>`")
        return

    async with ctx.typing():
        author_msgs = await collect_recent_user_messages(ctx.channel, ctx.author.id, 50)
        member_msgs = await collect_recent_user_messages(ctx.channel, member.id, 50)
        prompt = (
            "Moderate a playful debate between two users and declare a winner.\n"
            "No hate speech. Keep it entertaining.\n"
            "Output format:\n"
            "Round 1:\n"
            "Round 2:\n"
            "Round 3:\n"
            "Scoreboard: <user A score> - <user B score>\n"
            "Winner: ...\n"
            "Why: ...\n\n"
            f"Topic: {topic}\n"
            f"User A: {ctx.author.display_name}\n"
            f"User B: {member.display_name}\n"
            f"User A style sample:\n" + "\n".join(f"- {m}" for m in author_msgs[-14:]) + "\n\n"
            f"User B style sample:\n" + "\n".join(f"- {m}" for m in member_msgs[-14:])
        )
        try:
            result = await request_fun_ai(prompt, max_tokens=320, temperature=0.88)
        except Exception as error:
            print(f"[DEBATE ERROR] {error}")
            await ctx.send(friendly_ai_error(error))
            return
    await send_chunked(
        ctx.channel,
        f"🏛️ **Debate Arena**: {ctx.author.mention} vs {member.mention}\nTopic: **{topic}**\n\n{result}",
    )


@bot.command(name="ai", aliases=["ask"])
@commands.cooldown(3, 30, commands.BucketType.user)
async def ai_command(ctx: commands.Context, *, prompt: str | None = None) -> None:
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
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
            reply = await request_ai_completion(
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
    if not is_ai_configured():
        await ctx.send(ai_setup_message())
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
            summary = await request_ai_completion(
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
async def purge_bot_messages(ctx: commands.Context) -> None:
    deleted = await purge_recent_bot_webhook_messages(ctx.channel, trigger_message=ctx.message)

    await ctx.send(f"`{deleted}` messages have been deleted.", delete_after=3)
    await send_mod_log(
        ctx.guild,
        "Purge Bot Messages",
        moderator=ctx.author,
        channel=ctx.channel,
        details=f"Deleted: `{deleted}`",
    )


@bot.command(name="pba")
@commands.has_permissions(manage_messages=True)
async def purge_bot_messages_all(ctx: commands.Context) -> None:
    deleted_messages = await ctx.channel.purge(
        limit=None,
        check=lambda m: m.author.bot or m.webhook_id is not None,
        bulk=False,
    )
    deleted = len(deleted_messages)

    await ctx.send(f"`{deleted}` messages have been deleted.", delete_after=3)
    await send_mod_log(
        ctx.guild,
        "Purge Bot Messages (All)",
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


@bot.command(name="bulkdelete", aliases=["bd"])
@commands.has_permissions(manage_messages=True)
async def bulk_delete_messages(
    ctx: commands.Context, channel: discord.TextChannel, amount: int
) -> None:
    if amount < 1 or amount > 1000:
        await ctx.send("Amount must be between `1` and `1000`.")
        return

    if not channel.permissions_for(ctx.author).manage_messages:
        await ctx.send("You do not have permission to manage messages in that channel.")
        return

    me = ctx.guild.me
    if me is None:
        await ctx.send("Could not verify bot permissions in that channel.")
        return
    bot_perms = channel.permissions_for(me)
    if not bot_perms.manage_messages or not bot_perms.read_message_history:
        await ctx.send("I need `Manage Messages` and `Read Message History` in that channel.")
        return

    deleted = await channel.purge(limit=amount)
    total_deleted = len(deleted)

    await ctx.send(
        f"Deleted `{total_deleted}` messages in {channel.mention}.",
        delete_after=6,
    )
    await send_mod_log(
        ctx.guild,
        "Bulk Delete Messages",
        moderator=ctx.author,
        channel=channel,
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
    original_error = getattr(error, "original", error)
    original_text = str(original_error)

    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Command cooldown active. Try again in `{error.retry_after:.1f}`s.")
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You do not have permission to use this command.")
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command can only be used inside a server channel.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`. Use `{PREFIX}help`.")
        return
    if isinstance(error, (commands.BadArgument, commands.MemberNotFound, commands.UserNotFound)):
        await ctx.send("Invalid argument. Use the correct mention/id format.")
        return
    if "pynacl library needed in order to use voice" in original_text.lower():
        await ctx.send(
            "Voice dependency missing on host. Install `PyNaCl` and restart the bot."
        )
        return
    lowered = original_text.lower()
    if "websocket closed with 4006" in lowered or "voice handshake" in lowered:
        await ctx.send(
            "Voice connection failed (`4006`). This is usually a host UDP/network issue, not your command."
        )
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
