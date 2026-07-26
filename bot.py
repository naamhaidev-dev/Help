import asyncio
import json
import os
import logging
import re

from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
import aiohttp
import phonenumbers
from phonenumbers import geocoder, carrier

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()
DATA_FILE = "data_store.json"
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def load_data() -> Dict[str, Any]:
    if not os.path.isfile(DATA_FILE):
        return {"approved_users": [], "known_chats": []}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {"approved_users": [], "known_chats": []}


def save_data(data: Dict[str, Any]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def get_admin_ids() -> List[int]:
    raw = os.getenv("TELEGRAM_ADMIN_IDS", "")
    return [int(item.strip()) for item in raw.split(",") if item.strip().isdigit()]


def is_admin(user_id: Optional[int], admin_ids: List[int]) -> bool:
    return user_id is not None and user_id in admin_ids


from datetime import datetime

def record_search(command_name: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.bot_data.get("data")
    if data is None:
        return

    if "searches" not in data:
        data["searches"] = {}

    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    # Initialize today
    if today_str not in data["searches"]:
        data["searches"][today_str] = {"total": 0, "commands": {}}

    # Initialize total
    if "total" not in data["searches"]:
        data["searches"]["total"] = {"total": 0, "commands": {}}

    # Increment today
    data["searches"][today_str]["total"] += 1
    data["searches"][today_str]["commands"][command_name] = data["searches"][today_str]["commands"].get(command_name, 0) + 1

    # Increment total
    data["searches"]["total"]["total"] += 1
    data["searches"]["total"]["commands"][command_name] = data["searches"]["total"]["commands"].get(command_name, 0) + 1

    save_data(data)


PREMIUM_EMOJIS = {
    "💎": "5427168083074628963",
    "🥇": "5440539497383087970",
    "⌛": "5386367538735104399",
    "⚙️": "5341715473882955310",
    "⚙": "5341715473882955310",
    "⛔️": "5260293700088511294",
    "⛔": "5260293700088511294",
    "▶️": "5264919878082509254",
    "▶": "5264919878082509254",
    "☠️": "5251591568065845575",
    "☠": "5251591568065845575",
    "💀": "5251591568065845575",
    "📌": "6136663351427603393",
    "🤫": "6138532229137049159",
    "🗿": "5208878706717636743",
    "🎁": "6075873960573017149",
    "🍭": "6075445090908644952",
    "😉": "6136237758823273814",
    "🦇": "6138798143447244059",
    "🎵": "6089165857856952184",
    "🌐": "5395558210402807000",
    "⏳": "5316977222467206948",
    "👤": "5987557724886405444",
    "👨": "5350519289256355751",
    "📱": "5357421984600833714",
    "🪪": "5260561650213220533",
    "🔒": "5296369303661067030",
    "📍": "5391032818111363540",
    "🚀": "5866355487255039002",
    "✉️": "4929214028657460019",
    "✉": "4929214028657460019",
    "🌟": "5330519486279740988",
    "🔗": "5271604874419647061",
    "⚡": "5875091588174059190",
    "✅": "6107134841382246388",
    "🔴": "6104873438021686768",
    "👥": "5987557724886405444",
}

def get_emoji(emo: str) -> str:
    """Returns custom premium HTML tag if present in PREMIUM_EMOJIS, else returns the emoji char."""
    emoji_id = PREMIUM_EMOJIS.get(emo)
    if emoji_id:
        return f'<tg-emoji emoji-id="{emoji_id}">{emo}</tg-emoji>'
    return emo


def record_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if not chat:
        return

    data = context.bot_data.get("data")
    if data is None:
        return

    existing = next((item for item in data["known_chats"] if item["id"] == chat.id), None)
    chat_info = {
        "id": chat.id,
        "type": chat.type,
        "title": chat.title or "",
        "username": chat.username or "",
    }

    if existing is None:
        data["known_chats"].append(chat_info)
        save_data(data)
        return

    if existing != chat_info:
        existing.update(chat_info)
        save_data(data)


async def is_private_approved(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    data = context.bot_data.get("data", {})
    admin_ids = context.bot_data.get("admin_ids", [])

    if not user:
        return False

    if is_admin(user.id, admin_ids):
        return True

    if update.effective_chat and update.effective_chat.type == "private":
        approved = user.id in data.get("approved_users", [])
        if not approved and update.message:
            ch3_val = context.bot_data.get("required_ch3", "@AnnebellaOfficialchat")
            ch3_title, ch3_link = await get_chat_details(ch3_val, "Annebella Official Chat", "https://t.me/AnnebellaOfficialchat", context)

            text = (
                f"{get_emoji('⛔️')} <b>Private Usage Restricted!</b>\n\n"
                f"Your account is not approved for private messaging lookup.\n"
                f"👉 Ask an administrator to approve your ID: <code>{user.id}</code> using: <code>/approve {user.id}</code>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{get_emoji('👥')} <b>Alternative: Use in Official Group</b>\n"
                f"You can use all premium OSINT lookup commands for free inside our official group:\n"
                f"• <a href='{ch3_link}'>Join {ch3_title}</a>\n\n"
                f"{get_emoji('🦇')} <b>Annebella OSINT BOT System</b>"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton(text="💬 Join Official Group", url=ch3_link)
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        return approved

    return True


async def check_group_size(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    if not chat or chat.type not in {"group", "supergroup"}:
        return True

    try:
        count = await context.bot.get_chat_member_count(chat.id)
    except Exception as exc:
        logger.warning("Failed to check group size: %s", exc)
        return True

    if count < 25:
        if update.message:
            await update.message.reply_text(
                f"{get_emoji('⛔️')} <b>Group size too small!</b>\n\n"
                f"This bot requires a group with at least 25 members to work.\n"
                f"Current group size: <code>{count}</code>.",
                parse_mode="HTML"
            )
        return False

    return True


def get_join_link(chat_identifier: str) -> str:
    if not chat_identifier:
        return ""
    if chat_identifier.startswith("https://") or chat_identifier.startswith("http://"):
        return chat_identifier
    return f"https://t.me/{chat_identifier.lstrip('@')}"


async def resolve_chat_id(chat_identifier: str, context: ContextTypes.DEFAULT_TYPE, cache_key: str) -> str:
    cached = context.bot_data.get(cache_key)
    if cached:
        return cached

    if isinstance(chat_identifier, str):
        if chat_identifier.strip("-").isdigit():
            return chat_identifier
        try:
            chat = await context.bot.get_chat(chat_identifier)
            context.bot_data[cache_key] = str(chat.id)
            return str(chat.id)
        except Exception as exc:
            logger.warning("Failed to resolve chat %s: %s", chat_identifier, exc)
            return chat_identifier

    return chat_identifier





async def resolve_required_ch2_id(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    ch = context.bot_data.get("required_ch2")
    if not ch:
        return None
    return await resolve_chat_id(ch, context, "required_ch2_id")


async def resolve_required_ch3_id(context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
    ch = context.bot_data.get("required_ch3")
    if not ch:
        return None
    return await resolve_chat_id(ch, context, "required_ch3_id")


async def get_chat_details(chat_val: str, default_title: str, default_link: str, context: ContextTypes.DEFAULT_TYPE) -> tuple[str, str]:
    if not chat_val:
        return default_title, default_link
    title = default_title
    link = get_join_link(chat_val)
    try:
        chat_obj = await context.bot.get_chat(chat_val)
        if chat_obj.title:
            title = chat_obj.title
        if chat_obj.invite_link:
            link = chat_obj.invite_link
    except Exception:
        pass
    return title, link


async def notify_unapproved_access(update: Update, context: ContextTypes.DEFAULT_TYPE, reason: str) -> None:
    user = update.effective_user
    if user:
        logger.info("Unapproved access attempt by user %s (ID: %s) - Reason: %s", user.first_name, user.id, reason)


async def verify_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_private_approved(update, context):
        return False

    if not await check_group_size(update, context):
        return False

    user = update.effective_user
    if not user:
        return False

    admin_ids = context.bot_data.get("admin_ids", [])
    if is_admin(user.id, admin_ids):
        return True

    ch2 = await resolve_required_ch2_id(context)
    ch3 = await resolve_required_ch3_id(context)

    in_ch2 = True
    if ch2:
        try:
            member = await context.bot.get_chat_member(ch2, user.id)
            if member.status not in {"creator", "administrator", "member", "restricted"}:
                in_ch2 = False
        except Exception as exc:
            logger.warning("Failed to verify ch2 membership: %s", exc)
            in_ch2 = False

    in_ch3 = True
    if ch3:
        try:
            member = await context.bot.get_chat_member(ch3, user.id)
            if member.status not in {"creator", "administrator", "member", "restricted"}:
                in_ch3 = False
        except Exception as exc:
            logger.warning("Failed to verify ch3 membership: %s", exc)
            in_ch3 = False

    if in_ch2 and in_ch3:
        return True

    if update.message:
        ch2_val = context.bot_data.get("required_ch2")
        ch3_val = context.bot_data.get("required_ch3")

        ch2_title, ch2_link = await get_chat_details(ch2_val, "India Gates", "https://t.me/indiagates", context)
        ch3_title, ch3_link = await get_chat_details(ch3_val, "Annebella Official Chat", "https://t.me/AnnebellaOfficialchat", context)

        reasons = []
        if not in_ch2:
            reasons.append(f"Not Joined Channel 1 (<a href='{ch2_link}'>{ch2_title}</a>)")
        if not in_ch3:
            reasons.append(f"Not Joined Channel 2 (<a href='{ch3_link}'>{ch3_title}</a>)")
            
        reason = ", ".join(reasons)
        
        asyncio.create_task(notify_unapproved_access(update, context, reason))

        alert_text = (
            f"{get_emoji('⛔️')} <b>Access Denied!</b>\n\n"
            f"You must join our two official chats to unlock all premium features:\n"
            f"1. <a href='{ch2_link}'>Join {ch2_title}</a>\n"
            f"2. <a href='{ch3_link}'>Join {ch3_title}</a>\n\n"
            f"Once you have joined both, try typing /start again!"
        )

        keyboard = [
            [
                InlineKeyboardButton(text="📢 Channel 1", url=ch2_link),
                InlineKeyboardButton(text="📢 Channel 2", url=ch3_link),
            ],
            [
                InlineKeyboardButton(
                    text="🤖 Start Bot in Private",
                    url=f"https://t.me/{context.bot.username}?start=true",
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            alert_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
            disable_web_page_preview=True
        )
    return False


async def is_fully_verified(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat:
        return False

    admin_ids = context.bot_data.get("admin_ids", [])
    data = context.bot_data.get("data", {})

    if is_admin(user.id, admin_ids):
        return True

    # 1. Check private approval if chat is private
    if chat.type == "private":
        approved = user.id in data.get("approved_users", [])
        if not approved:
            return False

    # 2. Check group size if chat is group
    if chat.type in {"group", "supergroup"}:
        try:
            count = await context.bot.get_chat_member_count(chat.id)
            if count < 25:
                return False
        except Exception:
            pass

    # 3. Check ch2 join status
    ch2 = await resolve_required_ch2_id(context)
    if ch2:
        try:
            member = await context.bot.get_chat_member(ch2, user.id)
            if member.status not in {"creator", "administrator", "member", "restricted"}:
                return False
        except Exception:
            return False

    # 4. Check ch3 join status
    ch3 = await resolve_required_ch3_id(context)
    if ch3:
        try:
            member = await context.bot.get_chat_member(ch3, user.id)
            if member.status not in {"creator", "administrator", "member", "restricted"}:
                return False
        except Exception:
            return False

    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not update.message:
        return
    record_search("/start", context)

    is_verified = await is_fully_verified(update, context)

    ch2_val = context.bot_data.get("required_ch2")
    ch3_val = context.bot_data.get("required_ch3")

    ch2_title, ch2_link = await get_chat_details(ch2_val, "India Gates", "https://t.me/indiagates", context)
    ch3_title, ch3_link = await get_chat_details(ch3_val, "Annebella Official Chat", "https://t.me/AnnebellaOfficialchat", context)

    if is_verified:
        text = (
            f"{get_emoji('🦇')} <b>Annebella OSINT BOT</b> {get_emoji('🌟')}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{get_emoji('🥇')} <b>Status: VERIFIED & ACTIVE</b>\n\n"
            "You now have full access to all OSINT features!\n\n"
            f"{get_emoji('📌')} <b>Quick Commands:</b>\n"
            f"{get_emoji('✅')} /num <code>[phone_number]</code> - Search details of a phone number\n"
            f"{get_emoji('✅')} /tg <code>[@username]</code> - Search Telegram username to number\n"
            f"{get_emoji('✅')} /ff <code>[Free_Fire_UID]</code> - Search Free Fire UID details\n"
            f"{get_emoji('✅')} /vnum <code>[Vehicle_Number]</code> - Search Vehicle & Owner details\n"
            f"{get_emoji('✅')} /ifsc <code>[IFSC_Code]</code> - Search Bank details from IFSC\n"
            f"{get_emoji('✅')} /status - View your account access status\n"
            f"{get_emoji('✅')} /help - View all available commands\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{get_emoji('▶️')} <i>Start by typing <code>/num +91XXXXXXXXXX</code> to lookup a number!</i>\n\n"
            f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella"
        )
        await update.message.reply_text(text, parse_mode="HTML")
    else:
        text = (
            f"{get_emoji('🦇')} <b>Annebella OSINT BOT</b> {get_emoji('🌟')}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Welcome to the ultimate Phone Lookup & OSINT Search tool!\n\n"
            "To get started and unlock all premium features, please follow these steps:\n\n"
            f"{get_emoji('🌐')} <b>Step 1: Join Our Chats</b>\n"
            f"You must join our two official chats to use the bot:\n"
            f"1. <a href='{ch2_link}'>Join {ch2_title}</a>\n"
            f"2. <a href='{ch3_link}'>Join {ch3_title}</a>\n\n"
            f"{get_emoji('👥')} <b>Step 2: Add Bot to a Group</b>\n"
            "Click the <b>Add to Group</b> button below to add this bot to your group (minimum 25 members required). <b>Note:</b> The bot <u>must</u> be promoted to Administrator in the group for it to work!\n\n"
            f"{get_emoji('🔒')} <b>Step 3: Private Access</b>\n"
            "If you are using this in a private chat, please make sure you are approved by an administrator.\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{get_emoji('📌')} <i>Once completed, click /start again or type /help.</i>\n\n"
            f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella"
        )
        keyboard = [
            [
                InlineKeyboardButton(text="📢 Channel 1", url=ch2_link),
                InlineKeyboardButton(text="📢 Channel 2", url=ch3_link),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Add to Group",
                    url=f"https://t.me/{context.bot.username}?startgroup=true",
                ),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not await verify_channel_join(update, context):
        return
    record_search("/help", context)

    await update.message.reply_text(
        f"{get_emoji('🦇')} <b>Annebella OSINT BOT - Help Directory</b> {get_emoji('🌟')}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('✅')} /start - Welcome message\n"
        f"{get_emoji('✅')} /help - Show this help text\n"
        f"{get_emoji('✅')} /status - Show your current access status\n"
        f"{get_emoji('🔴')} /groups - List groups where the bot has been used (admin only)\n"
        f"{get_emoji('🔴')} /stats - Show bot statistics (admin only)\n"
        f"{get_emoji('🔴')} /approve &lt;user_id&gt; - Approve a user for private bot use (admin only)\n"
        f"{get_emoji('🔴')} /broadcast &lt;message&gt; - Send a broadcast message to all users/groups (admin only)\n"
        f"{get_emoji('✅')} /num &lt;phone_number&gt; - Search phone number info\n"
        f"{get_emoji('✅')} /tg &lt;@username&gt; - Search Telegram username to number\n"
        f"{get_emoji('✅')} /ff &lt;Free_Fire_UID&gt; - Search Free Fire UID details\n"
        f"{get_emoji('✅')} /vnum &lt;Vehicle_Number&gt; - Search Vehicle details with Owner Phone\n"
        f"{get_emoji('✅')} /ifsc &lt;IFSC_Code&gt; - Search Bank details from IFSC code\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella",
        parse_mode="HTML"
    )


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not await verify_channel_join(update, context):
        return
    # No longer echoing back to prevent repeating messages in groups/private.
    pass


async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    user = update.effective_user
    admin_ids = context.bot_data.get("admin_ids", [])
    data = context.bot_data.get("data", {})

    if not user or not is_admin(user.id, admin_ids):
        await update.message.reply_text("Only admins can approve users.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /approve <user_id>")
        return

    target = context.args[0]
    if not target.isdigit():
        await update.message.reply_text("Please specify a numeric user ID.")
        return

    target_id = int(target)
    if target_id in data.get("approved_users", []):
        await update.message.reply_text(f"User {target_id} is already approved.")
        return

    data.setdefault("approved_users", []).append(target_id)
    save_data(data)
    await update.message.reply_text(f"User {target_id} is now approved for private bot use.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    record_search("/status", context)
    user = update.effective_user
    admin_ids = context.bot_data.get("admin_ids", [])
    data = context.bot_data.get("data", {})
    if not user or not update.message:
        return

    approved = user.id in data.get("approved_users", [])
    is_admin_user = is_admin(user.id, admin_ids)
    chat_type = (update.effective_chat.type if update.effective_chat else "unknown").capitalize()

    status_str = f"{get_emoji('🥇')} <b>APPROVED</b>" if (approved or is_admin_user) else f"{get_emoji('⛔️')} <b>NOT APPROVED</b>"
    role_str = f"{get_emoji('🥇')} <b>ADMINISTRATOR</b>" if is_admin_user else f"{get_emoji('👤')} <b>REGULAR USER</b>"

    lines = [
        f"{get_emoji('🦇')} <b>Annebella OSINT BOT - USER STATUS</b> {get_emoji('🌟')}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⚙️')} <b>User ID:</b> <code>{user.id}</code>",
        f"{get_emoji('🌐')} <b>Chat Type:</b> <code>{chat_type}</code>",
        f"{get_emoji('🪪')} <b>Role:</b> {role_str}",
        f"{get_emoji('🔒')} <b>Access Status:</b> {status_str}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella"
    ]

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    user = update.effective_user
    admin_ids = context.bot_data.get("admin_ids", [])
    data = context.bot_data.get("data", {})

    if not user or not is_admin(user.id, admin_ids):
        await update.message.reply_text("Only admins can view statistics.")
        return

    approved = data.get("approved_users", [])
    chats = data.get("known_chats", [])
    groups = [chat for chat in chats if chat["type"] in {"group", "supergroup"}]
    private = [chat for chat in chats if chat["type"] == "private"]

    searches = data.get("searches", {})
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_data = searches.get(today_str, {"total": 0, "commands": {}})
    total_data = searches.get("total", {"total": 0, "commands": {}})

    today_breakdown = []
    for cmd, count in sorted(today_data.get("commands", {}).items(), key=lambda x: x[1], reverse=True):
        today_breakdown.append(f"  • <code>{cmd}</code>: <b>{count}</b>")
    today_breakdown_str = "\n".join(today_breakdown) if today_breakdown else "  • <i>No searches yet</i>"

    total_breakdown = []
    for cmd, count in sorted(total_data.get("commands", {}).items(), key=lambda x: x[1], reverse=True):
        total_breakdown.append(f"  • <code>{cmd}</code>: <b>{count}</b>")
    total_breakdown_str = "\n".join(total_breakdown) if total_breakdown else "  • <i>No searches yet</i>"

    lines = [
        f"{get_emoji('🦇')} <b>Annebella OSINT BOT STATISTICS</b> {get_emoji('🌟')}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('👤')} <b>Total Users:</b> <code>{len(private)}</code>",
        f"{get_emoji('🔒')} <b>PVT Users:</b> <code>{len(private)}</code>",
        f"{get_emoji('🥇')} <b>Approved Users:</b> <code>{len(approved)}</code>",
        f"{get_emoji('🌐')} <b>Total Groups:</b> <code>{len(groups)}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('📈')} <b>TODAY'S SEARCHES:</b> <code>{today_data.get('total', 0)}</code>",
        today_breakdown_str,
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('📊')} <b>TOTAL SEARCHES:</b> <code>{total_data.get('total', 0)}</code>",
        total_breakdown_str,
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⚙️')} <b>Approved IDs:</b> <code>{', '.join(str(uid) for uid in approved) if approved else 'None'}</code>"
    ]

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    user = update.effective_user
    admin_ids = context.bot_data.get("admin_ids", [])
    data = context.bot_data.get("data", {})

    if not user or not is_admin(user.id, admin_ids):
        await update.message.reply_text("Only admins can fetch the data file.")
        return

    approved = data.get("approved_users", [])
    chats = data.get("known_chats", [])
    groups = [chat for chat in chats if chat["type"] in {"group", "supergroup"}]
    private = [chat for chat in chats if chat["type"] == "private"]

    searches = data.get("searches", {})
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_total = searches.get(today_str, {}).get("total", 0)
    grand_total = searches.get("total", {}).get("total", 0)

    stats_text = (
        f"{get_emoji('🦇')} <b>Annebella OSINT BOT - Backup Database</b> {get_emoji('🌟')}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('👤')} <b>Total Users:</b> <code>{len(private)}</code>\n"
        f"{get_emoji('🔒')} <b>PVT Users:</b> <code>{len(private)}</code>\n"
        f"{get_emoji('🥇')} <b>Approved Users:</b> <code>{len(approved)}</code>\n"
        f"{get_emoji('🌐')} <b>Total Groups:</b> <code>{len(groups)}</code>\n"
        f"{get_emoji('📈')} <b>Today Searches:</b> <code>{today_total}</code>\n"
        f"{get_emoji('📊')} <b>Total Searches:</b> <code>{grand_total}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"Here is your live backup of <code>{DATA_FILE}</code>.\n\n"
        f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella"
    )

    if not os.path.isfile(DATA_FILE):
        await update.message.reply_text("Database file not found.")
        return

    try:
        with open(DATA_FILE, "rb") as doc:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=doc,
                filename=DATA_FILE,
                caption=stats_text,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error("Failed to send data file: %s", e)
        await update.message.reply_text(f"Error sending data file: {e}")


async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    user = update.effective_user
    admin_ids = context.bot_data.get("admin_ids", [])
    data = context.bot_data.get("data", {})

    if not user or not is_admin(user.id, admin_ids):
        await update.message.reply_text("Only admins can view groups.")
        return

    groups = [chat for chat in data.get("known_chats", []) if chat["type"] in {"group", "supergroup"}]
    if not groups:
        await update.message.reply_text("No groups have been recorded yet.")
        return

    status_message = await update.message.reply_text(
        f"{get_emoji('⌛')} <b>Fetching registered groups, please wait...</b>",
        parse_mode="HTML"
    )

    lines = []
    for idx, chat in enumerate(groups):
        chat_id = chat["id"]
        title = chat.get("title") or "Unnamed Group"
        username = chat.get("username")
        
        member_count_str = "<i>N/A (kicked/no admin)</i>"
        invite_link = "<i>No link</i>"

        # 1. Get member count with a strict timeout
        try:
            member_count = await asyncio.wait_for(context.bot.get_chat_member_count(chat_id), timeout=1.0)
            member_count_str = f"<code>{member_count}</code>"
        except Exception:
            pass

        # 2. Get invite link
        if username:
            invite_link = f"<a href='https://t.me/{username}'>Join Public Group</a>"
        else:
            try:
                chat_obj = await asyncio.wait_for(context.bot.get_chat(chat_id), timeout=1.0)
                if chat_obj.invite_link:
                    invite_link = f"<a href='{chat_obj.invite_link}'>Join Private Group</a>"
                else:
                    try:
                        link_obj = await asyncio.wait_for(context.bot.create_chat_invite_link(chat_id), timeout=1.0)
                        invite_link = f"<a href='{link_obj.invite_link}'>Join Private Group</a>"
                    except Exception:
                        pass
            except Exception:
                pass

        # Escape special HTML characters in title to prevent rendering breaks
        safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        line = (
            f"{get_emoji('🦇')} <b>Group {idx + 1}:</b> {safe_title}\n"
            f"{get_emoji('⚙️')} <b>ID:</b> <code>{chat_id}</code>\n"
            f"{get_emoji('👤')} <b>Members:</b> {member_count_str}\n"
            f"{get_emoji('🔗')} <b>Invite Link:</b> {invite_link}\n"
        )
        lines.append(line)

    # Split into multiple messages of 8 groups each to avoid 4096 limit
    chunk_size = 8
    chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]
    
    # Send the first chunk by editing status_message
    separator = "\n━━━━━━━━━━━━━━━━━━━━\n"
    first_chunk_text = (
        f"{get_emoji('🦇')} <b>Annebella OSINT BOT - Registered Groups (Part 1/{len(chunks)})</b> {get_emoji('🌟')}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        + separator.join(chunks[0])
    )
    await status_message.edit_text(first_chunk_text, parse_mode="HTML", disable_web_page_preview=True)

    # Send remaining chunks
    for i, chunk in enumerate(chunks[1:], start=2):
        chunk_text = (
            f"{get_emoji('🦇')} <b>Annebella OSINT BOT - Registered Groups (Part {i}/{len(chunks)})</b> {get_emoji('🌟')}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            + separator.join(chunk)
        )
        await update.message.reply_text(chunk_text, parse_mode="HTML", disable_web_page_preview=True)


async def delete_messages_after_delay(messages: List[Any], delay_seconds: int = 30) -> None:
    await asyncio.sleep(delay_seconds)
    for msg in messages:
        if msg:
            try:
                await msg.delete()
            except Exception as e:
                logger.warning("Failed to auto-delete message: %s", e)


async def num_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not await verify_channel_join(update, context):
        return
    record_search("/num", context)

    if not context.args:
        await update.message.reply_text("Usage: /num <phone_number>")
        return

    phone_number_str = context.args[0].strip()
    # Clean formatting like spaces, hyphens, and parentheses
    phone_number_str = phone_number_str.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Strip +91 or 91 prefix for Indian numbers
    if phone_number_str.startswith("+91"):
        phone_number_str = phone_number_str[3:]
    elif phone_number_str.startswith("91") and len(phone_number_str) == 12:
        phone_number_str = phone_number_str[2:]

    api_number = quote_plus(phone_number_str)
    api_url = f"https://xthrlen-lookup-api.vercel.app/api/public/lookup.js?type=number&q={api_number}"

    status_msg = await update.message.reply_text(
        f"{get_emoji('🚀')} <b>Processing query, please wait...</b>",
        parse_mode="HTML"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                if response.status == 500:
                    await status_msg.edit_text(
                        f"{get_emoji('⛔️')} <b>No records found for this phone number.</b>",
                        parse_mode="HTML"
                    )
                    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
                    return
                elif response.status != 200:
                    await status_msg.edit_text(
                        f"{get_emoji('⛔️')} <b>API request failed with HTTP {response.status}.</b>",
                        parse_mode="HTML"
                    )
                    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
                    return
                result = await response.json()
    except Exception as e:
        logger.warning("Error calling number lookup API: %s", e)
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>Could not reach the number lookup API. Try again later.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    if not isinstance(result, dict):
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>Unexpected API response format.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    # Check for success flag
    if result.get("success") is False or str(result.get("success")).lower() == "false":
        msg = result.get("msg", "No records found for this phone number.")
        await status_msg.edit_text(f"{get_emoji('⛔️')} <b>Lookup Failed:</b> {msg}", parse_mode="HTML")
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    # Extract all records (keys that are digit strings)
    records = []
    for k, v in result.items():
        if k.isdigit() and isinstance(v, dict):
            records.append((int(k), v))

    # Sort records by index
    records.sort(key=lambda x: x[0])

    if not records:
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>No records found for this phone number.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    # Format records
    def format_record(rec: Dict[str, Any]) -> str:
        emoji_map = {
            "name": get_emoji("👤"),
            "father name": get_emoji("👨"),
            "address": get_emoji("📍"),
            "circle/sim": get_emoji("🎵"),
            "mobile": get_emoji("📱"),
            "alternative mobile": get_emoji("📞"),
            "id number": get_emoji("🪪"),
            "mail": get_emoji("✉️"),
            "data_id": get_emoji("📌"),
        }
        lines = []
        for k, v in rec.items():
            # Clean key to look nice (e.g. "father name" -> "Father Name")
            nice_key = " ".join(word.capitalize() for word in k.split("_"))
            
            # Find matching emoji
            emoji = get_emoji("📌")
            for keyword, emo in emoji_map.items():
                if keyword in k.lower():
                    emoji = emo
                    break

            # Format value
            if v is None or str(v).lower() in ("none", "null", ""):
                val_str = "<i>N/A</i>"
            elif isinstance(v, bool):
                val_str = f"{get_emoji('🥇')} True" if v else f"{get_emoji('⛔️')} False"
            else:
                v_str = str(v).strip()
                if "address" in k.lower():
                    # Clean up ! markers typically found in raw addresses in these databases
                    while "!!" in v_str:
                        v_str = v_str.replace("!!", "!")
                    v_str = v_str.replace("!", ", ")
                    while ", ," in v_str:
                        v_str = v_str.replace(", ,", ",")
                    v_str = v_str.strip(", ")
                val_str = f"<code>{v_str}</code>"

            lines.append(f"{emoji} <b>{nice_key}:</b> {val_str}")
        return "\n".join(lines)

    formatted_records_list = []
    # Limit to first 5 records to prevent Telegram's 4096 character limit overflow
    sliced_records = records[:5]
    for idx, (rec_idx, rec_data) in enumerate(sliced_records):
        header = f"{get_emoji('🦇')} <b>Record {idx + 1}</b>"
        body = format_record(rec_data)
        formatted_records_list.append(f"{header}\n━━━━━━━━━━━━━━━━━━━━\n{body}")

    formatted_details = "\n\n".join(formatted_records_list)
    if len(records) > 5:
        formatted_details += f"\n\n{get_emoji('⛔️')} <i>Showing first 5 of {len(records)} records. Refine your query if needed.</i>"
    # Emoji list & UI design
    ui_lines = [
        f"{get_emoji('🦇')} <b>Annebella OSINT BOT Report</b> {get_emoji('💎')}",
        "━━━━━━━━━━━━━━━━━━━━",
        formatted_details,
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⌛')} <i>This response and your command will auto-delete in 30 seconds to maintain privacy.</i>"
    ]
    formatted_text = "\n".join(ui_lines)

    await status_msg.edit_text(formatted_text, parse_mode="HTML")
    
    # Auto-delete after 30 seconds
    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))


async def tg_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not await verify_channel_join(update, context):
        return
    record_search("/tg", context)

    if not context.args:
        await update.message.reply_text("Usage: /tg <@username>")
        return

    username = context.args[0].strip()
    if not username.startswith("@"):
        username = "@" + username

    username_clean = username.lower().lstrip("@")
    if username_clean in (
        "officialannebella", "officialannebella07", "annabella", "annebella", 
        "annebellavendor07", "annebellavendor", "darkvendor", "darkvendor07"
    ):
        status_msg = await update.message.reply_text(
            f"{get_emoji('🚀')} <b>Processing query, please wait...</b>",
            parse_mode="HTML"
        )
        await asyncio.sleep(1.5)
        await status_msg.edit_text(
            f"{get_emoji('🥇')} <b>YEH AAPKE FATHERSAAB HAI</b> {get_emoji('🥇')}",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    api_username = quote_plus(username)
    api_url = f"https://xthrlen-lookup-api.vercel.app/api/public/lookup.js?type=tg&q={api_username}"

    status_msg = await update.message.reply_text(
        f"{get_emoji('🚀')} <b>Processing query, please wait...</b>",
        parse_mode="HTML"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                if response.status == 500:
                    await status_msg.edit_text(
                        f"{get_emoji('⛔️')} <b>No records found for this username.</b>",
                        parse_mode="HTML"
                    )
                    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
                    return
                elif response.status != 200:
                    await status_msg.edit_text(
                        f"{get_emoji('⛔️')} <b>API request failed with HTTP {response.status}.</b>",
                        parse_mode="HTML"
                    )
                    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
                    return
                result = await response.json()
    except Exception as e:
        logger.warning("Error calling TG lookup API: %s", e)
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>Could not reach the lookup API. Try again later.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    if not isinstance(result, dict):
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>Unexpected API response format.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    # Check for success flag
    if result.get("success") is False or str(result.get("success")).lower() == "false":
        msg = result.get("msg", "No records found for this username.")
        await status_msg.edit_text(f"{get_emoji('⛔️')} <b>Lookup Failed:</b> {msg}", parse_mode="HTML")
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    # Extract all records (keys that are digit strings)
    records = []
    for k, v in result.items():
        if k.isdigit() and isinstance(v, dict):
            records.append((int(k), v))

    # Sort records by index
    records.sort(key=lambda x: x[0])

    # Fallback to flat result if no nested numeric indices exist
    if not records:
        filtered_dict = {
            k: v for k, v in result.items()
            if k not in ("success", "credit", "msg")
        }
        if filtered_dict:
            records.append((0, filtered_dict))

    if not records:
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>No records found for this username.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    # Format records
    def format_record(rec: Dict[str, Any]) -> str:
        emoji_map = {
            "name": get_emoji("👤"),
            "username": get_emoji("🏷️"),
            "id": get_emoji("🪪"),
            "father name": get_emoji("👨"),
            "address": get_emoji("📍"),
            "circle/sim": get_emoji("🎵"),
            "mobile": get_emoji("📱"),
            "phone": get_emoji("📱"),
            "alternative mobile": get_emoji("📞"),
            "id number": get_emoji("🪪"),
            "mail": get_emoji("✉️"),
            "data_id": get_emoji("📌"),
        }
        lines = []
        for k, v in rec.items():
            nice_key = " ".join(word.capitalize() for word in k.split("_"))
            
            emoji = get_emoji("📌")
            for keyword, emo in emoji_map.items():
                if keyword in k.lower():
                    emoji = emo
                    break

            if v is None or str(v).lower() in ("none", "null", ""):
                val_str = "<i>N/A</i>"
            elif isinstance(v, bool):
                val_str = f"{get_emoji('🥇')} True" if v else f"{get_emoji('⛔️')} False"
            else:
                v_str = str(v).strip()
                if "address" in k.lower():
                    while "!!" in v_str:
                        v_str = v_str.replace("!!", "!")
                    v_str = v_str.replace("!", ", ")
                    while ", ," in v_str:
                        v_str = v_str.replace(", ,", ",")
                    v_str = v_str.strip(", ")
                val_str = f"<code>{v_str}</code>"

            lines.append(f"{emoji} <b>{nice_key}:</b> {val_str}")
        return "\n".join(lines)

    formatted_records_list = []
    sliced_records = records[:5]
    for idx, (rec_idx, rec_data) in enumerate(sliced_records):
        header = f"{get_emoji('🦇')} <b>Record {idx + 1}</b>"
        body = format_record(rec_data)
        formatted_records_list.append(f"{header}\n━━━━━━━━━━━━━━━━━━━━\n{body}")

    formatted_details = "\n\n".join(formatted_records_list)
    if len(records) > 5:
        formatted_details += f"\n\n{get_emoji('⛔️')} <i>Showing first 5 of {len(records)} records. Refine your query if needed.</i>"

    # Emoji list & UI design
    ui_lines = [
        f"{get_emoji('🦇')} <b>Annebella TG LOOKUP Report</b> {get_emoji('💎')}",
        "━━━━━━━━━━━━━━━━━━━━",
        formatted_details,
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⌛')} <i>This response and your command will auto-delete in 30 seconds to maintain privacy.</i>"
    ]
    formatted_text = "\n".join(ui_lines)

    await status_msg.edit_text(formatted_text, parse_mode="HTML")
    
    # Auto-delete after 30 seconds
    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    user = update.effective_user
    admin_ids = context.bot_data.get("admin_ids", [])
    data = context.bot_data.get("data", {})

    if not user or not is_admin(user.id, admin_ids):
        await update.message.reply_text("Only admins can use the broadcast command.")
        return

    # Extract the exact text after /broadcast
    text_to_send = update.message.text.partition(" ")[2].strip()
    if not text_to_send:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    known_chats = data.get("known_chats", [])
    if not known_chats:
        await update.message.reply_text("No known chats found to broadcast to.")
        return

    status_message = await update.message.reply_text("📢 Starting broadcast, please wait...")
    
    success_count = 0
    fail_count = 0

    for chat in known_chats:
        chat_id = chat["id"]
        try:
            await context.bot.send_message(chat_id=chat_id, text=text_to_send)
            success_count += 1
        except Exception as e:
            logger.warning("Failed to send broadcast to %s: %s", chat_id, e)
            fail_count += 1
            
    await status_message.edit_text(
        f"📢 <b>Broadcast Completed!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Successful:</b> {success_count}\n"
        f"❌ <b>Failed:</b> {fail_count}\n"
        f"📊 <b>Total:</b> {len(known_chats)}",
        parse_mode="HTML"
    )


async def ff_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not await verify_channel_join(update, context):
        return
    record_search("/ff", context)

    if not context.args:
        await update.message.reply_text("Usage: /ff <Free_Fire_UID>")
        return

    uid = context.args[0].strip()
    api_url = f"https://anon-ff-info.vercel.app/info?key=free1805&uid={uid}"

    status_msg = await update.message.reply_text(
        f"{get_emoji('⏳')} <b>Searching Free Fire UID, please wait...</b>",
        parse_mode="HTML"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                if response.status != 200:
                    await status_msg.edit_text(
                        f"{get_emoji('⛔️')} <b>Free Fire API request failed with HTTP {response.status}.</b>",
                        parse_mode="HTML"
                    )
                    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
                    return
                
                result = await response.json()
    except Exception as e:
        logger.warning("Error calling Free Fire lookup API: %s", e)
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>Could not reach the Free Fire lookup API. Try again later.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    resp_data = result.get("response", {})
    success = resp_data.get("parameters", {}).get("success", False)
    
    if not success or not resp_data.get("data"):
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>No records found for Free Fire UID: {uid}.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    player = resp_data["data"][0]
    nickname = player.get("Nickname", "Unknown")
    level = player.get("Level", "N/A")
    xp = player.get("Experience (XP)", "N/A")
    ranked_points = player.get("Ranked Points", "N/A")
    region = player.get("Region", "N/A")
    likes = player.get("Likes", "N/A")
    bio = player.get("Signature – Bio", "N/A")
    created_at = player.get("Account Created", "N/A")
    last_login = player.get("Last Login", "N/A")
    prime = player.get("Prime", "N/A")

    # Escape HTML special chars in nickname and bio to avoid rendering crashes
    safe_nickname = nickname.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_bio = bio.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = [
        f"{get_emoji('🦇')} <b>FREE FIRE LOOKUP Report</b> {get_emoji('🌟')}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('👤')} <b>Nickname:</b> <code>{safe_nickname}</code>",
        f"{get_emoji('⚙️')} <b>UID:</b> <code>{uid}</code>",
        f"{get_emoji('⚡')} <b>Level:</b> <code>{level}</code> (XP: <code>{xp}</code>)",
        f"{get_emoji('🥇')} <b>Ranked Points:</b> <code>{ranked_points}</code>",
        f"{get_emoji('📍')} <b>Region:</b> <code>{region}</code>",
        f"{get_emoji('😉')} <b>Likes:</b> <code>{likes}</code>",
        f"{get_emoji('💎')} <b>Prime Status:</b> <code>{prime}</code>",
        f"{get_emoji('🤫')} <b>Bio / Signature:</b> <i>{safe_bio}</i>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⏳')} <b>Created:</b> <code>{created_at}</code>",
        f"{get_emoji('⌛')} <b>Last Login:</b> <code>{last_login}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⌛')} <i>This response and your command will auto-delete in 30 seconds to maintain privacy.</i>",
        f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella"
    ]

    formatted_text = "\n".join(lines)
    await status_msg.edit_text(formatted_text, parse_mode="HTML")
    
    # Auto-delete after 30 seconds
    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))


async def fetch_vehicle_api(vehicle_no: str) -> Optional[Dict[str, Any]]:
    url = f"https://api-by-black-hats-hackers.kesug.com/vehicle-api.php?vehicle_no={vehicle_no}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Fetch challenge page
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

            # 2. Extract AES challenge params
            match_a = re.search(r'a=toNumbers\("([0-9a-f]+)"\)', html)
            match_b = re.search(r'b=toNumbers\("([0-9a-f]+)"\)', html)
            match_c = re.search(r'c=toNumbers\("([0-9a-f]+)"\)', html)
            
            if not match_a or not match_b or not match_c:
                try:
                    return json.loads(html)
                except Exception:
                    return None

            a = bytes.fromhex(match_a.group(1))
            b = bytes.fromhex(match_b.group(1))
            c = bytes.fromhex(match_c.group(1))

            # 3. Decrypt cookie
            from Crypto.Cipher import AES
            decrypted = AES.new(a, AES.MODE_CBC, b).decrypt(c).hex()

            # 4. Make request with browser validation cookie
            cookies = {'__test': decrypted}
            async with session.get(f"{url}&i=1", headers=headers, cookies=cookies, timeout=10) as final_resp:
                if final_resp.status != 200:
                    return None
                return await final_resp.json()
    except Exception as e:
        logger.error("Failed to fetch vehicle info: %s", e)
        return None


async def vnum_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not await verify_channel_join(update, context):
        return
    record_search("/vnum", context)

    if not context.args:
        await update.message.reply_text("Usage: /vnum <Vehicle_Number> (e.g. /vnum UP92P2111)")
        return

    vehicle_no = context.args[0].strip().upper()
    status_msg = await update.message.reply_text(
        f"{get_emoji('⏳')} <b>Searching Vehicle Registration, please wait...</b>",
        parse_mode="HTML"
    )

    result = await fetch_vehicle_api(vehicle_no)
    if not result or not result.get("status") or "data" not in result:
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>No vehicle records found for: {vehicle_no}.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    vehicle_info = result["data"].get("vehicle_info", {}).get("data", {})
    if not vehicle_info:
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>Could not parse vehicle registry details. Try again later.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    owner = vehicle_info.get("owner_name", "N/A")
    father = vehicle_info.get("father_name", "N/A")
    mobile = vehicle_info.get("owner_mobile", "N/A")
    reg_no = vehicle_info.get("reg_no", vehicle_no)
    maker_model = vehicle_info.get("maker_modal", "N/A")
    maker = vehicle_info.get("maker", "N/A")
    vh_class = vehicle_info.get("vh_class", "N/A")
    fuel = vehicle_info.get("fuel_type", "N/A")
    reg_dt = vehicle_info.get("regn_dt", "N/A")
    age = vehicle_info.get("vehicle_age", "N/A")
    engine = vehicle_info.get("engine_no", "N/A")
    chassis = vehicle_info.get("chasi_no", "N/A")
    rto = vehicle_info.get("rto", "N/A")
    color = vehicle_info.get("vehicle_color", "N/A")

    # Escape HTML to protect rendering engine
    safe_owner = owner.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_father = father.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_maker = maker.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_model = maker_model.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_rto = rto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    lines = [
        f"{get_emoji('🦇')} <b>VEHICLE REGISTRATION REPORT</b> {get_emoji('🌟')}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('👤')} <b>Owner Name:</b> <code>{safe_owner}</code>",
        f"{get_emoji('👨')} <b>Father Name:</b> <code>{safe_father}</code>",
        f"{get_emoji('📱')} <b>Owner Mobile:</b> <code>{mobile}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⚙️')} <b>Reg No:</b> <code>{reg_no}</code>",
        f"{get_emoji('⚡')} <b>Model:</b> <code>{safe_model}</code>",
        f"{get_emoji('🍭')} <b>Maker:</b> <code>{safe_maker}</code>",
        f"{get_emoji('🌐')} <b>Class:</b> <code>{vh_class}</code>",
        f"{get_emoji('📍')} <b>RTO Office:</b> <code>{safe_rto}</code>",
        f"{get_emoji('🎨')} <b>Color:</b> <code>{color}</code>",
        f"{get_emoji('🎵')} <b>Fuel:</b> <code>{fuel}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⏳')} <b>Reg Date:</b> <code>{reg_dt}</code>",
        f"{get_emoji('⌛')} <b>Vehicle Age:</b> <code>{age}</code>",
        f"{get_emoji('🔒')} <b>Engine:</b> <code>{engine}</code>",
        f"{get_emoji('🔒')} <b>Chassis:</b> <code>{chassis}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⏳')} <i>This response and your command will auto-delete in 30 seconds to maintain privacy.</i>",
        f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella"
    ]

    formatted_text = "\n".join(lines)
    await status_msg.edit_text(formatted_text, parse_mode="HTML")
    
    # Auto-delete after 30 seconds
    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))


async def ifsc_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not await verify_channel_join(update, context):
        return
    record_search("/ifsc", context)

    if not context.args:
        await update.message.reply_text("Usage: /ifsc <IFSC_Code> (e.g. /ifsc BARB0ORAIXX)")
        return

    ifsc_code = context.args[0].strip().upper()
    api_url = f"https://ifsc.razorpay.com/{ifsc_code}"

    status_msg = await update.message.reply_text(
        f"{get_emoji('⏳')} <b>Searching IFSC Details, please wait...</b>",
        parse_mode="HTML"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                if response.status == 404:
                    await status_msg.edit_text(
                        f"{get_emoji('⛔️')} <b>Invalid IFSC Code: {ifsc_code}. No records found.</b>",
                        parse_mode="HTML"
                    )
                    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
                    return
                elif response.status != 200:
                    await status_msg.edit_text(
                        f"{get_emoji('⛔️')} <b>IFSC API request failed with HTTP {response.status}.</b>",
                        parse_mode="HTML"
                    )
                    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
                    return
                
                result = await response.json()
    except Exception as e:
        logger.warning("Error calling IFSC lookup API: %s", e)
        await status_msg.edit_text(
            f"{get_emoji('⛔️')} <b>Could not reach the IFSC lookup API. Try again later.</b>",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))
        return

    bank = result.get("BANK", "N/A")
    branch = result.get("BRANCH", "N/A")
    address = result.get("ADDRESS", "N/A")
    city = result.get("CITY", "N/A")
    state = result.get("STATE", "N/A")
    contact = result.get("CONTACT", "N/A")
    micr = result.get("MICR", "N/A")
    bankcode = result.get("BANKCODE", "N/A")
    
    neft = result.get("NEFT", False)
    imps = result.get("IMPS", False)
    rtgs = result.get("RTGS", False)
    upi = result.get("UPI", False)

    # Escape HTML to protect rendering engine
    safe_bank = bank.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_branch = branch.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_address = address.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_city = city.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_state = state.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def get_status_emoji(val: bool) -> str:
        return get_emoji('✅') if val else get_emoji('🔴')

    lines = [
        f"{get_emoji('🦇')} <b>IFSC BANK DETAILS REPORT</b> {get_emoji('🌟')}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('🌐')} <b>Bank Name:</b> <code>{safe_bank}</code>",
        f"{get_emoji('🪪')} <b>Bank Code:</b> <code>{bankcode}</code>",
        f"{get_emoji('⚙️')} <b>IFSC Code:</b> <code>{ifsc_code}</code>",
        f"{get_emoji('⚙️')} <b>MICR Code:</b> <code>{micr}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('📍')} <b>Branch:</b> <code>{safe_branch}</code>",
        f"{get_emoji('📍')} <b>Address:</b> <code>{safe_address}</code>",
        f"{get_emoji('📍')} <b>Location:</b> <code>{safe_city}, {safe_state}</code>",
        f"{get_emoji('📱')} <b>Contact:</b> <code>{contact}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"<b>Supported Methods:</b>",
        f"⚡ <b>NEFT:</b> {get_status_emoji(neft)}  |  ⚡ <b>IMPS:</b> {get_status_emoji(imps)}",
        f"⚡ <b>RTGS:</b> {get_status_emoji(rtgs)}  |  ⚡ <b>UPI:</b> {get_status_emoji(upi)}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"{get_emoji('⏳')} <i>This response and your command will auto-delete in 30 seconds to maintain privacy.</i>",
        f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella"
    ]

    formatted_text = "\n".join(lines)
    await status_msg.edit_text(formatted_text, parse_mode="HTML")
    
    # Auto-delete after 30 seconds
    asyncio.create_task(delete_messages_after_delay([update.message, status_msg], 30))


async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    record_chat(update, context)
    if not update.message or not update.message.new_chat_members:
        return

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue

        first_name = member.first_name
        mention = f"<a href='tg://user?id={member.id}'>{first_name}</a>"

        ch2_val = context.bot_data.get("required_ch2")
        ch3_val = context.bot_data.get("required_ch3")

        ch2_title, ch2_link = await get_chat_details(ch2_val, "India Gates", "https://t.me/indiagates", context)
        ch3_title, ch3_link = await get_chat_details(ch3_val, "Annebella Official Chat", "https://t.me/AnnebellaOfficialchat", context)

        text = (
            f"{get_emoji('🦇')} <b>Welcome to the Group, {mention}!</b> {get_emoji('🌟')}\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"Unleash the power of the ultimate premium OSINT search tool! {get_emoji('🚀')}\n\n"
            f"{get_emoji('✅')} <b>Use this Premium OSINT Bot:</b> @{context.bot.username}\n"
            f"<b>Please Join Our Two Official Chats:</b>\n"
            f"1. <a href='{ch2_link}'>Join {ch2_title}</a>\n"
            f"2. <a href='{ch3_link}'>Join {ch3_title}</a>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{get_emoji('🦇')} <b>Developer:</b> @OfficialAnnebella"
        )

        await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN environment variable is not set. "
            "Set it before running bot.py."
        )

    required_ch2 = os.getenv("TELEGRAM_REQUIRED_CH2", "@indiagates")
    required_ch3 = os.getenv("TELEGRAM_REQUIRED_CH3", "@AnnebellaOfficialchat")

    admin_ids = get_admin_ids()
    if not admin_ids:
        raise RuntimeError(
            "TELEGRAM_ADMIN_IDS environment variable is not set or does not contain valid IDs. "
            "Set one or more admin user IDs separated by commas."
        )

    application = ApplicationBuilder().token(token).build()
    application.bot_data["required_ch2"] = required_ch2
    application.bot_data["required_ch3"] = required_ch3
    application.bot_data["admin_ids"] = admin_ids
    application.bot_data["data"] = load_data()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("data", data_command))
    application.add_handler(CommandHandler("groups", groups_command))
    application.add_handler(CommandHandler("approve", approve_user))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("num", num_search))
    application.add_handler(CommandHandler("tg", tg_search))
    application.add_handler(CommandHandler("ff", ff_search))
    application.add_handler(CommandHandler("vnum", vnum_search))
    application.add_handler(CommandHandler("ifsc", ifsc_search))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, echo)
    )
    application.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member)
    )

    logger.info("Starting Telegram bot...")
    application.run_polling()


if __name__ == "__main__":
    main()
