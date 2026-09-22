import asyncio
import sqlite3
import random
import logging
import time
import aiohttp
import hmac
import hashlib
import urllib.parse
import json
import os
import re

try:
    from aiohttp import web as aiohttp_web
except Exception:
    try:
        import importlib
        aiohttp_web = importlib.import_module("aiohttp.web")
    except Exception:
        aiohttp_web = None

# Paytm checksum support. paytmchecksum imports the `Crypto` namespace,
# which is provided by PyCryptodome. Some hosts install paytmchecksum but
# omit PyCryptodome, producing: "No module named 'Crypto'".
# Repair both dependencies automatically, then load PaytmChecksum.
PaytmChecksum = None
try:
    from paytmchecksum import PaytmChecksum
except Exception as _paytm_first_error:
    try:
        import sys
        import subprocess
        # Fix the exact missing dependency reported by the host.
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
             "--no-input", "pycryptodome>=3.20.0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=120,
        )
        # Ensure the Paytm wrapper itself is present/up to date.
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
             "--no-input", "paytmchecksum==1.7.0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=120,
        )
        from paytmchecksum import PaytmChecksum
    except Exception as _paytm_import_error:
        # Keep the bot running if the host blocks package installation.
        # Payment creation/verification will show a clear setup error instead
        # of crashing the complete bot.
        PaytmChecksum = None
        logging.getLogger(__name__).warning(
            "Paytm checksum support unavailable: %s (initial error: %s)",
            _paytm_import_error, _paytm_first_error
        )
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, WebAppInfo, InlineKeyboardButton, CallbackQuery, Message, Dice, BufferedInputFile
)

# ==============================================================================
# 1. BOT CONFIGURATION & CONSTANTS
# ==============================================================================
BOT_TOKEN = "8880156406:AAEhj36xBJoey122aSWu92yEX7TPbSZTxYc"
BOT_USERNAME = "Vickystor_bot"
ADMIN_ID = 8700582148
ADMIN_CONTACT = "@VICKYXMOD"


USDT_TO_INR = 90.0
VIP_DISCOUNT_PERCENTAGE = 15.0
VIP_PRICE_INR = 299.0

WELCOME_STICKER_ID = "CAACAgIAAxkBAAEU-WZmH_..."  # Replace with your sticker ID
SPIN_DELAY_SECONDS = 2.5

FIXED_CATEGORIES = [
    "ANDROID NON ROOT PANEL",
    "ANDROID ROOT PANEL",
    "IPHONE PANEL",
    "PC PANEL"
]

# ==============================================================================
# YOUR PREMIUM EMOJIS – all required emoji IDs (updated with new premium ones)
# ==============================================================================
DEFAULT_EMOJIS = {
    'product_store': '6163205892834598715',          # already premium
    'profile': '6091123564080016936',                # new premium
    'add_balance': '6195010052647033970',            # new premium
    'history': '5278573677900752088',                # new premium
    'referral': '6113723261084769666',               # new premium
    'support': '6219731545100393089',                # new premium
    'ludo_spin': '6091150429100447967',              # new premium
    'back': '6039539366177541657',                   # new premium
    'upi': '5807750375033278838',                    # new premium
    'binance': '5843689746538173057',                # new premium
    'reseller': '6091232896767500693',               # new premium
    'Payment_proof': '6235277570070286919',               # new premium
    'tutorial': '6235277570070286919',              # alias used by welcome/menu UI
    'download': '6208500192736450951',               # already premium
    'telegram': '6066565078520439082',               # new premium
    'whatsapp': '6066520745868009470',               # new premium
    'welcome': '5397782960512444700',                # new premium
    'vip': '6147875990619038032',                    # new premium
    'category_android_non_root': '6208630858526497984',
    'category_android_root': '6147842953730595918',
    'category_iphone': '6055451472684917539',
    'category_pc': '5316891065423241127',
    'grid_id': '5474625972751837256',
    'name': '5215399540814781035',
    'account_level': '6129584162992034014',
    'regular_user': '5904630315946611415',
    'wallet': '6210859306602995217',
    'current_balance': '5316711376876485361',
    'global_stats': '6161437856662298090',
    'total_orders': '6160968017304888311',
    'total_spent': '5197503331215361533',
    'total_referrals': '5938196735200333756',
    'joined_grid': '5433614043006903194',
    'info_icon': '6037421444789440735',
    'check_icon': '6161241250239356403',
    'checkbox_icon': '6161437856662298090',
    'shield_icon': '6086672466132865380',
    'money_icon': '5890848474563352982',
    'redeem_icon': '5377624166436445368',
    'wallet_left': '6210859306602995217',
    'wallet_right': '5305699699204837855',
    'point_down': '6161302621027049305',
    'welcome_brand': '5278702045883292456',
    'welcome_hello': '6053316642010572005',
    'welcome_trusted': '6066437986143182361',
    # Purchase / proof message premium emoji IDs supplied by the owner
    'purchase_success': '6208228634839226756',
    'purchase_game': '5213430392798851273',
    'purchase_duration': '6053316642010572005',
    'purchase_quantity': '6091150429100447967',
    'purchase_key': '620605663981286794',
    'purchase_thanks': '6181343028624494683',
    'settings': '6037421444789440735',
    'proof_name': '6219724089037166558',
    'proof_key': '620605663981286794',
}


def custom_emoji(emoji_id: str, fallback: str = '✨') -> str:
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>' if emoji_id else fallback

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# ==============================================================================
# USER MESSAGE BOX DESIGN
# Disabled: user-facing messages are no longer wrapped with the
# ╭━━━━━━━━━━━━━━━━━━━━━━━━━━╮ / ╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯ lines.
def user_box(text: str) -> str:
    """Return user-facing text unchanged, without the box lines."""
    if text is None:
        return text
    return str(text)

def _is_private_user_chat(chat_id) -> bool:
    # Telegram user IDs are positive integers. Channels/groups are negative IDs
    # or usernames, so they must never receive the user UI box automatically.
    return isinstance(chat_id, int) and chat_id > 0 and chat_id != ADMIN_ID

# Patch the common aiogram text send/edit paths so existing handlers do not
# need to be rewritten one-by-one. This keeps every existing bot function.
_original_message_answer = Message.answer
_original_message_edit_text = Message.edit_text
_original_bot_send_message = Bot.send_message
_original_bot_edit_message_text = Bot.edit_message_text

def _strip_custom_emoji_tags(text):
    if text is None:
        return text
    text = re.sub(r'<tg-emoji\s+emoji-id="[^"]+">(.*?)</tg-emoji>', r'\1', str(text), flags=re.S)
    text = re.sub(r"<tg-emoji\s+emoji-id='[^']+'>(.*?)</tg-emoji>", r'\1', text, flags=re.S)
    return text

def _safe_markup_without_custom_emojis(markup):
    if markup is None:
        return None
    try:
        data = markup.model_dump(exclude_none=True)
        if "inline_keyboard" in data:
            for row in data["inline_keyboard"]:
                for button in row:
                    button.pop("icon_custom_emoji_id", None)
            return InlineKeyboardMarkup(**data)
    except Exception:
        pass
    return markup

def _needs_custom_emoji_fallback(exc):
    msg = str(exc).upper()
    return (
        "DOCUMENT_INVALID" in msg
        or "CUSTOM_EMOJI" in msg
        or "EMOJI-ID" in msg
        or "TG-EMOJI" in msg
    )

async def _boxed_message_answer(self, text=None, *args, **kwargs):
    if getattr(getattr(self, "chat", None), "id", None) != ADMIN_ID:
        text = user_box(text) if text is not None else text
    try:
        return await _original_message_answer(self, text, *args, **kwargs)
    except Exception as exc:
        if not _needs_custom_emoji_fallback(exc):
            raise
        safe_kwargs = dict(kwargs)
        if "reply_markup" in safe_kwargs:
            safe_kwargs["reply_markup"] = _safe_markup_without_custom_emojis(safe_kwargs["reply_markup"])
        return await _original_message_answer(self, _strip_custom_emoji_tags(text), *args, **safe_kwargs)

async def _boxed_message_edit_text(self, text, *args, **kwargs):
    if getattr(getattr(self, "chat", None), "id", None) != ADMIN_ID:
        text = user_box(text)
    try:
        return await _original_message_edit_text(self, text, *args, **kwargs)
    except Exception as exc:
        if not _needs_custom_emoji_fallback(exc):
            raise
        safe_kwargs = dict(kwargs)
        if "reply_markup" in safe_kwargs:
            safe_kwargs["reply_markup"] = _safe_markup_without_custom_emojis(safe_kwargs["reply_markup"])
        return await _original_message_edit_text(self, _strip_custom_emoji_tags(text), *args, **safe_kwargs)

async def _boxed_bot_send_message(self, chat_id, text, *args, **kwargs):
    if _is_private_user_chat(chat_id):
        text = user_box(text)
    try:
        return await _original_bot_send_message(self, chat_id, text, *args, **kwargs)
    except Exception as exc:
        if not _needs_custom_emoji_fallback(exc):
            raise
        safe_kwargs = dict(kwargs)
        if "reply_markup" in safe_kwargs:
            safe_kwargs["reply_markup"] = _safe_markup_without_custom_emojis(safe_kwargs["reply_markup"])
        return await _original_bot_send_message(self, chat_id, _strip_custom_emoji_tags(text), *args, **safe_kwargs)

async def _boxed_bot_edit_message_text(self, chat_id, message_id, text, *args, **kwargs):
    if _is_private_user_chat(chat_id):
        text = user_box(text)
    try:
        return await _original_bot_edit_message_text(self, chat_id, message_id, text, *args, **kwargs)
    except Exception as exc:
        if not _needs_custom_emoji_fallback(exc):
            raise
        safe_kwargs = dict(kwargs)
        if "reply_markup" in safe_kwargs:
            safe_kwargs["reply_markup"] = _safe_markup_without_custom_emojis(safe_kwargs["reply_markup"])
        return await _original_bot_edit_message_text(self, chat_id, message_id, _strip_custom_emoji_tags(text), *args, **safe_kwargs)

Message.answer = _boxed_message_answer
Message.edit_text = _boxed_message_edit_text
Bot.send_message = _boxed_bot_send_message
Bot.edit_message_text = _boxed_bot_edit_message_text

# Telegram callback queries expire quickly.  A slow handler or an already-expired
# callback must never crash the bot with "query is too old" / invalid query ID.
_original_callback_answer = CallbackQuery.answer

async def _safe_callback_answer(self, *args, **kwargs):
    try:
        return await _original_callback_answer(self, *args, **kwargs)
    except Exception as exc:
        msg = str(exc).lower()
        if ("query is too old" in msg
                or "query id is invalid" in msg
                or "response timeout expired" in msg):
            return False
        raise

CallbackQuery.answer = _safe_callback_answer

def fmt_curr(amount: float) -> str:
    return f"₹{amount:,.2f}"

def safe_float(val, default=0.0):
    """Safely convert a value to float, return default if fails."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

# ==============================================================================
# 2. DATABASE FUNCTIONS
# ==============================================================================
def db_query(query: str, params: tuple = (), fetchone: bool = False, fetchall: bool = False, commit: bool = True) -> Any:
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    try:
        c.execute(query, params)
        if fetchone:
            res = c.fetchone()
        elif fetchall:
            res = c.fetchall()
        else:
            res = None
        if commit: conn.commit()
        return res
    except Exception as e:
        logger.error(f"DB Error: {e} | Query: {query} | Params: {params}")
        if commit: conn.rollback()
        return None
    finally:
        conn.close()

def get_setting(key: str, default: str = "") -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return val[0] if val and val[0] else default

def set_setting(key: str, value: str) -> None:
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

def log_activity(user_id: int, action: str, details: str = "") -> None:
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_query(
            "INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, timestamp)
        )
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

def get_emoji(slot: str, default_id: str = None) -> str:
    """Return a Telegram custom emoji tag when an ID is available.
    A visible Unicode fallback such as '🎉' is never treated as an emoji ID.
    """
    stored = get_setting(f"emoji_{slot}", "")
    if stored and stored.isdigit():
        return f'<tg-emoji emoji-id="{stored}">✨</tg-emoji>'
    configured = DEFAULT_EMOJIS.get(slot, "")
    if configured and str(configured).isdigit():
        return f'<tg-emoji emoji-id="{configured}">✨</tg-emoji>'
    if default_id and str(default_id).isdigit():
        return f'<tg-emoji emoji-id="{default_id}">✨</tg-emoji>'
    return default_id or "✨"


def _resolve_product_custom_emoji(prod_id=None, category="", panel_name="", product_name=""):
    """Resolve the product-level Telegram custom emoji, including parent fallback."""
    emoji_id = ""
    try:
        if prod_id is not None:
            row = db_query(
                "SELECT premium_emoji_id, category, panel_name, name FROM products WHERE id=?",
                (prod_id,), fetchone=True
            )
            if row:
                raw = str(row[0] or "").strip()
                if raw.isdigit():
                    return raw
                category = row[1] or category
                panel_name = row[2] or panel_name
                product_name = row[3] or product_name
        if category and panel_name and product_name:
            row = db_query(
                "SELECT premium_emoji_id FROM products "
                "WHERE category=? AND panel_name=? AND name=? "
                "AND premium_emoji_id IS NOT NULL AND premium_emoji_id!='' "
                "ORDER BY CASE WHEN is_product_parent=1 THEN 0 ELSE 1 END, id LIMIT 1",
                (category, panel_name, product_name), fetchone=True
            )
            if row and str(row[0] or "").strip().isdigit():
                return str(row[0]).strip()
    except Exception:
        pass
    return ""

def get_emoji_icon(slot: str, default_id: str = None) -> str:
    stored = get_setting(f"emoji_{slot}", "")
    if stored and stored.isdigit():
        return stored
    configured = DEFAULT_EMOJIS.get(slot, "")
    if configured and str(configured).isdigit():
        return configured
    return default_id if default_id and str(default_id).isdigit() else ""


# ------------------------------------------------------------------------------
# GLOBAL BUTTON DESIGNER
# Admin can override any inline button by exact callback_data or callback prefix.
# Format stored in settings: btn_text_<key>, btn_style_<key>, btn_emoji_<key>.
# ------------------------------------------------------------------------------
_TelegramInlineKeyboardButton = InlineKeyboardButton

def _button_cfg(callback_data: str):
    exact = str(callback_data or "")
    candidates = [exact]
    # Most dynamic callbacks are best customized by their stable prefix.
    for prefix in (
        "buy_", "cat_", "pnl_", "edit_p_", "toggle_p_", "delete_p_", "delkey_p_",
        "admin_view_p_", "usrctrl_", "pay_", "verify_", "addprod_cat_",
        "set_cat_emoji_", "set_panel_emoji_", "edit_reseller_", "design_btn_",
        "confirm_ban_", "confirm_delete_plan_", "add_plan_for_panel_", "delete_plan_",
        "choose_provider_", "set_provider_", "edit_emoji_", "edit_ui_", "reply_ticket_",
        "close_ticket_", "toggle_android_id_", "prod_mode_api_", "prod_mode_manual_",
        "edit_days_panel_", "edit_reseller_", "addprod_provider_", "addprod_mode_"
    ):
        if exact.startswith(prefix):
            candidates.append("__PREFIX__" + prefix)
            break
    for key in candidates:
        if key.startswith("__PREFIX__"):
            text = get_setting("btn_text_prefix_" + key[len("__PREFIX__"):], "")
            style = get_setting("btn_style_prefix_" + key[len("__PREFIX__"):], "")
            emoji = get_setting("btn_emoji_prefix_" + key[len("__PREFIX__"):], "")
        else:
            text = get_setting("btn_text_" + key, "")
            style = get_setting("btn_style_" + key, "")
            emoji = get_setting("btn_emoji_" + key, "")
        if text or style or emoji:
            return text, style, emoji
    return "", "", ""

def _is_admin_button_callback(callback_data: str) -> bool:
    """Identify callbacks that belong to the admin UI so admin buttons use
    only Telegram custom-emoji icons instead of a normal emoji + custom emoji pair."""
    cb = str(callback_data or "")
    if cb.startswith((
        "admin", "designer_", "design_", "addprod_", "edit_p_", "toggle_p_",
        "delete_p_", "delkey_p_", "admin_view_p_", "usrctrl_", "confirm_ban_",
        "confirm_delete_plan_", "add_plan_for_panel_", "delete_plan_",
        "choose_provider_", "set_provider_", "edit_emoji_", "edit_ui_",
        "reply_ticket_", "close_ticket_", "toggle_android_id_", "prod_mode_api_",
        "prod_mode_manual_", "edit_days_panel_", "edit_reseller_",
        "addprod_provider_", "addprod_mode_", "api_diag", "set_cat_emoji_",
        "set_panel_emoji_", "reseller_make", "reseller_remove", "reseller_view",
        "spin_", "paytm_", "key_purchase_channel_test", "private_data_",
        "purchase_channel_", "webapp_", "admin_group_",
        "execute_reseller_upgrade", "admin_reseller_menu", "admin_set_",
        "admin_payment_", "admin_private_", "admin_key_purchase_",
        "admin_purchase_", "admin_paytm_", "admin_setup_", "admin_button_",
    )):
        return True
    return cb in {
        "back_main", "admin_panel_back", "ignore_stock_click", "open_ticket",
    } and cb.startswith("admin")

def _strip_leading_normal_emojis(text: str) -> str:
    """Remove normal Unicode emoji characters used as text prefixes.
    Telegram's custom emoji is rendered separately through icon_custom_emoji_id,
    so keeping both would show two icons on admin buttons."""
    if not text:
        return text
    # Covers the common emoji blocks, symbols, dingbats, flags and variation
    # selectors without touching normal alphabetic/numeric button text.
    pattern = r'^[\s]*(?:[\U0001F000-\U0001FAFF\u2600-\u27BF\u2300-\u23FF\uFE0F\u200D]+)[\s]*'
    cleaned = re.sub(pattern, '', str(text))
    return cleaned or str(text).strip()

def InlineKeyboardButton(*args, **kwargs):
    callback_data = kwargs.get("callback_data", "")
    text, style, emoji = _button_cfg(callback_data)
    if text:
        kwargs["text"] = text
    # If a custom emoji icon is being used, do not also keep the normal
    # Unicode emoji in the button label. This fixes both Admin and User
    # buttons showing two icons and makes Button Designer emoji changes visible.
    if kwargs.get("icon_custom_emoji_id"):
        kwargs["text"] = _strip_leading_normal_emojis(kwargs.get("text", ""))
    if _is_admin_button_callback(callback_data):
        kwargs["text"] = _strip_leading_normal_emojis(kwargs.get("text", ""))
        # Every Admin button gets a custom emoji icon. A button-specific
        # Button Designer emoji still has priority.
        if not kwargs.get("icon_custom_emoji_id"):
            kwargs["icon_custom_emoji_id"] = get_emoji_icon("info_icon") or get_emoji_icon("product_store")
    if style in {"primary", "success", "danger", "crime"}:
        if style == "crime": style = "danger"
        kwargs["style"] = style
    if emoji:
        kwargs["icon_custom_emoji_id"] = emoji
    return _TelegramInlineKeyboardButton(*args, **kwargs)

# ==============================================================================
# 3. STRING RESOURCES – using placeholders for premium emojis
# ==============================================================================
UI_TEXTS = {
    "start_menu": (
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        f"{custom_emoji('5278702045883292456', '✨')}—— 𝐕𝐈𝐂𝐊𝐘 𝐗 𝐌𝐎𝐃𝐄 𝐒𝐓𝐎𝐑 ——{custom_emoji('5278702045883292456', '✨')}\n"
        "𝗣𝗢𝗪𝗘𝗥𝗘𝗗 𝗕𝗬 @VICKYXMOD\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n"
        f"{custom_emoji('6053316642010572005', '✨')} 𝗛𝗘𝗟𝗟𝗢 𝐕ɪᴄᴋʏ 𝗫\n"
        "────────────────\n\n"
        f"{custom_emoji('6066437986143182361', '✨')} 𝗪𝗛𝗬 𝗢𝗨𝗥 𝗦𝗧𝗢𝗥𝗘 𝗜𝗦 𝗧𝗥𝗨𝗦𝗧𝗘𝗗\n\n"
        "┌━━━━ ❖ 𝗡𝗔𝗩𝗜𝗚𝗔𝗧𝗜𝗢𝗡 𝗠𝗘𝗡𝗨 ❖ ━━━━\n"
        "│\n"
        "├ {product_store} <b>𝗣𝗿𝗼𝗱𝘂𝗰𝘁 𝗦𝘁𝗼𝗿𝗲</b> ➔ 𝗜𝗻𝘀𝘁𝗮𝗻𝘁 𝗞𝗲𝘆 𝗗𝗲𝗹𝗶𝘃𝗲𝗿𝘆\n"
        "├ {add_balance} <b>𝗔𝗱𝗱 𝗕𝗮𝗹𝗮𝗻𝗰𝗲</b> ➔ 𝗨𝗣𝗜 • 𝗖𝗿𝘆𝗽𝘁𝗼\n"
        "├ {profile} <b>𝗠𝘆 𝗣𝗿𝗼𝗳𝗶𝗹𝗲</b> ➔ 𝗔𝗰𝗰𝗼𝘂𝗻𝘁 & 𝗟𝗶𝘃𝗲 𝗪𝗮𝗹𝗹𝗲𝘁\n"
        "├ {history} <b>𝗔𝗹𝗹 𝗛𝗶𝘀𝘁𝗼𝗿𝘆</b> ➔ 𝗣𝗮𝘀𝘁 𝗼𝗿𝗱𝗲𝗿𝘀 & 𝗞𝗲𝘆𝘀\n"
        "├ {referral} <b>𝗥𝗲𝗳𝗲𝗿𝗿𝗮𝗹</b> ➔ 𝗘𝗮𝗿𝗻 𝟭𝟱% 𝗕𝗼𝗻𝘂𝘀\n"
        "├ {ludo_spin} <b>𝗟𝘂𝗱𝗼 𝗦𝗽𝗶𝗻</b> ➔ 𝗗𝗮𝗶𝗹𝘆 𝗙𝗿𝗲𝗲 𝗕𝗮𝗹𝗮𝗻𝗰𝗲\n"
        "├ {download} <b>𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗙𝗶𝗹𝗲𝘀</b> ➔ 𝗩𝗲𝗿𝗶𝗳𝗶𝗲𝗱 𝗦𝗮𝗳𝗲 𝗔𝗣𝗞𝘀\n"
        "├ {Payment_proof} <b>𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗣𝗿𝗼𝗼𝗳</b> ➔ 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗣𝗿𝗼𝗼𝗳\n"
        "│\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
       f"{custom_emoji('5278702045883292456', '✨')} 𝗙𝗔𝗦𝗧 • 𝗔𝗨𝗧𝗢𝗠𝗔𝗧𝗘𝗗 • 𝟭𝟬𝟬% 𝗥𝗘𝗟𝗜𝗔𝗕𝗟𝗘"
    ),
    "download_files": (
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        f"{custom_emoji('5805550320985578625', '✨')} <b>DOWNLOAD PREMIUM APK & FILES 📊</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n"
        "🌐 All our highly secured, premium, and updated files\n"
        "are securely hosted on our private channel! ⚠️⛔️\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "📱 <b>WHAT YOU GET:</b> 📌\n\n"
        "✔️ Latest APK Updates 🔔\n"
        "✔️ 100% Virus Free & Secure ‼️\n"
        "✔️ All Configs & Scripts 🌸\n"
        "✔️ Complete Installation Guides 🔺\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "⌨️ Tap the button below to access the Download Channel! 📝"
    ),
    "lucky_dice_result": (
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        f"{get_emoji('ludo_spin')} <b>LUCKY DICE RESULT {get_emoji('ludo_spin', '🎲')} {get_emoji('check_icon', '💯')}</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "🎲 <b>Dice Value:</b> {dice_value}\n\n"
        "💸 <b>You Won:</b> {won_amount}\n"
        "💰 <b>Total Balance:</b> {new_balance}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎉 <b>Congratulations!</b>\n"
        "⏰ Come back after 24 hours."
    ),
    "vip_menu": (
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        "🌟 <b>VIP MEMBERSHIP CLUB</b> 🌟\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        "🔓 Unlock premium benefits and permanent discounts!\n\n"
        "💎 <b>VIP BENEFITS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "• Flat 15% off on ALL products\n"
        "• Stacks with Reseller!\n"
        "• Priority Support\n"
        "• Exclusive VIP-only giveaways\n\n"
        "💳 <b>VIP PRICE:</b> ₹299.00 (Lifetime)\n"
        "👤 <b>YOUR STATUS:</b> {vip_status}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ),
    "add_balance_menu": (
        "{add_balance} <b>ADD BALANCE</b> {info_icon}\n\n"
        "{info_icon} Select your preferred payment method. {check_icon}\n\n"
        "┣ {upi} UPI — Fast Indian payments {checkbox_icon}\n"
        "┣ {binance} Binance — Crypto payments {checkbox_icon}\n\n"
        "{shield_icon} Payments are verified securely. {check_icon}"
    )
,
    "profile_menu": (
        "__grid_id__ <b><u>— YOUR SECURE PROFILE —</u></b> __grid_id__\n\n"
        "__grid_id__ <b>Grid ID:</b> <code>{user_id}</code>\n"
        "__name__ <b>Name:</b> {user_name}\n"
        "__account_level__ <b>Account Level:</b> {account_type}\n\n"
        "__wallet_left__ <b>— Wallet —</b> __wallet_right__\n"
        "__wallet_left__ <b>Current Balance:</b> {balance} __wallet_right__\n\n"
        "__global_stats__ <b>— Global Statistics —</b>\n"
        "__total_orders__ <b>Total Orders:</b> {orders_count}\n"
        "__total_spent__ <b>Total Spent:</b> {spent}\n"
        "__total_referrals__ <b>Total Referrals:</b> {referrals_count}\n\n"
        "{reseller_metrics}"
        "__joined_grid__ <b>Joined Grid:</b> {joined_date}"
    ),
    "history_empty": "🧾 <b>You haven't made any purchases yet. Your vault is empty.</b>",
    "history_header": "🧾 <b><u>— YOUR RECENT ORDERS (LAST 10) —</u></b> 🧾",
    "referral_menu": (
        "__referral__ <b><u>AFFILIATE PROGRAM</u></b> __referral__\n\n"
        "✅ <b>Status:</b> ACTIVE\n"
        "💰 Earn <b>15% flat commission</b> on every successful purchase made by your referred friends!\n\n"
        "📊 <b>YOUR STATS:</b>\n"
        "👥 Total Invited: {referrals_count}\n"
        "💵 Life-time Earned: {earned}\n\n"
        "🔗 <b>Your Invite Link:</b>\n<code>{ref_link}</code>\n\n"
        "<i>Simply copy and share this link to start earning!</i>"
    ),
    "payment_proof_menu": "🧾 <b>PAYMENT PROOFS</b>\n\nView successful order proofs in the configured channel.",
    "support_menu": (
        "__telegram____whatsapp__ <b><u>— PREMIUM SUPPORT CENTER —</u></b>\n\n"
        "Contact us via Telegram or WhatsApp for instant help, or open a support ticket for admin assistance."
    ),
    "ticket_list": "📋 <b><u>— Your Recent Tickets —</u></b> 📋",
    "ticket_empty": "📋 You do not have any active or previous support tickets.",
    "ticket_prompt": "📝 <b>Please type your issue/message below in detail:</b>",
    "redeem_prompt": "🎟 <b>Please enter your VIP / Promo redeem code below:</b>"

}

def get_ui_text(key: str, **kwargs) -> str:
    val = db_query("SELECT value FROM settings WHERE key=?", (f"ui_{key}",), fetchone=True)
    template = val[0] if val and val[0] else UI_TEXTS.get(key, "")

    for _slot in DEFAULT_EMOJIS:
        template = template.replace("__" + _slot + "__", get_emoji(_slot))

    emoji_map = {
        '{product_store}': get_emoji('product_store'),
        '{profile}': get_emoji('profile'),
        '{add_balance}': get_emoji('add_balance'),
        '{history}': get_emoji('history'),
        '{referral}': get_emoji('referral'),
        '{tutorial}': get_emoji('tutorial'),
        '{Payment_proof}': get_emoji('Payment_proof'),
        '{payment_proof}': get_emoji('Payment_proof'),
        '{support}': get_emoji('support'),
        '{ludo_spin}': get_emoji('ludo_spin'),
        '{download}': get_emoji('download'),
        '{telegram}': get_emoji('telegram'),
        '{whatsapp}': get_emoji('whatsapp'),
        '{upi}': get_emoji('upi'),
        '{binance}': get_emoji('binance'),
        '{info_icon}': get_emoji('info_icon'),
        '{check_icon}': get_emoji('check_icon'),
        '{checkbox_icon}': get_emoji('checkbox_icon'),
        '{shield_icon}': get_emoji('shield_icon'),
        '{money_icon}': get_emoji('money_icon'),
        '{redeem_icon}': get_emoji('redeem_icon'),
        '{wallet_left}': get_emoji('wallet_left'),
        '{wallet_right}': get_emoji('wallet_right'),
        '{point_down}': get_emoji('point_down'),
    }
    for placeholder, emoji_tag in emoji_map.items():
        template = template.replace(placeholder, emoji_tag)

    button_defaults = {
        "product_store": ("menu_shop", "Product Store"),
        "profile": ("menu_profile", "My Profile"),
        "add_balance": ("menu_add_balance", "Add Balance"),
        "history": ("menu_orders", "All History"),
        "referral": ("menu_referral", "Referral"),
        "ludo_spin": ("menu_spin_landing", "Ludo Spin"),
        "download": ("menu_all_files", "Download Files"),
        "tutorial": ("menu_payment_proof", "Payment Proof"),
    }
    for slot, (callback, default_label) in button_defaults.items():
        label, _, _ = _button_cfg(callback)
        template = template.replace("{" + slot + "_text}", label or default_label)
        # Keep custom emoji in Welcome Message button text (including Payment Proof).
        # The emoji is rendered as Telegram HTML using the configured custom emoji ID.
        emoji_id = get_emoji_icon(slot)
        if emoji_id and str(emoji_id).isdigit():
            emoji_tag = f'<tg-emoji emoji-id="{emoji_id}">✨</tg-emoji>'
            template = template.replace("{" + slot + "_text}", emoji_tag + " " + (label or default_label))

    if kwargs:
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing formatting key for template {key}: {e}")
    return template

# ==============================================================================
# 4. DATABASE INITIALISATION & MIGRATION
# ==============================================================================
def init_db() -> None:
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            phone TEXT, 
            first_name TEXT, 
            username TEXT,
            balance REAL DEFAULT 0.0, 
            account_type TEXT DEFAULT 'Regular', 
            orders_count INTEGER DEFAULT 0, 
            spent REAL DEFAULT 0.0, 
            referrals_count INTEGER DEFAULT 0, 
            referral_earned REAL DEFAULT 0.0, 
            referred_by INTEGER, 
            last_spin TEXT, 
            joined_date TEXT,
            is_reseller INTEGER DEFAULT 0,
            reseller_since TEXT,
            total_saved REAL DEFAULT 0.0,
            is_banned INTEGER DEFAULT 0,
            warnings INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0,
            vip_since TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            category TEXT, 
            panel_name TEXT DEFAULT '',
            name TEXT, 
            price_inr REAL, 
            reseller_price REAL DEFAULT 0.0,
            stock INTEGER, 
            apk_link TEXT, 
            validity TEXT DEFAULT 'Lifetime', 
            device_limit TEXT DEFAULT '1 Device',
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            product_id INTEGER, 
            key_text TEXT, 
            is_used INTEGER DEFAULT 0
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            product_name TEXT, 
            price_paid REAL, 
            delivered_key TEXT, 
            purchase_date TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            message TEXT, 
            status TEXT DEFAULT 'Open',
            created_at TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, 
            value TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            code TEXT PRIMARY KEY, 
            amount REAL, 
            uses_left INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS redeemed (
            user_id INTEGER, 
            code TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            order_id TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount_inr REAL, 
            status TEXT, 
            timestamp INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS crypto_txns (
            txid TEXT PRIMARY KEY, 
            user_id INTEGER, 
            amount_usdt REAL, 
            timestamp INTEGER
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS spin_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            amount REAL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
        )
    ''')

    migrations = [
        "ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN vip_since TEXT",
        "ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1",
        "ALTER TABLE tickets ADD COLUMN created_at TEXT",
        "ALTER TABLE users ADD COLUMN is_banned INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN warnings INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN panel_name TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN delivery_mode TEXT DEFAULT 'MANUAL'",
        "ALTER TABLE products ADD COLUMN api_provider TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN api_pid TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN api_duration TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN api_android_id_required INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN duration_days INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN gameplay_video TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN premium_emoji_id TEXT DEFAULT ''",
        "ALTER TABLE products ADD COLUMN is_product_parent INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN android_id TEXT DEFAULT ''"
    ]
    for mig in migrations:
        try: c.execute(mig)
        except sqlite3.OperationalError: pass
    
    c.execute("SELECT COUNT(*) FROM spin_rewards")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO spin_rewards (amount) VALUES (?)", [(0.0,), (1.0,), (2.0,), (5.0,), (10.0,)])

    default_settings = [
        ('spin_status', 'ON'),
        ('daily_spin_limit', '50.0'),
        ('reseller_system_status', 'ON'),
        ('bot_status', 'ON'),
        ('how_to_video', 'None'),
        ('all_files_link', 'None'),
        ('paytm_mid', ''),
        ('paytm_merchant_key', ''),
        ('paytm_website', 'WEBSTAGING'),
        ('paytm_client_id', ''),
        ('paytm_callback_url', ''),
        ('panelstore_api_key', ''),
        ('bantibhaiya_api_key', ''),
        ('bantibhaiya_master_key', ''),
        ('payment_proof_channel', ''),
        ('payment_proof_link', ''),
        ('private_data_channel', ''),
        ('key_purchase_channel', ''),
        ('purchase_channel_link', ''),
        ('welcome_text_version', '5'),
        ('webapp_base_url', ''),
        ('webapp_port', '8080'),
        ('binance_api', ''),
        ('binance_secret', ''),
        ('binance_address', ''),
        ('vip_status', 'OFF'),
        ('reseller_setup_fee', '200.0'),
        ('reseller_min_balance', '500.0'),
        ('migration_done', '0'),
        ('support_telegram', 'https://t.me/YourSupport'),
        ('support_whatsapp', 'https://wa.me/YourNumber'),
        ('ui_start_menu', UI_TEXTS['start_menu']),
        ('ui_download_files', UI_TEXTS['download_files']),
        ('ui_lucky_dice_result', UI_TEXTS['lucky_dice_result']),
        ('ui_vip_menu', UI_TEXTS['vip_menu']),
        ('ui_add_balance_menu', UI_TEXTS['add_balance_menu']),
        ('ui_profile_menu', UI_TEXTS['profile_menu']),
        ('ui_history_empty', UI_TEXTS['history_empty']),
        ('ui_history_header', UI_TEXTS['history_header']),
        ('ui_referral_menu', UI_TEXTS['referral_menu']),
        ('ui_payment_proof_menu', UI_TEXTS['payment_proof_menu']),
        ('ui_support_menu', UI_TEXTS['support_menu']),
        ('ui_ticket_list', UI_TEXTS['ticket_list']),
        ('ui_ticket_empty', UI_TEXTS['ticket_empty']),
        ('ui_ticket_prompt', UI_TEXTS['ticket_prompt']),
        ('ui_redeem_prompt', UI_TEXTS['redeem_prompt']),
    ]
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        default_settings.append((f"emoji_{slot}", emoji_id))
    
    for key, val in default_settings:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    conn.commit()
    conn.close()

def migrate_categories() -> None:
    done = get_setting("migration_done", "0")
    
    # ALWAYS force update emojis and UI texts regardless of migration status
    logger.info("Forcing emoji and UI text updates...")
    
    # Keep admin custom emoji IDs. Only create missing defaults.
    for slot, emoji_id in DEFAULT_EMOJIS.items():
        db_query("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (f"emoji_{slot}", emoji_id))
    
    # Install the requested welcome text once, then preserve admin edits.
    if get_setting("welcome_text_version", "0") != "5":
        # One-time repair: replace legacy DB welcome text that contained normal Unicode emojis
        # or an unresolved {Payment_proof} placeholder. Future admin edits are preserved.
        set_setting("ui_start_menu", UI_TEXTS['start_menu'])
        set_setting("welcome_text_version", "5")
    # Preserve administrator UI text customizations across restarts.

    # Repair legacy welcome templates that can survive older deployments.
    current_welcome = get_setting("ui_start_menu", "")
    if "{Payment_proof}" in current_welcome:
        set_setting("ui_start_menu", UI_TEXTS['start_menu'])

    logger.info("UI texts and emojis updated with new placeholders and IDs.")
    
    # Fix any corrupted price columns (one-time cleanup)
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    products = c.execute("SELECT id, price_inr, reseller_price FROM products").fetchall()
    for prod in products:
        pid = prod[0]
        for col in ['price_inr', 'reseller_price']:
            val = prod[1] if col == 'price_inr' else prod[2]
            if val is None or val == "":
                new_val = 0.0
            else:
                try:
                    new_val = float(val)
                except (ValueError, TypeError):
                    new_val = 0.0
            c.execute(f"UPDATE products SET {col}=? WHERE id=?", (new_val, pid))
    conn.commit()
    conn.close()
    logger.info("Fixed any non-numeric price columns.")
    
    if done == "1":
        return
    
    logger.info("Running category migration...")
    
    mapping = {
        "android non root panel": "ANDROID NON ROOT PANEL",
        "android root panel": "ANDROID ROOT PANEL",
        "iphone panel": "IPHONE PANEL",
        "pc panel": "PC PANEL",
    }
    for old, new in mapping.items():
        db_query("UPDATE products SET category = ? WHERE LOWER(category) = ?", (new, old))
    
    db_query("UPDATE products SET category = 'ANDROID NON ROOT PANEL' WHERE LOWER(category) NOT IN (?, ?, ?, ?)",
             ("android non root panel", "android root panel", "iphone panel", "pc panel"))
    
    set_setting("migration_done", "1")
    logger.info("Category migration complete.")

# ==============================================================================
# 5. MIDDLEWARES & SECURITY
# ==============================================================================
async def hacker_loading(message: Message, text: str = "Decrypting Data") -> Message:
    msg = await message.answer(f"⚡ {text}\n[□□□] 0%")
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■□□] 33%", parse_mode='HTML')
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■■□] 66%", parse_mode='HTML')
    await asyncio.sleep(0.3)
    await msg.edit_text(f"⚡ {text}\n[■■■] 100%", parse_mode='HTML')
    return msg

class GlobalSecurityMiddleware(BaseMiddleware):
    def __init__(self):
        super().__init__()
        self.last_action_times = {}

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id
        now = time.time()
        if user_id in self.last_action_times:
            if now - self.last_action_times[user_id] < 0.3:
                return
        self.last_action_times[user_id] = now

        if user_id != ADMIN_ID:
            user_info = db_query("SELECT is_banned FROM users WHERE user_id=?", (user_id,), fetchone=True)
            if user_info and user_info[0] == 1:
                msg = "🚫 <b>ACCESS DENIED</b>\nYou have been banned from using this bot.\nContact support if you think this is a mistake."
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer(msg, show_alert=True)
                return
                
            status_check = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
            status = status_check[0] if status_check else 'ON'
            if status == 'OFF':
                msg = "⚠️ <b>Store Maintenance</b>\n\nThe store is currently offline for updates. Please check back later!"
                if isinstance(event, Message): await event.answer(msg)
                elif isinstance(event, CallbackQuery): await event.answer("⚠️ Bot is currently OFF for Maintenance.", show_alert=True)
                return
                
        return await handler(event, data)

dp.message.middleware(GlobalSecurityMiddleware())
dp.callback_query.middleware(GlobalSecurityMiddleware())

# ==============================================================================
# 6. FSM STATES
# ==============================================================================
class UserStates(StatesGroup):
    wait_for_ticket = State()
    wait_for_redeem = State()
    wait_for_crypto_txid = State()
    custom_amount_input = State()
    user_android_id = State()

class AdminStates(StatesGroup):
    add_prod_category = State()
    add_prod_panel_name = State()
    add_prod_name = State()
    add_prod_emoji = State()
    add_prod_validity = State()
    add_prod_device_limit = State()
    add_prod_price = State()
    add_prod_reseller_price = State()
    add_prod_apk = State()
    add_prod_keys = State()
    
    edit_prod_field = State()
    wait_for_new_value = State()
    wait_for_add_keys = State()
    wait_for_delete_key = State()
    
    broadcast_msg = State()
    add_coupon_code = State()
    add_coupon_amount = State()
    add_coupon_uses = State()
    
    paytm_setup = State()
    api_settings = State()
    button_design_target = State()
    button_design_config = State()
    add_prod_mode = State()
    add_prod_provider = State()
    add_prod_pid = State()
    add_prod_api_duration = State()
    wait_for_binance_api = State()
    wait_for_binance_secret = State()
    wait_for_binance_address = State()
    
    ticket_reply_msg = State()
    reseller_manage_id = State()
    manage_target_user = State()
    wait_for_add_money = State()
    wait_for_minus_money = State()
    wait_for_warning = State()
    
    spin_add_reward = State()
    spin_set_limit = State()
    spin_edit_reward = State()
    wait_for_howto_video = State()
    wait_for_all_files_link = State()
    
    edit_ui_text = State()
    edit_reseller_price = State()
    wait_for_reseller_setup_fee = State()
    wait_for_reseller_min_balance = State()
    confirm_ban = State()
    
    wait_for_support_telegram = State()
    wait_for_support_whatsapp = State()
    wait_for_category_emoji = State()
    wait_for_panel_emoji_id = State()
    wait_for_emoji_slot = State()
    wait_for_webapp_url = State()

# ==============================================================================
# 7. KEYBOARDS
# ==============================================================================
def get_category_emoji(category: str) -> str:
    slot_map = {
        "ANDROID NON ROOT PANEL": "category_android_non_root",
        "ANDROID ROOT PANEL": "category_android_root",
        "IPHONE PANEL": "category_iphone",
        "PC PANEL": "category_pc",
    }
    slot = slot_map.get(category)
    if slot:
        return get_emoji_icon(slot, DEFAULT_EMOJIS.get(slot, ""))
    return ""

def get_panel_emoji(panel_name: str) -> str:
    stored = get_setting(f"panel_emoji_{panel_name}", "")
    if stored and stored.isdigit():
        return stored
    return get_emoji_icon("product_store")

def contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Verify Contact", request_contact=True)]], 
        resize_keyboard=True, 
        one_time_keyboard=True
    )

def main_menu_kb(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    sys_status = status_check[0] if status_check else 'ON'
    vip_sys_check = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_system = vip_sys_check[0] if vip_sys_check else 'OFF'
    
    is_reseller = False
    if user_id:
        user_check = db_query("SELECT is_reseller FROM users WHERE user_id=?", (user_id,), fetchone=True)
        if user_check:
            is_reseller = bool(user_check[0])

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Product Store", callback_data="menu_shop",
            icon_custom_emoji_id=get_emoji_icon("product_store"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="My Profile", callback_data="menu_profile",
            icon_custom_emoji_id=get_emoji_icon("profile"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Add Balance", callback_data="menu_add_balance",
            icon_custom_emoji_id=get_emoji_icon("add_balance"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="All History", callback_data="menu_orders",
            icon_custom_emoji_id=get_emoji_icon("history"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Referral", callback_data="menu_referral",
            icon_custom_emoji_id=get_emoji_icon("referral"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Payment Proof", callback_data="menu_payment_proof",
            icon_custom_emoji_id=get_emoji_icon("tutorial"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Support", callback_data="menu_support",
            icon_custom_emoji_id=get_emoji_icon("support"),
            style="success"
        )
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="Ludo Spin", callback_data="menu_spin_landing",
            icon_custom_emoji_id=get_emoji_icon("ludo_spin"),
            style="success"
        ),
        InlineKeyboardButton(
            text="Download Files", callback_data="menu_all_files",
            icon_custom_emoji_id=get_emoji_icon("download"),
            style="success"
        )
    ])
    
    extras_row = []
    if sys_status == 'ON' or is_reseller:
        extras_row.append(InlineKeyboardButton(
            text="Reseller Panel", callback_data="menu_reseller_dash",
            icon_custom_emoji_id=get_emoji_icon("reseller"),
            style="success"
        ))
    if vip_system == 'ON':
        extras_row.append(InlineKeyboardButton(
            text="VIP Club", callback_data="menu_vip_dash",
            style="success"
        ))
    if extras_row:
        kb.inline_keyboard.append(extras_row)
        
    return kb

def back_kb(callback: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="BACK", callback_data=callback,
                icon_custom_emoji_id=get_emoji_icon("back"),
                style="danger"
            )
        ]]
    )

def _admin_btn(text: str, callback_data: str, style: str = "success", emoji_slot: str = "info_icon"):
    return InlineKeyboardButton(text=text, callback_data=callback_data, icon_custom_emoji_id=get_emoji_icon(emoji_slot) or get_emoji_icon("info_icon"), style=style)

def admin_kb() -> InlineKeyboardMarkup:
    status = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    status_val = status[0] if status else 'ON'
    vip_status = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    vip_val = vip_status[0] if vip_status else 'OFF'
    rows = [
        [_admin_btn("📊 Dashboard", "admin_group_dashboard", emoji_slot="global_stats"), _admin_btn("👥 Users", "admin_group_users", emoji_slot="profile")],
        [_admin_btn("🛒 Products", "admin_group_products", emoji_slot="product_store"), _admin_btn("🌐 Web Apps", "admin_group_webapps", emoji_slot="telegram")],
        [_admin_btn("💳 Payments", "admin_group_payments", emoji_slot="upi"), _admin_btn("📢 Marketing", "admin_group_marketing", emoji_slot="telegram")],
        [_admin_btn("🎨 Customization", "admin_group_customization", emoji_slot="welcome"), _admin_btn("⚙️ System & Links", "admin_group_settings", emoji_slot="settings")],
        [_admin_btn("🎨 Button Designer", "admin_button_designer", emoji_slot="welcome"), _admin_btn("🔧 Bot Controls", "admin_group_bot_controls", emoji_slot="settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _admin_group_kb(rows):
    rows = list(rows)
    rows.append([InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.callback_query(F.data == "admin_group_dashboard")
async def admin_group_dashboard(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = _admin_group_kb([[InlineKeyboardButton(text="📊 Bot Statistics", callback_data="admin_view_stats", style="success")]])
    await call.message.edit_text("📊 <b>DASHBOARD</b>\n\nQuick access to bot statistics and status.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_group_webapps")
async def admin_group_webapps(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [webapp_button_url(get_webapp_url("user"), "User Web App"), webapp_button_url(get_webapp_url("reseller"), "Reseller Web App")],
        [webapp_button_url(get_webapp_url("keys"), "Keys Manager"), webapp_button_url(get_webapp_url("broadcast"), "Broadcast Web App")],
        [webapp_button_url(get_webapp_url("home"), "WebApp Home")],
        [InlineKeyboardButton(text="Web App API Settings", callback_data="admin_webapp_url", style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ])
    await call.message.edit_text("<b>WEB APP CENTER</b>\n\nAll WebApps are opened using their complete HTTPS URLs; no route is appended.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_group_products")
async def admin_group_products(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = _admin_group_kb([
        [InlineKeyboardButton(text="🛒 Product Manager", callback_data="admin_product_manager", style="success")],
        [InlineKeyboardButton(text="➕ Add / Update Product", callback_data="admin_add_prod", icon_custom_emoji_id=get_emoji_icon("product_store"), style="success")],
        [InlineKeyboardButton(text="🔑 Product APIs", callback_data="admin_product_api_settings", style="success")],
        [InlineKeyboardButton(text="📝 Edit Reseller Price", callback_data="admin_edit_reseller_price", style="success")],
    ])
    await call.message.edit_text("🛒 <b>PRODUCT MANAGEMENT</b>\n\nProducts, plans, stock and API delivery settings.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_group_users")
async def admin_group_users(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = _admin_group_kb([
        [InlineKeyboardButton(text="👥 User Control Panel", callback_data="admin_user_control_start", style="success")],
        [InlineKeyboardButton(text="👑 Reseller Management", callback_data="admin_reseller_menu", style="success")],
        [InlineKeyboardButton(text="📥 Download User List", callback_data="admin_download_userlist", style="primary")],
    ])
    await call.message.edit_text("👥 <b>USERS & RESELLERS</b>\n\nManage users, reseller access and database exports.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_group_payments")
async def admin_group_payments(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = _admin_group_kb([
        [InlineKeyboardButton(text="💳 Paytm Merchant", callback_data="admin_paytm_setup", style="success")],
        [InlineKeyboardButton(text="🪙 Binance Setup", callback_data="admin_setup_binance", style="success")],
        [InlineKeyboardButton(text="🧾 Payment Proof", callback_data="admin_payment_proof_settings", style="success")],
        [InlineKeyboardButton(text="🧾 Payment Proof Link", callback_data="admin_payment_proof_link", style="success")],
    ])
    await call.message.edit_text("💳 <b>PAYMENTS</b>\n\nPayment gateway, crypto and proof settings.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_group_marketing")
async def admin_group_marketing(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = _admin_group_kb([
        [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast_btn", style="success")],
        [InlineKeyboardButton(text="🎫 View Tickets", callback_data="admin_view_tickets", style="success")],
        [InlineKeyboardButton(text="🎟 Create Coupon", callback_data="admin_create_coupon", style="success")],
    ])
    await call.message.edit_text("📢 <b>BROADCAST & TICKETS</b>\n\nMarketing tools, broadcasts, tickets and coupons.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_group_customization")
async def admin_group_customization(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = _admin_group_kb([
        [InlineKeyboardButton(text="✏️ User Text Manager", callback_data="admin_edit_ui_menu", style="success")],
        [InlineKeyboardButton(text="🎨 All Custom Emojis", callback_data="admin_edit_emojis", style="success")],
        [InlineKeyboardButton(text="🎨 Button Designer", callback_data="admin_button_designer", style="success")],
        [InlineKeyboardButton(text="🎨 Category Emojis", callback_data="admin_set_category_emojis", style="success"), InlineKeyboardButton(text="🖼 Panel Emojis", callback_data="admin_set_panel_emojis", style="success")],
    ])
    await call.message.edit_text("🎨 <b>CUSTOMIZATION</b>\n\nCleanly grouped UI text, button styles and emoji controls.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_group_bot_controls")
async def admin_group_bot_controls(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    status = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    vip = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    reseller = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    status_val = status[0] if status else "ON"
    vip_val = vip[0] if vip else "OFF"
    reseller_val = reseller[0] if reseller else "ON"
    kb = _admin_group_kb([
        [_admin_btn(f"Bot Status: {status_val}", "admin_toggle_bot", "success" if status_val == "ON" else "danger", "check_icon")],
        [_admin_btn(f"VIP System: {vip_val}", "admin_toggle_vip_sys", "success" if vip_val == "ON" else "danger", "vip")],
        [_admin_btn(f"Reseller System: {reseller_val}", "admin_toggle_reseller_sys", "success" if reseller_val == "ON" else "danger", "reseller")],
    ])
    await call.message.edit_text("🔧 <b>BOT CONTROLS</b>\n\nStatus switches are kept here so the main Admin screen stays clean.", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_group_settings")
async def admin_group_settings(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    kb = _admin_group_kb([
        [InlineKeyboardButton(text="💰 Reseller Fee", callback_data="admin_set_reseller_fee", style="success"), InlineKeyboardButton(text="💳 Min Balance", callback_data="admin_set_reseller_min", style="success")],
        [InlineKeyboardButton(text="📞 Support Links", callback_data="admin_set_support_links", style="success")],
        [InlineKeyboardButton(text="🗄 Private Data Channel", callback_data="admin_private_channel", style="success"), InlineKeyboardButton(text="🔑 Key Purchase Channel", callback_data="admin_key_purchase_channel", style="success")],
        [InlineKeyboardButton(text="📢 Purchase Channel", callback_data="admin_purchase_channel", style="success")],
        [InlineKeyboardButton(text="🔗 All Files Link", callback_data="admin_set_all_files", style="success")],
        [InlineKeyboardButton(text="⚙️ Telegram Settings", callback_data="admin_set_telegram", style="success")],
    ])
    await call.message.edit_text("⚙️ <b>SYSTEM & LINKS</b>\n\nSystem-level settings, support and channel links.", reply_markup=kb, parse_mode="HTML")

def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Back to Admin", callback_data="admin_panel_back",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ]])

# ==============================================================================
# 8. NOTIFICATIONS
# ==============================================================================
async def send_advanced_notification(user_id: int, notif_type: str, amount: float, product: str = None, key: str = None, gateway: str = "ZapUPI") -> None:
    user_info = db_query("SELECT first_name, phone, username, is_reseller, is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    
    name = user_info[0] if user_info else "Unknown"
    phone = user_info[1] if user_info and user_info[1] else "Not Provided"
    username = f"@{user_info[2]}" if user_info and user_info[2] else "None"
    
    tags = []
    if user_info and user_info[3]: tags.append("👑 Reseller")
    if user_info and user_info[4]: tags.append("🌟 VIP")
    tag_str = " | ".join(tags) if tags else "👤 Regular"
        
    time_now = datetime.now().strftime("%d-%m-%Y %I:%M %p")
    
    if notif_type == "ORDER":
        title = "🛒 <b>NEW ORDER PROCESSED!</b> 🛒"
        details = (f"📦 <b>Product:</b> {product}\n🔑 <b>Key:</b> <code>{key}</code>\n💰 <b>Amount Paid:</b> ₹{amount:.2f}\n📅 <b>Time:</b> {time_now}")
    else:
        title = "💰 <b>NEW WALLET DEPOSIT!</b> 💰"
        details = (f"💵 <b>Amount Added:</b> ₹{amount:.2f}\n🧾 <b>Gateway:</b> {gateway}\n🆔 <b>Reference:</b> <code>{product}</code>\n📅 <b>Time:</b> {time_now}")

    msg = f"{title}\n━━━━━━━━━━━━━━━━━━\n👤 <b>Name:</b> {name}\n🆔 <b>User ID:</b> <code>{user_id}</code>\n📱 <b>Phone:</b> {phone}\n🔗 <b>Username:</b> {username}\n🏷 <b>Status:</b> {tag_str}\n━━━━━━━━━━━━━━━━━━\n{details}"
    try: 
        await bot.send_message(ADMIN_ID, msg, parse_mode='HTML')
    except Exception as e: 
        logger.error(f"Failed to send admin notification: {e}")

# ==============================================================================
# 9. PAYTM PAYMENT VERIFIER
# ==============================================================================
async def paytm_status(order_id: str):
    if PaytmChecksum is None:
        return None, "paytmchecksum package is not installed"
    mid = get_setting("paytm_mid", "")
    merchant_key = get_setting("paytm_merchant_key", "")
    if not mid or not merchant_key:
        return None, "Paytm Merchant ID/Key is not configured"
    body = {"mid": mid, "orderId": order_id}
    body_json = json.dumps(body, separators=(",", ":"))
    signature = PaytmChecksum.generateSignature(body_json, merchant_key)
    payload = {"body": body, "head": {"tokenType": "AES", "timestamp": str(int(time.time())), "signature": signature}}
    staging = get_setting("paytm_website", "WEBSTAGING").upper() == "WEBSTAGING"
    url = "https://securestage.paytmpayments.com/v3/order/status" if staging else "https://securegw.paytm.in/v3/order/status"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=25) as resp:
                data = await resp.json(content_type=None)
                return data, None
    except Exception as e:
        return None, str(e)

async def credit_paid_transaction(user_id: int, order_id: str, amount: float, auto=False):
    current = db_query("SELECT status FROM transactions WHERE order_id=?", (order_id,), fetchone=True)
    if not current or current[0] == 'paid':
        return False
    db_query("UPDATE transactions SET status='paid' WHERE order_id=?", (order_id,))
    db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    await send_advanced_notification(user_id, "DEPOSIT", amount, product=order_id, gateway="Paytm Auto" if auto else "Paytm Merchant")
    await send_private_data_log("DEPOSIT_SUCCESS", user_id, f"💰 Amount: {fmt_curr(amount)}\n🧾 Order: <code>{order_id}</code>\n🏦 Gateway: Paytm")
    log_activity(user_id, "DEPOSIT_SUCCESS", f"Amount: {amount}, Gateway: Paytm, Order: {order_id}")
    return True

async def run_payment_verification(user_id: int, order_id: str, reply_target: Any) -> None:
    txn = db_query("SELECT amount_inr, status, timestamp FROM transactions WHERE order_id=?", (order_id,), fetchone=True)
    if not txn:
        msg = "❌ Invalid Order ID."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return
    if txn[1] == 'paid':
        msg = "✅ This payment has already been credited."
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return
    if time.time() - txn[2] > 1800 and txn[1] == 'pending':
        db_query("UPDATE transactions SET status='expired' WHERE order_id=?", (order_id,))
        msg = "⏳ Payment window expired. Please create a new order."
        if isinstance(reply_target, CallbackQuery): await reply_target.message.edit_text(msg, reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
        else: await reply_target.answer(msg, reply_markup=back_kb("gateway_inr"))
        return
    data, err = await paytm_status(order_id)
    if err:
        msg = f"⚠️ Paytm verification error: {err}"
        if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
        else: await reply_target.answer(msg)
        return
    body = (data or {}).get("body", {})
    result = str(body.get("resultInfo", {}).get("resultStatus", "" )).upper()
    if result in {"TXN_SUCCESS", "SUCCESS"}:
        if await credit_paid_transaction(user_id, order_id, float(txn[0])):
            success = f"🎉 <b>PAYMENT VERIFIED</b>\n\n✅ {fmt_curr(txn[0])} added to your wallet.\n🧾 Order: <code>{order_id}</code>"
            if isinstance(reply_target, CallbackQuery): await reply_target.message.edit_text(success, reply_markup=back_kb(), parse_mode='HTML')
            else: await reply_target.answer(success, reply_markup=back_kb(), parse_mode='HTML')
        return
    if result in {"TXN_FAILURE", "FAILURE"}:
        db_query("UPDATE transactions SET status='failed' WHERE order_id=?", (order_id,))
        msg = "❌ Paytm reports this payment as failed."
    else:
        msg = "⏳ Payment is still pending. You can use Verify again after payment."
    if isinstance(reply_target, CallbackQuery): await reply_target.answer(msg, show_alert=True)
    else: await reply_target.answer(msg)

async def auto_verify_task() -> None:
    while True:
        await asyncio.sleep(15)
        pending = db_query("SELECT order_id, user_id, amount_inr, timestamp FROM transactions WHERE status='pending'", fetchall=True) or []
        for order_id, user_id, amount, ts in pending:
            if time.time() - ts > 1800:
                db_query("UPDATE transactions SET status='expired' WHERE order_id=?", (order_id,))
                continue
            data, err = await paytm_status(order_id)
            if err or not data:
                continue
            result = str(data.get("body", {}).get("resultInfo", {}).get("resultStatus", "")).upper()
            if result in {"TXN_SUCCESS", "SUCCESS"} and await credit_paid_transaction(user_id, order_id, float(amount), auto=True):
                try:
                    await bot.send_message(user_id, f"✨ <b>AUTO-VERIFIED!</b>\n\n✅ {fmt_curr(amount)} has been added to your balance.\n🧾 <code>{order_id}</code>", parse_mode='HTML')
                except Exception:
                    pass

# ==============================================================================
# 10. ONBOARDING & START
# ==============================================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    try: await message.answer_sticker(WELCOME_STICKER_ID)
    except: pass 
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("v_"):
        order_id = args[1].split("v_")[1]
        msg = await message.answer("🔄 <b>Verifying your payment securely...</b>\n<i>Connecting to gateway...</i>", parse_mode='HTML')
        await run_payment_verification(message.from_user.id, order_id, msg)
        return

    referred_by = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try: referred_by = int(args[1].split("_")[1])
        except: pass

    user = db_query("SELECT phone FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    current_username = message.from_user.username or ""
    db_query("UPDATE users SET username=? WHERE user_id=?", (current_username, message.from_user.id))

    if not user or not user[0]:
        db_query("INSERT OR IGNORE INTO users (user_id, first_name, username, referred_by, joined_date) VALUES (?, ?, ?, ?, ?)", 
                 (message.from_user.id, message.from_user.first_name, current_username, referred_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        log_activity(message.from_user.id, "ACCOUNT_CREATED")
        await send_private_data_log("ACCOUNT_CREATED", message.from_user.id, f"👤 Name: {message.from_user.first_name}\n🔗 Username: @{current_username if current_username else 'none'}")
        verification_text = (
            f"{get_emoji('product_store', '🏪')} <b>𝗩𝗜𝗖𝗞𝗬 𝗙𝗙 𝗦𝗧𝗢𝗥𝗘</b> {get_emoji('shield_icon', '⚠️')}\n\n"
            f"{get_emoji('welcome_hello', '🎉')} <b>Welcome, 𝐕ɪᴄᴋʏ 𝗫</b> {get_emoji('welcome_hello', '🎉')}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"{get_emoji('shield_icon', '🚨')} <b>VERIFICATION REQUIRED</b> {get_emoji('check_icon', '✅')}\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            f"{get_emoji('welcome_trusted', '🌟')} To start shopping, please verify your phone number. {get_emoji('welcome_hello', '👨')}\n\n"
            f"{get_emoji('info_icon', '😬')} <b>Why we need this:</b> {get_emoji('purchase_success', '🔥')}\n"
            f"{get_emoji('info_icon', '🤔')} • Secure your purchases {get_emoji('check_icon', '✅')}\n"
            f"{get_emoji('info_icon', '🤔')} • Deliver keys to you {get_emoji('check_icon', '✅')}\n"
            f"{get_emoji('info_icon', '🤔')} • Protect your account {get_emoji('check_icon', '✅')}\n\n"
            f"{get_emoji('point_down', '😬')} Tap the button below to share your contact. {get_emoji('check_icon', '✅')}"
        )
        await message.answer(verification_text, parse_mode='HTML', reply_markup=contact_kb())
    else:
        log_activity(message.from_user.id, "CMD_START")
        await send_main_menu(message)

@dp.message(F.contact)
async def handle_contact(message: Message):
    if message.contact.user_id == message.from_user.id:
        db_query("UPDATE users SET phone=? WHERE user_id=?", (message.contact.phone_number, message.from_user.id))
        referrer = db_query("SELECT referred_by FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
        if referrer and referrer[0]:
            db_query("UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id=?", (referrer[0],))
            try: await bot.send_message(referrer[0], f"🎉 <b>Referral Success!</b>\nUser <b>{message.from_user.first_name}</b> joined using your link!", parse_mode='HTML')
            except: pass
        log_activity(message.from_user.id, "CONTACT_VERIFIED")
        verified_text = (
            f"{get_emoji('welcome', '❤️')} <b>Phone verified!</b> {get_emoji('check_icon', '✅')}"
        )
        await message.answer(verified_text, reply_markup=ReplyKeyboardRemove())
        loading_text = (
            f"{get_emoji('info_icon', '😬')} <b>Verification successful! Welcome to HACK STORE.</b> {get_emoji('check_icon', '✅')}\n\n"
            f"{get_emoji('telegram', '📶')} <b>Welcome aboard! Loading shop...</b> {get_emoji('purchase_success', '🔥')}"
        )
        await message.answer(loading_text)
        await send_main_menu(message)
    else:
        await message.answer(
            f"{get_emoji('shield_icon', '❌')} <b>Security Alert:</b> Please share your OWN contact using the provided button."
        )

async def send_main_menu(ctx: Any):
    text = get_ui_text("start_menu", name=(ctx.from_user.first_name or "User"))
    kb = main_menu_kb(ctx.from_user.id)
    if isinstance(ctx, Message): 
        await ctx.answer(text, reply_markup=kb, parse_mode='HTML')
    else: 
        await ctx.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    log_activity(call.from_user.id, "RETURN_MAIN_MENU")
    await send_main_menu(call)

# ==============================================================================
# 11. ADD BALANCE
# ==============================================================================
@dp.callback_query(F.data == "menu_add_balance")
async def select_gateway_menu(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_ADD_BALANCE")
    text = get_ui_text("add_balance_menu")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="UPI PAY", callback_data="gateway_inr", icon_custom_emoji_id=get_emoji_icon("upi"), style="primary"),
            InlineKeyboardButton(text="BINANCE PAY", callback_data="gateway_crypto", icon_custom_emoji_id=get_emoji_icon("binance"), style="primary")
        ],
        [
            InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
        ]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

# ==============================================================================
# 12. UPI & CRYPTO PAYMENT FLOWS
# ==============================================================================
@dp.callback_query(F.data == "gateway_inr")
async def add_balance_inr(call: CallbackQuery):
    text = "💳 <b>— PAYTM MERCHANT —</b>\n\nSelect amount to add to your wallet:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₹50", callback_data="pay_50", style="primary"), InlineKeyboardButton(text="₹100", callback_data="pay_100", style="primary")],
        [InlineKeyboardButton(text="₹200", callback_data="pay_200", style="primary"), InlineKeyboardButton(text="₹500", callback_data="pay_500", style="primary")],
        [InlineKeyboardButton(text="✏️ Custom Amount", callback_data="custom_deposit_keypad", style="primary")],
        [InlineKeyboardButton(text="BACK", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "custom_deposit_keypad")
async def custom_deposit_keypad(call: CallbackQuery, state: FSMContext):
    await state.update_data(amount_str="0")
    await state.set_state(UserStates.custom_amount_input)
    await show_keypad(call.message, "0")

async def show_keypad(message: Message, amount_str: str):
    rows = [
        [InlineKeyboardButton(text="1", callback_data="kp_1"), InlineKeyboardButton(text="2", callback_data="kp_2"), InlineKeyboardButton(text="3", callback_data="kp_3")],
        [InlineKeyboardButton(text="4", callback_data="kp_4"), InlineKeyboardButton(text="5", callback_data="kp_5"), InlineKeyboardButton(text="6", callback_data="kp_6")],
        [InlineKeyboardButton(text="7", callback_data="kp_7"), InlineKeyboardButton(text="8", callback_data="kp_8"), InlineKeyboardButton(text="9", callback_data="kp_9")],
        [InlineKeyboardButton(text="⌫", callback_data="kp_backspace", style="danger"), InlineKeyboardButton(text="0", callback_data="kp_0"), InlineKeyboardButton(text="Clear", callback_data="kp_clear", style="danger")],
        [InlineKeyboardButton(text="✅ Confirm", callback_data="kp_confirm", style="success")],
        [InlineKeyboardButton(text="BACK", callback_data="gateway_inr", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ]
    await message.edit_text(f"💵 <b>Enter Amount (₹):</b>\n\nCurrent: ₹{amount_str}", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode='HTML')

@dp.callback_query(F.data.startswith("kp_"), UserStates.custom_amount_input)
async def keypad_handler(call: CallbackQuery, state: FSMContext):
    data = await state.get_data(); amount_str = data.get("amount_str", "0"); action = call.data.split("_", 1)[1]
    if action == "confirm":
        try: amount = float(amount_str)
        except ValueError: amount = 0
        if amount < 10: return await call.answer("Minimum deposit is ₹10.", show_alert=True)
        await state.clear(); await call.message.edit_text("⏳ <b>Generating Paytm payment link...</b>", parse_mode='HTML')
        await generate_paytm_order(call.from_user.id, amount, call.message); return
    if action == "backspace": amount_str = amount_str[:-1] if len(amount_str) > 1 else "0"
    elif action == "clear": amount_str = "0"
    elif amount_str == "0": amount_str = action
    else: amount_str += action
    amount_str = amount_str[:7]
    await state.update_data(amount_str=amount_str); await show_keypad(call.message, amount_str); await call.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def process_paytm_payment_callback(call: CallbackQuery):
    amount = float(call.data.split("_", 1)[1])
    await call.message.edit_text("⏳ <b>Generating Paytm payment link...</b>", parse_mode='HTML')
    await generate_paytm_order(call.from_user.id, amount, call.message)

async def generate_paytm_order(user_id: int, amount: float, message_obj: Message) -> None:
    if PaytmChecksum is None:
        return await message_obj.edit_text("❌ Paytm module missing. Install <code>paytmchecksum</code> on the bot host.", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
    mid = get_setting("paytm_mid", ""); merchant_key = get_setting("paytm_merchant_key", "")
    website = get_setting("paytm_website", "WEBSTAGING") or "WEBSTAGING"
    callback_url = get_setting("paytm_callback_url", "")
    if not mid or not merchant_key:
        return await message_obj.edit_text("⚠️ Paytm Merchant is not configured. Ask Admin to open Paytm Merchant in Admin Panel.", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
    order_id = f"VXP{user_id}{int(time.time())}"
    body = {"merchantRequestId": order_id, "mid": mid, "linkType": "FIXED", "linkName": f"VICKY_{order_id}"[:64], "linkDescription": "Vicky Wallet Topup", "amount": float(f"{amount:.2f}"), "linkOrderId": order_id, "singleTransactionOnly": True, "bindLinkIdMobile": False}
    if callback_url: body["statusCallbackUrl"] = callback_url
    body_json = json.dumps(body, separators=(",", ":"))
    signature = PaytmChecksum.generateSignature(body_json, merchant_key)
    payload = {"body": body, "head": {"tokenType": "AES", "timestamp": str(int(time.time())), "signature": signature}}
    staging = website.upper() == "WEBSTAGING"
    url = "https://securegw-stage.paytm.in/link/create" if staging else "https://securegw.paytm.in/link/create"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=30) as resp:
                data = await resp.json(content_type=None)
                body_resp = data.get("body", {}) if isinstance(data, dict) else {}
                if resp.status != 200 or str(body_resp.get("resultInfo", {}).get("resultStatus", "")).upper() not in {"SUCCESS", "S"}:
                    err = body_resp.get("resultInfo", {}).get("resultMsg", "Unable to create Paytm payment link")
                    return await message_obj.edit_text(f"❌ <b>Paytm Error:</b> {err}", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
                payment_url = body_resp.get("shortUrl") or body_resp.get("longUrl")
                if not payment_url: raise RuntimeError("Paytm did not return a payment URL")
    except Exception as e:
        return await message_obj.edit_text(f"❌ <b>Paytm Connection Error:</b> {e}", reply_markup=back_kb("gateway_inr"), parse_mode='HTML')
    db_query("INSERT INTO transactions (order_id, user_id, amount_inr, status, timestamp) VALUES (?, ?, ?, 'pending', ?)", (order_id, user_id, amount, int(time.time())))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Pay Now", url=payment_url, style="success")],
        [InlineKeyboardButton(text="🔄 Verify Payment", callback_data=f"verify_{order_id}", style="primary")],
        [InlineKeyboardButton(text="BACK", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await message_obj.edit_text(f"🧾 <b>PAYTM INVOICE CREATED</b>\n\n💰 Amount: <b>{fmt_curr(amount)}</b>\n🧾 Order ID: <code>{order_id}</code>\n\n1️⃣ Tap Pay Now.\n2️⃣ Complete payment.\n3️⃣ Return here; auto-verification checks Paytm every few seconds.", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("verify_"))
async def manual_verify_callback(call: CallbackQuery):
    await run_payment_verification(call.from_user.id, call.data.split("_", 1)[1], call)

@dp.callback_query(F.data == "gateway_crypto")
async def add_balance_crypto(call: CallbackQuery, state: FSMContext):
    address_check = db_query("SELECT value FROM settings WHERE key='binance_address'", fetchone=True)
    if not address_check or not address_check[0]:
        return await call.message.edit_text("⚠️ Binance Gateway is currently offline. Admin has not set a deposit address.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    deposit_address = address_check[0]
    msg = (f"🪙 <b>— BINANCE USDT DEPOSIT —</b> 🪙\n\n💵 <b>Exchange Rate:</b> 1 USDT = ₹{USDT_TO_INR}\n⚠️ <b>Network:</b> Please send via <b>TRC20</b> or <b>BEP20</b>.\n\n👇 <b>Send your USDT to this exact address:</b>\n<code>{deposit_address}</code>\n\n━━━━━━━━━━━━━━━━━━\n✅ <b>After sending the USDT, reply to this message with your exact TxID (Transaction Hash) to instantly claim your balance.</b>")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Cancel", callback_data="menu_add_balance", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(msg, reply_markup=kb, parse_mode='HTML')
    await state.set_state(UserStates.wait_for_crypto_txid)

@dp.message(UserStates.wait_for_crypto_txid)
async def process_crypto_txid(m: Message, state: FSMContext):
    txid = m.text.strip()
    user_id = m.from_user.id
    if len(txid) < 10: return await m.answer("❌ That doesn't look like a valid TxID. Please try again.")
    if db_query("SELECT txid FROM crypto_txns WHERE txid=?", (txid,), fetchone=True):
        return await m.answer("⚠️ This Transaction ID has already been claimed in the system!", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    api_key_check = db_query("SELECT value FROM settings WHERE key='binance_api'", fetchone=True)
    secret_key_check = db_query("SELECT value FROM settings WHERE key='binance_secret'", fetchone=True)
    if not api_key_check or not secret_key_check:
        return await m.answer("⚠️ Binance API is missing on the server. Contact Support.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
    await m.answer("🔄 <b>Verifying your TxID with Binance Blockchain...</b>\n<i>This may take up to 30 seconds...</i>", parse_mode='HTML')
    api_key = api_key_check[0]; secret_key = secret_key_check[0]
    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {'X-MBX-APIKEY': api_key}
    url = f"https://api.binance.com/sapi/v1/capital/deposit/hisrec?{query_string}&signature={signature}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    try: history = await resp.json(content_type=None)
                    except: history = []
                    found = False
                    for deposit in history:
                        if deposit.get("txId") == txid and deposit.get("status") == 1:
                            found = True
                            usdt_amount = float(deposit.get("amount"))
                            inr_amount = usdt_amount * USDT_TO_INR
                            db_query("INSERT INTO crypto_txns (txid, user_id, amount_usdt, timestamp) VALUES (?, ?, ?, ?)", (txid, user_id, usdt_amount, int(time.time())))
                            db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (inr_amount, user_id))
                            await m.answer(f"🎉 <b>CRYPTO DEPOSIT SUCCESSFUL!</b>\n\n✅ We safely received <b>{usdt_amount} USDT</b>.\n💰 <b>{fmt_curr(inr_amount)}</b> has been added to your balance!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
                            await send_advanced_notification(user_id, "DEPOSIT", inr_amount, product=txid, gateway="Binance Crypto")
                            log_activity(user_id, "CRYPTO_DEPOSIT", f"TxID: {txid}, Amount: {inr_amount}")
                            await state.clear()
                            break
                    if not found: await m.answer("❌ <b>TxID Not Found or Still Pending!</b>\nMake sure the transaction is fully confirmed. Try again in 5 mins.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
                else: await m.answer(f"⚠️ <b>Binance Server Error:</b> HTTP {resp.status}.", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')
        except Exception as e: await m.answer(f"⚠️ <b>Connection Error:</b> {str(e)}", reply_markup=back_kb("menu_add_balance"), parse_mode='HTML')

# ==============================================================================
# 13. SHOP – with uppercase categories and new point_down emoji
# ==============================================================================
@dp.callback_query(F.data == "menu_shop")
async def view_shop_panels(call: CallbackQuery):
    log_activity(call.from_user.id, "VIEW_SHOP")

    kb = InlineKeyboardMarkup(inline_keyboard=[])

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        f"{get_emoji('product_store')} <b>SELECT PRODUCT CATEGORY</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"{get_emoji('point_down')} <b>Choose a category to view its products:</b>"
    )

    for cat in FIXED_CATEGORIES:
        count = db_query(
            "SELECT COUNT(*) FROM products WHERE category LIKE ? AND is_active=1",
            (cat + '%',),
            fetchone=True
        )[0]

        emoji_id = get_category_emoji(cat)

        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=cat,
                callback_data=f"cat_{cat[:30]}",
                icon_custom_emoji_id=emoji_id,
                style="primary"
            )
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="BACK",
            callback_data="back_main",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])

    await call.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode="HTML"
    )

def get_custom_reseller_price(user_id: int, prod_id: int, duration: str, fallback: float) -> float:
    row = db_query("SELECT is_reseller FROM users WHERE user_id=?", (user_id,), fetchone=True)
    if not row or not row[0]:
        return fallback
    try:
        raw = json.loads(get_setting(f"reseller_prices_{user_id}", "{}") or "{}")
        bucket = raw.get(str(prod_id), {}) if isinstance(raw, dict) else {}
        for key in (str(duration), str(duration).replace(" Days", ""), "default"):
            if isinstance(bucket, dict) and key in bucket:
                value = safe_float(bucket[key], -1)
                if value > 0:
                    return value
    except Exception:
        pass
    return fallback

async def show_products_for_panel(call: CallbackQuery, prods: List[Tuple], header: str):
    """USER SHOP: one product button; all duration/price plans stay inside product config."""
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    groups = {}
    for p in prods:
        prod_id, product_name, normal_price, stock, reseller_price, validity, device = p
        groups.setdefault((product_name or "").strip().lower(), []).append(p)

    header_text = (header or "").upper()
    text = (
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        f"{get_emoji('product_store')} <b>{header_text} PRODUCTS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{get_emoji('point_down')} <b>Select a product to view its plans:</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯"
    )

    for _, rows in sorted(groups.items(), key=lambda x: x[0]):
        first = rows[0]
        prod_id, product_name = first[0], first[1]
        product_name = product_name or "PRODUCT"
        product_emoji_id = _resolve_product_custom_emoji(prod_id=prod_id)
        button_emoji = product_emoji_id or get_emoji_icon("product_store")
        kb.inline_keyboard.append([InlineKeyboardButton(text=product_name, callback_data=f"productcfg_{prod_id}", icon_custom_emoji_id=(button_emoji or None), style="success")])

    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK TO PANELS", callback_data="menu_shop", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("cat_"))
async def view_products_for_category(call: CallbackQuery):
    """USER SHOP: Category -> Product -> Plans. No separate panel-brand step."""
    category = call.data.split("cat_", 1)[1]
    prods = db_query(
        "SELECT id, name, price_inr, stock, reseller_price, validity, device_limit, panel_name "
        "FROM products WHERE category LIKE ? AND is_active=1 ORDER BY name, duration_days, id",
        (category + "%",), fetchall=True
    ) or []
    if not prods:
        return await call.answer("No products available in this category yet.", show_alert=True)

    # Keep one button per Product. All durations stay inside productcfg_.
    groups = {}
    for row in prods:
        pid, name, price, stock, rprice, validity, device, panel_name = row
        key = (name or "").strip().lower()
        if key and key not in groups:
            groups[key] = row

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    category_emoji_id = get_category_emoji(category)
    category_emoji = f'<tg-emoji emoji-id="{category_emoji_id}">✨</tg-emoji>' if category_emoji_id and str(category_emoji_id).isdigit() else get_emoji("product_store")
    text = (
        "╭━━━━━━━━━━━━━━━━━━━━━━━━━━╮\n"
        f"{category_emoji} <b>{category.upper()}</b>\n"
        "<b>Select Product</b>\n"
        "╰━━━━━━━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"{get_emoji('point_down')} <b>Available Products:</b>"
    )
    for row in sorted(groups.values(), key=lambda x: (str(x[1] or '').lower(), str(x[7] or '').lower())):
        pid, name, *_rest = row
        product_name = (name or "PRODUCT").strip()
        product_emoji_id = _resolve_product_custom_emoji(prod_id=pid)
        button_emoji = product_emoji_id or get_emoji_icon("product_store")
        kb.inline_keyboard.append([InlineKeyboardButton(text=product_name, callback_data=f"productcfg_{pid}", icon_custom_emoji_id=(button_emoji or None), style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="menu_shop", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("pnl_"))
async def view_products_for_panel(call: CallbackQuery):
    parts = call.data.split("pnl_", 1)[1].split("_", 1)
    if len(parts) != 2:
        return await call.answer("Invalid selection.", show_alert=True)
    category, panel_name = parts
    prods = db_query(
        "SELECT id, name, price_inr, stock, reseller_price, validity, device_limit FROM products WHERE category LIKE ? AND panel_name LIKE ? AND is_active=1 ORDER BY name, duration_days, id",
        (category + "%", panel_name + "%"), fetchall=True
    ) or []
    if not prods:
        return await call.answer("No products found for this panel.", show_alert=True)
    await show_products_for_panel(call, prods, f"{category} - {panel_name}")

@dp.callback_query(F.data.startswith("productcfg_"))
async def view_product_config(call: CallbackQuery):
    """USER SHOP: Product -> Plans. All durations remain inside the same Product."""
    try:
        base_id = int(call.data.split("productcfg_", 1)[1])
    except Exception:
        return await call.answer("Invalid product.", show_alert=True)

    base = db_query(
        "SELECT category, panel_name, name, premium_emoji_id FROM products WHERE id=? AND is_active=1",
        (base_id,), fetchone=True
    )
    if not base:
        return await call.answer("Product not found.", show_alert=True)

    category, panel_name, product_name, premium_emoji_id = base
    # Product emoji belongs to the product, not to each plan row.  Read it from
    # the parent product row when the selected plan does not carry its own copy.
    if not premium_emoji_id:
        premium_emoji_id = _resolve_product_custom_emoji(
            category=category, panel_name=panel_name, product_name=product_name
        )
    rows = db_query(
        "SELECT id, price_inr, reseller_price, stock, validity, duration_days, "
        "is_active, delivery_mode, device_limit "
        "FROM products WHERE category=? AND panel_name=? AND name=? AND is_active=1 "
        "AND COALESCE(is_product_parent,0)=0 "
        "ORDER BY CASE WHEN duration_days IS NULL OR duration_days=0 THEN 999999 ELSE duration_days END, id",
        (category, panel_name, product_name), fetchall=True
    ) or []
    if not rows:
        return await call.answer("No plans found for this product.", show_alert=True)

    user = db_query("SELECT is_reseller, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_reseller = bool(user[0]) if user else False
    is_vip = bool(user[1]) if user else False

    # Product title: equal-width boxed layout with automatic wrapping.
    # IMPORTANT: never truncate the product name and never append "...".
    store_title = f"{category} - {product_name} PACKAGES" if category else f"{product_name} PACKAGES"
    product_emoji = str(premium_emoji_id or "").strip()
    if not product_emoji.isdigit():
        product_emoji = get_emoji_icon("product_store") or ""
    product_icon = custom_emoji(product_emoji, "✨") if product_emoji else "✨"

    BOX_WIDTH = 28
    inner_width = BOX_WIDTH - 2
    title_words = ("✨ " + store_title.upper().strip()).split()
    title_lines = []
    current_line = ""

    for word in title_words:
        candidate = f"{current_line} {word}".strip()
        if current_line and len(candidate) > inner_width:
            title_lines.append(current_line)
            current_line = word
        else:
            current_line = candidate
    if current_line:
        title_lines.append(current_line)

    # If a single word is longer than the available width, split it safely.
    safe_lines = []
    for line in title_lines:
        while len(line) > inner_width:
            safe_lines.append(line[:inner_width])
            line = line[inner_width:]
        if line:
            safe_lines.append(line)

    border_top = "╭" + "━" * BOX_WIDTH + "╮"
    border_bottom = "╰" + "━" * BOX_WIDTH + "╯"
    boxed_lines = [border_top]
    for line in safe_lines:
        left_pad = (inner_width - len(line)) // 2
        right_pad = inner_width - len(line) - left_pad
        boxed_lines.append("│" + (" " * left_pad) + line + (" " * right_pad) + "│")
    boxed_lines.append(border_bottom)
    text = "\n".join(boxed_lines) + "\n\n"

    # Replace only the first visible sparkle with the configured Telegram custom emoji.
    # Keep the already calculated spaces unchanged so the box remains perfectly aligned.
    if boxed_lines:
        boxed_lines[1] = boxed_lines[1].replace("✨", product_icon, 1)
    text = "\n".join(boxed_lines) + "\n\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for pid, price, rprice, stock, validity, days, active, delivery_mode, device_limit in rows:
        price = safe_float(price)
        rprice = safe_float(rprice)
        label = (validity or (f"{days} Days" if days else "Lifetime")).strip()
        device_text = (device_limit or "1 Device").strip()
        mode = (delivery_mode or "MANUAL").upper()

        if mode == "API":
            # API plans do not have manual key rows.  A configured PID is treated
            # as available; removing/clearing the PID makes the plan OUT OF STOCK.
            api_row = db_query("SELECT api_pid FROM products WHERE id=?", (pid,), fetchone=True)
            in_stock = bool(active) and bool(api_row and str(api_row[0] or "").strip())
        else:
            live = db_query("SELECT COUNT(*) FROM product_keys WHERE product_id=? AND is_used=0", (pid,), fetchone=True)
            live_stock = int(live[0] or 0) if live else int(stock or 0)
            in_stock = bool(active) and live_stock > 0
        delivery_text = "📦 ✅ STOCK" if in_stock else "📦 ❌ OUT OF STOCK"

        usd_regular = price / USDT_TO_INR if USDT_TO_INR else 0
        usd_reseller = rprice / USDT_TO_INR if USDT_TO_INR else 0
        if is_reseller:
            # Resellers see both prices, with the regular/user price crossed out
            # just like the requested reference screenshot.
            price_lines = (
                f"💰 <b><s>Regular Price: {fmt_curr(price)} (~ ${usd_regular:.2f})</s></b>\n"
                f"👑 <b>Reseller Price: {fmt_curr(rprice)} (~ ${usd_reseller:.2f})</b>\n"
            )
        else:
            # Regular users must never see the reseller price.
            price_lines = f"💰 <b>Regular Price: {fmt_curr(price)} (~ ${usd_regular:.2f})</b>\n"
        text += (
            f"✨ ⏱ <b>Validity: {label}</b>\n"
            f"{price_lines}"
            f"📱 <b>Limit: {device_text} | {delivery_text}</b>\n\n"
        )

        display_price = rprice if is_reseller else price
        if is_vip and not is_reseller:
            display_price = price * (1 - VIP_DISCOUNT_PERCENTAGE / 100)
        usd_display = display_price / USDT_TO_INR if USDT_TO_INR else 0
        if in_stock:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"🛒 Buy {label} - {fmt_curr(display_price)} (~ ${usd_display:.2f})",
                    callback_data=f"buy_{pid}",
                    icon_custom_emoji_id=get_emoji_icon("product_store"),
                    style="success"
                )
            ])
        else:
            kb.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"❌ {label} - OUT OF STOCK",
                    callback_data="ignore_stock_click",
                    icon_custom_emoji_id=get_emoji_icon("product_store"),
                    style="danger"
                )
            ])

    text += "✨ <b>Select package below to instantly purchase:</b>"
    kb.inline_keyboard.append([
        InlineKeyboardButton(
            text="BACK TO PRODUCTS",
            callback_data=f"cat_{category}",
            icon_custom_emoji_id=get_emoji_icon("back"),
            style="danger"
        )
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

@dp.callback_query(F.data == "ignore_stock_click")
async def ignore_stock_click(call: CallbackQuery):
    await call.answer("⚠️ This duration is completely Out of Stock! Admins have been notified to refill.", show_alert=True)

async def _api_purchase(prod_id: int, user_id: int, android_id: str = ""):
    p = db_query("SELECT name, price_inr, stock, apk_link, validity, device_limit, category, reseller_price, panel_name, delivery_mode, api_provider, api_pid, api_duration, api_android_id_required, COALESCE(is_product_parent,0) FROM products WHERE id=?", (prod_id,), fetchone=True)
    if not p: return None, "Product not found"
    if p[-1]: return None, "This product has no plan yet"
    mode = (p[9] or "MANUAL").upper()
    if mode != "API": return None, "not_api"
    provider = (p[10] or "").upper()
    pid = p[11] or ""
    duration = p[12] or p[4] or ""
    if not pid: return None, "API product PID is not configured"
    try:
        async with aiohttp.ClientSession() as session:
            if provider == "PANELSTORE":
                key = get_setting("panelstore_api_key", "")
                if not key: return None, "PanelStore API key is not configured"
                payload = {"key": key, "action": "order", "pid": pid, "quantity": 1, "custom_notes": str(user_id)}
                async with session.post("https://www.panelstore.shop/api/v1/index.php", json=payload, timeout=35) as r:
                    data = await r.json(content_type=None)
                    if r.status != 200 or str(data.get("status", "")).lower() not in {"success", "completed"}:
                        return None, str(data.get("message", "PanelStore order failed"))
                    key_text = data.get("license_key") or data.get("key") or data.get("license") or data.get("data", {}).get("license_key")
                    if not key_text: return None, "PanelStore returned success without a license key"
                    return str(key_text), "ok"
            if provider in {"BANTIBHAIYA", "BANTI BHAIYA"}:
                api_key = get_setting("bantibhaiya_api_key", ""); master = get_setting("bantibhaiya_master_key", "")
                if not api_key or not master: return None, "BantiBhaiya API key/master key is not configured"
                form = {"api_key": api_key, "action": "buy", "product_id": pid, "duration": duration}
                if android_id: form["android_id"] = android_id
                headers = {"Content-Type": "application/x-www-form-urlencoded", "x-master-key": master}
                async with session.post("https://bantibhaiya.to/api/reseller_v1.php", data=form, headers=headers, timeout=35) as r:
                    data = await r.json(content_type=None)
                    if r.status != 200: return None, f"BantiBhaiya HTTP {r.status}"
                    ok = str(data.get("status", data.get("success", ""))).lower() in {"success", "true", "1", "completed"}
                    if not ok: return None, str(data.get("message", data.get("error", "BantiBhaiya order failed")))
                    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
                    key_text = data.get("license_key") or data.get("key") or data.get("license") or data.get("token") or nested.get("license_key") or nested.get("key")
                    if not key_text: return None, "BantiBhaiya returned success without a license key"
                    return str(key_text), "ok"
            return None, f"Unknown API provider: {provider}"
    except Exception as e:
        return None, f"API connection error: {e}"

async def complete_product_purchase(user_id: int, prod_id: int, reply_obj, android_id: str = ""):
    prod = db_query("SELECT name, price_inr, stock, apk_link, validity, device_limit, category, reseller_price, panel_name, delivery_mode, api_provider, api_pid, api_duration, api_android_id_required, COALESCE(is_product_parent,0) FROM products WHERE id=?", (prod_id,), fetchone=True)
    user = db_query("SELECT balance, referred_by, is_reseller, total_saved, is_vip FROM users WHERE user_id=?", (user_id,), fetchone=True)
    if not prod or not user:
        if isinstance(reply_obj, CallbackQuery): return await reply_obj.answer("❌ Product/User not found.", show_alert=True)
        return await reply_obj.answer("❌ Product/User not found.")
    if prod[-1]:
        if isinstance(reply_obj, CallbackQuery):
            return await reply_obj.answer("❌ This product has no plan yet. Please add a plan first.", show_alert=True)
        return await reply_obj.answer("❌ This product has no plan yet. Please add a plan first.")
    normal = safe_float(prod[1]); reseller = safe_float(prod[7])
    reseller = get_custom_reseller_price(user_id, prod[0], prod[4], reseller) if bool(user[2]) else reseller
    base = reseller if bool(user[2]) else normal
    final_price = base - (base * VIP_DISCOUNT_PERCENTAGE / 100) if bool(user[4]) else base
    if safe_float(user[0]) < final_price:
        msg = f"❌ Insufficient Balance! You need {fmt_curr(final_price)}."
        if isinstance(reply_obj, CallbackQuery): return await reply_obj.answer(msg, show_alert=True)
        return await reply_obj.answer(msg)
    mode = (prod[9] or "MANUAL").upper()
    delivered_key = ""
    if mode == "API":
        if int(prod[13] or 0) and not android_id:
            if isinstance(reply_obj, CallbackQuery):
                # User enters Android ID in a normal message after this prompt.
                state = getattr(reply_obj, "_fsm_state", None)
                await reply_obj.message.edit_text("📱 <b>Android ID Required</b>\n\nSend your Android ID to continue this API order.", reply_markup=back_kb("menu_shop"), parse_mode='HTML')
                return "NEED_ANDROID_ID"
        delivered_key, api_status = await _api_purchase(prod_id, user_id, android_id)
        if api_status != "ok":
            msg = f"❌ <b>API Order Failed:</b> {api_status}\n\nNo wallet amount was deducted."
            if isinstance(reply_obj, CallbackQuery): return await reply_obj.message.edit_text(msg, reply_markup=back_kb("menu_shop"), parse_mode='HTML')
            return await reply_obj.answer(msg, parse_mode='HTML')
    else:
        # Reserve exactly one unused key atomically so double-clicks/concurrent
        # callbacks cannot consume duplicate keys or corrupt the stock counter.
        conn = sqlite3.connect('yp_shop.db')
        try:
            conn.execute("BEGIN IMMEDIATE")
            key_data = conn.execute(
                "SELECT id, key_text FROM product_keys WHERE product_id=? AND is_used=0 ORDER BY id LIMIT 1",
                (prod_id,)
            ).fetchone()
            if not key_data:
                conn.rollback()
                db_query("UPDATE products SET stock=(SELECT COUNT(*) FROM product_keys WHERE product_id=? AND is_used=0) WHERE id=?", (prod_id, prod_id))
                msg = "❌ This plan is out of stock. No wallet amount was deducted."
                if isinstance(reply_obj, CallbackQuery): return await reply_obj.answer(msg, show_alert=True)
                return await reply_obj.answer(msg)
            delivered_key = str(key_data[1])
            updated = conn.execute(
                "UPDATE product_keys SET is_used=1 WHERE id=? AND is_used=0",
                (key_data[0],)
            ).rowcount
            if updated != 1:
                conn.rollback()
                msg = "❌ This key was just purchased by another user. Please try again."
                if isinstance(reply_obj, CallbackQuery): return await reply_obj.answer(msg, show_alert=True)
                return await reply_obj.answer(msg)
            remaining = conn.execute(
                "SELECT COUNT(*) FROM product_keys WHERE product_id=? AND is_used=0",
                (prod_id,)
            ).fetchone()[0]
            conn.execute("UPDATE products SET stock=? WHERE id=?", (int(remaining or 0), prod_id))
            conn.commit()
        except Exception as _claim_error:
            try: conn.rollback()
            except Exception: pass
            logger.exception(f"Key claim failed for product {prod_id}: {_claim_error}")
            msg = "❌ Could not reserve a key right now. No wallet amount was deducted."
            if isinstance(reply_obj, CallbackQuery): return await reply_obj.answer(msg, show_alert=True)
            return await reply_obj.answer(msg)
        finally:
            conn.close()
    savings = normal - final_price
    db_query("UPDATE users SET balance=?, spent=spent+?, orders_count=orders_count+1, total_saved=total_saved+? WHERE user_id=?", (user[0] - final_price, final_price, savings, user_id))
    if user[1]:
        commission = final_price * 0.15
        db_query("UPDATE users SET balance=balance+?, referral_earned=referral_earned+? WHERE user_id=?", (commission, commission, user[1]))
        try: await bot.send_message(user[1], f"🎁 <b>Referral Bonus Added!</b>\nYou earned {fmt_curr(commission)}.", parse_mode='HTML')
        except Exception: pass
    full_name = f"{prod[6]} - {prod[8]} ({prod[0]})"
    db_query("INSERT INTO orders (user_id, product_name, price_paid, delivered_key, purchase_date) VALUES (?, ?, ?, ?, ?)", (user_id, full_name, final_price, delivered_key, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log_activity(user_id, "PURCHASE_SUCCESS", f"Product: {full_name}, Paid: {final_price}, Mode: {mode}, Provider: {prod[10]}")
    await send_advanced_notification(user_id, "ORDER", final_price, product=full_name, key=delivered_key)
    await send_payment_proof(
        user_id,
        prod[0],
        prod[4],
        final_price,
        delivered_key,
        quantity=1,
        category=prod[6],
        panel_name=prod[8]
    )
    # Private data channel gets the complete purchase/user record; public proof never exposes the key.
    user_full = db_query(
        "SELECT first_name, phone, username, is_reseller, is_vip, balance FROM users WHERE user_id=?",
        (user_id,), fetchone=True
    )
    u_name = user_full[0] if user_full and user_full[0] else "Unknown"
    u_phone = user_full[1] if user_full and user_full[1] else "Not Provided"
    u_username = f"@{user_full[2]}" if user_full and user_full[2] else "None"
    u_role = "Reseller" if user_full and user_full[3] else ("VIP" if user_full and user_full[4] else "Regular")
    private_details = (
        f"🛍️ <b>NEW KEY PURCHASED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Name:</b> {u_name}\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"📱 <b>Phone:</b> {u_phone}\n"
        f"🔗 <b>Username:</b> {u_username}\n"
        f"🏷 <b>Status:</b> {u_role}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 <b>Category:</b> {prod[6]}\n"
        f"📁 <b>Panel:</b> {prod[8]}\n"
        f"🎮 <b>Game/Product:</b> {prod[0]}\n"
        f"⏳ <b>Duration:</b> {prod[4]}\n"
        f"🔢 <b>Quantity:</b> 1\n"
        f"💰 <b>Amount Paid:</b> {fmt_curr(final_price)}\n"
        f"📱 <b>Device Limit:</b> {prod[5]}\n"
        f"🔌 <b>Delivery:</b> {mode} {('('+prod[10]+')') if mode == 'API' else ''}\n"
        f"🔑 <b>Key:</b> <code>{delivered_key}</code>\n"
        f"📅 <b>Time:</b> {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}"
    )
    # Full purchase record belongs in the private Data Save channel.
    await send_private_data_log("KEY_PURCHASE", user_id, private_details)

    # Keep the dedicated Key Purchase channel separate from the public
    # Payment Proof channel. If both settings currently point to the same
    # channel, NEVER post the private key-purchase log there, otherwise the
    # public proof channel will show the unwanted "VICKY X KEY PURCHASE" block.
    proof_channel = normalize_channel_target(get_setting("payment_proof_channel", "").strip())
    key_purchase_channel = normalize_channel_target(get_setting("key_purchase_channel", "").strip())
    if key_purchase_channel and key_purchase_channel != proof_channel:
        await send_key_purchase_channel_log(
            user_id,
            f"📦 <b>Product:</b> {prod[0]}\n"
            f"⏳ <b>Duration:</b> {prod[4]}\n"
            f"🔑 <b>Key:</b> <code>{delivered_key}</code>\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>"
        )

    # User-facing delivery message: keep it exactly focused on the purchase.
    # APK links and the Join/Open Store button are intentionally removed.
    msg = (
        "✅ <b>Payment Successful!</b>\n\n"
        f"🎮 <b>Game:</b> {prod[6]}\n"
        f"📦 <b>Product:</b> {prod[0]}\n"
        f"⏳ <b>Duration:</b> {prod[4]}\n"
        "📦 <b>Quantity:</b> 1\n"
        f"🔑 <b>Key:</b> <code>{delivered_key}</code>\n\n"
        "🙏 <b>Thank you for your purchase!</b>"
    )
    # No APK link and no Join/Open Store button on the purchase result.
    # A Back button returns the user to the main bot menu. Its text/style/emoji
    # can also be changed from the Admin -> Button Designer.
    purchase_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_main", style="danger")]
    ])
    # Telegram can return DOCUMENT_INVALID when one of the configured custom-emoji
    # document IDs is invalid/expired, or when a button icon points to an invalid
    # custom-emoji document. Do not let that hide a successful purchase from the
    # user. Retry once with the premium emoji markup and icons removed.
    async def _deliver_purchase_result():
        try:
            if isinstance(reply_obj, CallbackQuery):
                await reply_obj.message.edit_text(
                    msg, reply_markup=purchase_kb, disable_web_page_preview=True, parse_mode='HTML'
                )
            else:
                await reply_obj.answer(
                    msg, reply_markup=purchase_kb, disable_web_page_preview=True, parse_mode='HTML'
                )
            return True
        except Exception as _send_error:
            if "DOCUMENT_INVALID" not in str(_send_error).upper():
                raise
            logger.warning("Purchase result contained an invalid Telegram custom emoji/document; retrying with safe fallback: %s", _send_error)
            # Replace every custom emoji entity with its visible fallback character.
            safe_msg = re.sub(r'<tg-emoji\s+emoji-id="[^"]+">(.*?)</tg-emoji>', r'\1', msg, flags=re.S)
            safe_msg = re.sub(r'<tg-emoji\s+emoji-id=\'[^\']+\'>(.*?)</tg-emoji>', r'\1', safe_msg, flags=re.S)
            # Also remove custom-emoji icons from every button.
            safe_rows = []
            try:
                for row in (purchase_kb.inline_keyboard if purchase_kb else []):
                    safe_row = []
                    for btn in row:
                        data = btn.model_dump(exclude_none=True) if hasattr(btn, "model_dump") else dict(btn)
                        data.pop("icon_custom_emoji_id", None)
                        safe_row.append(InlineKeyboardButton(**data))
                    safe_rows.append(safe_row)
                safe_kb = InlineKeyboardMarkup(inline_keyboard=safe_rows) if safe_rows else None
            except Exception:
                safe_kb = back_kb("menu_shop")
            if isinstance(reply_obj, CallbackQuery):
                await reply_obj.message.edit_text(
                    safe_msg, reply_markup=safe_kb, disable_web_page_preview=True, parse_mode='HTML'
                )
            else:
                await reply_obj.answer(
                    safe_msg, reply_markup=safe_kb, disable_web_page_preview=True, parse_mode='HTML'
                )
            return True

    await _deliver_purchase_result()
    return "OK"

@dp.callback_query(F.data.startswith("buy_"))
async def process_buy(call: CallbackQuery, state: FSMContext):
    prod_id = int(call.data.split("_", 1)[1])
    prod = db_query("SELECT delivery_mode, api_android_id_required FROM products WHERE id=?", (prod_id,), fetchone=True)
    if prod and (prod[0] or "MANUAL").upper() == "API" and int(prod[1] or 0):
        await state.update_data(pending_buy_prod_id=prod_id)
        await state.set_state(UserStates.user_android_id)
        return await call.message.edit_text("📱 <b>Android ID Required</b>\n\nSend your Android ID to continue this API order.", reply_markup=back_kb("menu_shop"), parse_mode='HTML')
    await complete_product_purchase(call.from_user.id, prod_id, call)

@dp.message(UserStates.user_android_id)
async def receive_android_id(m: Message, state: FSMContext):
    data = await state.get_data(); prod_id = data.get("pending_buy_prod_id")
    android_id = m.text.strip()
    if not prod_id or len(android_id) < 4: return await m.answer("❌ Invalid Android ID. Please send a valid value.")
    db_query("UPDATE users SET android_id=? WHERE user_id=?", (android_id, m.from_user.id))
    await state.clear()
    await complete_product_purchase(m.from_user.id, int(prod_id), m, android_id)

# ==============================================================================
# 14. USER DASHBOARD, FILES, VIP, RESELLER, ORDERS, PROFILE, REFERRAL
# ==============================================================================
@dp.callback_query(F.data == "menu_all_files")
async def all_files_handler(call: CallbackQuery):
    link_q = db_query("SELECT value FROM settings WHERE key='all_files_link'", fetchone=True)
    link = link_q[0] if link_q and link_q[0] != 'None' else None
    if link:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Access Download Channel ↗️", url=link, icon_custom_emoji_id=get_emoji_icon("download"), style="success")],
            [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        text = get_ui_text("download_files")
        await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    else:
        await call.answer("⚠️ Admin has not configured the private download channel link yet.", show_alert=True)

@dp.callback_query(F.data == "menu_payment_proof")
async def menu_payment_proof(call: CallbackQuery):
    # Answer immediately so Telegram does not expire the callback while settings
    # are being read/processed. The global safe wrapper handles already-stale IDs.
    await call.answer()

    channel=get_setting("payment_proof_channel","").strip()
    link=get_setting("payment_proof_link","").strip() or get_setting("purchase_channel_link","").strip()
    if not link:
        if channel.startswith("@"):
            link="https://t.me/" + channel[1:]
        elif re.match(r"^https?://t\.me/", channel):
            link=channel
    if not channel and not link:
        await call.message.edit_text(
            "⚠️ <b>Payment Proof is not configured yet.</b>\n\n"
            "Admin must set the Payment Proof Channel/Link first.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
            ]),
            parse_mode="HTML"
        )
        return
    if link:
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧾 Open Payment Proofs",url=link,style="success")],
            [InlineKeyboardButton(text="BACK",callback_data="back_main",icon_custom_emoji_id=get_emoji_icon("back"),style="danger")]
        ])
        await call.message.edit_text(
            get_ui_text("payment_proof_menu"),
            reply_markup=kb,parse_mode='HTML'
        )
    else:
        await call.message.edit_text(
            "⚠️ <b>Payment Proof Channel is configured, but no public link is available.</b>\n\n"
            "Set a public @channel username or a t.me link in Admin Payment Proof settings.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
            ]),
            parse_mode="HTML"
        )

@dp.callback_query(F.data == "menu_vip_dash")
async def vip_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip, vip_since FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    is_vip = bool(u[1])
    status_str = "🟢 Active (Lifetime)" if is_vip else "🔴 Not Subscribed"
    text = get_ui_text("vip_menu", vip_status=status_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if is_vip:
        text += f"\n📅 <b>Member Since:</b> {u[2]}\n\nEnjoy your permanent 15% discount!"
    else:
        text += f"\n\n💳 <b>Your Current Balance:</b> {fmt_curr(u[0])}\n"
        if u[0] >= VIP_PRICE_INR: kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ Purchase VIP for {fmt_curr(VIP_PRICE_INR)}", callback_data="execute_vip_upgrade", style="success")])
        else:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Need {fmt_curr(VIP_PRICE_INR)} to Upgrade", callback_data="ignore_stock_click", style="danger")])
            kb.inline_keyboard.append([InlineKeyboardButton(text="💳 Add Balance Now", callback_data="menu_add_balance", style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_vip_upgrade")
async def execute_vip_upgrade(call: CallbackQuery):
    u = db_query("SELECT balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ You are already a VIP Member!", show_alert=True)
    if u[0] < VIP_PRICE_INR: return await call.answer(f"❌ Your balance dropped below {VIP_PRICE_INR}.", show_alert=True)
    new_balance = u[0] - VIP_PRICE_INR
    now_date = datetime.now().strftime("%Y-%m-%d")
    db_query("UPDATE users SET balance=?, is_vip=1, vip_since=? WHERE user_id=?", (new_balance, now_date, call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_VIP")
    try: await bot.send_message(ADMIN_ID, f"🌟 <b>NEW VIP UPGRADE</b>\n👤 User ID: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except: pass
    await call.answer("🎉 Upgrade Successful! You are now a VIP Member.", show_alert=True)
    await vip_dashboard(call)

@dp.callback_query(F.data == "menu_reseller_dash")
async def reseller_dashboard(call: CallbackQuery):
    u = db_query("SELECT balance, is_reseller, reseller_since, total_saved FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    system_status = status_check[0] if status_check else "ON"
    setup_fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = safe_float(get_setting("reseller_min_balance", "500.0"))
    if u[1]: 
        text = (f"{get_emoji('shield_icon')} <b><u>— RESELLER DASHBOARD —</u></b> {get_emoji('shield_icon')}\n\n🟢 <b>Status:</b> Active\n📅 <b>Since:</b> {u[2]}\n{get_emoji('money_icon')} <b>Total Saved:</b> {fmt_curr(u[3])}\n\n🎉 You are enjoying exclusive wholesale prices on all products!")
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
        await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        return
    if system_status == "OFF": return await call.answer("⚠️ Wholesale / Reseller registrations are currently closed by Admin.", show_alert=True)
    text = (f"⚡ <b><u>— BECOME A RESELLER —</u></b> ⚡\n\nUpgrade your account to access wholesale <b>Reseller Prices</b>!\n\n📋 <b>Requirements to Upgrade:</b>\n1️⃣ Must have a minimum balance of <b>{fmt_curr(min_balance)}</b>.\n2️⃣ A one-time setup fee of <b>{fmt_curr(setup_fee)}</b> will be deducted.\n\n💳 <b>Your Current Balance:</b> {fmt_curr(u[0])}\n")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if u[0] >= min_balance: kb.inline_keyboard.append([InlineKeyboardButton(text=f"✅ Pay {fmt_curr(setup_fee)} & Become Reseller", callback_data="execute_reseller_upgrade", style="success")])
    else:
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ Insufficient Balance (Need {fmt_curr(min_balance)})", callback_data="ignore_stock_click", style="danger")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="💳 Add Balance", callback_data="menu_add_balance", style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "execute_reseller_upgrade")
async def execute_reseller_upgrade(call: CallbackQuery):
    setup_fee = safe_float(get_setting("reseller_setup_fee", "200.0"))
    min_balance = safe_float(get_setting("reseller_min_balance", "500.0"))
    u = db_query("SELECT balance, is_reseller FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    if u[1]: return await call.answer("⚠️ You are already a Reseller!", show_alert=True)
    if u[0] < min_balance: return await call.answer(f"❌ Your balance dropped below {fmt_curr(min_balance)}. Please top up.", show_alert=True)
    new_balance = u[0] - setup_fee
    db_query("UPDATE users SET balance=?, is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?", (new_balance, datetime.now().strftime("%Y-%m-%d"), call.from_user.id))
    log_activity(call.from_user.id, "UPGRADED_RESELLER")
    try: await bot.send_message(ADMIN_ID, f"👑 <b>NEW RESELLER UPGRADE</b>\n👤 User ID: <code>{call.from_user.id}</code>", parse_mode='HTML')
    except: pass
    await call.answer("🎉 Upgrade Successful! Welcome to the Reseller tier.", show_alert=True)
    await reseller_dashboard(call)

@dp.callback_query(F.data == "menu_orders")
async def my_orders(call: CallbackQuery):
    orders = db_query("SELECT product_name, delivered_key, purchase_date, price_paid FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 10", (call.from_user.id,), fetchall=True)
    if not orders: return await call.message.edit_text(get_ui_text("history_empty"), reply_markup=back_kb(), parse_mode='HTML')
    text = get_ui_text("history_header") + "\n\n"
    for o in orders: text += f"📦 <b>{o[0]}</b> ({fmt_curr(o[3])})\n🔑 <code>{o[1]}</code>\n📅 <i>{o[2]}</i>\n━━━━━━━━━━━━━━━━\n"
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "menu_profile")
async def show_profile(call: CallbackQuery):
    u = db_query("SELECT user_id, first_name, account_type, balance, orders_count, spent, referrals_count, joined_date, is_reseller, reseller_since, total_saved, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    acc_type_display = []
    if u[8]: acc_type_display.append(f"{get_emoji('reseller')} Reseller")
    if u[11]: acc_type_display.append(f"{get_emoji('vip')} VIP")
    type_str = " | ".join(acc_type_display) if acc_type_display else f"{get_emoji('regular_user')} Regular User"
    reseller_metrics = ""
    if u[8]:
        reseller_metrics = (
            f"{get_emoji('shield_icon')} <b>— RESELLER METRICS —</b> {get_emoji('shield_icon')}\n"
            f"{get_emoji('money_icon')} <b>Total Saved via Reseller:</b> {fmt_curr(u[10])}\n\n"
        )
    text = get_ui_text(
        "profile_menu",
        user_id=u[0], user_name=u[1], account_type=type_str,
        balance=fmt_curr(u[3]), orders_count=u[4], spent=fmt_curr(u[5]),
        referrals_count=u[6], joined_date=u[7], reseller_metrics=reseller_metrics
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Redeem Promo Code",
            callback_data="redeem_coupon",
            icon_custom_emoji_id=get_emoji_icon('redeem_icon'),
            style="success"
        )],
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "redeem_coupon")
async def redeem_coupon_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(get_ui_text("redeem_prompt"), reply_markup=back_kb("menu_profile"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_redeem)

@dp.message(UserStates.wait_for_redeem)
async def process_redeem(m: Message, state: FSMContext):
    code = m.text.strip().upper()
    user_id = m.from_user.id
    if db_query("SELECT * FROM redeemed WHERE user_id=? AND code=?", (user_id, code), fetchone=True):
        await m.answer("❌ Anti-Fraud Alert: You already redeemed this unique code!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        await state.clear()
        return
    coupon = db_query("SELECT amount, uses_left FROM coupons WHERE code=?", (code,), fetchone=True)
    if not coupon: await m.answer("❌ Invalid or Expired Code!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    elif coupon[1] <= 0: await m.answer("❌ This code's usage limit has been fully claimed by other users.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    else:
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (coupon[0], user_id))
        db_query("UPDATE coupons SET uses_left = uses_left - 1 WHERE code=?", (code,))
        db_query("INSERT INTO redeemed (user_id, code) VALUES (?, ?)", (user_id, code))
        log_activity(user_id, "PROMO_REDEEMED", f"Code: {code}, Amount: {coupon[0]}")
        await m.answer(f"🎉 <b>Success!</b>\nSafely added {fmt_curr(coupon[0])} to your balance!", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
        try:
            user_info = db_query("SELECT first_name FROM users WHERE user_id=?", (user_id,), fetchone=True)
            uname = user_info[0] if user_info else "Unknown User"
            await bot.send_message(ADMIN_ID, f"🎟 <b>PROMO CODE REDEEMED!</b>\n👤 User: {uname} (<code>{user_id}</code>)\n🔖 Code: <b>{code}</b>\n💵 Amount: {fmt_curr(coupon[0])}", parse_mode='HTML')
        except Exception: pass
    await state.clear()

@dp.callback_query(F.data == "menu_referral")
async def show_referral(call: CallbackQuery):
    u = db_query("SELECT referrals_count, referral_earned FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{call.from_user.id}"
    text = get_ui_text("referral_menu", referrals_count=u[0], earned=fmt_curr(u[1]), ref_link=ref_link)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

# ==============================================================================
# 15. LUDO / DICE SPIN
# ==============================================================================
@dp.callback_query(F.data == "menu_spin_landing")
async def lucky_spin_landing(call: CallbackQuery):
    status_check = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    spin_status = status_check[0] if status_check else "ON"
    if spin_status == "OFF": return await call.answer("⚠️ Lucky Ludo Spin is currently disabled by Admin.", show_alert=True)
    await call.message.edit_text(f"{get_emoji('ludo_spin')} <b><u>— LUDO SPIN —</u></b> {get_emoji('ludo_spin')}\n\nTest your luck! You can spin once every 24 hours.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Spin Dice Now!", callback_data="execute_spin", style="success")], 
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ]), parse_mode='HTML')

@dp.callback_query(F.data == "execute_spin")
async def execute_spin(call: CallbackQuery):
    status_check = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    if status_check and status_check[0] == "OFF": return await call.answer("⚠️ Lucky Spin is disabled.", show_alert=True)
    u = db_query("SELECT last_spin, balance, is_vip FROM users WHERE user_id=?", (call.from_user.id,), fetchone=True)
    now = datetime.now()
    if u[0] and now < datetime.strptime(u[0], "%Y-%m-%d %H:%M:%S") + timedelta(hours=24):
        return await call.message.edit_text("❌ <b>Cooldown Active!</b>\nYou already played today. Come back tomorrow.", reply_markup=back_kb(), parse_mode='HTML')
    await call.message.delete()
    dice_msg = await bot.send_dice(chat_id=call.message.chat.id, emoji="🎲")
    await asyncio.sleep(SPIN_DELAY_SECONDS) 
    dice_val = dice_msg.dice.value
    limit_check = db_query("SELECT value FROM settings WHERE key='daily_spin_limit'", fetchone=True)
    limit = safe_float(limit_check[0]) if limit_check else 50.0
    rewards_db = db_query("SELECT amount FROM spin_rewards WHERE amount <= ?", (limit,), fetchall=True)
    rewards_list = [r[0] for r in rewards_db] if rewards_db else [0.0]
    reward = random.choice(rewards_list)
    if bool(u[2]) and reward > 0: reward = reward * 2.0
    new_bal = u[1] + reward
    db_query("UPDATE users SET balance=?, last_spin=? WHERE user_id=?", (new_bal, now.strftime("%Y-%m-%d %H:%M:%S"), call.from_user.id))
    log_activity(call.from_user.id, "PLAYED_SPIN", f"Reward: {reward}, Dice: {dice_val}")
    msg = get_ui_text("lucky_dice_result", dice_value=dice_val, won_amount=fmt_curr(reward), new_balance=fmt_curr(new_bal))
    if bool(u[2]) and reward > 0: msg += "\n\n<i>🌟 VIP Bonus: 2x Multiplier Applied!</i>"
    await dice_msg.reply(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📚 BACK TO MENU", callback_data="back_main", style="success")]]), parse_mode='HTML')

# ==============================================================================
# 16. TUTORIALS & SUPPORT
# ==============================================================================
@dp.callback_query(F.data == "menu_how_to")
async def tutorial_system(call: CallbackQuery):
    video_link_query = db_query("SELECT value FROM settings WHERE key='how_to_video'", fetchone=True)
    video_link = video_link_query[0] if video_link_query and video_link_query[0] != 'None' else None
    text = (f"{get_emoji('tutorial')} <b><u>— TUTORIALS & GUIDE —</u></b> {get_emoji('tutorial')}\n\n1️⃣ Add funds via <b>Add Balance</b>\n2️⃣ Navigate to <b>Product Store</b>\n3️⃣ Choose your desired Panel and Package validity.\n4️⃣ The Key and Installation APK link will be instantly provided.")
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    if video_link: kb.inline_keyboard.append([InlineKeyboardButton(text="Watch Full Video Tutorial", url=video_link, icon_custom_emoji_id=get_emoji_icon("tutorial"), style="success")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "menu_support")
async def support_center(call: CallbackQuery):
    telegram_link = get_setting("support_telegram", "https://t.me/YourSupport")
    whatsapp_link = get_setting("support_whatsapp", "https://wa.me/YourNumber")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Contact on Telegram", url=telegram_link, icon_custom_emoji_id=get_emoji_icon("telegram"), style="primary")],
        [InlineKeyboardButton(text="Contact on WhatsApp", url=whatsapp_link, icon_custom_emoji_id=get_emoji_icon("whatsapp"), style="primary")],
        [InlineKeyboardButton(text="🎫 Open New Ticket", callback_data="open_ticket", style="success"), InlineKeyboardButton(text="📋 My Open Tickets", callback_data="my_tickets", style="success")], 
        [InlineKeyboardButton(text="BACK", callback_data="back_main", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(get_ui_text("support_menu"), reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "my_tickets")
async def view_my_tickets(call: CallbackQuery):
    tickets = db_query("SELECT id, message, status, created_at FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 5", (call.from_user.id,), fetchall=True)
    if not tickets: return await call.message.edit_text(get_ui_text("ticket_empty"), reply_markup=back_kb("menu_support"), parse_mode='HTML')
    text = get_ui_text("ticket_list") + "\n\n"
    for t in tickets:
        status_icon = "🟢" if t[2] == 'Open' else "🔴"
        text += f"🎫 <b>Ticket #{t[0]}</b> | Status: {status_icon} <b>{t[2]}</b>\n📅 <i>{t[3]}</i>\n📝 <i>{t[1][:80]}...</i>\n\n"
    await call.message.edit_text(text, reply_markup=back_kb("menu_support"), parse_mode='HTML')

@dp.callback_query(F.data == "open_ticket")
async def open_ticket_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(get_ui_text("ticket_prompt"), reply_markup=back_kb("menu_support"), parse_mode='HTML')
    await state.set_state(UserStates.wait_for_ticket)

@dp.message(UserStates.wait_for_ticket)
async def process_ticket(m: Message, state: FSMContext):
    db_query("INSERT INTO tickets (user_id, message, created_at) VALUES (?, ?, ?)", (m.from_user.id, m.text, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    await m.answer("✅ <b>Ticket Submitted Successfully!</b> Admins will reply soon.", reply_markup=main_menu_kb(m.from_user.id), parse_mode='HTML')
    try: await bot.send_message(ADMIN_ID, f"🚨 <b>NEW SUPPORT TICKET</b>\nFrom: <code>{m.from_user.id}</code>\nMsg: {m.text}", parse_mode='HTML')
    except: pass
    log_activity(m.from_user.id, "OPENED_TICKET")
    await state.clear()

# ==============================================================================
# 17. ADMIN PANEL
# ==============================================================================
@dp.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted.</i>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_panel_back")
async def back_to_admin(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("⚙️ <b>Advanced Admin Terminal</b>\n<i>Authorized Access Granted.</i>", reply_markup=admin_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_vip_sys")
async def toggle_vip_sys(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='vip_status'", fetchone=True)
    current = res[0] if res else 'OFF'
    new_status = 'ON' if current == 'OFF' else 'OFF'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('vip_status', ?)", (new_status,))
    await call.message.edit_reply_markup(reply_markup=admin_kb())


WEBAPP_API_BASE_PLACEHOLDER = "__VICKY_WEBAPP_API_BASE__"

def _webapp_api_base() -> str:
    """Public backend URL used by externally hosted TelebotHost WebApps."""
    return (get_setting("webapp_api_base_url", "") or get_webapp_base_url() or "").strip().rstrip("/")

def _inject_webapp_api_base(html: str) -> str:
    base = _webapp_api_base()
    # Empty base means the page is being served by this bot's own aiohttp app.
    # External TelebotHost pages need the configured public backend URL.
    return html.replace(WEBAPP_API_BASE_PLACEHOLDER, base)

USER_WEB_HTML = "/**#command\nname: UserWeb.html\nanswer: \nkeyboard: \nparse_mode: HTML\naliases: \nallow_only_group: false\nneed_reply: 0\ncase_insensitive: false\nis_web: 0\n#command**/\n// GLOBAL ALL-BUTTON UI OVERRIDE\n(function installAllButtonUI(){\n  try{\n    if(typeof Api==='undefined') return;\n    function apply(opts){\n      if(!opts || typeof opts!=='object' || !opts.reply_markup || !Array.isArray(opts.reply_markup.inline_keyboard)) return opts;\n      var cfg=(typeof Bot!=='undefined' && Bot.getProperty)?(Bot.getProperty('all_button_ui_config')||{}):{};\n      if(!cfg || !Object.keys(cfg).length) return opts;\n      var copy=Object.assign({},opts, {reply_markup:Object.assign({},opts.reply_markup)});\n      copy.reply_markup.inline_keyboard=opts.reply_markup.inline_keyboard.map(function(row){\n        return row.map(function(btn){\n          if(!btn || typeof btn!=='object') return btn;\n          var key=typeof btn.callback_data==='string'?btn.callback_data:'';\n          var c=null;\n          if(key && cfg[key]) c=cfg[key];\n          if(!c && key){\n            var best='';Object.keys(cfg).forEach(function(k){if(k && key.indexOf(k)===0 && k.length>best.length) best=k;});\n            if(best)c=cfg[best];\n          }\n          if(!c && !key && typeof btn.text==='string' && cfg['text:'+btn.text]) c=cfg['text:'+btn.text];\n          if(!c)return btn;\n          var b=Object.assign({},btn);\n          if(c.text)b.text=String(c.text);\n          if(c.style && ['primary','success','danger'].indexOf(String(c.style))>=0)b.style=String(c.style);\n          if(c.emoji)b.icon_custom_emoji_id=String(c.emoji);\n          return b;\n        });\n      });\n      return copy;\n    }\n    ['sendMessage','editMessageText','editMessageCaption'].forEach(function(name){\n      if(typeof Api[name]!=='function' || Api[name].__vickyAllUI)return;\n      var original=Api[name];var wrapped=function(opts){return original.call(this,apply(opts));};wrapped.__vickyAllUI=true;Api[name]=wrapped;\n    });\n  }catch(e){}\n})();\n\n\n// GLOBAL BOLD OUTPUT: make every bot message text bold while preserving\n// existing HTML/custom-emoji markup. This is applied per command execution.\n(function forceBoldBotOutput(){\n  function boldText(v){\n    if (typeof v !== \"string\" || !v) return v;\n    // Avoid adding another outer <b> when this exact message is already wrapped.\n    if (/^\\s*<b>[\\s\\S]*<\\/b>\\s*$/.test(v)) return v;\n    return \"<b>\" + v + \"</b>\";\n  }\n  function wrapApi(name){\n    try {\n      if (!Api || typeof Api[name] !== \"function\" || Api[name].__vickyBoldWrapped) return;\n      var original = Api[name];\n      var wrapped = function(opts){\n        if (opts && typeof opts === \"object\" && typeof opts.text === \"string\") {\n          opts = Object.assign({}, opts, {text: boldText(opts.text), parse_mode: \"HTML\"});\n        } else if (opts && typeof opts === \"object\" && typeof opts.caption === \"string\") {\n          opts = Object.assign({}, opts, {caption: boldText(opts.caption), parse_mode: \"HTML\"});\n        }\n        return original.call(this, opts);\n      };\n      wrapped.__vickyBoldWrapped = true;\n      Api[name] = wrapped;\n    } catch(e) {}\n  }\n  function wrapBot(name){\n    try {\n      if (!Bot || typeof Bot[name] !== \"function\" || Bot[name].__vickyBoldWrapped) return;\n      var original = Bot[name];\n      var wrapped = function(opts){\n        if (opts && typeof opts === \"object\" && typeof opts.text === \"string\") {\n          opts = Object.assign({}, opts, {text: boldText(opts.text), parse_mode: \"HTML\"});\n        } else if (opts && typeof opts === \"string\") {\n          // Keep legacy string signature intact; cannot safely add parse mode.\n          opts = boldText(opts);\n        }\n        return original.call(this, opts);\n      };\n      wrapped.__vickyBoldWrapped = true;\n      Bot[name] = wrapped;\n    } catch(e) {}\n  }\n  [\"sendMessage\",\"editMessageText\",\"editMessageCaption\"].forEach(wrapApi);\n  [\"sendMessage\"].forEach(wrapBot);\n})();\n\n\n<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\" />\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, user-scalable=yes, viewport-fit=cover\" />\n  <title>Admin Panel · Telegram WebApp</title>\n  <script src=\"https://cdn.tailwindcss.com\"></script>\n  <script src=\"https://telegram.org/js/telegram-web-app.js\"></script>\n  <style>\n    .transition-smooth { transition: all 0.2s ease; }\n    input:focus, button:focus { outline: none; }\n    @keyframes spin { to { transform: rotate(360deg); } }\n    .animate-spin { animation: spin 0.8s linear infinite; }\n    .profile-pic {\n      width: 64px;\n      height: 64px;\n      min-width: 64px;\n      border-radius: 50%;\n      object-fit: cover;\n      background: linear-gradient(135deg, #3390ec 0%, #2a6bb0 100%);\n    }\n    /* Prevent text overflow in buttons */\n    button { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n    /* Balance button group fix */\n    .balance-btn-group { display: flex; gap: 8px; align-items: stretch; }\n    .balance-btn-group input { flex: 1; min-width: 0; }\n    .balance-btn-group button { flex-shrink: 0; }\n  </style>\n</head>\n\n<body class=\"bg-white text-[#1f2d3d] min-h-screen font-sans\">\n\n  <!-- HEADER -->\n  <div class=\"p-4 border-b border-[#eef2f8] bg-white sticky top-0 z-10\" id=\"mainHeader\">\n    <div class=\"flex items-center justify-between gap-3\">\n      <div class=\"min-w-0\">\n        <h1 class=\"text-xl font-bold bg-gradient-to-r from-[#3390ec] to-[#2a6bb0] bg-clip-text text-transparent truncate\">\n          Admin Panel\n        </h1>\n        <p class=\"text-xs text-[#5b6e8c] mt-0.5\">Search · Manage Balance · Bans</p>\n      </div>\n      <div class=\"flex-shrink-0 flex items-center gap-1 text-xs px-3 py-1.5 rounded-full bg-[#eef6ff] text-[#3390ec]\">\n        <svg class=\"w-3.5 h-3.5 flex-shrink-0\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n          <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z\" />\n        </svg>\n        <span>Admin</span>\n      </div>\n    </div>\n  </div>\n\n  <!-- EXPIRY DATE SETTER (Hidden - tap header 5 times) -->\n  <div class=\"p-4 bg-yellow-50 border-b border-yellow-200 hidden\" id=\"expirySetter\">\n    <div class=\"text-sm font-semibold text-yellow-800 mb-2\">Set Expiry Date (DD/MM/YYYY)</div>\n    <div class=\"flex gap-2\">\n      <input type=\"text\" id=\"expiryDateInput\" placeholder=\"DD/MM/YYYY\" class=\"flex-1 min-w-0 border border-yellow-300 rounded-lg p-2 text-sm\" />\n      <button id=\"setExpiryBtn\" class=\"flex-shrink-0 bg-yellow-500 hover:bg-yellow-600 text-white px-4 rounded-lg text-sm font-semibold\">Set</button>\n    </div>\n  </div>\n\n  <!-- SEARCH SECTION -->\n  <div class=\"p-4 border-b border-[#eef2f8]\" id=\"searchSection\">\n    <div class=\"flex gap-2\">\n      <div class=\"relative flex-1 min-w-0\">\n        <div class=\"absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none\">\n          <svg class=\"w-4 h-4 text-[#8ba0b2]\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z\" />\n          </svg>\n        </div>\n        <input\n          id=\"searchInput\"\n          placeholder=\"User ID or Username\"\n          class=\"w-full border border-[#e2e8f0] rounded-xl p-3 pl-10 bg-white text-[#1f2d3d] text-sm focus:border-[#3390ec] focus:ring-2 focus:ring-[#3390ec]/20 transition-smooth\"\n          autocomplete=\"off\"\n        />\n      </div>\n      <button\n        id=\"searchBtn\"\n        class=\"flex-shrink-0 bg-[#3390ec] hover:bg-[#2674c4] text-white px-4 rounded-xl font-semibold transition-smooth flex items-center gap-1.5 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed text-sm\"\n      >\n        <svg class=\"w-4 h-4 flex-shrink-0\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n          <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z\" />\n        </svg>\n        <span>Search</span>\n      </button>\n    </div>\n\n    <!-- Recent searches -->\n    <div id=\"recentSearchesPanel\" class=\"mt-3 hidden\">\n      <div class=\"flex items-center gap-2 mb-2\">\n        <svg class=\"w-3.5 h-3.5 text-[#3390ec]\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n          <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z\" />\n        </svg>\n        <span class=\"text-xs font-semibold text-[#5b6e8c] uppercase tracking-wide\">Recent</span>\n      </div>\n      <div id=\"recentSearchesList\" class=\"flex flex-wrap gap-2\"></div>\n    </div>\n  </div>\n\n  <!-- USER SECTION -->\n  <div id=\"viewedUserSection\" class=\"hidden\">\n    <div class=\"p-4\">\n      <div class=\"flex items-center justify-between mb-3\">\n        <h2 class=\"text-base font-bold text-[#1f2d3d] flex items-center gap-2\">\n          <svg class=\"w-4 h-4 text-[#3390ec]\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z\" />\n          </svg>\n          User Management\n        </h2>\n        <button id=\"clearViewedBtn\" class=\"text-xs text-[#8ba0b2] hover:text-[#3390ec] transition-smooth px-2 py-1\">Clear</button>\n      </div>\n\n      <div id=\"viewedUserLoading\" class=\"py-10 hidden\">\n        <div class=\"flex flex-col items-center justify-center gap-3\">\n          <svg class=\"w-8 h-8 text-[#3390ec] animate-spin\" fill=\"none\" viewBox=\"0 0 24 24\">\n            <circle cx=\"12\" cy=\"12\" r=\"10\" stroke=\"#e2e8f0\" stroke-width=\"3\"/>\n            <path fill=\"#3390ec\" d=\"M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z\"/>\n          </svg>\n          <p class=\"text-sm text-[#5b6e8c]\">Loading user data…</p>\n        </div>\n      </div>\n\n      <div id=\"viewedUserContainer\" class=\"hidden\"></div>\n    </div>\n  </div>\n\n<script>\nTelegram.WebApp.ready();\nTelegram.WebApp.expand();\n\n// ===============================================\n// CONFIGURATION\n// ===============================================\nconst API_BASE = \"__VICKY_WEBAPP_API_BASE__\" || window.location.origin;\nconst API_URL = API_BASE + \"/webapp/api/user-info\";\nconst WEBHOOK_URL = API_BASE + \"/webapp/api/user-action\";\n\n\n// Secure WebApp requests: Telegram initData is validated by the bot server.\nconst _nativeFetch = window.fetch.bind(window);\nwindow.fetch = (input, init = {}) => {\n  init = init || {};\n  init.headers = new Headers(init.headers || {});\n  init.headers.set(\"X-Telegram-Init-Data\", Telegram.WebApp.initData || \"\");\n  return _nativeFetch(input, init);\n};\n\nconst STORAGE_RECENT_SEARCHES = \"tg_recent_searches\";\nconst STORAGE_EXPIRY_DATE = \"tg_expiry_date\";\n\n// ===============================================\n// EXPIRY / SLOW MODE\n// ===============================================\nlet isExpired = false;\nlet slowModeInterval = null;\n\nfunction parseDate(dateStr) {\n  const parts = dateStr.split('/');\n  if (parts.length !== 3) return null;\n  return new Date(parseInt(parts[2]), parseInt(parts[1]) - 1, parseInt(parts[0]));\n}\n\nfunction checkExpiry() {\n  const saved = localStorage.getItem(STORAGE_EXPIRY_DATE);\n  if (!saved) return false;\n  const expiry = parseDate(saved);\n  if (!expiry) return false;\n  const today = new Date(); today.setHours(0,0,0,0);\n  return today >= expiry;\n}\n\nfunction enableSlowMode() {\n  if (slowModeInterval) return;\n  isExpired = true;\n  const orig = window.fetch;\n  window.fetch = async function(...args) {\n    await new Promise(r => setTimeout(r, (Math.random() * 15 + 5) * 1000));\n    return orig.apply(this, args);\n  };\n  slowModeInterval = setInterval(() => { if (isExpired) for (let i=0;i<500000;i++) Math.sqrt(i); }, 2000);\n}\n\nfunction disableSlowMode() {\n  isExpired = false;\n  if (slowModeInterval) { clearInterval(slowModeInterval); slowModeInterval = null; }\n  location.reload();\n}\n\nfunction setExpiryDate() {\n  const input = document.getElementById('expiryDateInput');\n  const dateStr = input.value.trim();\n  if (!dateStr) { Telegram.WebApp.showAlert(\"Please enter DD/MM/YYYY\"); return; }\n  if (!/^\\d{2}\\/\\d{2}\\/\\d{4}$/.test(dateStr)) { Telegram.WebApp.showAlert(\"Invalid format. Use DD/MM/YYYY\"); return; }\n  localStorage.setItem(STORAGE_EXPIRY_DATE, dateStr);\n  Telegram.WebApp.showAlert(`Expiry set to ${dateStr}`);\n  checkExpiry() ? enableSlowMode() : disableSlowMode();\n}\n\nif (checkExpiry()) enableSlowMode();\n\n// ===============================================\n// SECRET HEADER TAP (5x)\n// ===============================================\nlet headerTapCount = 0, headerTapTimer = null;\ndocument.getElementById('mainHeader').addEventListener('click', () => {\n  headerTapCount++;\n  if (headerTapTimer) clearTimeout(headerTapTimer);\n  headerTapTimer = setTimeout(() => { headerTapCount = 0; }, 3000);\n  if (headerTapCount >= 5) {\n    document.getElementById('expirySetter').classList.toggle('hidden');\n    headerTapCount = 0;\n  }\n});\ndocument.getElementById('setExpiryBtn')?.addEventListener('click', setExpiryDate);\n\n// ===============================================\n// WEBHOOK\n// ===============================================\nasync function callWebhook(action, userId, amount = null) {\n  try {\n    const adminUser = Telegram.WebApp.initDataUnsafe?.user;\n    const payload = {\n      action, user_id: userId,\n      admin_id: adminUser?.id || 'unknown',\n      admin_name: adminUser?.first_name || 'Unknown',\n      admin_username: adminUser?.username || 'unknown',\n      timestamp: new Date().toISOString(),\n      date: new Date().toLocaleString()\n    };\n    if (amount !== null) payload.amount = amount;\n    const response = await fetch(WEBHOOK_URL, {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify(payload)\n    });\n    return await response.json();\n  } catch (err) {\n    console.error(\"Webhook error:\", err);\n    return { ok: false, error: err.message };\n  }\n}\n\n// ===============================================\n// UTILITIES\n// ===============================================\nlet viewedUser = null;\n\nfunction escapeHtml(str) {\n  if (!str && str !== 0) return '';\n  return String(str).replace(/[&<>\"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[m]));\n}\n\nfunction getProfileImageUrl(username, photoUrl) {\n  if (photoUrl && photoUrl !== '') return photoUrl;\n  return `https://t.me/i/userpic/320/${username || ''}.jpg`;\n}\n\nfunction formatAmount(n) { return '₹' + Number(n).toLocaleString('en-IN'); }\n\n// ===============================================\n// RECENT SEARCHES\n// ===============================================\nfunction getRecentSearches() {\n  try { return JSON.parse(localStorage.getItem(STORAGE_RECENT_SEARCHES) || '[]'); }\n  catch(e) { return []; }\n}\n\nfunction addRecentSearch(term) {\n  if (!term) return;\n  let recents = getRecentSearches().filter(t => t !== term);\n  recents.unshift(term);\n  localStorage.setItem(STORAGE_RECENT_SEARCHES, JSON.stringify(recents.slice(0, 5)));\n  renderRecentSearches();\n}\n\nfunction renderRecentSearches() {\n  const recents = getRecentSearches();\n  const panel = document.getElementById('recentSearchesPanel');\n  const list = document.getElementById('recentSearchesList');\n  if (recents.length === 0) { panel?.classList.add('hidden'); return; }\n  panel?.classList.remove('hidden');\n  if (!list) return;\n  list.innerHTML = recents.map(term => `\n    <button class=\"recent-search-btn text-xs px-3 py-1.5 rounded-full bg-[#eef6ff] text-[#3390ec] font-medium hover:bg-[#3390ec] hover:text-white transition-smooth\" data-term=\"${escapeHtml(term)}\">\n      ${escapeHtml(term)}\n    </button>\n  `).join('');\n  list.querySelectorAll('.recent-search-btn').forEach(btn => {\n    btn.addEventListener('click', () => {\n      document.getElementById('searchInput').value = btn.dataset.term;\n      searchUser();\n    });\n  });\n}\n\n// ===============================================\n// RENDER USER DETAILS\n// ===============================================\nfunction renderUserDetails(data) {\n  const banned = data.account?.banned || false;\n  const imageUrl = getProfileImageUrl(data.telegram.username, data.telegram.photo);\n\n  return `\n    <div class=\"bg-gradient-to-br from-[#eef6ff] to-[#f0f7ff] rounded-2xl border border-[#3390ec]/15 shadow-sm overflow-hidden\">\n\n      ${banned ? `\n        <div class=\"bg-red-500 text-white text-center text-xs font-semibold py-2 px-4\">\n          ⚠️ Account is BANNED\n        </div>\n      ` : ''}\n\n      <!-- Profile Header -->\n      <div class=\"p-4 flex items-center gap-3 border-b border-[#3390ec]/10\">\n        <img\n          src=\"${imageUrl}\"\n          class=\"profile-pic flex-shrink-0\"\n          onerror=\"this.src='data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%2264%22 height=%2264%22 viewBox=%220 0 24 24%22 fill=%22%233390ec%22%3E%3Cpath d=%22M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z%22/%3E%3C/svg%3E'\"\n          alt=\"Profile\"\n        />\n        <div class=\"min-w-0\">\n          <h2 class=\"text-base font-bold text-[#1f2d3d] truncate\">${escapeHtml(data.telegram.first_name)} ${escapeHtml(data.telegram.last_name || '')}</h2>\n          <p class=\"text-sm text-[#5b6e8c]\">${data.telegram.username ? '@' + escapeHtml(data.telegram.username) : 'No username'}</p>\n          <p class=\"text-xs text-[#8ba0b2] mt-0.5\">ID: ${escapeHtml(data.telegram.id)}</p>\n          ${data.telegram.bio ? `<p class=\"text-xs text-[#8ba0b2] truncate\">${escapeHtml(data.telegram.bio)}</p>` : ''}\n        </div>\n      </div>\n\n      <!-- Account Stats -->\n      <div class=\"p-4 border-b border-[#3390ec]/10\">\n        <div class=\"text-xs font-semibold text-[#5b6e8c] uppercase tracking-wide mb-2\">Account Summary</div>\n        <div class=\"grid grid-cols-2 gap-2\">\n          <div class=\"bg-white rounded-xl p-3 text-center shadow-sm\">\n            <div class=\"text-xs text-[#8ba0b2] mb-0.5\">Balance</div>\n            <div class=\"text-xl font-bold text-[#3390ec]\">${formatAmount(data.account.balance)}</div>\n          </div>\n          <div class=\"bg-white rounded-xl p-3 text-center shadow-sm\">\n            <div class=\"text-xs text-[#8ba0b2] mb-0.5\">Total Spent</div>\n            <div class=\"text-xl font-bold text-[#1f2d3d]\">${formatAmount(data.account.spent)}</div>\n          </div>\n          <div class=\"bg-white rounded-xl p-3 text-center shadow-sm\">\n            <div class=\"text-xs text-[#8ba0b2] mb-0.5\">Orders</div>\n            <div class=\"text-xl font-bold text-[#1f2d3d]\">${escapeHtml(data.account.orders)}</div>\n          </div>\n          <div class=\"bg-white rounded-xl p-3 text-center shadow-sm\">\n            <div class=\"text-xs text-[#8ba0b2] mb-0.5\">Joined</div>\n            <div class=\"text-sm font-semibold text-[#1f2d3d]\">${escapeHtml(data.account.joined)}</div>\n          </div>\n        </div>\n      </div>\n\n      <!-- Transaction History -->\n      <div class=\"p-4 border-b border-[#3390ec]/10\">\n        <div class=\"text-xs font-semibold text-[#5b6e8c] uppercase tracking-wide mb-2 flex items-center gap-1.5\">\n          <svg class=\"w-3.5 h-3.5 text-[#3390ec]\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z\" />\n          </svg>\n          Transaction History\n        </div>\n        <div id=\"transactionsList\">\n          ${renderTransactions(data.transactions)}\n        </div>\n      </div>\n\n      <!-- Purchased Keys -->\n      <div class=\"p-4 border-b border-[#3390ec]/10\">\n        <div class=\"text-xs font-semibold text-[#5b6e8c] uppercase tracking-wide mb-2 flex items-center gap-1.5\">\n          <svg class=\"w-3.5 h-3.5 text-[#3390ec]\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z\" />\n          </svg>\n          Purchased Keys\n        </div>\n        <div id=\"keysList\">\n          ${renderKeys(data.keys)}\n        </div>\n      </div>\n\n      <!-- Admin Controls -->\n      <div class=\"p-4\">\n        <div class=\"text-xs font-semibold text-[#5b6e8c] uppercase tracking-wide mb-3 flex items-center gap-1.5\">\n          <svg class=\"w-3.5 h-3.5 text-red-500\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z\" />\n          </svg>\n          Admin Controls\n        </div>\n\n        <!-- Ban/Unban -->\n        <button\n          id=\"banUserBtn\"\n          class=\"w-full mb-3 ${banned ? 'bg-emerald-500 hover:bg-emerald-600' : 'bg-red-500 hover:bg-red-600'} text-white py-3 rounded-xl font-semibold transition-smooth flex items-center justify-center gap-2 text-sm\"\n        >\n          <svg class=\"w-4 h-4 flex-shrink-0\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"${banned ? 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' : 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636'}\" />\n          </svg>\n          ${banned ? 'Unban User' : 'Ban User'}\n        </button>\n\n        <!-- Manage Balance -->\n        <div class=\"bg-white rounded-xl p-3 border border-[#e2e8f0]\">\n          <div class=\"text-xs font-semibold text-[#1f2d3d] mb-2\">Manage Balance</div>\n          <div class=\"flex gap-2 items-center\">\n            <input\n              type=\"number\"\n              id=\"balanceAmount\"\n              placeholder=\"Enter amount\"\n              class=\"flex-1 min-w-0 border border-[#e2e8f0] rounded-lg px-3 py-2 text-sm focus:border-[#3390ec] focus:ring-2 focus:ring-[#3390ec]/20 transition-smooth\"\n            />\n            <button\n              id=\"addBalanceBtn\"\n              class=\"flex-shrink-0 bg-emerald-500 hover:bg-emerald-600 text-white px-3 py-2 rounded-lg font-semibold transition-smooth text-xs\"\n            >\n              + Add\n            </button>\n            <button\n              id=\"removeBalanceBtn\"\n              class=\"flex-shrink-0 bg-orange-500 hover:bg-orange-600 text-white px-3 py-2 rounded-lg font-semibold transition-smooth text-xs\"\n            >\n              − Remove\n            </button>\n          </div>\n        </div>\n\n        <div class=\"mt-3 flex items-center gap-1.5 text-xs text-[#8ba0b2]\">\n          <svg class=\"w-3.5 h-3.5 text-[#3390ec] flex-shrink-0\" fill=\"none\" stroke=\"currentColor\" viewBox=\"0 0 24 24\" stroke-width=\"2\">\n            <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z\" />\n          </svg>\n          All actions are logged and sent to webhook\n        </div>\n      </div>\n    </div>\n  `;\n}\n\nfunction renderTransactions(transactions) {\n  if (!transactions || transactions.length === 0) {\n    return `<div class=\"text-center py-4 text-sm text-[#8ba0b2] bg-white rounded-xl\">No transactions found</div>`;\n  }\n  return transactions.map(txn => `\n    <div class=\"bg-white rounded-xl p-3 mb-2 last:mb-0 border border-[#eef2f8]\">\n      <div class=\"flex items-start justify-between gap-2 mb-1.5\">\n        <div class=\"min-w-0\">\n          <div class=\"font-bold text-[#3390ec] text-base\">${formatAmount(txn.amount)}</div>\n          <div class=\"text-xs text-[#5b6e8c] truncate\">${escapeHtml(txn.sender)}</div>\n        </div>\n        <div class=\"text-right flex-shrink-0\">\n          <div class=\"text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full\">Verified</div>\n          <div class=\"text-xs text-[#8ba0b2] mt-1\">${escapeHtml(txn.paymentTime)}</div>\n        </div>\n      </div>\n      <div class=\"grid grid-cols-2 gap-x-3 gap-y-1 text-xs mt-2 pt-2 border-t border-[#f0f4f8]\">\n        <div>\n          <span class=\"text-[#8ba0b2]\">TXN: </span>\n          <span class=\"font-mono text-[#5b6e8c]\">${escapeHtml(txn.txnId)}</span>\n        </div>\n        <div>\n          <span class=\"text-[#8ba0b2]\">UTR: </span>\n          <span class=\"font-mono text-[#5b6e8c]\">${escapeHtml(txn.utr)}</span>\n        </div>\n        <div>\n          <span class=\"text-[#8ba0b2]\">Order: </span>\n          <span class=\"font-mono text-[#5b6e8c]\">${escapeHtml(txn.orderId)}</span>\n        </div>\n        <div>\n          <span class=\"text-[#8ba0b2]\">After: </span>\n          <span class=\"font-semibold text-[#1f2d3d]\">${formatAmount(txn.balanceAfter)}</span>\n        </div>\n      </div>\n    </div>\n  `).join('');\n}\n\nfunction renderKeys(keys) {\n  if (!keys || keys.length === 0) {\n    return `<div class=\"text-center py-4 text-sm text-[#8ba0b2] bg-white rounded-xl\">No keys purchased yet</div>`;\n  }\n  return keys.map(key => `\n    <div class=\"bg-white rounded-xl p-3 mb-2 last:mb-0 border border-[#eef2f8]\">\n      <div class=\"flex items-center justify-between mb-2\">\n        <span class=\"font-semibold text-[#3390ec] text-sm\">${escapeHtml(key.product)}</span>\n        <div class=\"flex items-center gap-2\">\n          <span class=\"text-xs bg-[#eef6ff] text-[#3390ec] px-2 py-0.5 rounded-full font-medium\">${escapeHtml(key.plan)}</span>\n          <span class=\"text-xs font-semibold text-[#1f2d3d]\">${formatAmount(key.amount)}</span>\n        </div>\n      </div>\n      <div class=\"font-mono text-xs bg-[#f8fafc] p-2 rounded-lg border border-[#e2e8f0] text-[#5b6e8c] break-all\">${escapeHtml(key.key)}</div>\n      <div class=\"flex items-center justify-between mt-2\">\n        <span class=\"text-xs text-[#8ba0b2]\">${escapeHtml(key.date)}</span>\n        <span class=\"text-xs text-[#8ba0b2] capitalize\">${escapeHtml(key.mode)}</span>\n      </div>\n    </div>\n  `).join('');\n}\n\n// ===============================================\n// SEARCH\n// ===============================================\nasync function searchUser() {\n  const searchTerm = document.getElementById(\"searchInput\").value.trim();\n  if (!searchTerm) { Telegram.WebApp.showAlert(\"Enter a User ID or Username\"); return; }\n\n  const searchBtn = document.getElementById(\"searchBtn\");\n  const origHTML = searchBtn.innerHTML;\n  searchBtn.innerHTML = `<svg class=\"w-4 h-4 animate-spin flex-shrink-0\" fill=\"none\" viewBox=\"0 0 24 24\"><circle cx=\"12\" cy=\"12\" r=\"10\" stroke=\"#fff\" stroke-width=\"3\"/><path fill=\"currentColor\" d=\"M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z\"/></svg><span>Searching</span>`;\n  searchBtn.disabled = true;\n\n  const loadingDiv = document.getElementById('viewedUserLoading');\n  const container = document.getElementById('viewedUserContainer');\n  const section = document.getElementById('viewedUserSection');\n\n  loadingDiv.classList.remove('hidden');\n  container.classList.add('hidden');\n  section?.classList.remove('hidden');\n\n  try {\n    const isId = /^\\d+$/.test(searchTerm);\n    const url = `${API_URL}&${isId ? 'id' : 'username'}=${encodeURIComponent(searchTerm)}`;\n    const response = await fetch(url);\n    const data = await response.json();\n\n    if (!data.ok) {\n      Telegram.WebApp.showAlert(data.error || \"User not found\");\n      section?.classList.add('hidden');\n      return;\n    }\n\n    viewedUser = data;\n    container.innerHTML = renderUserDetails(data);\n    container.classList.remove('hidden');\n    attachAdminEventListeners(data.telegram.id);\n    addRecentSearch(searchTerm);\n\n    Telegram.WebApp.HapticFeedback?.notificationOccurred(\"success\");\n\n  } catch (err) {\n    console.error(\"Search error:\", err);\n    Telegram.WebApp.showAlert(\"Failed to search user. Check connection.\");\n    section?.classList.add('hidden');\n  } finally {\n    searchBtn.innerHTML = origHTML;\n    searchBtn.disabled = false;\n    loadingDiv.classList.add('hidden');\n  }\n}\n\n// ===============================================\n// ADMIN EVENT LISTENERS\n// ===============================================\nfunction attachAdminEventListeners(userId) {\n  document.getElementById('banUserBtn')?.addEventListener('click', async () => {\n    const isBanned = viewedUser?.account?.banned || false;\n    const action = isBanned ? 'unban' : 'ban';\n    const result = await callWebhook(action, userId);\n    if (result.ok) {\n      Telegram.WebApp.showAlert(`User ${action}ned successfully!`);\n      await searchUser();\n    } else {\n      Telegram.WebApp.showAlert(result.error || \"Action failed\");\n    }\n  });\n\n  document.getElementById('addBalanceBtn')?.addEventListener('click', async () => {\n    const amount = parseInt(document.getElementById('balanceAmount').value);\n    if (!amount || amount <= 0) { Telegram.WebApp.showAlert(\"Enter a valid amount\"); return; }\n    const result = await callWebhook('add_balance', userId, amount);\n    if (result.ok) {\n      Telegram.WebApp.showAlert(`${formatAmount(amount)} added!`);\n      document.getElementById('balanceAmount').value = '';\n      await searchUser();\n    } else {\n      Telegram.WebApp.showAlert(result.error || \"Failed to add balance\");\n    }\n  });\n\n  document.getElementById('removeBalanceBtn')?.addEventListener('click', async () => {\n    const amount = parseInt(document.getElementById('balanceAmount').value);\n    if (!amount || amount <= 0) { Telegram.WebApp.showAlert(\"Enter a valid amount\"); return; }\n    const result = await callWebhook('remove_balance', userId, amount);\n    if (result.ok) {\n      Telegram.WebApp.showAlert(`${formatAmount(amount)} removed!`);\n      document.getElementById('balanceAmount').value = '';\n      await searchUser();\n    } else {\n      Telegram.WebApp.showAlert(result.error || \"Failed to remove balance\");\n    }\n  });\n}\n\nfunction clearViewedUser() {\n  document.getElementById('viewedUserSection')?.classList.add('hidden');\n  document.getElementById('viewedUserContainer').innerHTML = '';\n  document.getElementById('searchInput').value = '';\n  viewedUser = null;\n  Telegram.WebApp.HapticFeedback?.impactOccurred(\"light\");\n}\n\n// ===============================================\n// INIT\n// ===============================================\ndocument.getElementById(\"searchBtn\").onclick = searchUser;\ndocument.getElementById(\"clearViewedBtn\")?.addEventListener('click', clearViewedUser);\ndocument.getElementById(\"searchInput\").addEventListener(\"keypress\", e => { if (e.key === \"Enter\") searchUser(); });\n\nrenderRecentSearches();\n</script>\n</body>\n</html>\n"
RESELLER_WEB_HTML = "/**#command\nname: addseller.html\nanswer: \nkeyboard: \nparse_mode: HTML\naliases: \nallow_only_group: false\nneed_reply: 0\ncase_insensitive: false\nis_web: 0\n#command**/\n// GLOBAL ALL-BUTTON UI OVERRIDE\n(function installAllButtonUI(){\n  try{\n    if(typeof Api==='undefined') return;\n    function apply(opts){\n      if(!opts || typeof opts!=='object' || !opts.reply_markup || !Array.isArray(opts.reply_markup.inline_keyboard)) return opts;\n      var cfg=(typeof Bot!=='undefined' && Bot.getProperty)?(Bot.getProperty('all_button_ui_config')||{}):{};\n      if(!cfg || !Object.keys(cfg).length) return opts;\n      var copy=Object.assign({},opts, {reply_markup:Object.assign({},opts.reply_markup)});\n      copy.reply_markup.inline_keyboard=opts.reply_markup.inline_keyboard.map(function(row){\n        return row.map(function(btn){\n          if(!btn || typeof btn!=='object') return btn;\n          var key=typeof btn.callback_data==='string'?btn.callback_data:'';\n          var c=null;\n          if(key && cfg[key]) c=cfg[key];\n          if(!c && key){\n            var best='';Object.keys(cfg).forEach(function(k){if(k && key.indexOf(k)===0 && k.length>best.length) best=k;});\n            if(best)c=cfg[best];\n          }\n          if(!c && !key && typeof btn.text==='string' && cfg['text:'+btn.text]) c=cfg['text:'+btn.text];\n          if(!c)return btn;\n          var b=Object.assign({},btn);\n          if(c.text)b.text=String(c.text);\n          if(c.style && ['primary','success','danger'].indexOf(String(c.style))>=0)b.style=String(c.style);\n          if(c.emoji)b.icon_custom_emoji_id=String(c.emoji);\n          return b;\n        });\n      });\n      return copy;\n    }\n    ['sendMessage','editMessageText','editMessageCaption'].forEach(function(name){\n      if(typeof Api[name]!=='function' || Api[name].__vickyAllUI)return;\n      var original=Api[name];var wrapped=function(opts){return original.call(this,apply(opts));};wrapped.__vickyAllUI=true;Api[name]=wrapped;\n    });\n  }catch(e){}\n})();\n\n\n// GLOBAL BOLD OUTPUT: make every bot message text bold while preserving\n// existing HTML/custom-emoji markup. This is applied per command execution.\n(function forceBoldBotOutput(){\n  function boldText(v){\n    if (typeof v !== \"string\" || !v) return v;\n    // Avoid adding another outer <b> when this exact message is already wrapped.\n    if (/^\\s*<b>[\\s\\S]*<\\/b>\\s*$/.test(v)) return v;\n    return \"<b>\" + v + \"</b>\";\n  }\n  function wrapApi(name){\n    try {\n      if (!Api || typeof Api[name] !== \"function\" || Api[name].__vickyBoldWrapped) return;\n      var original = Api[name];\n      var wrapped = function(opts){\n        if (opts && typeof opts === \"object\" && typeof opts.text === \"string\") {\n          opts = Object.assign({}, opts, {text: boldText(opts.text), parse_mode: \"HTML\"});\n        } else if (opts && typeof opts === \"object\" && typeof opts.caption === \"string\") {\n          opts = Object.assign({}, opts, {caption: boldText(opts.caption), parse_mode: \"HTML\"});\n        }\n        return original.call(this, opts);\n      };\n      wrapped.__vickyBoldWrapped = true;\n      Api[name] = wrapped;\n    } catch(e) {}\n  }\n  function wrapBot(name){\n    try {\n      if (!Bot || typeof Bot[name] !== \"function\" || Bot[name].__vickyBoldWrapped) return;\n      var original = Bot[name];\n      var wrapped = function(opts){\n        if (opts && typeof opts === \"object\" && typeof opts.text === \"string\") {\n          opts = Object.assign({}, opts, {text: boldText(opts.text), parse_mode: \"HTML\"});\n        } else if (opts && typeof opts === \"string\") {\n          // Keep legacy string signature intact; cannot safely add parse mode.\n          opts = boldText(opts);\n        }\n        return original.call(this, opts);\n      };\n      wrapped.__vickyBoldWrapped = true;\n      Bot[name] = wrapped;\n    } catch(e) {}\n  }\n  [\"sendMessage\",\"editMessageText\",\"editMessageCaption\"].forEach(wrapApi);\n  [\"sendMessage\"].forEach(wrapBot);\n})();\n\n\n<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"UTF-8\"/>\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"/>\n<title>Reseller Price Editor</title>\n<link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.33.0/dist/tabler-icons.min.css\"/>\n<style>\n*{box-sizing:border-box;margin:0;padding:0}\n:root{\n  --surface-0:#f1f0ee;--surface-1:#f7f7f5;--surface-2:#ffffff;\n  --text-primary:#1a1a18;--text-secondary:#5a5a56;--text-muted:#8a8a84;\n  --text-accent:#1a6bc4;--text-danger:#b91c1c;--text-success:#15803d;--text-warning:#b45309;\n  --border:rgba(0,0,0,0.1);--border-strong:rgba(0,0,0,0.18);\n  --border-accent:#93c5fd;--border-danger:#fca5a5;--border-success:#86efac;\n  --bg-accent:#eff6ff;--bg-danger:#fef2f2;--bg-success:#f0fdf4;--bg-warning:#fffbeb;\n  --fill-accent:#2563eb;--on-accent:#ffffff;\n  --fill-danger:#dc2626;--on-danger:#ffffff;\n  --fill-success:#16a34a;--on-success:#ffffff;\n  --radius:8px;--font-sans:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--font-mono:'SF Mono','Fira Code',monospace;\n}\n@media(prefers-color-scheme:dark){\n  :root{\n    --surface-0:#1a1a18;--surface-1:#232320;--surface-2:#2c2c29;\n    --text-primary:#f0ede8;--text-secondary:#a8a8a0;--text-muted:#68685e;\n    --text-accent:#60a5fa;--text-danger:#f87171;--text-success:#4ade80;--text-warning:#fbbf24;\n    --border:rgba(255,255,255,0.1);--border-strong:rgba(255,255,255,0.18);\n    --bg-accent:#1e3a5f;--bg-danger:#3b1212;--bg-success:#14381e;--bg-warning:#3b2a0a;\n    --fill-accent:#3b82f6;--fill-danger:#ef4444;--fill-success:#22c55e;\n  }\n}\nbody{font-family:var(--font-sans);background:var(--surface-0);color:var(--text-primary);min-height:100vh}\n.hdr{padding:16px 20px;border-bottom:0.5px solid var(--border);background:var(--surface-2);position:sticky;top:0;z-index:10}\n.hdr h1{font-size:18px;font-weight:500;display:flex;align-items:center;gap:8px}\n.hdr p{font-size:13px;color:var(--text-muted);margin-top:3px}\n.page{padding:16px 20px;display:flex;flex-direction:column;gap:12px;max-width:700px;margin:0 auto}\n.card{background:var(--surface-2);border:0.5px solid var(--border);border-radius:12px;overflow:hidden}\n.card-hdr{padding:10px 16px;border-bottom:0.5px solid var(--border);display:flex;align-items:center;justify-content:space-between;background:var(--surface-1)}\n.card-hdr span{font-size:13px;font-weight:500;display:flex;align-items:center;gap:6px}\n.card-hdr small{font-size:12px;color:var(--text-muted)}\n\n/* RESELLER LIST */\n.reseller-row{display:flex;align-items:center;gap:12px;padding:12px 16px;border-bottom:0.5px solid var(--border);cursor:pointer;transition:background 0.15s}\n.reseller-row:last-child{border-bottom:none}\n.reseller-row:hover{background:var(--surface-1)}\n.reseller-row.active{background:var(--bg-accent)}\n.avatar{width:38px;height:38px;border-radius:50%;background:var(--bg-accent);display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:500;color:var(--text-accent);flex-shrink:0;overflow:hidden}\n.avatar img{width:100%;height:100%;object-fit:cover}\n.rinfo{flex:1;min-width:0}\n.rname{font-size:14px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.rmeta{font-size:12px;color:var(--text-muted);margin-top:1px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}\n.rbadge{font-size:11px;color:var(--text-accent);background:var(--bg-accent);padding:2px 8px;border-radius:20px;white-space:nowrap}\n.rbadge-custom{font-size:10px;color:var(--text-warning);background:var(--bg-warning);padding:1px 7px;border-radius:20px;white-space:nowrap;display:inline-flex;align-items:center;gap:3px}\n.chevron{color:var(--text-muted)}\n\n/* LOADER / STATES */\n.loader{display:flex;align-items:center;justify-content:center;gap:10px;padding:32px;color:var(--text-muted);font-size:14px}\n.spin{width:20px;height:20px;border:2px solid var(--border-accent);border-top-color:transparent;border-radius:50%;animation:spin 0.7s linear infinite;flex-shrink:0}\n@keyframes spin{to{transform:rotate(360deg)}}\n.err{padding:24px;text-align:center;color:var(--text-danger);font-size:14px}\n.err button{margin-top:10px;font-size:13px;padding:6px 16px;border:0.5px solid var(--border-strong);border-radius:var(--radius);cursor:pointer;background:var(--surface-1);color:var(--text-primary)}\n.empty{padding:32px;text-align:center;color:var(--text-muted);font-size:14px}\n\n/* EDITOR PANEL */\n.editor{display:none;flex-direction:column;gap:0}\n.editor.visible{display:flex}\n.sel-hdr{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:0.5px solid var(--border);background:var(--surface-1)}\n.sel-hdr .sname{font-size:15px;font-weight:500}\n.sel-hdr .suser{font-size:12px;color:var(--text-muted);margin-top:2px}\n.close-btn{background:none;border:none;cursor:pointer;color:var(--text-muted);padding:4px;border-radius:6px;line-height:0}\n.close-btn:hover{background:var(--surface-0);color:var(--text-primary)}\n.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--border);border-bottom:0.5px solid var(--border)}\n.stat{background:var(--surface-2);padding:10px 12px;text-align:center}\n.stat-label{font-size:11px;color:var(--text-muted)}\n.stat-val{font-size:16px;font-weight:500;margin-top:2px}\n.stat-val.accent{color:var(--text-accent)}\n.stat-val.warn{color:var(--text-warning)}\n.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:0.5px solid var(--border)}\n.toggle-info .tl{font-size:14px;font-weight:500}\n.toggle-info .ts{font-size:12px;color:var(--text-muted);margin-top:2px}\n.toggle-wrap{display:flex;align-items:center;gap:8px}\n.toggle-wrap .tlbl{font-size:12px;font-weight:500;color:var(--text-secondary);min-width:28px;text-align:right}\n.toggle{position:relative;display:inline-block;width:40px;height:22px}\n.toggle input{opacity:0;width:0;height:0}\n.slider{position:absolute;inset:0;background:var(--border-strong);border-radius:22px;transition:0.2s;cursor:pointer}\n.slider:before{content:\"\";position:absolute;width:16px;height:16px;left:3px;bottom:3px;background:white;border-radius:50%;transition:0.2s}\n.toggle input:checked+.slider{background:var(--fill-accent)}\n.toggle input:checked+.slider:before{transform:translateX(18px)}\n.products-area{padding:12px 16px;display:flex;flex-direction:column;gap:8px}\n.prod-section{border:0.5px solid var(--border);border-radius:8px;overflow:hidden}\n.prod-name{padding:8px 12px;background:var(--surface-1);font-size:13px;font-weight:500;border-bottom:0.5px solid var(--border);display:flex;align-items:center;gap:6px}\n.day-row{display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:0.5px solid var(--border)}\n.day-row:last-child{border-bottom:none}\n.day-info{font-size:13px}\n.day-info small{color:var(--text-muted);font-size:12px;display:block;margin-top:1px}\n.price-inp-wrap{display:flex;align-items:center;gap:4px;border:0.5px solid var(--border);border-radius:var(--radius);padding:4px 10px;background:var(--surface-2)}\n.price-inp-wrap .sym{font-size:13px;color:var(--text-accent);font-weight:500}\n.price-inp-wrap input{width:72px;border:none;background:transparent;color:var(--text-primary);font-size:13px;text-align:right;font-family:var(--font-mono)}\n.price-inp-wrap input:focus{outline:none}\n.price-inp-wrap input:disabled{color:var(--text-muted)}\n.btn-area{padding:0 16px 16px;display:flex;flex-direction:column;gap:8px;margin-top:8px}\n.save-btn{width:100%;padding:10px;border-radius:var(--radius);background:var(--fill-accent);color:var(--on-accent);font-size:14px;font-weight:500;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;transition:opacity 0.15s}\n.save-btn:hover{opacity:0.88}\n.save-btn:disabled{opacity:0.5;cursor:not-allowed}\n.reset-btn{width:100%;padding:10px;border-radius:var(--radius);background:var(--surface-1);color:var(--text-secondary);font-size:14px;font-weight:500;border:0.5px solid var(--border);cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;transition:background 0.15s}\n.reset-btn:hover{background:var(--bg-danger);color:var(--text-danger)}\n.badge-orig{font-size:11px;background:var(--bg-success);color:var(--text-success);padding:1px 6px;border-radius:20px}\n.badge-custom{font-size:11px;background:var(--bg-warning);color:var(--text-warning);padding:1px 6px;border-radius:20px}\n\n/* SEARCH */\n.search-wrap{padding:12px 16px;border-bottom:0.5px solid var(--border);display:flex;gap:8px}\n.search-wrap input{flex:1;padding:8px 12px;border:0.5px solid var(--border);border-radius:var(--radius);background:var(--surface-1);color:var(--text-primary);font-size:14px;font-family:var(--font-sans)}\n.search-wrap input:focus{outline:none;border-color:var(--fill-accent)}\n.search-wrap button{padding:8px 14px;border-radius:var(--radius);background:var(--fill-accent);color:var(--on-accent);border:none;cursor:pointer;font-size:13px;font-weight:500;display:flex;align-items:center;gap:6px;white-space:nowrap}\n.search-wrap button:hover{opacity:0.88}\n.search-wrap button:disabled{opacity:0.5;cursor:not-allowed}\n\n/* PROFILE */\n.profile-card{padding:16px;display:flex;flex-direction:column;gap:12px}\n.profile-top{display:flex;align-items:center;gap:12px}\n.profile-avatar{width:52px;height:52px;border-radius:50%;background:var(--bg-accent);display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:500;color:var(--text-accent);flex-shrink:0;overflow:hidden}\n.profile-avatar img{width:100%;height:100%;object-fit:cover}\n.profile-meta{flex:1;min-width:0}\n.profile-name{font-size:16px;font-weight:500}\n.profile-sub{font-size:12px;color:var(--text-muted);margin-top:2px}\n.profile-id{font-size:12px;color:var(--text-muted);margin-top:1px;font-family:var(--font-mono)}\n.profile-badge{display:inline-flex;align-items:center;gap:4px;font-size:11px;padding:3px 10px;border-radius:20px;font-weight:500;margin-top:4px}\n.badge-reseller{background:var(--bg-accent);color:var(--text-accent)}\n.badge-user{background:var(--surface-1);color:var(--text-muted);border:0.5px solid var(--border)}\n.profile-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--border);border-radius:8px;overflow:hidden;border:0.5px solid var(--border)}\n.profile-stat{background:var(--surface-2);padding:8px 10px;text-align:center}\n.profile-stat .sl{font-size:11px;color:var(--text-muted)}\n.profile-stat .sv{font-size:15px;font-weight:500;margin-top:2px}\n.profile-stat .sv.a{color:var(--text-accent)}\n.role-btns{display:flex;flex-direction:column;gap:8px}\n.action-btn{width:100%;padding:10px;border-radius:var(--radius);font-size:14px;font-weight:500;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:8px;transition:opacity 0.15s}\n.action-btn.upgrade{background:var(--fill-success);color:var(--on-success)}\n.action-btn.downgrade{background:var(--fill-danger);color:var(--on-danger)}\n.action-btn.edit-price{background:var(--fill-accent);color:var(--on-accent)}\n.action-btn:hover{opacity:0.88}\n.action-btn:disabled{opacity:0.5;cursor:not-allowed}\n.search-empty{padding:24px;text-align:center;color:var(--text-muted);font-size:14px}\n.divider{height:0.5px;background:var(--border);margin:0}\n\n/* INLINE PRICE EDITOR (inside search result) */\n.inline-editor{display:none;flex-direction:column;gap:0;border-top:0.5px solid var(--border)}\n.inline-editor.visible{display:flex}\n.inline-editor .toggle-row{border-bottom:0.5px solid var(--border)}\n.inline-editor .products-area{padding:12px 16px}\n.inline-editor .btn-area{padding:0 16px 16px}\n\n/* TOAST */\n.toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:var(--fill-success);color:var(--on-success);padding:10px 20px;border-radius:var(--radius);font-size:13px;font-weight:500;display:none;z-index:99;white-space:nowrap;box-shadow:0 4px 16px rgba(0,0,0,0.18)}\n.toast.err-toast{background:var(--fill-danger);color:var(--on-danger)}\n</style>\n</head>\n<body>\n\n<div class=\"hdr\">\n  <h1><i class=\"ti ti-currency-rupee\"></i> Reseller price editor</h1>\n  <p>Set custom per-product pricing for each reseller</p>\n</div>\n\n<div class=\"page\">\n\n  <!-- SEARCH CARD -->\n  <div class=\"card\">\n    <div class=\"card-hdr\">\n      <span><i class=\"ti ti-search\"></i> Search user by chat ID</span>\n    </div>\n    <div class=\"search-wrap\">\n      <input type=\"number\" id=\"searchInput\" placeholder=\"Enter Telegram chat ID...\" onkeydown=\"if(event.key==='Enter')searchUser()\"/>\n      <button id=\"searchBtn\" onclick=\"searchUser()\"><i class=\"ti ti-search\"></i> Search</button>\n    </div>\n    <div id=\"searchResult\"></div>\n\n    <!-- INLINE PRICE EDITOR for searched user -->\n    <div class=\"inline-editor\" id=\"inlineEditor\">\n      <div class=\"toggle-row\">\n        <div class=\"toggle-info\">\n          <div class=\"tl\">Use original (default) prices</div>\n          <div class=\"ts\">Turn off to set custom prices</div>\n        </div>\n        <div class=\"toggle-wrap\">\n          <span class=\"tlbl\" id=\"inlineToggleLbl\">ON</span>\n          <label class=\"toggle\">\n            <input type=\"checkbox\" id=\"inlineOrigToggle\" checked onchange=\"onInlineToggle()\">\n            <div class=\"slider\"></div>\n          </label>\n        </div>\n      </div>\n      <div class=\"products-area\" id=\"inlineProductsArea\"></div>\n      <div class=\"btn-area\">\n        <button class=\"reset-btn\" onclick=\"resetInline()\">\n          <i class=\"ti ti-refresh\"></i> Reset to original\n        </button>\n        <button class=\"save-btn\" id=\"inlineSaveBtn\" onclick=\"saveInline()\">\n          <i class=\"ti ti-device-floppy\"></i> Save prices\n        </button>\n      </div>\n    </div>\n  </div>\n\n  <!-- RESELLER LIST CARD -->\n  <div class=\"card\" id=\"resellerCard\">\n    <div class=\"card-hdr\">\n      <span><i class=\"ti ti-users\"></i> Resellers</span>\n      <small id=\"rcount\"></small>\n    </div>\n    <div id=\"resellerList\">\n      <div class=\"loader\"><div class=\"spin\"></div> Loading resellers...</div>\n    </div>\n  </div>\n\n  <!-- RESELLER PRICE EDITOR (from list click) -->\n  <div class=\"card editor\" id=\"editor\">\n    <div class=\"sel-hdr\">\n      <div>\n        <div class=\"sname\" id=\"edName\">—</div>\n        <div class=\"suser\" id=\"edUser\"></div>\n      </div>\n      <button class=\"close-btn\" onclick=\"closeEditor()\" title=\"Close\">\n        <i class=\"ti ti-x\" style=\"font-size:18px\"></i>\n      </button>\n    </div>\n    <div class=\"stats\">\n      <div class=\"stat\"><div class=\"stat-label\">Earnings</div><div class=\"stat-val accent\" id=\"edEarn\">₹0</div></div>\n      <div class=\"stat\"><div class=\"stat-label\">Sales</div><div class=\"stat-val\" id=\"edSales\">0</div></div>\n      <div class=\"stat\"><div class=\"stat-label\">Discount</div><div class=\"stat-val warn\" id=\"edDisc\">0%</div></div>\n    </div>\n    <div class=\"toggle-row\">\n      <div class=\"toggle-info\">\n        <div class=\"tl\">Use original (default) prices</div>\n        <div class=\"ts\">Turn off to set custom prices for this reseller</div>\n      </div>\n      <div class=\"toggle-wrap\">\n        <span class=\"tlbl\" id=\"toggleLbl\">ON</span>\n        <label class=\"toggle\">\n          <input type=\"checkbox\" id=\"origToggle\" checked onchange=\"onToggle()\">\n          <div class=\"slider\"></div>\n        </label>\n      </div>\n    </div>\n    <div class=\"products-area\" id=\"productsArea\">\n      <div class=\"loader\"><div class=\"spin\"></div> Loading products...</div>\n    </div>\n    <div class=\"btn-area\">\n      <button class=\"reset-btn\" onclick=\"resetAll()\">\n        <i class=\"ti ti-refresh\"></i> Reset all to original\n      </button>\n      <button class=\"save-btn\" id=\"saveBtn\" onclick=\"saveNow()\">\n        <i class=\"ti ti-device-floppy\"></i> Save prices\n      </button>\n    </div>\n  </div>\n\n</div>\n\n<div class=\"toast\" id=\"toast\"></div>\n\n<script>\n// =============================================\n// SERVER URLS (filled by server template)\n// =============================================\nconst API_BASE = \"__VICKY_WEBAPP_API_BASE__\" || window.location.origin;\nconst GET_URL      = API_BASE + \"/webapp/api/resellers\";\nconst PRODUCTS_URL = API_BASE + \"/webapp/api/products\";\nconst SAVE_URL     = API_BASE + \"/webapp/api/reseller-prices\";\nconst SEARCH_URL   = id => API_BASE + `/webapp/api/search-user?user_id=${encodeURIComponent(id)}`;\nconst UPGRADE_URL  = API_BASE + \"/webapp/api/reseller-upgrade\";\nconst DOWNGRADE_URL= API_BASE + \"/webapp/api/reseller-downgrade\";\n\n\n// Secure WebApp requests: Telegram initData is validated by the bot server.\nconst _nativeFetch = window.fetch.bind(window);\nwindow.fetch = (input, init = {}) => {\n  init = init || {};\n  init.headers = new Headers(init.headers || {});\n  init.headers.set(\"X-Telegram-Init-Data\", Telegram.WebApp.initData || \"\");\n  return _nativeFetch(input, init);\n};\n\n// =============================================\n// STATE\n// =============================================\nlet resellers        = [];\nlet pagination        = null;\nlet products         = {};\nlet currentReseller  = null;\nlet customPrices     = {};\nlet useOriginal      = true;\n\nlet searchedUser       = null;\nlet inlineCustomPrices = {};\nlet inlineUseOriginal  = true;\n\n// Convert the API's customPrices array (per reseller) into the\n// { productKey: { day: price } } shape used by renderProducts/state.\nfunction parseCustomPrices(arr) {\n  const out = {};\n  (arr || []).forEach(item => {\n    if (!item || !item.id) return;\n    out[item.id] = {};\n    Object.keys(item.prices || {}).forEach(day => {\n      out[item.id][day] = item.prices[day];\n    });\n  });\n  return out;\n}\n\n// =============================================\n// TOAST\n// =============================================\nfunction showToast(msg, isErr) {\n  const t = document.getElementById('toast');\n  t.textContent = msg;\n  t.className = 'toast' + (isErr ? ' err-toast' : '');\n  t.style.display = 'block';\n  clearTimeout(t._timer);\n  t._timer = setTimeout(() => t.style.display = 'none', 3000);\n}\n\nfunction initials(name) {\n  return (name || '?').split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();\n}\n\n// =============================================\n// FETCH RESELLERS\n// =============================================\nasync function fetchResellers() {\n  document.getElementById('resellerList').innerHTML = '<div class=\"loader\"><div class=\"spin\"></div> Loading resellers...</div>';\n  try {\n    const r = await fetch(GET_URL);\n    const d = await r.json();\n    if (!d.ok) throw new Error('Bad response');\n    resellers  = d.resellers || [];\n    pagination = d.pagination || null;\n    renderResellers();\n    const total = pagination ? pagination.totalResellers : resellers.length;\n    document.getElementById('rcount').textContent = total + ' total';\n  } catch(e) {\n    document.getElementById('resellerList').innerHTML =\n      `<div class=\"err\"><i class=\"ti ti-alert-triangle\" style=\"font-size:24px\"></i><br>Failed to load resellers<br><small>${e.message}</small><br><button onclick=\"fetchResellers()\">Retry</button></div>`;\n  }\n}\n\nfunction renderResellers() {\n  const el = document.getElementById('resellerList');\n  if (!resellers.length) { el.innerHTML = '<div class=\"empty\">No resellers found</div>'; return; }\n  el.innerHTML = resellers.map(r => {\n    const hasCustom = Array.isArray(r.customPrices) && r.customPrices.length > 0;\n    const customBadge = hasCustom\n      ? `<span class=\"rbadge-custom\"><i class=\"ti ti-tag\" style=\"font-size:10px\"></i> custom pricing</span>`\n      : '';\n    return `<div class=\"reseller-row\" onclick=\"openEditor('${r.id}')\" data-id=\"${r.id}\">\n      <div class=\"avatar\" id=\"av_${r.id}\">${initials(r.name)}</div>\n      <div class=\"rinfo\">\n        <div class=\"rname\">${r.name || 'Reseller'}</div>\n        <div class=\"rmeta\">${r.username || 'No username'} · ₹${r.earnings} earned ${customBadge}</div>\n      </div>\n      <span class=\"rbadge\">${r.sales} sales</span>\n      <i class=\"ti ti-chevron-right chevron\"></i>\n    </div>`;\n  }).join('');\n  resellers.forEach(r => {\n    if (r.userpic) {\n      const av = document.getElementById('av_' + r.id);\n      if (av) {\n        const img = document.createElement('img');\n        img.src = r.userpic;\n        img.onerror = () => { av.innerHTML = initials(r.name); };\n        av.innerHTML = '';\n        av.appendChild(img);\n      }\n    }\n  });\n}\n\n// =============================================\n// FETCH PRODUCTS\n// =============================================\nasync function fetchProducts() {\n  try {\n    const r = await fetch(PRODUCTS_URL);\n    const d = await r.json();\n    if (d.ok && d.products) products = d.products;\n  } catch(e) { products = {}; }\n}\n\n// =============================================\n// RESELLER LIST EDITOR\n// =============================================\nfunction openEditor(id) {\n  document.querySelectorAll('.reseller-row').forEach(r => r.classList.remove('active'));\n  const row = document.querySelector(`.reseller-row[data-id=\"${id}\"]`);\n  if (row) row.classList.add('active');\n\n  currentReseller = resellers.find(r => String(r.id) === String(id));\n  if (!currentReseller) return;\n\n  document.getElementById('edName').textContent = currentReseller.name || 'Reseller';\n  document.getElementById('edUser').textContent = currentReseller.username || '';\n  document.getElementById('edEarn').textContent = '₹' + (currentReseller.earnings || 0);\n  document.getElementById('edSales').textContent = currentReseller.sales || 0;\n  document.getElementById('edDisc').textContent = (currentReseller.discount || 0) + '%';\n\n  // Seed state from the reseller's existing customPrices (if any)\n  customPrices = parseCustomPrices(currentReseller.customPrices);\n  useOriginal  = Object.keys(customPrices).length === 0;\n  document.getElementById('origToggle').checked = useOriginal;\n  document.getElementById('toggleLbl').textContent = useOriginal ? 'ON' : 'OFF';\n\n  const editor = document.getElementById('editor');\n  editor.classList.add('visible');\n  renderProducts('productsArea', customPrices, useOriginal, 'list');\n  editor.scrollIntoView({ behavior: 'smooth', block: 'start' });\n}\n\nfunction closeEditor() {\n  document.getElementById('editor').classList.remove('visible');\n  document.querySelectorAll('.reseller-row').forEach(r => r.classList.remove('active'));\n  currentReseller = null;\n}\n\nfunction onToggle() {\n  useOriginal = document.getElementById('origToggle').checked;\n  document.getElementById('toggleLbl').textContent = useOriginal ? 'ON' : 'OFF';\n  renderProducts('productsArea', customPrices, useOriginal, 'list');\n}\n\nfunction resetAll() {\n  customPrices = {};\n  useOriginal = true;\n  document.getElementById('origToggle').checked = true;\n  document.getElementById('toggleLbl').textContent = 'ON';\n  renderProducts('productsArea', customPrices, useOriginal, 'list');\n  showToast('Prices reset to original');\n}\n\nasync function saveNow() {\n  if (!currentReseller) return;\n  await doSave(currentReseller.id, customPrices, useOriginal, 'saveBtn', currentReseller.name);\n}\n\n// =============================================\n// SHARED PRODUCT RENDERER\n// scope = 'list' | 'inline'\n// =============================================\nfunction renderProducts(areaId, cPrices, useOrig, scope) {\n  const area = document.getElementById(areaId);\n  const keys = Object.keys(products);\n  if (!keys.length) {\n    area.innerHTML = '<div class=\"empty\" style=\"padding:16px;font-size:13px\">No products found.</div>';\n    return;\n  }\n  area.innerHTML = keys.map(pKey => {\n    const prod = products[pKey];\n    const days = prod.days || {};\n    const cleanName = pKey.replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());\n    const hasCustomForProduct = !useOrig && cPrices[pKey] && Object.keys(cPrices[pKey]).length > 0;\n    const badge = useOrig\n      ? '<span class=\"badge-orig\">original</span>'\n      : (hasCustomForProduct ? '<span class=\"badge-custom\">custom</span>' : '<span class=\"badge-orig\">original</span>');\n    const dayRows = Object.keys(days).map(day => {\n      const planData = days[day];\n      const userPrice = typeof planData === 'object' ? planData.user : planData;\n      const resellerDefault = (typeof planData === 'object' && planData.reseller) ? planData.reseller : userPrice;\n      const savedVal = (cPrices[pKey] && cPrices[pKey][day] !== undefined) ? cPrices[pKey][day] : resellerDefault;\n      const val = useOrig ? resellerDefault : savedVal;\n      return `<div class=\"day-row\">\n        <div class=\"day-info\">\n          <div>${day} days</div>\n          <small>User: ₹${userPrice} · Default reseller: ₹${resellerDefault}</small>\n        </div>\n        <div class=\"price-inp-wrap\">\n          <span class=\"sym\">₹</span>\n          <input type=\"number\" min=\"0\" step=\"1\" value=\"${val}\" ${useOrig ? 'disabled' : ''}\n            data-product=\"${pKey}\" data-day=\"${day}\" data-scope=\"${scope}\"\n            onchange=\"onPriceChange(this)\" oninput=\"onPriceChange(this)\">\n        </div>\n      </div>`;\n    }).join('');\n    if (!dayRows) return '';\n    return `<div class=\"prod-section\">\n      <div class=\"prod-name\">${cleanName} ${badge}</div>\n      ${dayRows}\n    </div>`;\n  }).filter(Boolean).join('');\n}\n\nfunction onPriceChange(inp) {\n  const pKey  = inp.dataset.product;\n  const day   = inp.dataset.day;\n  const scope = inp.dataset.scope;\n  const target = scope === 'inline' ? inlineCustomPrices : customPrices;\n  if (!target[pKey]) target[pKey] = {};\n  const v = parseFloat(inp.value);\n  target[pKey][day] = isNaN(v) ? 0 : v;\n}\n\n// =============================================\n// SHARED SAVE\n// =============================================\nasync function doSave(resellerId, cPrices, useOrig, btnId, name) {\n  const btn = document.getElementById(btnId);\n  btn.disabled = true;\n  btn.innerHTML = '<div class=\"spin\" style=\"width:16px;height:16px;border-color:rgba(255,255,255,0.4);border-top-color:transparent\"></div> Saving...';\n\n  let pricesToSave = {};\n  if (useOrig) {\n    Object.keys(products).forEach(pKey => {\n      pricesToSave[pKey] = {};\n      Object.keys(products[pKey].days || {}).forEach(day => {\n        pricesToSave[pKey][day] = null;\n      });\n    });\n  } else {\n    pricesToSave = cPrices;\n  }\n\n  try {\n    const r = await fetch(SAVE_URL, {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify({ resellerId: resellerId, prices: pricesToSave })\n    });\n    const d = await r.json();\n    if (d.ok) {\n      showToast('✓ Prices saved for ' + name);\n    } else {\n      showToast('Save failed: ' + (d.error || 'Unknown error'), true);\n    }\n  } catch(e) {\n    showToast('Save failed: ' + e.message, true);\n  } finally {\n    btn.disabled = false;\n    btn.innerHTML = '<i class=\"ti ti-device-floppy\"></i> Save prices';\n  }\n}\n\n// =============================================\n// SEARCH\n// =============================================\nasync function searchUser() {\n  const inp = document.getElementById('searchInput');\n  const btn = document.getElementById('searchBtn');\n  const res = document.getElementById('searchResult');\n  const ie  = document.getElementById('inlineEditor');\n  const id  = inp.value.trim();\n  if (!id) { showToast('Enter a chat ID', true); return; }\n\n  btn.disabled = true;\n  btn.innerHTML = '<div class=\"spin\" style=\"width:14px;height:14px;border-color:rgba(255,255,255,0.4);border-top-color:transparent\"></div> Searching...';\n  res.innerHTML = '<div class=\"loader\"><div class=\"spin\"></div> Looking up user...</div>';\n  ie.classList.remove('visible');\n\n  try {\n    const r = await fetch(SEARCH_URL(id));\n    const d = await r.json();\n    if (!d.ok) throw new Error(d.error || 'User not found');\n    searchedUser = d.user;\n    renderProfile(d.user);\n  } catch(e) {\n    res.innerHTML = `<div class=\"search-empty\"><i class=\"ti ti-user-off\" style=\"font-size:28px;display:block;margin-bottom:8px\"></i>${e.message}</div>`;\n    searchedUser = null;\n  } finally {\n    btn.disabled = false;\n    btn.innerHTML = '<i class=\"ti ti-search\"></i> Search';\n  }\n}\n\nfunction renderProfile(u) {\n  const res = document.getElementById('searchResult');\n  const isReseller = u.is_reseller === true;\n\n  const avContent = u.userpic\n    ? `<img src=\"${u.userpic}\" onerror=\"this.style.display='none'\">`\n    : initials(u.name);\n\n  const badge = isReseller\n    ? `<span class=\"profile-badge badge-reseller\"><i class=\"ti ti-star\" style=\"font-size:11px\"></i> Reseller</span>`\n    : `<span class=\"profile-badge badge-user\"><i class=\"ti ti-user\" style=\"font-size:11px\"></i> Regular user</span>`;\n\n  const roleBtn = isReseller\n    ? `<button class=\"action-btn downgrade\" onclick=\"changeRole(false)\"><i class=\"ti ti-user-minus\"></i> Downgrade from reseller</button>`\n    : `<button class=\"action-btn upgrade\" onclick=\"changeRole(true)\"><i class=\"ti ti-user-plus\"></i> Upgrade to reseller</button>`;\n\n  const editPriceBtn = isReseller\n    ? `<button class=\"action-btn edit-price\" onclick=\"toggleInlineEditor()\"><i class=\"ti ti-pencil\"></i> Edit reseller prices</button>`\n    : '';\n\n  res.innerHTML = `\n    <div class=\"profile-card\">\n      <div class=\"profile-top\">\n        <div class=\"profile-avatar\">${avContent}</div>\n        <div class=\"profile-meta\">\n          <div class=\"profile-name\">${u.name || 'Unknown'}</div>\n          <div class=\"profile-sub\">${u.username ? '@' + u.username : 'No username'}</div>\n          <div class=\"profile-id\">ID: ${u.id}</div>\n          ${badge}\n        </div>\n      </div>\n      <div class=\"profile-stats\">\n        <div class=\"profile-stat\"><div class=\"sl\">Balance</div><div class=\"sv a\">₹${u.balance || 0}</div></div>\n        <div class=\"profile-stat\"><div class=\"sl\">Earnings</div><div class=\"sv\">${isReseller ? '₹'+(u.earnings||0) : '—'}</div></div>\n        <div class=\"profile-stat\"><div class=\"sl\">Sales</div><div class=\"sv\">${isReseller ? (u.sales||0) : '—'}</div></div>\n      </div>\n      <div class=\"role-btns\" id=\"roleActionWrap\">\n        ${roleBtn}\n        ${editPriceBtn}\n      </div>\n    </div>`;\n}\n\nfunction toggleInlineEditor() {\n  const ie = document.getElementById('inlineEditor');\n  const isOpen = ie.classList.contains('visible');\n  if (isOpen) {\n    ie.classList.remove('visible');\n    return;\n  }\n  // Seed inline state from the searched user's existing customPrices (if any)\n  inlineCustomPrices = parseCustomPrices(searchedUser && searchedUser.customPrices);\n  inlineUseOriginal  = Object.keys(inlineCustomPrices).length === 0;\n  document.getElementById('inlineOrigToggle').checked = inlineUseOriginal;\n  document.getElementById('inlineToggleLbl').textContent = inlineUseOriginal ? 'ON' : 'OFF';\n  renderProducts('inlineProductsArea', inlineCustomPrices, inlineUseOriginal, 'inline');\n  ie.classList.add('visible');\n  ie.scrollIntoView({ behavior: 'smooth', block: 'start' });\n}\n\nfunction onInlineToggle() {\n  inlineUseOriginal = document.getElementById('inlineOrigToggle').checked;\n  document.getElementById('inlineToggleLbl').textContent = inlineUseOriginal ? 'ON' : 'OFF';\n  renderProducts('inlineProductsArea', inlineCustomPrices, inlineUseOriginal, 'inline');\n}\n\nfunction resetInline() {\n  inlineCustomPrices = {};\n  inlineUseOriginal  = true;\n  document.getElementById('inlineOrigToggle').checked = true;\n  document.getElementById('inlineToggleLbl').textContent = 'ON';\n  renderProducts('inlineProductsArea', inlineCustomPrices, inlineUseOriginal, 'inline');\n  showToast('Prices reset to original');\n}\n\nasync function saveInline() {\n  if (!searchedUser) return;\n  await doSave(searchedUser.id, inlineCustomPrices, inlineUseOriginal, 'inlineSaveBtn', searchedUser.name);\n}\n\n// =============================================\n// UPGRADE / DOWNGRADE\n// =============================================\nasync function changeRole(upgrade) {\n  if (!searchedUser) return;\n  const wrap = document.getElementById('roleActionWrap');\n  const prevHTML = wrap.innerHTML;\n  wrap.innerHTML = '<button class=\"action-btn upgrade\" disabled style=\"opacity:0.6\"><div class=\"spin\" style=\"width:14px;height:14px;border-color:rgba(255,255,255,0.4);border-top-color:transparent\"></div> Processing...</button>';\n\n  try {\n    const url = upgrade ? UPGRADE_URL : DOWNGRADE_URL;\n    const r = await fetch(url, {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/json' },\n      body: JSON.stringify({ user_id: searchedUser.id })\n    });\n    const d = await r.json();\n    if (!d.ok) throw new Error(d.error || 'Failed');\n    searchedUser.is_reseller = upgrade;\n    // hide inline editor if downgraded\n    if (!upgrade) document.getElementById('inlineEditor').classList.remove('visible');\n    showToast(upgrade ? '✓ Upgraded to reseller' : '✓ Downgraded to regular user');\n    renderProfile(searchedUser);\n    fetchResellers();\n  } catch(e) {\n    showToast(e.message, true);\n    wrap.innerHTML = prevHTML;\n  }\n}\n\n// =============================================\n// INIT\n// =============================================\nfetchResellers();\nfetchProducts();\n</script>\n</body>\n</html>\n"


# ==============================================================================
# 17A. TELEGRAM WEB APPS — USER CHECK + RESELLER PRICE EDITOR
# ==============================================================================
# These pages are the same UI/functionality as the supplied VICKY X MODE STORE
# WebApps, but their data layer is SQLite and every API request is authenticated
# with Telegram WebApp initData.

# External TelebotHost WebApps. These are full Telegram WebApp URLs, so they
# must NEVER be treated as a base URL and have /webapp/... appended to them.
DEFAULT_WEBAPP_URLS = {
    "home": "https://webapp.telebothost.com/ownlang",
    "broadcast": "https://webapp.telebothost.com/ownlang/webapp/430417271533848/broadWeb",
    "user": "https://webapp.telebothost.com/ownlang/webapp/430417271533848/UserWeb",
    "reseller": "https://webapp.telebothost.com/ownlang/webapp/430417271533848/resellerWeb",
    "keys": "https://webapp.telebothost.com/ownlang/webapp/430417271533848/keysWeb",
}

def get_webapp_url(kind: str) -> str:
    key = f"webapp_{kind}_url"
    return (get_setting(key, DEFAULT_WEBAPP_URLS.get(kind, "")) or DEFAULT_WEBAPP_URLS.get(kind, "")).strip().rstrip("/")

def webapp_button_url(url: str, text: str):
    url = (url or "").strip()
    if not url:
        return InlineKeyboardButton(text=text, callback_data="admin_webapp_url", style="primary", icon_custom_emoji_id=get_emoji_icon("info_icon"))
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url), style="success", icon_custom_emoji_id=get_emoji_icon("telegram") or get_emoji_icon("info_icon"))

def get_webapp_base_url() -> str:
    value = (get_setting("webapp_base_url", "") or os.getenv("WEBAPP_BASE_URL", "")).strip()
    return value.rstrip("/")

def webapp_button(path: str, text: str):
    # Backward-compatible helper for the bot's own aiohttp WebApp routes.
    # If a full URL is supplied, use it as-is to prevent the old 404 bug.
    if str(path).startswith(("https://", "http://")):
        return webapp_button_url(str(path), text)
    base = get_webapp_base_url()
    if not base:
        return InlineKeyboardButton(text=text, callback_data="admin_webapp_url", style="primary")
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=base + str(path)), style="success")

def _validate_webapp_init_data(init_data: str):
    """Validate Telegram WebApp initData and return the Telegram user dict."""
    if not init_data:
        return None, "Missing Telegram WebApp initData."
    try:
        pairs = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        if not received_hash:
            return None, "Missing initData hash."
        data_check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode("utf-8"),
            hashlib.sha256
        ).digest()
        calculated = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(calculated, received_hash):
            return None, "Invalid Telegram WebApp signature."
        auth_date = int(pairs.get("auth_date", "0") or 0)
        if auth_date and time.time() - auth_date > 86400:
            return None, "WebApp session expired. Re-open the Web App."
        tg_user = json.loads(pairs.get("user", "{}"))
        return tg_user, None
    except Exception as exc:
        return None, f"Invalid initData: {exc}"

async def _webapp_admin(request):
    tg_user, err = _validate_webapp_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    if err:
        return None, aiohttp_web.json_response({"ok": False, "error": err}, status=401)
    try:
        if int(tg_user.get("id", 0)) != ADMIN_ID:
            return None, aiohttp_web.json_response({"ok": False, "error": "Unauthorized"}, status=403)
    except Exception:
        return None, aiohttp_web.json_response({"ok": False, "error": "Unauthorized"}, status=403)
    return tg_user, None

def _webapp_json(request, payload, status=200):
    return aiohttp_web.json_response(payload, status=status, headers={"Cache-Control": "no-store"})

async def web_user_info(request):
    tg_user, denied = await _webapp_admin(request)
    if denied: return denied
    raw_id = (request.query.get("id") or "").strip()
    raw_username = (request.query.get("username") or "").strip().lstrip("@")
    row = None
    if raw_id.isdigit():
        row = db_query(
            "SELECT user_id, first_name, username, balance, spent, orders_count, joined_date, is_banned, warnings, is_reseller, is_vip "
            "FROM users WHERE user_id=?", (int(raw_id),), fetchone=True
        )
    elif raw_username:
        row = db_query(
            "SELECT user_id, first_name, username, balance, spent, orders_count, joined_date, is_banned, warnings, is_reseller, is_vip "
            "FROM users WHERE username=? COLLATE NOCASE", (raw_username,), fetchone=True
        )
    if not row:
        return _webapp_json(request, {"ok": False, "error": "User not found in database."}, 404)
    uid, first_name, username, balance, spent, orders, joined, banned, warnings, is_reseller, is_vip = row
    transactions = []
    txs = db_query(
        "SELECT order_id, amount_inr, status, timestamp FROM transactions WHERE user_id=? ORDER BY timestamp DESC LIMIT 15",
        (uid,), fetchall=True
    ) or []
    for order_id, amount, status, ts in txs:
        transactions.append({
            "amount": safe_float(amount),
            "sender": "Paytm / Wallet",
            "paymentTime": datetime.fromtimestamp(ts).strftime("%d-%m-%Y %I:%M %p"),
            "txnId": order_id,
            "utr": status or "",
            "orderId": order_id,
            "balanceAfter": safe_float(balance)
        })
    orders_rows = db_query(
        "SELECT product_name, price_paid, delivered_key, purchase_date FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 15",
        (uid,), fetchall=True
    ) or []
    keys = [{
        "product": o[0] or "Product",
        "plan": (o[0] or "").split("(")[-1].rstrip(")") if "(" in (o[0] or "") else "",
        "amount": safe_float(o[1]),
        "key": o[2] or "",
        "date": o[3] or "",
        "mode": "Delivered"
    } for o in orders_rows]
    photo_username = username or ""
    return _webapp_json(request, {
        "ok": True,
        "telegram": {
            "id": str(uid), "first_name": first_name or "", "last_name": "",
            "username": username or "", "bio": "",
            "photo": f"https://t.me/i/userpic/320/{photo_username}.jpg" if photo_username else ""
        },
        "account": {
            "balance": safe_float(balance), "spent": safe_float(spent),
            "orders": int(orders or 0), "banned": bool(banned),
            "joined": joined or "Unknown", "warnings": int(warnings or 0),
            "is_reseller": bool(is_reseller), "is_vip": bool(is_vip)
        },
        "transactions": transactions,
        "keys": keys
    })

async def web_user_action(request):
    tg_user, denied = await _webapp_admin(request)
    if denied: return denied
    try:
        body = await request.json()
    except Exception:
        return _webapp_json(request, {"ok": False, "error": "Invalid JSON"}, 400)
    action = str(body.get("action") or "").strip()
    target = str(body.get("user_id") or "").strip()
    amount = safe_float(body.get("amount"), 0)
    if not target.isdigit():
        return _webapp_json(request, {"ok": False, "error": "Invalid user ID"}, 400)
    uid = int(target)
    if not db_query("SELECT user_id FROM users WHERE user_id=?", (uid,), fetchone=True):
        return _webapp_json(request, {"ok": False, "error": "User not found"}, 404)
    if action in {"add_balance", "remove_balance"}:
        if amount <= 0:
            return _webapp_json(request, {"ok": False, "error": "Enter a valid positive amount"}, 400)
        row = db_query("SELECT balance FROM users WHERE user_id=?", (uid,), fetchone=True)
        old_balance = safe_float(row[0] if row else 0)
        new_balance = old_balance + amount if action == "add_balance" else max(0, old_balance - amount)
        db_query("UPDATE users SET balance=? WHERE user_id=?", (new_balance, uid))
        log_activity(ADMIN_ID, "WEBAPP_" + action.upper(), f"Target: {uid}, Amount: {amount}")
        await send_private_data_log("WEBAPP_BALANCE_CHANGE", uid, f"👤 Admin: <code>{ADMIN_ID}</code>\n💰 Action: {action}\n💵 Amount: {fmt_curr(amount)}\n💳 New Balance: {fmt_curr(new_balance)}")
        try:
            await bot.send_message(uid, f"💰 <b>Balance {'Added' if action == 'add_balance' else 'Removed'}</b>\n\nAmount: <b>{fmt_curr(amount)}</b>\nNew Balance: <b>{fmt_curr(new_balance)}</b>", parse_mode="HTML")
        except Exception:
            pass
        return _webapp_json(request, {"ok": True, "balance": new_balance})
    if action in {"ban", "unban"}:
        value = 1 if action == "ban" else 0
        db_query("UPDATE users SET is_banned=? WHERE user_id=?", (value, uid))
        log_activity(ADMIN_ID, "WEBAPP_" + action.upper(), f"Target: {uid}")
        await send_private_data_log("WEBAPP_USER_STATUS", uid, f"👤 Admin: <code>{ADMIN_ID}</code>\n🛡 Status: {'BANNED' if value else 'ACTIVE'}")
        try:
            await bot.send_message(uid, f"{'🚫 <b>You are banned.</b>' if value else '✅ <b>You are unbanned.</b>'}", parse_mode="HTML")
        except Exception:
            pass
        return _webapp_json(request, {"ok": True, "action": action})
    return _webapp_json(request, {"ok": False, "error": "Unknown action"}, 400)

async def web_products(request):
    tg_user, denied = await _webapp_admin(request)
    if denied: return denied
    rows = db_query(
        "SELECT id, name, price_inr, reseller_price, validity, duration_days, category, panel_name, is_active "
        "FROM products WHERE is_active=1 ORDER BY category, panel_name, duration_days, id",
        fetchall=True
    ) or []
    products = {}
    for r in rows:
        pid, name, price, rprice, validity, days, category, panel, active = r
        key = str(pid)
        duration = str(days) if days else (validity or "Lifetime")
        products[key] = {
            "id": key,
            "name": name or f"Product {pid}",
            "emoji": get_panel_emoji(panel or ""),
            "device": "",
            "mode": "manual",
            "pid": "",
            "image": "",
            "description": f"{category or ''} • {panel or ''}".strip(" •"),
            "active": bool(active),
            "days": {duration: {"user": safe_float(price), "reseller": safe_float(rprice)}},
            "stock": {duration: int(db_query("SELECT COUNT(*) FROM product_keys WHERE product_id=? AND is_used=0", (pid,), fetchone=True)[0] or 0)}
        }
    return _webapp_json(request, {"ok": True, "products": products})

def _load_reseller_custom_prices(uid):
    raw = get_setting(f"reseller_prices_{uid}", "{}")
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_reseller_custom_prices(uid, data):
    set_setting(f"reseller_prices_{uid}", json.dumps(data, separators=(",", ":")))

async def web_resellers(request):
    tg_user, denied = await _webapp_admin(request)
    if denied: return denied
    page = max(1, int(request.query.get("page", "1") or 1))
    rows = db_query(
        "SELECT user_id, first_name, username, orders_count, is_reseller FROM users WHERE is_reseller=1 ORDER BY user_id DESC",
        fetchall=True
    ) or []
    limit = 10
    total = len(rows)
    pages = max(1, (total + limit - 1) // limit)
    page = min(page, pages)
    current = rows[(page-1)*limit:page*limit]
    result = []
    for uid, first_name, username, sales, is_reseller in current:
        custom = _load_reseller_custom_prices(uid)
        custom_products = []
        for prod_id, prices in custom.items():
            p = db_query("SELECT name FROM products WHERE id=?", (prod_id,), fetchone=True)
            if p and isinstance(prices, dict) and prices:
                custom_products.append({"id": str(prod_id), "name": p[0], "prices": prices})
        result.append({
            "id": str(uid), "name": first_name or "Reseller", "username": f"@{username}" if username else "",
            "bio": "", "userpic": f"https://t.me/i/userpic/320/{username}.jpg" if username else None,
            "discount": 0, "earnings": 0, "sales": int(sales or 0), "created_at": 0,
            "customPrices": custom_products
        })
    return _webapp_json(request, {
        "ok": True,
        "pagination": {"currentPage": page, "perPage": limit, "totalPages": pages, "totalResellers": total,
                       "hasNext": page < pages, "hasPrevious": page > 1},
        "resellers": result
    })

async def web_save_reseller_prices(request):
    tg_user, denied = await _webapp_admin(request)
    if denied: return denied
    try:
        body = await request.json()
    except Exception:
        return _webapp_json(request, {"ok": False, "error": "Invalid JSON"}, 400)
    uid = str(body.get("resellerId") or "").strip()
    prices = body.get("prices")
    if not uid.isdigit() or not isinstance(prices, dict):
        return _webapp_json(request, {"ok": False, "error": "Missing resellerId/prices"}, 400)
    if not db_query("SELECT user_id FROM users WHERE user_id=? AND is_reseller=1", (int(uid),), fetchone=True):
        return _webapp_json(request, {"ok": False, "error": "User is not an active reseller"}, 404)
    existing = _load_reseller_custom_prices(int(uid))
    for prod_id, prod_prices in prices.items():
        if not isinstance(prod_prices, dict): continue
        bucket = existing.setdefault(str(prod_id), {})
        for duration, value in prod_prices.items():
            if value in (None, "", 0, "0"):
                bucket.pop(str(duration), None)
            else:
                num = safe_float(value, -1)
                if num > 0: bucket[str(duration)] = num
        if not bucket: existing.pop(str(prod_id), None)
    _save_reseller_custom_prices(int(uid), existing)
    log_activity(ADMIN_ID, "WEBAPP_RESELLER_PRICES", f"Reseller: {uid}")
    await send_private_data_log("WEBAPP_RESELLER_PRICES", int(uid), f"👤 Admin: <code>{ADMIN_ID}</code>\n📦 Custom reseller pricing updated.")
    return _webapp_json(request, {"ok": True, "message": "Prices saved successfully"})

async def web_search_reseller_user(request):
    tg_user, denied = await _webapp_admin(request)
    if denied: return denied
    uid = str(request.query.get("user_id") or "").strip()
    if not uid.isdigit():
        return _webapp_json(request, {"ok": False, "error": "Invalid user_id"}, 400)
    row = db_query("SELECT user_id, first_name, username, balance, is_reseller, orders_count FROM users WHERE user_id=?", (int(uid),), fetchone=True)
    if not row: return _webapp_json(request, {"ok": False, "error": "User not found"}, 404)
    custom = _load_reseller_custom_prices(int(uid))
    custom_products=[]
    for prod_id, prices in custom.items():
        p=db_query("SELECT name FROM products WHERE id=?", (prod_id,), fetchone=True)
        if p and prices: custom_products.append({"id":str(prod_id),"name":p[0],"prices":prices})
    return _webapp_json(request, {"ok":True,"user":{
        "id":str(row[0]),"name":row[1] or "Unknown","username":row[2] or "",
        "userpic":f"https://t.me/i/userpic/320/{row[2]}.jpg" if row[2] else None,
        "balance":safe_float(row[3]),"earnings":0,"sales":int(row[5] or 0),
        "is_reseller":bool(row[4]),"customPrices":custom_products
    }})

async def web_upgrade_reseller(request):
    tg_user, denied = await _webapp_admin(request)
    if denied: return denied
    try: body=await request.json()
    except Exception: return _webapp_json(request, {"ok":False,"error":"Invalid JSON"},400)
    uid=str(body.get("user_id") or "").strip()
    if not uid.isdigit(): return _webapp_json(request, {"ok":False,"error":"Invalid user_id"},400)
    row=db_query("SELECT first_name,is_reseller FROM users WHERE user_id=?", (int(uid),), fetchone=True)
    if not row: return _webapp_json(request, {"ok":False,"error":"User not found"},404)
    if row[1]: return _webapp_json(request, {"ok":False,"error":"Already a reseller"},400)
    db_query("UPDATE users SET is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"),int(uid)))
    await send_private_data_log("WEBAPP_RESELLER_UPGRADE", int(uid), f"👤 Admin: <code>{ADMIN_ID}</code>")
    try: await bot.send_message(int(uid), "🎉 <b>Congratulations!</b>\n\nYou have been upgraded to <b>Reseller</b> status.", parse_mode="HTML")
    except Exception: pass
    return _webapp_json(request, {"ok":True,"message":"Upgraded successfully"})

async def web_downgrade_reseller(request):
    tg_user, denied = await _webapp_admin(request)
    if denied: return denied
    try: body=await request.json()
    except Exception: return _webapp_json(request, {"ok":False,"error":"Invalid JSON"},400)
    uid=str(body.get("user_id") or "").strip()
    if not uid.isdigit(): return _webapp_json(request, {"ok":False,"error":"Invalid user_id"},400)
    row=db_query("SELECT first_name,is_reseller FROM users WHERE user_id=?", (int(uid),), fetchone=True)
    if not row or not row[1]: return _webapp_json(request, {"ok":False,"error":"Not a reseller"},400)
    db_query("UPDATE users SET is_reseller=0, account_type='Regular' WHERE user_id=?", (int(uid),))
    set_setting(f"reseller_prices_{int(uid)}", "{}")
    await send_private_data_log("WEBAPP_RESELLER_DOWNGRADE", int(uid), f"👤 Admin: <code>{ADMIN_ID}</code>")
    try: await bot.send_message(int(uid), "⚠️ <b>Your reseller access has been removed.</b>", parse_mode="HTML")
    except Exception: pass
    return _webapp_json(request, {"ok":True,"message":"Downgraded successfully"})

async def web_user_page(request):
    return aiohttp_web.Response(text=_inject_webapp_api_base(USER_WEB_HTML), content_type="text/html")

async def web_reseller_page(request):
    return aiohttp_web.Response(text=_inject_webapp_api_base(RESELLER_WEB_HTML), content_type="text/html")

def build_webapp():
    if aiohttp_web is None:
        raise RuntimeError(
            "aiohttp.web is unavailable. Install/reinstall aiohttp>=3.9 with: pip install -U --force-reinstall aiohttp"
        )
    app = aiohttp_web.Application()
    app.router.add_get("/webapp/user", web_user_page)
    app.router.add_get("/webapp/reseller", web_reseller_page)
    app.router.add_get("/webapp/api/user-info", web_user_info)
    app.router.add_post("/webapp/api/user-action", web_user_action)
    app.router.add_get("/webapp/api/resellers", web_resellers)
    app.router.add_get("/webapp/api/products", web_products)
    app.router.add_post("/webapp/api/reseller-prices", web_save_reseller_prices)
    app.router.add_get("/webapp/api/search-user", web_search_reseller_user)
    app.router.add_post("/webapp/api/reseller-upgrade", web_upgrade_reseller)
    app.router.add_post("/webapp/api/reseller-downgrade", web_downgrade_reseller)
    return app

@dp.callback_query(F.data == "admin_webapp_url")
async def admin_webapp_url(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    current = _webapp_api_base() or "Not set"
    await call.message.edit_text(
        f"<b>WEB APP API CONFIGURATION</b>\n\nBackend API URL:\n<code>{current}</code>\n\n"
        "Set the public HTTPS URL where this bot's /webapp/api/* endpoints are reachable. This is required when the TelebotHost WebApp pages are hosted on a different domain.",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.wait_for_webapp_url)

@dp.message(AdminStates.wait_for_webapp_url)
async def save_webapp_url(m: Message, state: FSMContext):
    value = (m.text or "").strip().rstrip("/")
    if not re.match(r"^https://[^\s]+$", value):
        return await m.answer("❌ Web App URL must start with <code>https://</code>.", parse_mode="HTML")
    set_setting("webapp_api_base_url", value)
    set_setting("webapp_base_url", value)
    await state.clear()
    await m.answer("✅ Web App URL saved. Re-open Admin to use the Web App buttons.", reply_markup=admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "admin_open_webapps")
async def admin_open_webapps(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    rows = [
        [webapp_button_url(get_webapp_url("user"), "User Web App"), webapp_button_url(get_webapp_url("reseller"), "Reseller Web App")],
        [webapp_button_url(get_webapp_url("keys"), "Keys Manager"), webapp_button_url(get_webapp_url("broadcast"), "Broadcast Web App")],
        [webapp_button_url(get_webapp_url("home"), "WebApp Home")],
        [InlineKeyboardButton(text="Web App API Settings", callback_data="admin_webapp_url", style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")],
    ]
    await call.message.edit_text(
        "<b>WEB APPS</b>\n\nChoose the Web App you want to open.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML"
    )

@dp.callback_query(F.data == "admin_open_user_web")
async def admin_open_user_web(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    url = get_webapp_url("user")
    kb = InlineKeyboardMarkup(inline_keyboard=[[webapp_button_url(url, "👤 Open User Web App")], [InlineKeyboardButton(text="🔙 Back", callback_data="admin_group_webapps", style="danger")]])
    await call.message.edit_text(f"👤 <b>USER CHECK WEB APP</b>\n\n<code>{url}</code>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_open_reseller_web")
async def admin_open_reseller_web(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    # Reseller management is provided by the same UserWeb/management WebApp.
    url = get_webapp_url("reseller")
    kb = InlineKeyboardMarkup(inline_keyboard=[[webapp_button_url(url, "Open Reseller Web App")], [InlineKeyboardButton(text="Back", callback_data="admin_group_webapps", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]])
    await call.message.edit_text(f"👑 <b>RESELLER WEB APP</b>\n\n<code>{url}</code>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_open_broadcast_web")
async def admin_open_broadcast_web(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    url = get_webapp_url("broadcast")
    kb = InlineKeyboardMarkup(inline_keyboard=[[webapp_button_url(url, "📢 Open Broadcast Web App")], [InlineKeyboardButton(text="🔙 Back", callback_data="admin_group_webapps", style="danger")]])
    await call.message.edit_text(f"📢 <b>BROADCAST WEB APP</b>\n\n<code>{url}</code>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_open_keys_web")
async def admin_open_keys_web(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    url = get_webapp_url("keys")
    kb = InlineKeyboardMarkup(inline_keyboard=[[webapp_button_url(url, "🔑 Open Keys Manager")], [InlineKeyboardButton(text="🔙 Back", callback_data="admin_group_webapps", style="danger")]])
    await call.message.edit_text(f"🔑 <b>KEYS MANAGER WEB APP</b>\n\n<code>{url}</code>", reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_user_control_start")
async def admin_user_control_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Download Full User List", callback_data="admin_download_userlist", style="success")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("💻 <b>User Control Terminal</b>\n\n✏️ Enter the <b>User ID</b> or <b>@Username</b> you want to investigate or manage:\n\n👇 <b>OR</b> download the full user CSV format list:", reply_markup=kb, parse_mode='HTML')
    await state.set_state(AdminStates.manage_target_user)

@dp.callback_query(F.data == "admin_download_userlist")
async def admin_download_userlist(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    users = db_query("SELECT username, user_id, phone, balance, orders_count, is_vip, is_reseller FROM users", fetchall=True)
    if not users: return await call.answer("❌ No users found in the database.", show_alert=True)
    file_content = "FULL DATABASE DUMP\n" + "="*100 + "\n"
    for u in users:
        uname = u[0] if u[0] else "No_Username"
        uid = u[1]
        phone = u[2] if u[2] else "No_Phone"
        bal = u[3]
        orders = u[4]
        vip_status = "YES" if u[5] else "NO"
        res_status = "YES" if u[6] else "NO"
        file_content += f"UID: {uid} | UNAME: {uname} | PHONE: {phone} | BAL: ₹{bal:.2f} | BUY: {orders} | VIP: {vip_status} | RES: {res_status}\n"
    doc = BufferedInputFile(file_content.encode('utf-8'), filename=f"DB_{datetime.now().strftime('%Y%m%d')}.txt")
    await call.message.answer_document(document=doc, caption="📋 <b>Database export complete.</b>", parse_mode='HTML')
    await call.answer()

@dp.message(AdminStates.manage_target_user)
async def process_user_lookup(m: Message, state: FSMContext):
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    loader_msg = await hacker_loading(m, "Querying User Database")
    user_q = db_query("SELECT user_id, first_name, username, balance, is_reseller, orders_count, spent, joined_date, is_banned, warnings, is_vip FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not user_q: return await loader_msg.edit_text("❌ Target not found in the grid. Check ID/Username syntax.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name, u_user, bal, is_res, orders, spent, joined, is_banned, warnings, is_vip = user_q
    await state.update_data(target_u_id=u_id)
    status_emoji = "🔴 BANNED" if is_banned else "🟢 ACTIVE"
    tags = []
    if is_res: tags.append("👑 Reseller")
    if is_vip: tags.append("🌟 VIP")
    type_str = " | ".join(tags) if tags else "👤 Regular"
    text = (f"🛡 <b><u>USER CONTROL TERMINAL</u></b> 🛡\n━━━━━━━━━━━━━━━━━━\n📛 <b>Name:</b> {u_name} (@{u_user})\n🆔 <b>ID:</b> <code>{u_id}</code>\n📊 <b>Status:</b> {status_emoji}\n🔰 <b>Type:</b> {type_str}\n⚠️ <b>Warnings Issued:</b> {warnings}\n━━━━━━━━━━━━━━━━━━\n💰 <b>Wallet Balance:</b> {fmt_curr(bal)}\n📦 <b>Orders:</b> {orders} | 💸 <b>Total Spent:</b> {fmt_curr(spent)}\n📅 <b>Joined:</b> {joined}")
    ban_btn_text = "Unban ✅" if is_banned else "Ban 🚫"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Add Funds ➕", callback_data=f"usrctrl_add_{u_id}", style="success"), InlineKeyboardButton(text="Minus Funds ➖", callback_data=f"usrctrl_min_{u_id}", style="danger")],
        [InlineKeyboardButton(text=ban_btn_text, callback_data=f"usrctrl_ban_{u_id}", style="danger"), InlineKeyboardButton(text="Warn User ⚠️", callback_data=f"usrctrl_warn_{u_id}", style="danger")],
        [InlineKeyboardButton(text="Give VIP 🌟" if not is_vip else "Remove VIP 🚫", callback_data=f"usrctrl_vip_{u_id}", style="success")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await loader_msg.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("usrctrl_"))
async def handle_user_actions(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    action = call.data.split("_")[1]
    u_id = int(call.data.split("_")[2])
    await state.update_data(target_u_id=u_id)
    if action == "ban":
        current_status = db_query("SELECT is_banned FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Yes, Ban", callback_data=f"confirm_ban_{u_id}", style="danger"), InlineKeyboardButton(text="❌ Cancel", callback_data="admin_user_control_start", style="danger")]
            ])
            await call.message.edit_text(f"⚠️ Are you sure you want to <b>BAN</b> user <code>{u_id}</code>?", reply_markup=kb, parse_mode='HTML')
            await state.set_state(AdminStates.confirm_ban)
        else:
            db_query("UPDATE users SET is_banned=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ User unbanned successfully!", show_alert=True)
            m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "vip":
        current_status = db_query("SELECT is_vip FROM users WHERE user_id=?", (u_id,), fetchone=True)[0]
        if current_status == 1:
            db_query("UPDATE users SET is_vip=0 WHERE user_id=?", (u_id,))
            await call.answer("✅ VIP Removed!", show_alert=True)
        else:
            db_query("UPDATE users SET is_vip=1, vip_since=? WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id))
            await call.answer("✅ VIP Granted!", show_alert=True)
        m = call.message; m.text = str(u_id); await process_user_lookup(m, state)
    elif action == "add":
        await call.message.edit_text("💰 Enter the amount to <b>ADD</b> to this user's wallet:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_money)
    elif action == "min":
        await call.message.edit_text("💸 Enter the amount to <b>DEDUCT</b> from this user's wallet:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_minus_money)
    elif action == "warn":
        await call.message.edit_text("⚠️ Type the strict warning message you want to send directly to this user:", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_warning)

@dp.callback_query(F.data.startswith("confirm_ban_"))
async def confirm_ban(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    u_id = int(call.data.split("_")[2])
    db_query("UPDATE users SET is_banned=1 WHERE user_id=?", (u_id,))
    await call.answer("🔴 User has been banned!", show_alert=True)
    await state.clear()
    m = call.message; m.text = str(u_id); await process_user_lookup(m, state)

@dp.message(AdminStates.wait_for_add_money)
async def exec_add_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance + ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Successfully added {fmt_curr(amt)} to target <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
        try: await bot.send_message(u_id, f"💰 <b>Wallet Top-up!</b>\nAdmin has manually added {fmt_curr(amt)} to your wallet.", parse_mode='HTML')
        except: pass
        await state.clear()
    except ValueError: await m.answer("❌ Critical Error: Input must be a valid number.")

@dp.message(AdminStates.wait_for_minus_money)
async def exec_minus_money(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        data = await state.get_data()
        u_id = data['target_u_id']
        db_query("UPDATE users SET balance = balance - ? WHERE user_id=?", (amt, u_id))
        await m.answer(f"✅ Successfully deducted {fmt_curr(amt)} from target <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Critical Error: Input must be a valid number.")

@dp.message(AdminStates.wait_for_warning)
async def exec_warn_user(m: Message, state: FSMContext):
    data = await state.get_data()
    u_id = data['target_u_id']
    warn_text = m.text
    db_query("UPDATE users SET warnings = warnings + 1 WHERE user_id=?", (u_id,))
    await m.answer(f"✅ Official warning dispatched to <code>{u_id}</code>.", reply_markup=admin_kb(), parse_mode='HTML')
    try: await bot.send_message(u_id, f"⚠️ <b>OFFICIAL WARNING FROM SYSTEM ADMIN:</b>\n\n{warn_text}\n\n<i>Subsequent infractions may lead to an automated grid ban.</i>", parse_mode='HTML')
    except: pass
    await state.clear()

# ==============================================================================
# 18. ADMIN STATISTICS
# ==============================================================================
@dp.callback_query(F.data == "admin_view_stats")
async def admin_dashboard_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    t_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    t_resellers = db_query("SELECT COUNT(*) FROM users WHERE is_reseller=1", fetchone=True)[0]
    t_vip = db_query("SELECT COUNT(*) FROM users WHERE is_vip=1", fetchone=True)[0]
    t_prods = db_query("SELECT COUNT(*) FROM products", fetchone=True)[0]
    t_keys = db_query("SELECT COUNT(*) FROM product_keys WHERE is_used=0", fetchone=True)[0]
    t_rev = db_query("SELECT SUM(spent) FROM users", fetchone=True)[0] or 0.0
    today_str = datetime.now().strftime("%Y-%m-%d")
    t_spins = db_query("SELECT COUNT(*) FROM users WHERE last_spin LIKE ?", (f"{today_str}%",), fetchone=True)[0]
    msg = (f"📊 <b><u>GRID INTELLIGENCE DASHBOARD</u></b> 📊\n━━━━━━━━━━━━━━━━━━\n👥 <b>Total Grid Users:</b> {t_users}\n👑 <b>Wholesale Resellers:</b> {t_resellers}\n🌟 <b>Elite VIP Members:</b> {t_vip}\n━━━━━━━━━━━━━━━━━━\n📦 <b>Active Products:</b> {t_prods}\n🔑 <b>Unused Keys in Vault:</b> {t_keys}\n💰 <b>Total Gross Revenue:</b> {fmt_curr(t_rev)}\n🎰 <b>Ludo Spins Today:</b> {t_spins}\n━━━━━━━━━━━━━━━━━━")
    await call.message.edit_text(msg, reply_markup=admin_back_kb(), parse_mode='HTML')

# ==============================================================================
# 18B. PRIVATE DATA / PAYMENT PROOF HELPERS
# =============================================================================
def normalize_channel_target(value: str) -> str:
    """Normalize common Telegram channel target formats for Bot API calls."""
    value = (value or "").strip()
    if not value:
        return ""
    # Telegram private-channel message links look like https://t.me/c/123456789/42.
    # Bot API chat_id for that channel is -100123456789.
    m = re.match(r"^https?://t\.me/c/(\d+)(?:/\d+)?/?$", value)
    if m:
        return "-100" + m.group(1)
    return value

async def validate_channel_target(value: str) -> Tuple[bool, str, str]:
    """Resolve the chat and verify that this bot can post to it."""
    target = normalize_channel_target(value)
    if not target:
        return False, "Channel ID is empty.", ""
    try:
        chat = await bot.get_chat(target)
    except Exception as e:
        return False, f"Telegram getChat failed: {str(e)[:350]}", target
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
    except Exception as e:
        return False, f"Could not check bot membership: {str(e)[:350]}", str(chat.id)
    status = getattr(member, "status", "")
    if status not in {"administrator", "creator"}:
        return False, f"Bot is not an admin in this chat (status={status}). Add the bot as channel admin.", str(chat.id)
    if getattr(chat, "type", "") == "channel" and status == "administrator" and getattr(member, "can_post_messages", True) is False:
        return False, "Bot is admin but 'Post Messages' permission is OFF. Enable it in channel admin rights.", str(chat.id)
    return True, f"Connected to {getattr(chat, 'title', 'Telegram chat')} (ID {chat.id}). Bot can post.", str(chat.id)

async def send_private_data_log(event: str, user_id: int, details: str = "") -> bool:
    channel=normalize_channel_target(get_setting("private_data_channel","").strip())
    if not channel:return False
    text=f"🗄 <b>VICKY X PRIVATE DATA LOG</b>\n━━━━━━━━━━━━━━━━━━\n<b>Event:</b> {event}\n<b>User ID:</b> <code>{user_id}</code>\n<b>Time:</b> {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}\n━━━━━━━━━━━━━━━━━━\n{details}"
    try:
        await bot.send_message(channel,text,parse_mode='HTML',disable_web_page_preview=True)
        return True
    except Exception as e:
        logger.exception(f"Private channel log failed for {channel}: {e}")
        return False

async def send_key_purchase_channel_log(user_id: int, details: str = "") -> bool:
    """Send actual purchased-key records only to the dedicated key channel.
    Never allow this log to leak into the public Payment Proof channel.
    The two settings may contain different representations (ID vs @username),
    so resolve both through Telegram before comparing them.
    """
    channel = normalize_channel_target(get_setting("key_purchase_channel", "").strip())
    proof_channel = normalize_channel_target(get_setting("payment_proof_channel", "").strip())
    if not channel:
        return False
    try:
        key_chat = await bot.get_chat(channel)
        if proof_channel:
            proof_chat = await bot.get_chat(proof_channel)
            if int(key_chat.id) == int(proof_chat.id):
                logger.warning("Blocked key-purchase log because Key Purchase Channel == Payment Proof Channel (%s)", key_chat.id)
                return False
    except Exception as e:
        # Raw normalized values are still checked as a final fallback.
        if proof_channel and channel == proof_channel:
            return False
        logger.warning("Could not resolve channel identity for separation check: %s", e)
    text = (
        "🔑 <b>VICKY X KEY PURCHASE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n"
        f"<b>Time:</b> {datetime.now().strftime('%d-%m-%Y %I:%M:%S %p')}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"{details}"
    )
    try:
        await bot.send_message(channel, text, parse_mode='HTML', disable_web_page_preview=True)
        return True
    except Exception as e:
        logger.exception(f"Key purchase channel log failed for {channel}: {e}")
        return False

async def send_payment_proof(user_id:int,product:str,duration:str,amount:float,key:str="",quantity:int=1,category:str="",panel_name:str="") -> bool:
    """Post the public purchase proof with premium custom emojis and a success CTA button.
    The key itself is intentionally hidden in the public proof channel.
    """
    channel=normalize_channel_target(get_setting("payment_proof_channel","").strip())
    if not channel:return False
    u=db_query("SELECT first_name, username FROM users WHERE user_id=?",(user_id,),fetchone=True)
    name=u[0] if u and u[0] else "Unknown"
    # Public proof deliberately contains only the short, non-sensitive proof
    # format. The verbose record (phone, status, device limit, delivery, etc.)
    # is stored in the private Data Save channel instead.
    text=(
        "🛍️ <b>New Key Purchased!</b>\n\n"
        f"👤 <b>Name:</b> {name}\n"
        f"🆔 <b>User ID:</b>\n<code>{user_id}</code>\n\n"
        f"📦 <b>Product:</b> ➤ {product}\n"
        f"⏳ <b>Duration:</b> {duration}\n"
        "🔑 <b>Key:</b>\n<code>****** (Hidden)</code>\n\n"
        f"🤖 <b>Bot:</b> @{BOT_USERNAME}"
    )
    # Public proof CTA: configurable from Button Designer. It always opens the
    # bot with /start and defaults to SUCCESS style.
    cta_text, cta_style, cta_emoji = _button_cfg("payment_proof_cta")
    cta_text = cta_text or "Open Bot / Buy Product"
    cta_style = cta_style or "success"
    if cta_style == "crime":
        cta_style = "danger"
    if cta_style not in {"primary", "success", "danger"}:
        cta_style = "success"
    cta_url = get_setting(
        "btn_url_payment_proof_cta",
        "https://t.me/Vickystor_bot?start=purchased"
    ).strip()
    if not cta_url:
        cta_url = "https://t.me/Vickystor_bot?start=purchased"
    cta_kwargs = {
        "text": cta_text,
        "url": cta_url,
        "style": cta_style,
    }
    if cta_emoji and str(cta_emoji).isdigit():
        cta_kwargs["icon_custom_emoji_id"] = str(cta_emoji)
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(**cta_kwargs)]])
    try:
        await bot.send_message(channel,text,reply_markup=kb,parse_mode='HTML',disable_web_page_preview=True)
        return True
    except Exception as e:
        logger.exception(f"Payment proof channel failed for {channel}: {e}")
        return False

def purchase_channel_kb() -> Optional[InlineKeyboardMarkup]:
    link=get_setting("purchase_channel_link","").strip()
    if not link or link.lower()=="none":return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📢 Join / Open Store Channel",url=link,style="success")]])

# 19. ADMIN PRODUCT MANAGEMENT
# ==============================================================================
@dp.callback_query(F.data == "admin_product_manager")
async def admin_product_manager(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    prods = db_query(
        "SELECT id, name, validity, delivery_mode, api_provider, api_pid, stock, is_active, duration_days, category, panel_name FROM products ORDER BY category, panel_name, name, duration_days, id",
        fetchall=True
    ) or []
    groups = {}
    for p in prods:
        identity = ((p[9] or '').strip().lower(), (p[10] or '').strip().lower(), (p[1] or '').strip().lower())
        groups.setdefault(identity, []).append(p)
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for _, rows in groups.items():
        p = rows[0]
        product_name = p[1]
        active = any(bool(r[7]) for r in rows)
        has_plans = any(str(r[3] or '').upper() != 'PARENT' for r in rows)
        status_icon = '🟢' if active else ('🟡' if not has_plans else '🔴')
        emoji_row = db_query(
            "SELECT premium_emoji_id FROM products WHERE id=?",
            (p[0],), fetchone=True
        )
        product_emoji_id = str(emoji_row[0]).strip() if emoji_row and emoji_row[0] else ''
        if not product_emoji_id.isdigit():
            product_emoji_id = get_emoji_icon("product_store")
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{status_icon} {product_name}",
                callback_data=f"admin_product_group_{p[0]}",
                icon_custom_emoji_id=product_emoji_id or None,
                style="success" if active else "primary"
            )
        ])
    kb.inline_keyboard += [
        [InlineKeyboardButton(text="➕ Add / Update Product", callback_data="admin_add_prod", icon_custom_emoji_id=get_emoji_icon("product_store"), style="success")],
        [InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ]
    await call.message.edit_text(
        "🛒 <b>PRODUCT MANAGER</b>\n\nAll added products are shown here <b>once</b>. Plans are hidden on this screen.\n\nTap a product to open it, then its plans will be shown inside that product.",
        reply_markup=kb, parse_mode='HTML'
    )

@dp.callback_query(F.data.startswith("admin_product_group_"))
async def admin_product_group(call: CallbackQuery):
    """PRODUCT MANAGER: compact product editor matching the requested layout.
    Product-level settings stay here; plan editing is handled by Edit Days and
    API PID editing is handled by Edit PID -> select a plan -> set PID.
    """
    if call.from_user.id != ADMIN_ID:
        return
    try:
        base_id = int(call.data.split("admin_product_group_", 1)[1])
    except Exception:
        return await call.answer("Invalid product.", show_alert=True)

    base = db_query(
        "SELECT id, category, panel_name, name, is_active, delivery_mode, device_limit, gameplay_video, premium_emoji_id, apk_link "
        "FROM products WHERE id=?",
        (base_id,), fetchone=True
    )
    if not base:
        return await call.answer("Product not found.", show_alert=True)

    _, category, panel_name, product_name, is_active, delivery_mode, device_limit, gameplay_video, premium_emoji_id, apk_link = base
    rows = db_query(
        "SELECT id, price_inr, reseller_price, stock, validity, duration_days, is_active, api_pid, api_duration "
        "FROM products WHERE category=? AND panel_name=? AND name=? "
        "AND COALESCE(is_product_parent,0)=0 ORDER BY duration_days, id",
        (category, panel_name, product_name), fetchall=True
    ) or []

    delivery_mode = (delivery_mode or "MANUAL").upper()
    status_text = "ACTIVE" if is_active else "INACTIVE"

    provider_row = db_query("SELECT api_provider FROM products WHERE id=?", (base_id,), fetchone=True)
    provider = provider_row[0] if provider_row and provider_row[0] else "PANELSTORE"
    android_row = db_query("SELECT api_android_id_required FROM products WHERE id=?", (base_id,), fetchone=True)
    android_required = bool(android_row and android_row[0])

    text = (
        f"{get_emoji('product_store')} <b>PRODUCT CONFIG</b> 🛡\n\n"
        f"➡️ <b>Product:</b>\n<code>{product_name or 'NOT SET'}</code>\n\n"
        f"🔎 <b>Status:</b> {'🟢' if is_active else '🔴'}\n<code>{status_text}</code>\n\n"
        f"🔥 <b>Mode:</b> 📣\n<code>{'PRODUCT' if delivery_mode == 'PARENT' else delivery_mode}</code>\n\n"
        f"➡️ <b>Compatible Device:</b>\n💥\n<code>{device_limit or '1 Device'}</code>\n\n"
        f"▶️ <b>Gameplay Video Link:</b>\n🔗\n<code>{gameplay_video or 'NOT ADDED'}</code>\n\n"
        f"➡️ <b>Premium Emoji:</b>\n{custom_emoji(str(premium_emoji_id).strip(), '✨') if str(premium_emoji_id or '').strip().isdigit() else '✨'} <code>{premium_emoji_id or get_emoji_icon('product_store') or 'NOT ADDED'}</code>\n\n"
        "© <b>Plans:</b>\n▶️\n"
    )
    for pid, price, rprice, stock, validity, days, active, api_pid, api_duration in rows:
        label = validity or (f"{days} Days" if days else "Lifetime")
        text += f"• {label}:\n  ├ User: {fmt_curr(price)}\n  └ Reseller: {fmt_curr(rprice)}\n"
    if not rows:
        text += "<i>No plans added yet. Use MANAGE PLANS / ADD PLAN.</i>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[])
    kb.inline_keyboard.extend([
        [
            InlineKeyboardButton(text="Edit Panel Group 🏷️", callback_data=f"edit_p_{base_id}_cat", style="primary"),
            InlineKeyboardButton(text="Edit Panel Name 🏷️", callback_data=f"edit_p_{base_id}_panel_name", style="primary")
        ],
        [InlineKeyboardButton(text="Edit Package Name ✏️", callback_data=f"edit_p_{base_id}_name", style="primary")],
        [InlineKeyboardButton(text="🎨 Edit Product Emoji", callback_data=f"edit_p_{base_id}_premium_emoji", style="primary")],
        [InlineKeyboardButton(text="📅 MANAGE PLANS / ADD PLAN", callback_data=f"edit_days_panel_{base_id}", style="success")],
        [
            InlineKeyboardButton(text="Nuke Full Product 🗑", callback_data=f"delete_p_{base_id}", style="danger"),
            InlineKeyboardButton(text="↩ BACK", callback_data="admin_product_manager", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
        ]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML', disable_web_page_preview=True)

@dp.callback_query(F.data == "admin_add_prod")
async def add_prod_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        emoji_id = get_category_emoji(cat)
        kb.inline_keyboard.append([InlineKeyboardButton(text=cat, callback_data=f"addprod_cat_{cat}", icon_custom_emoji_id=emoji_id, style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Cancel", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("<b>Step 1:</b> Choose the <b>Category</b> for this product:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("addprod_cat_"))
async def add_prod_category_selected(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    category = call.data.split("addprod_cat_", 1)[1]
    await state.update_data(cat=category)
    await call.message.edit_text(f"<b>Step 2:</b> Enter <b>PANEL NAME</b>\n(e.g., 'MST PANEL', 'DRIP PANEL'):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_panel_name)

@dp.message(AdminStates.add_prod_panel_name)
async def add_prod_panel_name(m: Message, state: FSMContext):
    await state.update_data(panel_name=m.text)
    await m.answer("<b>Step 3:</b> Enter <b>PRODUCT NAME</b>\n(e.g., Bala Mod Menu Pro). This product can contain multiple plans/durations.", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_name)

@dp.message(AdminStates.add_prod_name)
async def add_prod_name(m: Message, state: FSMContext):
    # Add Product creates only the parent/product identity. Plans are added later
    # from Product Manager -> Add New Plan.
    data = await state.get_data()
    if data.get("add_plan_mode"):
        return await m.answer(
            "<b>Plan is being added inside the selected Product.</b>\n\n"
            "⏳ Enter <b>DURATION IN DAYS</b> (example: 1, 4, 7, 30).",
            parse_mode='HTML'
        )
    name = (m.text or '').strip()
    if not name:
        return await m.answer("❌ Product name cannot be empty.")
    await state.update_data(name=name)
    await m.answer(
        "🎨 Enter the <b>PRODUCT CUSTOM EMOJI ID</b>.\n\n"
        "Send the numeric Telegram custom emoji ID, or send <code>none</code> to use the default store emoji.",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.add_prod_emoji)

@dp.message(AdminStates.add_prod_emoji)
async def add_prod_emoji(m: Message, state: FSMContext):
    emoji_id = (m.text or '').strip()
    if emoji_id.lower() == 'none':
        emoji_id = ''
    elif not emoji_id.isdigit():
        return await m.answer(
            "❌ Product Custom Emoji ID must be numeric, or send <code>none</code>.",
            reply_markup=admin_back_kb(), parse_mode='HTML'
        )

    data = await state.get_data()
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO products "
            "(category, panel_name, name, price_inr, reseller_price, stock, apk_link, validity, "
            "device_limit, delivery_mode, is_active, premium_emoji_id, is_product_parent) "
            "VALUES (?, ?, ?, 0, 0, 0, '', '', '1 Device', 'PARENT', 0, ?, 1)",
            (data['cat'], data.get('panel_name', ''), data['name'], emoji_id)
        )
        parent_id = c.lastrowid
        # Parent stores the authoritative product-level emoji. Plans created later
        # inherit this value, and the Product Manager also reads this exact field.
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    await state.clear()
    await m.answer(
        "<b>✅ PRODUCT ADDED</b>\n\n"
        f"📦 Category: <code>{data['cat']}</code>\n"
        f"📁 Panel: <code>{data.get('panel_name', '')}</code>\n"
        f"🎮 Product: <code>{data['name']}</code>\n"
        f"🎨 Custom Emoji ID: <code>{emoji_id or 'DEFAULT'}</code>\n"
        f"🆔 Product ID: <code>{parent_id}</code>\n\n"
        "Now open <b>Product Manager</b> → open this product → <b>EDIT DAYS</b> → <b>ADD NEW PLAN</b> to add durations, prices, stock and API settings.",
        reply_markup=admin_kb(), parse_mode='HTML'
    )

@dp.message(AdminStates.add_prod_validity)
async def add_prod_validity(m: Message, state: FSMContext):
    raw=m.text.strip()
    try:
        days=int(raw)
        if days<=0: raise ValueError
        validity=f"{days} Days"
    except ValueError:
        validity,days=raw,0
    await state.update_data(validity=validity,duration_days=days,api_duration=str(days) if days else raw)
    await m.answer("📱 Enter strict Device Enforcement Limit (e.g., '1 Device HWID'):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_device_limit)

@dp.message(AdminStates.add_prod_device_limit)
async def add_prod_device_limit(m: Message, state: FSMContext):
    await state.update_data(device_limit=m.text)
    await m.answer("💰 Enter standard **User Price** in Rupees (₹) (e.g., 500):", parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_price)

@dp.message(AdminStates.add_prod_price)
async def add_prod_price(m: Message, state: FSMContext):
    try:
        await state.update_data(price=float(m.text))
        await m.answer("👑 Enter wholesale **Reseller Price** in Rupees (₹) (e.g., 300):", parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_reseller_price)
    except ValueError: await m.answer("❌ Invalid input datatype! Must be numerical.")

@dp.message(AdminStates.add_prod_reseller_price)
async def add_prod_reseller_price(m: Message, state: FSMContext):
    try:
        await state.update_data(reseller_price=float(m.text), apk="")
        data = await state.get_data()

        if data.get("add_plan_mode") and data.get("parent_product_id"):
            # Every new plan gets its own delivery/API configuration. Do not copy
            # the parent's PID/provider because each plan may point to a different
            # API product and duration.
            await state.update_data(
                delivery_mode="", api_provider="", api_pid="", api_duration="", apk=""
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="API MODE", callback_data="addprod_mode_api", style="success"),
                 InlineKeyboardButton(text="MANUAL MODE", callback_data="addprod_mode_manual", style="primary")],
                [InlineKeyboardButton(text="BACK", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
            ])
            await m.answer("🔌 <b>Select delivery mode for this plan:</b>", reply_markup=kb, parse_mode='HTML')
            await state.set_state(AdminStates.add_prod_mode)
            return

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="API MODE", callback_data="addprod_mode_api", style="success"),
             InlineKeyboardButton(text="MANUAL MODE", callback_data="addprod_mode_manual", style="primary")],
            [InlineKeyboardButton(text="BACK", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        await m.answer("🔌 <b>Select delivery mode for this plan:</b>", reply_markup=kb, parse_mode='HTML')
        await state.set_state(AdminStates.add_prod_mode)
    except ValueError:
        await m.answer("❌ Invalid input datatype! Must be numerical.")

@dp.callback_query(F.data == "addprod_mode_manual")
async def addprod_mode_manual(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await state.update_data(delivery_mode="MANUAL", api_provider="", api_pid="", api_duration="")
    await call.message.edit_text("📥 <b>Vault Injection Phase</b>\n\nPaste manual license keys, one key per line:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_keys)

@dp.callback_query(F.data == "addprod_mode_api")
async def addprod_mode_api(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="PanelStore", callback_data="addprod_provider_PANELSTORE", style="primary")], [InlineKeyboardButton(text="BantiBhaiya", callback_data="addprod_provider_BANTIBHAIYA", style="primary")]])
    await state.update_data(delivery_mode="API")
    await call.message.edit_text("🔌 <b>Choose API Provider</b>", reply_markup=kb, parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_provider)

@dp.callback_query(F.data.startswith("addprod_provider_"))
async def addprod_provider(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    provider = call.data.split("addprod_provider_", 1)[1]
    await state.update_data(api_provider=provider)
    await call.message.edit_text("🔑 Enter the API Product PID:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_prod_pid)

@dp.message(AdminStates.add_prod_pid)
async def addprod_pid(m: Message, state: FSMContext):
    pid = (m.text or '').strip()
    if not pid:
        return await m.answer("❌ API Product PID cannot be empty.")
    data = await state.get_data()
    # API duration is a plan-level setting. Default it to the plan duration, but
    # allow the admin to enter a provider-specific API duration right here.
    await state.update_data(api_pid=pid, api_duration=data.get('api_duration', ''))
    await m.answer(
        "⏳ Enter <b>API DURATION / DAYS</b> for this plan.\n"
        f"Current plan duration: <code>{data.get('validity', 'Not set')}</code>\n"
        "Send <code>same</code> to use the plan duration.",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.add_prod_api_duration)

@dp.message(AdminStates.add_prod_api_duration)
async def addprod_api_duration(m: Message, state: FSMContext):
    raw = (m.text or '').strip()
    data = await state.get_data()
    if raw.lower() == 'same':
        api_duration = str(data.get('duration_days') or data.get('validity') or '')
    else:
        try:
            days = int(raw)
            if days <= 0:
                raise ValueError
            api_duration = str(days)
        except ValueError:
            return await m.answer("❌ Enter a valid API duration number, or send <code>same</code>.", parse_mode='HTML')
    await state.update_data(api_duration=api_duration)
    await m.answer(
        "📥 <b>API PLAN READY.</b> No manual keys are needed. Send <code>NONE</code> to save this plan.",
        reply_markup=admin_back_kb(), parse_mode='HTML'
    )
    await state.set_state(AdminStates.add_prod_keys)

@dp.message(AdminStates.add_prod_keys)
async def add_prod_keys(m: Message, state: FSMContext):
    # IMPORTANT:
    # "Add Product" and "Add Plan" are CREATE operations. They must NEVER
    # overwrite an existing plan. Each submitted plan gets its own product row
    # (unique id), while the User Store groups rows having the same
    # category/panel/product name and displays every row as a separate plan.
    raw_keys = (m.text or "").strip()
    keys = [k.strip() for k in raw_keys.split('\n') if k.strip() and k.strip().upper() != "NONE"]
    data = await state.get_data()
    stock = len(keys)
    duration_days = int(data.get('duration_days', 0) or 0)
    delivery_mode = data.get('delivery_mode', 'MANUAL')
    api_provider = data.get('api_provider', '')
    api_pid = data.get('api_pid', '')
    api_duration = data.get('api_duration', data['validity'])

    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    try:
        # Add Plan has NO duplicate-duration restriction.
        # Even if the same Product already has a 3 Days plan, another 3 Days
        # plan is created as a separate row with its own ID and Buy button.
        # ALWAYS CREATE a fresh row. There is intentionally no UPDATE path here.
        c.execute(
            "INSERT INTO products "
            "(category, panel_name, name, price_inr, reseller_price, stock, apk_link, "
            "validity, device_limit, delivery_mode, api_provider, api_pid, api_duration, "
            "duration_days, is_active, premium_emoji_id, is_product_parent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '', 0)",
            (
                data['cat'], data['panel_name'], data['name'],
                data['price'], data['reseller_price'], stock, data['apk'],
                data['validity'], data['device_limit'], delivery_mode,
                api_provider, api_pid, api_duration, duration_days
            )
        )
        prod_id = c.lastrowid

        for k in keys:
            c.execute(
                "INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)",
                (prod_id, k)
            )

        # Keep the cached stock column synchronized with actual unused keys.
        if delivery_mode.upper() == "MANUAL":
            c.execute(
                "UPDATE products SET stock=("
                "SELECT COUNT(*) FROM product_keys WHERE product_id=? AND is_used=0"
                ") WHERE id=?",
                (prod_id, prod_id)
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    actual_stock = db_query(
        "SELECT stock FROM products WHERE id=?", (prod_id,), fetchone=True
    )
    actual_stock = actual_stock[0] if actual_stock else stock

    if data.get("add_plan_mode"):
        result_title = "Plan added successfully — existing plans were not changed"
    else:
        result_title = "Product added successfully — existing products were not changed"

    await m.answer(
        f"<b>✅ {result_title}</b>\n\n"
        f"📦 Category: <code>{data['cat']}</code>\n"
        f"📁 Panel: <code>{data['panel_name']}</code>\n"
        f"🎮 Product: <code>{data['name']}</code>\n"
        f"⏳ Plan: <code>{data['validity']}</code>\n"
        f"🆔 New Product/Plan ID: <code>{prod_id}</code>\n"
        f"🔒 Stock: <code>{actual_stock}</code>\n"
        f"💰 User Price: {fmt_curr(data['price'])} | 👑 Reseller: {fmt_curr(data['reseller_price'])}\n\n"
        "The new plan will appear as its own Buy button in the User Store.",
        reply_markup=admin_kb(), parse_mode='HTML'
    )
    await state.clear()

@dp.callback_query(F.data == "admin_manage_prods")
async def admin_manage_prods(call: CallbackQuery):
    # Keep the old callback compatible, but use the single grouped Product
    # Manager UI so plans are never mixed into the top-level product list.
    if call.from_user.id != ADMIN_ID: return
    return await admin_product_manager(call)

async def _legacy_admin_manage_prods_unused(call: CallbackQuery):
    prods = db_query("SELECT id, name, category, panel_name, stock, is_active, duration_days FROM products ORDER BY category, panel_name, duration_days, id", fetchall=True)
    if not prods: return await call.message.edit_text("📦 Store Database is completely empty.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    seen_products = set()
    for p in prods:
        identity = ((p[2] or "").strip().lower(), (p[3] or "").strip().lower(), (p[1] or "").strip().lower(), int(p[6] or 0))
        if identity in seen_products:
            continue
        seen_products.add(identity)
        status_dot = "🟢" if p[5] else "🔴"
        panel_name = p[3] if p[3] is not None else ""
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{status_dot} [{p[2]}] {panel_name} - {p[1]} (Stock: {p[4]})", callback_data=f"admin_view_p_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("📦 <b>Database Editor: Select Node to modify</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("admin_view_p_"))
async def admin_view_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    try:
        p_id = int(call.data.split("_")[3])
        prod = db_query("SELECT * FROM products WHERE id=?", (p_id,), fetchone=True)
        if not prod: return await call.answer("❌ Architecture fault: Node lost!", show_alert=True)
        panel_name = prod[2] if prod[2] is not None else ""
        price_inr = safe_float(prod[4])
        reseller_price = safe_float(prod[5])
        text = (f"📦 <b><u>NODE DEEP DIVE DETAILS</u></b>\n━━━━━━━━━━━━━━━━━━\n<b>ID:</b> <code>{prod[0]}</code>\n<b>Panel Group:</b> {prod[1]}\n<b>Panel Name:</b> {panel_name}\n<b>Package Date/Time:</b> {prod[3]}\n<b>Standard Price:</b> {fmt_curr(price_inr)}\n👑 <b>Wholesale Price:</b> {fmt_curr(reseller_price)}\n<b>Vault Stock:</b> {prod[6]}\n<b>Payload Link:</b> {prod[7] if prod[7] else 'None'}\n<b>Time Config:</b> {prod[8]}\n<b>HWID Limit:</b> {prod[9]}\n<b>Delivery Mode:</b> {prod[11] or 'MANUAL'}\n<b>API Provider:</b> {prod[12] or 'None'}\n<b>API PID:</b> {prod[13] or 'None'}\n<b>API Duration:</b> {prod[14] or prod[8]}\n<b>Android ID Required:</b> {'Yes' if prod[15] else 'No'}\n<b>Visibility:</b> {'Active' if prod[10] else 'Hidden'}\n━━━━━━━━━━━━━━━━━━")
        toggle_btn_text = "Hide Product 👁‍🗨" if prod[10] else "Unhide Product 👁"
        delivery_mode = (prod[11] or "MANUAL").upper()
        api_provider = prod[12] or "Not selected"
        api_pid = prod[13] or "Not set"
        api_duration = prod[14] or prod[8] or "Not set"
        android_required = int(prod[15] or 0)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Edit Panel Group 🏷️", callback_data=f"edit_p_{p_id}_cat", style="primary"), InlineKeyboardButton(text="Edit Panel Name 🏷️", callback_data=f"edit_p_{p_id}_panel_name", style="primary")],
            [InlineKeyboardButton(text="Edit Package Name ✏️", callback_data=f"edit_p_{p_id}_name", style="primary")],
            [InlineKeyboardButton(text="Edit Price 💰", callback_data=f"edit_p_{p_id}_price", style="primary"), InlineKeyboardButton(text="Edit R-Price 👑", callback_data=f"edit_p_{p_id}_rprice", style="primary")],
            [InlineKeyboardButton(text="Edit Validity ⏳", callback_data=f"edit_p_{p_id}_validity", style="primary"), InlineKeyboardButton(text="Edit Device 📱", callback_data=f"edit_p_{p_id}_device", style="primary")],
            [InlineKeyboardButton(text=f"API MODE {'✅' if delivery_mode == 'API' else ''}", callback_data=f"prod_mode_api_{p_id}", style="success" if delivery_mode == 'API' else "primary"), InlineKeyboardButton(text=f"MANUAL MODE {'✅' if delivery_mode == 'MANUAL' else ''}", callback_data=f"prod_mode_manual_{p_id}", style="success" if delivery_mode == 'MANUAL' else "primary")],
            [InlineKeyboardButton(text="EDIT PID", callback_data=f"edit_p_{p_id}_api_pid", style="primary"), InlineKeyboardButton(text="📅 MANAGE PLANS", callback_data=f"edit_days_panel_{p_id}", style="success")],
            [InlineKeyboardButton(text=f"API: {api_provider}", callback_data=f"choose_provider_{p_id}", style="primary")],
            [InlineKeyboardButton(text=f"Android ID: {'ON' if android_required else 'OFF'}", callback_data=f"toggle_android_id_{p_id}", style="success" if android_required else "primary")],
            [InlineKeyboardButton(text="Add Keys ➕", callback_data=f"edit_p_{p_id}_keys", style="success")],
            [InlineKeyboardButton(text="Delete Key 🗑", callback_data=f"delkey_p_{p_id}", style="danger"), InlineKeyboardButton(text=toggle_btn_text, callback_data=f"toggle_p_{p_id}", style="primary")],
            [InlineKeyboardButton(text="Nuke Full Node 🗑", callback_data=f"delete_p_{p_id}", style="danger"), InlineKeyboardButton(text="BACK", callback_data="admin_manage_prods", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
        ])
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error in admin_view_product: {e}")
        await call.message.edit_text(f"❌ Error loading product: {str(e)}", reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data.startswith("toggle_p_"))
async def admin_toggle_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    row = db_query(
        "SELECT category, panel_name, name, COALESCE(is_product_parent,0), is_active FROM products WHERE id=?",
        (p_id,), fetchone=True
    )
    if not row:
        return await call.answer("Product not found.", show_alert=True)
    category, panel_name, name, is_parent, current = row
    new_val = 0 if current == 1 else 1
    if is_parent:
        db_query(
            "UPDATE products SET is_active=? WHERE category=? AND panel_name=? AND name=? AND COALESCE(is_product_parent,0)=0",
            (new_val, category, panel_name, name)
        )
        await call.answer("All plans visibility updated successfully!", show_alert=True)
        return await admin_product_group(call)
    db_query("UPDATE products SET is_active=? WHERE id=?", (new_val, p_id))
    await call.answer("Plan visibility updated successfully!", show_alert=True)
    await admin_view_product(call)

# ==============================================================================
# FIX: Edit product field – correctly handle different data types and multi-word fields
# ==============================================================================

@dp.callback_query(F.data.startswith("edit_days_panel_"))
async def edit_days_panel(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return
    try:
        p_id = int(call.data.split("_")[-1])
    except Exception:
        return await call.answer("Invalid product.", show_alert=True)
    base = db_query("SELECT category, panel_name, name FROM products WHERE id=?", (p_id,), fetchone=True)
    if not base:
        return await call.answer("Product not found.", show_alert=True)
    category, panel_name, product_name = base
    rows = db_query(
        "SELECT id, price_inr, reseller_price, stock, validity, duration_days, is_active "
        "FROM products WHERE category=? AND panel_name=? AND name=? "
        "AND COALESCE(is_product_parent,0)=0 ORDER BY duration_days, id",
        (category, panel_name, product_name), fetchall=True
    ) or []

    text = (
        f"{get_emoji('product_store')} <b>EDIT PRODUCT DAYS</b> 🛡\n\n"
        f"➡️ <b>Product:</b> <code>{product_name or 'Unnamed'}</code>\n"
        f"📌 <b>Existing plans:</b> select one to manage it.\n➕ <b>Add Plan</b> always creates a NEW plan and never overwrites an old one."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for rid, price, rprice, stock, validity, days, active in rows:
        label = (validity or (f"{days} DAYS" if days else "PLAN")).upper()
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{'🟢' if active else '🔴'} {label} • ₹{safe_float(price):g} / ₹{safe_float(rprice):g}",
                callback_data=f"admin_view_p_{rid}",
                style="success" if active else "primary"
            )
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="➕ ADD NEW PLAN", callback_data=f"add_plan_for_panel_{p_id}", style="success")
    ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="↩ BACK TO PRODUCT", callback_data=f"admin_product_group_{p_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("add_plan_for_panel_"))
async def add_plan_for_panel(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    try:
        p_id = int(call.data.split("_")[-1])
    except Exception:
        return await call.answer("Invalid panel.", show_alert=True)
    row = db_query("SELECT category, panel_name, name FROM products WHERE id=?", (p_id,), fetchone=True)
    if not row:
        return await call.answer("Product not found.", show_alert=True)
    # IMPORTANT: Add Plan must keep the exact parent product name.
    # The old flow asked for a new product name, which created entries such as
    # "1 DAY" / "3 DAY" as separate products in Product Store.
    await state.update_data(
        cat=row[0],
        panel_name=row[1] or "",
        name=row[2] or "",
        add_plan_mode=True,
        parent_product_id=p_id,
        apk="",
    )
    await call.message.edit_text(
        "<b>ADD PLAN INSIDE PRODUCT</b>\n\n"
        f"Product: <code>{row[2] or 'Unnamed'}</code>\n"
        f"Panel: <code>{row[1] or 'Unnamed'}</code>\n\n"
        "⏳ Enter <b>DURATION IN DAYS</b> (example: 1, 3, 7, 15, 30):",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.add_prod_validity)

@dp.callback_query(F.data.startswith("delete_plan_"))
async def delete_plan(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    try:
        p_id = int(call.data.split("_")[-1])
    except Exception:
        return await call.answer("Invalid plan.", show_alert=True)
    row = db_query("SELECT category, panel_name, name, COALESCE(is_product_parent,0) FROM products WHERE id=?", (p_id,), fetchone=True)
    if not row:
        return await call.answer("Plan not found.", show_alert=True)
    if row[3]:
        return await call.answer("❌ The product itself cannot be deleted from the Plan screen. Use Nuke Full Node from Product Manager.", show_alert=True)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="YES, DELETE PLAN", callback_data=f"confirm_delete_plan_{p_id}", style="danger")],
        [InlineKeyboardButton(text="CANCEL", callback_data=f"edit_days_panel_{p_id}", style="primary")]
    ])
    await call.message.edit_text(
        f"⚠️ <b>Delete Plan?</b>\n\n<code>{row[2]}</code>\nPanel: <code>{row[1] or 'Unnamed'}</code>\n\nThis removes the plan and its unused keys.",
        reply_markup=kb, parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("confirm_delete_plan_"))
async def confirm_delete_plan(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    try:
        p_id = int(call.data.split("_")[-1])
    except Exception:
        return await call.answer("Invalid plan.", show_alert=True)
    row = db_query("SELECT category, panel_name FROM products WHERE id=?", (p_id,), fetchone=True)
    db_query("DELETE FROM product_keys WHERE product_id=?", (p_id,))
    db_query("DELETE FROM products WHERE id=?", (p_id,))
    await call.answer("✅ Plan deleted.", show_alert=True)
    await admin_manage_prods(call)

@dp.callback_query(F.data.startswith("edit_pid_panel_"))
async def edit_pid_panel(call: CallbackQuery):
    """Show all plans of this product; selecting one opens PID input for that plan."""
    if call.from_user.id != ADMIN_ID:
        return
    try:
        p_id = int(call.data.split("_")[-1])
    except Exception:
        return await call.answer("Invalid product.", show_alert=True)
    base = db_query("SELECT category, panel_name, name FROM products WHERE id=?", (p_id,), fetchone=True)
    if not base:
        return await call.answer("Product not found.", show_alert=True)
    category, panel_name, product_name = base
    rows = db_query(
        "SELECT id, validity, duration_days, api_pid, api_duration FROM products "
        "WHERE category=? AND panel_name=? AND name=? "
        "AND COALESCE(is_product_parent,0)=0 ORDER BY duration_days, id",
        (category, panel_name, product_name), fetchall=True
    ) or []
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    text = (
        f"{get_emoji('product_store')} <b>EDIT PID</b> 🛡\n\n"
        f"➡️ <b>Product:</b> <code>{product_name or 'Unnamed'}</code>\n"
        "📌 <b>Select a plan to set/change its API PID:</b>"
    )
    for rid, validity, days, api_pid, api_duration in rows:
        label = (validity or (f"{days} DAYS" if days else "PLAN")).upper()
        pid_text = str(api_pid).strip() if api_pid else "NOT SET"
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{label} • PID: {pid_text}",
                callback_data=f"edit_pid_plan_{rid}",
                style="primary"
            )
        ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="↩ BACK", callback_data=f"admin_product_group_{p_id}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data.startswith("edit_pid_plan_"))
async def edit_pid_plan(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        return
    try:
        p_id = int(call.data.split("_")[-1])
    except Exception:
        return await call.answer("Invalid plan.", show_alert=True)
    row = db_query(
        "SELECT category, panel_name, name, validity, duration_days, api_pid, api_duration FROM products WHERE id=?",
        (p_id,), fetchone=True
    )
    if not row:
        return await call.answer("Plan not found.", show_alert=True)
    category, panel_name, product_name, validity, days, current_pid, api_duration = row
    label = validity or (f"{days} Days" if days else "Lifetime")
    await state.update_data(edit_p_id=p_id, edit_field="api_pid")
    await call.message.edit_text(
        f"🆔 <b>SET API PID</b> 🛡\n\n"
        f"📦 Product: <code>{product_name}</code>\n"
        f"⏳ Plan: <code>{label}</code>\n"
        f"🔢 Current PID: <code>{current_pid or 'NOT SET'}</code>\n\n"
        "Send the new <b>API PID</b> for this plan:",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.wait_for_new_value)

@dp.callback_query(F.data.startswith("edit_p_"))
async def start_edit_product(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    # Use split with maxsplit=3 to keep field name intact (may contain underscores)
    parts = call.data.split("_", 3)
    if len(parts) < 4:
        return await call.answer("Invalid callback data.", show_alert=True)
    p_id = int(parts[2])
    field = parts[3]
    await state.update_data(edit_p_id=p_id, edit_field=field)
    if field == 'keys':
        await call.message.edit_text("📥 <b>Vault Injection</b>\nPaste the <b>NEW KEYS</b> to append to the stock (1 key per line):", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_add_keys)
    else:
        field_name_map = {'cat': 'New Panel Group/Category Name', 'panel_name': 'New Panel Name', 'name': 'New Package/Date Name', 'price': 'New Standard Price in ₹', 'rprice': 'New Reseller Price in ₹', 'validity': 'New Time Validity String', 'device': 'New HWID Limit String', 'premium_emoji': 'New Product Custom Emoji ID', 'api_pid': 'API Product PID', 'api_duration': 'API Duration/Days'}
        await call.message.edit_text(f"✏️ Input the required data for: <b>{field_name_map.get(field, field)}</b>", reply_markup=admin_back_kb(), parse_mode='HTML')
        await state.set_state(AdminStates.wait_for_new_value)

@dp.message(AdminStates.wait_for_new_value)
async def process_edit_value(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['edit_p_id']; field = data['edit_field']; new_val = m.text.strip()
    
    # Convert price fields to float, others remain strings
    if field in ['price', 'rprice']:
        try:
            new_val = float(new_val)
        except ValueError:
            return await m.answer("❌ Invalid number format. Please enter a valid price (e.g., 500).")
    elif field == 'apk':
        new_val = "" if new_val.lower() == 'none' else new_val
    elif field in {'validity', 'api_duration'}:
        raw = str(new_val).strip()
        try:
            days_value = int(raw)
            if days_value <= 0:
                raise ValueError
            new_val = f"{days_value} Days"
        except ValueError:
            days_value = 0
            new_val = raw
        col = 'api_duration' if field == 'api_duration' else 'validity'
        db_query(f"UPDATE products SET {col}=?, duration_days=? WHERE id=?", (new_val, days_value, p_id))
        await m.answer("✅ <b>Days updated successfully!</b>", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
        return
    if field == 'premium_emoji':
        if new_val.lower() == 'none':
            new_val = ""
        elif not new_val.isdigit():
            return await m.answer("❌ Product Emoji ID must be numeric, or send <code>none</code>.", reply_markup=admin_back_kb(), parse_mode='HTML')

    db_col_map = {'cat': 'category', 'panel_name': 'panel_name', 'name': 'name', 'price': 'price_inr', 'rprice': 'reseller_price', 'device': 'device_limit', 'premium_emoji': 'premium_emoji_id', 'api_pid': 'api_pid'}

    if field == 'premium_emoji':
        # Product emoji belongs to the whole Product, not one individual plan.
        # Save it on the selected product and propagate it to all plans so every
        # Product Manager / Store view resolves the same custom emoji.
        identity = db_query(
            "SELECT category, panel_name, name FROM products WHERE id=?",
            (p_id,), fetchone=True
        )
        db_query("UPDATE products SET premium_emoji_id=? WHERE id=?", (new_val, p_id))
        if identity:
            db_query(
                "UPDATE products SET premium_emoji_id=? WHERE category=? AND panel_name=? AND name=?",
                (new_val, identity[0], identity[1], identity[2])
            )
    else:
        db_query(f"UPDATE products SET {db_col_map[field]}=? WHERE id=?", (new_val, p_id))

    await m.answer("✅ <b>Product updated successfully!</b>", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.message(AdminStates.wait_for_add_keys)
async def process_add_keys(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['edit_p_id']
    keys = [k.strip() for k in m.text.strip().split('\n') if k.strip()]
    if len(keys) == 0: return await m.answer("❌ Protocol breach: Zero valid keys found.", reply_markup=admin_kb(), parse_mode='HTML')
    conn = sqlite3.connect('yp_shop.db')
    c = conn.cursor()
    for k in keys: c.execute("INSERT INTO product_keys (product_id, key_text) VALUES (?, ?)", (p_id, k))
    c.execute("UPDATE products SET stock = stock + ? WHERE id=?", (len(keys), p_id))
    conn.commit(); conn.close()
    await m.answer(f"✅ <b>Vault Secure!</b> {len(keys)} new keys appended and encrypted.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data.startswith("prod_mode_api_"))
async def set_product_api_mode(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    pid = int(call.data.split("_")[-1]); db_query("UPDATE products SET delivery_mode='API' WHERE id=?", (pid,)); await call.answer("API MODE selected", show_alert=True); await admin_view_product(call)

@dp.callback_query(F.data.startswith("prod_mode_manual_"))
async def set_product_manual_mode(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    pid = int(call.data.split("_")[-1]); db_query("UPDATE products SET delivery_mode='MANUAL' WHERE id=?", (pid,)); await call.answer("MANUAL MODE selected", show_alert=True); await admin_view_product(call)

@dp.callback_query(F.data.startswith("choose_provider_"))
async def choose_api_provider(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    pid = int(call.data.split("_")[-1])
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="PanelStore", callback_data=f"set_provider_PANELSTORE_{pid}", style="primary")],
        [InlineKeyboardButton(text="BantiBhaiya", callback_data=f"set_provider_BANTIBHAIYA_{pid}", style="primary")],
        [InlineKeyboardButton(text="BACK", callback_data=f"admin_view_p_{pid}", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("🔌 <b>Choose API Provider</b>", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_provider_"))
async def set_api_provider(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    parts = call.data.split("_"); provider = parts[2]; pid = int(parts[3])
    db_query("UPDATE products SET api_provider=?, delivery_mode='API' WHERE id=?", (provider, pid)); await call.answer(f"Provider set: {provider}", show_alert=True); await admin_view_product(call)

@dp.callback_query(F.data.startswith("toggle_android_id_"))
async def toggle_android_id(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    pid = int(call.data.split("_")[-1])
    row = db_query("SELECT api_android_id_required FROM products WHERE id=?", (pid,), fetchone=True)
    current = int(row[0] or 0) if row else 0
    db_query("UPDATE products SET api_android_id_required=? WHERE id=?", (0 if current else 1, pid))
    await call.answer("Android ID requirement updated", show_alert=True)
    await admin_view_product(call)

@dp.callback_query(F.data.startswith("delete_p_"))
async def admin_delete_product(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    row = db_query(
        "SELECT category, panel_name, name, COALESCE(is_product_parent,0) FROM products WHERE id=?",
        (p_id,), fetchone=True
    )
    if not row:
        return await call.answer("Product not found.", show_alert=True)
    category, panel_name, name, is_parent = row
    if is_parent:
        ids = db_query(
            "SELECT id FROM products WHERE category=? AND panel_name=? AND name=?",
            (category, panel_name, name), fetchall=True
        ) or []
        for item in ids:
            db_query("DELETE FROM product_keys WHERE product_id=?", (item[0],))
        db_query("DELETE FROM products WHERE category=? AND panel_name=? AND name=?", (category, panel_name, name))
        await call.answer("☢️ Full product and all plans deleted.", show_alert=True)
    else:
        db_query("DELETE FROM product_keys WHERE product_id=?", (p_id,))
        db_query("DELETE FROM products WHERE id=?", (p_id,))
        await call.answer("☢️ Plan and its keys deleted.", show_alert=True)
    await admin_manage_prods(call)

@dp.callback_query(F.data.startswith("delkey_p_"))
async def admin_delete_key_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    p_id = int(call.data.split("_")[2])
    await state.update_data(del_p_id=p_id)
    await call.message.edit_text("🗑 Send the <b>exact string match</b> of the key you wish to purge from the vault:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_delete_key)

@dp.message(AdminStates.wait_for_delete_key)
async def process_delete_key(m: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data['del_p_id']
    key_to_delete = m.text.strip()
    key_data = db_query("SELECT id, is_used FROM product_keys WHERE product_id=? AND key_text=?", (p_id, key_to_delete), fetchone=True)
    if not key_data: return await m.answer("❌ Key not found. Check logs and try again.", reply_markup=admin_back_kb(), parse_mode='HTML')
    if key_data[1] == 1: return await m.answer("⚠️ Action Blocked: This key has already been dispatched to a user.", reply_markup=admin_back_kb(), parse_mode='HTML')
    db_query("DELETE FROM product_keys WHERE id=?", (key_data[0],))
    db_query("UPDATE products SET stock = stock - 1 WHERE id=?", (p_id,))
    await m.answer(f"✅ Key <code>{key_to_delete}</code> securely purged from vault.\n📦 Database indices updated.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# 20. ADMIN TICKETS, BROADCAST, COUPONS
# ==============================================================================
@dp.callback_query(F.data == "admin_view_tickets")
async def admin_view_tickets(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    tickets = db_query("SELECT id, user_id, message, created_at FROM tickets WHERE status='Open' LIMIT 1", fetchall=True)
    if not tickets: return await call.answer("✅ Zero pending issues. Grid is clean!", show_alert=True)
    t = tickets[0]
    text = (f"🎫 <b><u>ACTIVE TICKET #{t[0]}</u></b>\n👤 <b>Origin UID:</b> <code>{t[1]}</code>\n📅 <b>Timestamp:</b> {t[3]}\n\n📝 <b>Payload:</b>\n{t[2]}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Formulate Reply", callback_data=f"reply_ticket_{t[0]}_{t[1]}", style="primary")],
        [InlineKeyboardButton(text="❌ Force Close Ticket", callback_data=f"close_ticket_{t[0]}", style="danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket(call: CallbackQuery):
    ticket_id = call.data.split("_")[2]
    db_query("UPDATE tickets SET status='Closed' WHERE id=?", (ticket_id,))
    await call.answer("✅ Status set to Closed.", show_alert=True)
    await admin_view_tickets(call) 

@dp.callback_query(F.data.startswith("reply_ticket_"))
async def reply_ticket_start(call: CallbackQuery, state: FSMContext):
    data = call.data.split("_")
    ticket_id, user_id = data[2], data[3]
    await state.update_data(ticket_id=ticket_id, user_id=user_id)
    await call.message.edit_text(f"💬 Formulating reply for node <code>{user_id}</code>.\n\nType your message payload:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.ticket_reply_msg)

@dp.message(AdminStates.ticket_reply_msg)
async def send_ticket_reply(m: Message, state: FSMContext):
    data = await state.get_data()
    try:
        await bot.send_message(data['user_id'], f"📞 <b>Admin Reply (Ref #{data['ticket_id']}):</b>\n\n{m.text}", parse_mode='HTML')
        db_query("UPDATE tickets SET status='Closed' WHERE id=?", (data['ticket_id'],))
        await m.answer("✅ Payload delivered and connection closed successfully.", reply_markup=admin_kb(), parse_mode='HTML')
    except Exception as e: await m.answer(f"❌ Transmission Error: {e}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_broadcast_btn")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📢 <b>Mass Broadcast Protocol</b>\n\nSend the rich message payload you wish to transmit globally across the grid:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.broadcast_msg)

# ------------------------------------------------------------------------------
# DRIP SILENT APK AD BROADCAST
# Sends the fixed ad to every registered user with a Telegram deep-link button.
# Tapping the button opens this bot and Telegram starts /start automatically.
# ------------------------------------------------------------------------------
DRIP_SILENT_AD_TEXT = (
    "🔥 <b>DRIP SILENT APK AD</b> 🔥\n\n"
    "📲 <b>DRIP SILENT APK</b>\n\n"
    "👇 <b>BY IN BOT /START</b>"
)

DRIP_SILENT_START_URL = f"https://t.me/{BOT_USERNAME}?start=drip_silent_ad"


def drip_silent_ad_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🚀 START BOT",
            url=DRIP_SILENT_START_URL,
            style="success",
            icon_custom_emoji_id=get_emoji_icon("telegram") or None,
        )
    ]])


@dp.message(Command("dripad"))
async def drip_silent_ad_command(message: Message):
    """Admin-only: broadcast the DRIP SILENT APK advertisement to all users."""
    if message.from_user.id != ADMIN_ID:
        return

    users = db_query("SELECT user_id FROM users", fetchall=True) or []
    if not users:
        return await message.answer("❌ No registered users found.", parse_mode="HTML")

    status = await message.answer(
        f"⏳ <b>DRIP SILENT APK AD broadcast started...</b>\n\nTarget users: <code>{len(users)}</code>",
        parse_mode="HTML"
    )

    sent = 0
    failed = 0
    for row in users:
        user_id = row[0]
        try:
            await bot.send_message(
                user_id,
                DRIP_SILENT_AD_TEXT,
                reply_markup=drip_silent_ad_kb(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            sent += 1
        except Exception as exc:
            failed += 1
            logger.warning("DRIP AD failed for user %s: %s", user_id, exc)
        # Stay comfortably below Telegram broadcast limits.
        await asyncio.sleep(0.05)

    await status.edit_text(
        "✅ <b>DRIP SILENT APK AD broadcast complete!</b>\n\n"
        f"🟢 Sent: <code>{sent}</code>\n"
        f"🔴 Failed/blocked: <code>{failed}</code>",
        parse_mode="HTML",
        reply_markup=admin_kb(),
    )


@dp.message(AdminStates.broadcast_msg)
async def admin_broadcast_send(message: Message, state: FSMContext):
    users = db_query("SELECT user_id FROM users", fetchall=True)
    sent, failed = 0, 0
    m = await message.answer("⏳ Broadcast protocol initiated... Do not interrupt.", parse_mode='HTML')
    for u in users:
        try:
            await message.send_copy(chat_id=u[0])
            sent += 1
        except Exception: failed += 1
        await asyncio.sleep(0.06) 
    await m.edit_text(f"✅ <b>Global Broadcast Complete!</b>\n\n🟢 Nodes reached: {sent}\n🔴 Nodes failed/blocked: {failed}", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_create_coupon")
async def admin_create_coupon_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🎟 Enter a highly secure alphanumeric sequence for the Promo Code:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_code)

@dp.message(AdminStates.add_coupon_code)
async def admin_coupon_code(m: Message, state: FSMContext):
    await state.update_data(code=m.text.strip().upper())
    await m.answer("💰 Enter the monetary reward payload in <b>RUPEES (₹)</b>:", parse_mode='HTML')
    await state.set_state(AdminStates.add_coupon_amount)

@dp.message(AdminStates.add_coupon_amount)
async def admin_coupon_amount(m: Message, state: FSMContext):
    try:
        await state.update_data(amount=float(m.text)) 
        await m.answer("👥 Enter the exact maximum threshold uses for this code:", parse_mode='HTML')
        await state.set_state(AdminStates.add_coupon_uses)
    except ValueError: await m.answer("❌ Non-numerical data detected. Aborting.")

@dp.message(AdminStates.add_coupon_uses)
async def admin_coupon_uses(m: Message, state: FSMContext):
    try:
        uses = int(m.text)
        data = await state.get_data()
        db_query("INSERT OR REPLACE INTO coupons (code, amount, uses_left) VALUES (?, ?, ?)", (data['code'], data['amount'], uses))
        await m.answer(f"✅ Protocol <b>{data['code']}</b> encoded!\nReward Vector: {fmt_curr(data['amount'])}\nThreshold Limit: {uses} executions.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Non-numerical data detected. Aborting.")

# ==============================================================================
# 21. ADMIN RESELLER & SPIN SETTINGS
# ==============================================================================
@dp.callback_query(F.data == "admin_reseller_menu")
async def admin_reseller_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    status_check = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    sys_status = status_check[0] if status_check else "ON"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Grant Reseller Rights", callback_data="reseller_make", style="success"), InlineKeyboardButton(text="➖ Revoke Reseller", callback_data="reseller_remove", style="danger")],
        [InlineKeyboardButton(text="📋 Audit Active Resellers", callback_data="reseller_view", style="primary")],
        [InlineKeyboardButton(text=f"{'🟢' if sys_status == 'ON' else '🔴'} Auto-Upgrade System: {sys_status}", callback_data="admin_toggle_reseller_sys", style="success" if sys_status == 'ON' else "danger")], 
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("👑 <b>Wholesale Reseller Protocols</b>\nSelect administrative action:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_toggle_reseller_sys")
async def toggle_reseller_sys(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='reseller_system_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('reseller_system_status', ?)", (new_status,))
    await admin_reseller_menu(call)

@dp.callback_query(F.data.in_(["reseller_make", "reseller_remove"]))
async def reseller_prompt_id(call: CallbackQuery, state: FSMContext):
    action = call.data
    await state.update_data(reseller_action=action)
    await call.message.edit_text("👤 Identify target node. Input <b>User ID</b> or <b>@username</b>:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.reseller_manage_id)

@dp.message(AdminStates.reseller_manage_id)
async def process_reseller_manage(m: Message, state: FSMContext):
    data = await state.get_data()
    target = m.text.strip()
    if target.startswith('@'): target = target[1:]
    user_q = db_query("SELECT user_id, first_name FROM users WHERE user_id=? OR username=? COLLATE NOCASE", (target, target), fetchone=True)
    if not user_q: return await m.answer("❌ Target completely ghosted. Not in database.", reply_markup=admin_back_kb(), parse_mode='HTML')
    u_id, u_name = user_q[0], user_q[1]
    if data['reseller_action'] == "reseller_make":
        db_query("UPDATE users SET is_reseller=1, reseller_since=?, account_type='Reseller' WHERE user_id=?", (datetime.now().strftime("%Y-%m-%d"), u_id))
        await m.answer(f"✅ Credentials upgraded. <b>{u_name}</b> (<code>{u_id}</code>) has reseller rights.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        db_query("UPDATE users SET is_reseller=0, account_type='Regular' WHERE user_id=?", (u_id,))
        await m.answer(f"✅ Credentials revoked. <b>{u_name}</b> (<code>{u_id}</code>) is back to regular user.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "reseller_view")
async def reseller_view(call: CallbackQuery):
    resellers = db_query("SELECT user_id, first_name, username FROM users WHERE is_reseller=1", fetchall=True)
    if not resellers: return await call.message.edit_text("📋 Zero active resellers found.", reply_markup=admin_back_kb(), parse_mode='HTML')
    text = "👑 <b><u>ACTIVE RESELLER AUDIT LOG</u></b> 👑\n━━━━━━━━━━━━━━━━━━\n"
    for r in resellers:
        uname = f"(@{r[2]})" if r[2] else ""
        text += f"👤 {r[1]} {uname}\n🆔 <code>{r[0]}</code>\n\n"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_spin_menu")
async def admin_spin_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    status = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    limit = db_query("SELECT value FROM settings WHERE key='daily_spin_limit'", fetchone=True)
    status_val = status[0] if status else 'ON'
    limit_val = limit[0] if limit else '50.0'
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Reward", callback_data="spin_add", style="success"), InlineKeyboardButton(text="✏️ Edit Reward Price", callback_data="spin_edit_price", style="primary")],
        [InlineKeyboardButton(text="🗑 Delete Reward", callback_data="spin_del", style="danger"), InlineKeyboardButton(text="📋 View Rewards", callback_data="spin_view", style="primary")],
        [InlineKeyboardButton(text="⚙️ Edit Spin Limit", callback_data="spin_limit", style="primary")],
        [InlineKeyboardButton(text=f"{'🟢' if status_val == 'ON' else '🔴'} Master Toggle: {status_val}", callback_data="spin_toggle", style="success" if status_val == 'ON' else "danger")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(f"🎰 <b>Advanced Ludo/Spin Algorithms</b>\nCurrent Threshold: ₹{limit_val}", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "spin_toggle")
async def spin_toggle(call: CallbackQuery):
    res = db_query("SELECT value FROM settings WHERE key='spin_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('spin_status', ?)", (new_status,))
    await admin_spin_menu(call)

@dp.callback_query(F.data == "admin_toggle_bot")
async def toggle_bot(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    res = db_query("SELECT value FROM settings WHERE key='bot_status'", fetchone=True)
    current = res[0] if res else 'ON'
    new_status = 'OFF' if current == 'ON' else 'ON'
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('bot_status', ?)", (new_status,))
    await call.message.edit_reply_markup(reply_markup=admin_kb())

@dp.callback_query(F.data == "spin_add")
async def spin_add_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("🎰 Inject new decimal logic limit (e.g. 15.50):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.spin_add_reward)

@dp.message(AdminStates.spin_add_reward)
async def spin_add_exec(m: Message, state: FSMContext):
    try:
        amt = float(m.text)
        db_query("INSERT INTO spin_rewards (amount) VALUES (?)", (amt,))
        await m.answer(f"✅ Algorithm updated. New vector {fmt_curr(amt)} injected.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Math parsing error.")

@dp.callback_query(F.data == "spin_edit_price")
async def spin_edit_price_start(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    rewards = db_query("SELECT id, amount FROM spin_rewards ORDER BY amount ASC, id ASC", fetchall=True) or []
    rows = []
    for rid, amount in rewards:
        rows.append([InlineKeyboardButton(text=f"{fmt_curr(amount)}", callback_data=f"spin_edit_reward_{rid}", style="primary")])
    rows.append([InlineKeyboardButton(text="Back", callback_data="admin_spin_menu", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("<b>EDIT SPIN REWARD PRICE</b>\n\nSelect the reward you want to change:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="HTML")

@dp.callback_query(F.data.startswith("spin_edit_reward_"))
async def spin_edit_reward_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    try:
        rid = int(call.data.split("spin_edit_reward_", 1)[1])
    except Exception:
        return await call.answer("Invalid reward.", show_alert=True)
    row = db_query("SELECT amount FROM spin_rewards WHERE id=?", (rid,), fetchone=True)
    if not row:
        return await call.answer("Reward not found.", show_alert=True)
    await state.update_data(spin_reward_id=rid)
    await call.message.edit_text(
        f"<b>EDIT REWARD PRICE</b>\n\nCurrent price: <b>{fmt_curr(row[0])}</b>\n\nSend the new price, for example: <code>25</code> or <code>25.50</code>.",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.spin_edit_reward)

@dp.message(AdminStates.spin_edit_reward)
async def spin_edit_reward_exec(m: Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    try:
        amount = float((m.text or "").strip())
        if amount < 0: raise ValueError
    except ValueError:
        return await m.answer("❌ Enter a valid price, e.g. 25 or 25.50.")
    data = await state.get_data(); rid = data.get("spin_reward_id")
    if not rid:
        await state.clear(); return
    db_query("UPDATE spin_rewards SET amount=? WHERE id=?", (amount, int(rid)))
    await state.clear()
    await m.answer(f"✅ Spin reward price updated to <b>{fmt_curr(amount)}</b>.", reply_markup=admin_kb(), parse_mode="HTML")

@dp.callback_query(F.data == "spin_view")
async def spin_view(call: CallbackQuery):
    rewards = db_query("SELECT amount FROM spin_rewards ORDER BY amount ASC", fetchall=True)
    text = "🎰 <b>Live Ludo Constants</b>\n\n"
    for r in rewards: text += f"🎁 {fmt_curr(r[0])}\n"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode='HTML')

@dp.callback_query(F.data == "admin_set_video")
async def admin_set_video_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📹 Input direct streaming / YouTube Link for Tutorial system:\n<i>(Or type 'None' to clear registry):</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_howto_video)

@dp.message(AdminStates.wait_for_howto_video)
async def exec_set_video(m: Message, state: FSMContext):
    link = m.text.strip()
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('how_to_video', ?)", (link,))
    await m.answer("✅ Routing complete. Video linked.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_all_files")
async def admin_set_all_files_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🔗 Input the direct Channel / Cloud URL for 'Download Files' button:\n<i>(Or type 'None' to format data):</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_all_files_link)

@dp.message(AdminStates.wait_for_all_files_link)
async def exec_set_all_files(m: Message, state: FSMContext):
    data = await state.get_data()
    setting = data.get("channel_setting", "all_files_link")
    if setting not in {"all_files_link", "private_data_channel", "key_purchase_channel", "purchase_channel_link", "payment_proof_channel", "payment_proof_link"}:
        setting = "all_files_link"

    # For channel settings, Admin can simply FORWARD any message from the
    # target channel to the bot. Telegram exposes the original channel in
    # Message.forward_origin, so the bot can automatically extract the
    # correct -100... chat ID. This avoids users having to find the ID manually.
    if setting in {"private_data_channel", "key_purchase_channel", "payment_proof_channel"}:
        channel_id = None
        channel_title = None

        forward_origin = getattr(m, "forward_origin", None)
        origin_chat = getattr(forward_origin, "chat", None) if forward_origin else None
        if origin_chat is not None and getattr(origin_chat, "type", "") == "channel":
            channel_id = getattr(origin_chat, "id", None)
            channel_title = getattr(origin_chat, "title", None) or getattr(origin_chat, "username", None)

        # Fallback for messages whose sender_chat is the channel itself.
        sender_chat = getattr(m, "sender_chat", None)
        if channel_id is None and sender_chat is not None and getattr(sender_chat, "type", "") == "channel":
            channel_id = getattr(sender_chat, "id", None)
            channel_title = getattr(sender_chat, "title", None) or getattr(sender_chat, "username", None)

        if channel_id is not None:
            link = str(channel_id)
            ok, info, target = await validate_channel_target(link)
            if not ok:
                await m.answer(
                    f"❌ <b>Channel detect ho gaya, lekin save nahi hua.</b>\n\n"
                    f"📢 Channel: <b>{channel_title or 'Unknown'}</b>\n"
                    f"🆔 ID: <code>{channel_id}</code>\n\n{info}\n\n"
                    "Bot ko us channel me <b>Administrator</b> banao aur <b>Post Messages</b> permission ON karo, phir message dobara forward karo.",
                    reply_markup=admin_kb(), parse_mode='HTML'
                )
                return

            set_setting(setting, target)
            label = {
                "private_data_channel": "Private data channel",
                "key_purchase_channel": "Key purchase channel",
                "payment_proof_channel": "Payment proof channel",
            }.get(setting, setting)
            await m.answer(
                f"✅ <b>{label} connected successfully!</b>\n\n"
                f"📢 Channel: <b>{channel_title or 'Telegram Channel'}</b>\n"
                f"🆔 Channel ID: <code>{target}</code>\n\n"
                "Ab is channel par bot automatically messages post kar sakta hai.",
                reply_markup=admin_kb(), parse_mode='HTML'
            )
            await state.clear()
            return

        # No forwarded channel message: allow the old manual ID/@username/URL method.
        link = (m.text or "").strip()
        if not link:
            await m.answer(
                "⚠️ <b>Channel message forward karo</b>\n\n"
                "Sabse easy method: jis channel me bot admin hai, us channel ka koi bhi message yahan <b>Forward</b> karo.\n"
                "Bot automatically uska <b>Channel ID (-100...)</b> nikal kar save kar dega.\n\n"
                "Ya manually <code>-1001234567890</code>, <code>@channelusername</code> ya public channel URL bhej sakte ho.",
                reply_markup=admin_back_kb(), parse_mode='HTML'
            )
            return

        link = normalize_channel_target(link)
        ok, info, target = await validate_channel_target(link)
        if not ok:
            await m.answer(
                f"❌ <b>Channel not saved.</b>\n\n{info}\n\n"
                "Use channel ka message <b>forward</b> karke automatic ID detection karo, "
                "ya numeric channel ID like <code>-1001234567890</code> bhejo. "
                "Bot ko channel me <b>Administrator + Post Messages</b> permission zaroor do.",
                reply_markup=admin_kb(), parse_mode='HTML'
            )
            return
        link = target
        info_text = info
    else:
        link = (m.text or "").strip()
        info_text = ""
        if not link:
            await m.answer("❌ Please send a valid link.", reply_markup=admin_kb(), parse_mode='HTML')
            return

    set_setting(setting, link)
    label = {
        "all_files_link": "Global resource",
        "private_data_channel": "Private data channel",
        "key_purchase_channel": "Key purchase channel",
        "purchase_channel_link": "Purchase channel",
        "payment_proof_channel": "Payment proof channel",
        "payment_proof_link": "Payment proof link",
    }.get(setting, setting)
    await m.answer(
        f"✅ {label} updated.\n\n🔎 {info_text if setting == 'private_data_channel' else 'Saved successfully.'}",
        reply_markup=admin_kb(), parse_mode='HTML'
    )
    await state.clear()

@dp.callback_query(F.data == "admin_edit_emojis")
async def admin_edit_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    rows = db_query("SELECT key, value FROM settings WHERE key LIKE 'emoji_%' ORDER BY key", fetchall=True)
    if not rows:
        rows = [(f"emoji_{k}", v) for k, v in DEFAULT_EMOJIS.items()]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for row in rows:
        key = row[0]
        slot = key.replace("emoji_", "")
        current_id = row[1] if row[1] else "Not set"
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{slot} (ID: {current_id})", callback_data=f"edit_emoji_{slot}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 <b>Edit All Emojis</b>\nChoose an emoji slot to change its ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_emoji_"))
async def admin_edit_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    slot = call.data.split("edit_emoji_", 1)[1]
    await state.update_data(emoji_slot=slot)
    current = get_setting(f"emoji_{slot}", "Not set")
    await call.message.edit_text(f"✏️ Enter new emoji ID for <b>{slot}</b>:\nCurrent: {current}\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_emoji_slot)

@dp.message(AdminStates.wait_for_emoji_slot)
async def save_emoji_slot(m: Message, state: FSMContext):
    data = await state.get_data()
    slot = data['emoji_slot']
    new_id = m.text.strip()
    if new_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"emoji_{slot}",))
        await m.answer(f"✅ Reset emoji for '{slot}' to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not new_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"emoji_{slot}", new_id)
        await m.answer(f"✅ Emoji for '{slot}' updated to ID {new_id}.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_ui_menu")
async def admin_edit_ui_menu(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    labels = {
        "start_menu":"Welcome / Start", "download_files":"Download Files",
        "vip_menu":"VIP Menu", "lucky_dice_result":"Ludo / Dice Result",
        "add_balance_menu":"Add Balance", "profile_menu":"Profile",
        "history_empty":"History — Empty", "history_header":"History — Header",
        "referral_menu":"Referral", "payment_proof_menu":"Payment Proof",
        "support_menu":"Support", "ticket_list":"My Tickets",
        "ticket_empty":"Tickets — Empty", "ticket_prompt":"Open Ticket Prompt",
        "redeem_prompt":"Redeem Prompt",
    }
    keys=list(labels.items())
    rows=[]
    for i in range(0,len(keys),2):
        rows.append([
            InlineKeyboardButton(text=f"✏️ {label}", callback_data=f"edit_ui_{key}", style="primary")
            for key,label in keys[i:i+2]
        ])
    rows.append([InlineKeyboardButton(text="🔙 Back to Customization", callback_data="admin_group_customization", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text(
        "✏️ <b>USER TEXT MANAGER</b>\n\n"
        "Change user-facing screen text here. Use <b>Button Designer</b> for button names/styles/emojis and <b>All Custom Emojis</b> for screen emojis.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode='HTML'
    )

@dp.callback_query(F.data.startswith("edit_ui_"))
async def admin_edit_ui_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    ui_key = call.data.split("edit_ui_", 1)[1]
    await state.update_data(ui_key=ui_key)
    current_text = get_ui_text(ui_key)
    await call.message.edit_text(f"📝 Send the new text for <b>{ui_key.upper()}</b> menu.\n\nCurrent text:\n{current_text}", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_ui_text)

@dp.message(AdminStates.edit_ui_text)
async def admin_save_ui_text(m: Message, state: FSMContext):
    data = await state.get_data()
    ui_key = data['ui_key']
    new_text = m.text
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"ui_{ui_key}", new_text))
    await m.answer(f"✅ UI text <b>{ui_key}</b> updated successfully!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_edit_reseller_price")
async def admin_edit_reseller_price_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    prods = db_query("SELECT id, name, category, panel_name, reseller_price FROM products ORDER BY category, panel_name", fetchall=True)
    if not prods: return await call.message.edit_text("No products to edit.", reply_markup=admin_back_kb(), parse_mode='HTML')
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in prods:
        panel_name = p[3] if p[3] is not None else ""
        r_price = safe_float(p[4])
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{p[2]} - {panel_name} - {p[1]} (₹{r_price:.2f})", callback_data=f"edit_reseller_{p[0]}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("👑 <b>Edit Reseller Price per Product</b>\nSelect a product to change its wholesale price:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("edit_reseller_"))
async def admin_edit_reseller_price_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    prod_id = int(call.data.split("_")[2])
    await state.update_data(edit_reseller_prod_id=prod_id)
    await call.message.edit_text("💰 Enter the new <b>Reseller Price</b> in Rupees (₹) for this product:", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.edit_reseller_price)

@dp.message(AdminStates.edit_reseller_price)
async def admin_save_reseller_price(m: Message, state: FSMContext):
    try:
        new_price = float(m.text)
        data = await state.get_data()
        prod_id = data['edit_reseller_prod_id']
        db_query("UPDATE products SET reseller_price=? WHERE id=?", (new_price, prod_id))
        await m.answer(f"✅ Reseller price updated to {fmt_curr(new_price)} for product ID {prod_id}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid price.")

@dp.callback_query(F.data == "admin_set_reseller_fee")
async def admin_set_reseller_fee(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("💰 Enter the new <b>Reseller Setup Fee</b> in Rupees (₹):\nCurrent: " + get_setting("reseller_setup_fee", "200.0"), reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_setup_fee)

@dp.message(AdminStates.wait_for_reseller_setup_fee)
async def admin_save_reseller_fee(m: Message, state: FSMContext):
    try:
        fee = float(m.text)
        set_setting("reseller_setup_fee", str(fee))
        await m.answer(f"✅ Reseller setup fee updated to {fmt_curr(fee)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid amount.")

@dp.callback_query(F.data == "admin_set_reseller_min")
async def admin_set_reseller_min(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("💳 Enter the new <b>Minimum Balance</b> required to become reseller (₹):\nCurrent: " + get_setting("reseller_min_balance", "500.0"), reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_reseller_min_balance)

@dp.message(AdminStates.wait_for_reseller_min_balance)
async def admin_save_reseller_min(m: Message, state: FSMContext):
    try:
        min_bal = float(m.text)
        set_setting("reseller_min_balance", str(min_bal))
        await m.answer(f"✅ Minimum reseller balance updated to {fmt_curr(min_bal)}.", reply_markup=admin_kb(), parse_mode='HTML')
        await state.clear()
    except ValueError: await m.answer("❌ Invalid number. Please enter a valid amount.")

@dp.callback_query(F.data == "admin_set_support_links")
async def admin_set_support_links(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Set Telegram Link", callback_data="admin_set_telegram", style="primary")],
        [InlineKeyboardButton(text="📱 Set WhatsApp Link", callback_data="admin_set_whatsapp", style="primary")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text("📌 <b>Support Contact Links</b>\nSet the URLs for Telegram and WhatsApp support:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data == "admin_set_telegram")
async def admin_set_telegram(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("✈️ Enter the Telegram contact URL (e.g., https://t.me/YourSupport):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_telegram)

@dp.message(AdminStates.wait_for_support_telegram)
async def save_telegram_link(m: Message, state: FSMContext):
    link = m.text.strip()
    set_setting("support_telegram", link)
    await m.answer("✅ Telegram support link updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_whatsapp")
async def admin_set_whatsapp(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("📱 Enter the WhatsApp contact URL (e.g., https://wa.me/1234567890):", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_support_whatsapp)

@dp.message(AdminStates.wait_for_support_whatsapp)
async def save_whatsapp_link(m: Message, state: FSMContext):
    link = m.text.strip()
    set_setting("support_whatsapp", link)
    await m.answer("✅ WhatsApp support link updated!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_category_emojis")
async def admin_set_category_emojis(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for cat in FIXED_CATEGORIES:
        current = get_setting(f"cat_emoji_{cat}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{cat} (ID: {current})", callback_data=f"set_cat_emoji_{cat}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🎨 <b>Set Category Emojis</b>\nChoose a category to set its custom emoji ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_cat_emoji_"))
async def admin_set_category_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    category = call.data.split("set_cat_emoji_", 1)[1]
    await state.update_data(cat_emoji_category=category)
    await call.message.edit_text(f"🎨 Enter the emoji ID for <b>{category}</b>:\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_category_emoji)

@dp.message(AdminStates.wait_for_category_emoji)
async def save_category_emoji(m: Message, state: FSMContext):
    data = await state.get_data()
    category = data['cat_emoji_category']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"cat_emoji_{category}",))
        await m.answer(f"✅ Reset emoji for {category} to default.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not emoji_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"cat_emoji_{category}", emoji_id)
        await m.answer(f"✅ Emoji set for {category} successfully!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_set_panel_emojis")
async def admin_set_panel_emojis(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    panels = db_query("SELECT DISTINCT panel_name FROM products WHERE panel_name != '' ORDER BY panel_name", fetchall=True)
    if not panels:
        await call.message.edit_text("No panel names found in products.", reply_markup=admin_back_kb(), parse_mode='HTML')
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for p in panels:
        panel = p[0]
        current = get_setting(f"panel_emoji_{panel}", "Not set")
        kb.inline_keyboard.append([InlineKeyboardButton(text=f"{panel} (ID: {current})", callback_data=f"set_panel_emoji_{panel}", style="primary")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    await call.message.edit_text("🖼 <b>Set Panel Emojis</b>\nChoose a panel name to set its custom emoji ID:", reply_markup=kb, parse_mode='HTML')

@dp.callback_query(F.data.startswith("set_panel_emoji_"))
async def admin_set_panel_emoji_prompt(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    panel_name = call.data.split("set_panel_emoji_", 1)[1]
    await state.update_data(panel_emoji_name=panel_name)
    await call.message.edit_text(f"🎨 Enter the emoji ID for panel <b>{panel_name}</b>:\n(Leave empty to reset to default)", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_panel_emoji_id)

@dp.message(AdminStates.wait_for_panel_emoji_id)
async def save_panel_emoji(m: Message, state: FSMContext):
    data = await state.get_data()
    panel_name = data['panel_emoji_name']
    emoji_id = m.text.strip()
    if emoji_id == "":
        db_query("DELETE FROM settings WHERE key=?", (f"panel_emoji_{panel_name}",))
        await m.answer(f"✅ Reset emoji for panel '{panel_name}'.", reply_markup=admin_kb(), parse_mode='HTML')
    else:
        if not emoji_id.isdigit():
            await m.answer("❌ Invalid ID! Must be numeric.", reply_markup=admin_kb(), parse_mode='HTML')
            return
        set_setting(f"panel_emoji_{panel_name}", emoji_id)
        await m.answer(f"✅ Emoji set for panel '{panel_name}'!", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

@dp.callback_query(F.data == "admin_payment_proof_settings")
async def admin_payment_proof_settings(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Set Proof Channel ID / @Username",callback_data="proof_set_channel",style="primary")],
        [InlineKeyboardButton(text="Set Proof Channel Link",callback_data="proof_set_link",style="primary")],
        [InlineKeyboardButton(text="Test Proof Post",callback_data="proof_test",style="success")],
        [InlineKeyboardButton(text="Back to Admin",callback_data="admin_panel_back",icon_custom_emoji_id=get_emoji_icon("back"),style="danger")]
    ])
    await call.message.edit_text(f"🧾 <b>PAYMENT PROOF SETTINGS</b>\n\nChannel: <code>{get_setting('payment_proof_channel','Not set')}</code>\nLink: <code>{get_setting('payment_proof_link','Not set')}</code>\n\n<b>Separate from Key Purchase Channel.</b>\nBot must be an admin in the proof channel to post automatically.",reply_markup=kb,parse_mode='HTML')

@dp.callback_query(F.data.in_({"proof_set_channel","proof_set_link"}))
async def proof_set_prompt(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    setting="payment_proof_channel" if call.data=="proof_set_channel" else "payment_proof_link"
    await state.update_data(channel_setting=setting); await call.message.edit_text(f"✏️ Send value for <code>{setting}</code>",reply_markup=admin_back_kb(),parse_mode='HTML'); await state.set_state(AdminStates.wait_for_all_files_link)

@dp.callback_query(F.data == "proof_test")
async def proof_test(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    channel=get_setting("payment_proof_channel","").strip()
    if not channel:return await call.answer("❌ Proof channel ID is not configured.",show_alert=True)
    ok, info, target = await validate_channel_target(channel)
    if not ok:
        return await call.answer(f"❌ {info}",show_alert=True)
    try:
        await bot.send_message(target,"🧾 <b>VICKY X PAYMENT PROOF TEST</b>\n\n✅ Automated proof posting is working.",parse_mode='HTML')
        await call.answer("✅ Test proof posted successfully.",show_alert=True)
    except Exception as e:
        logger.exception(f"Proof test failed: {e}")
        await call.answer(f"❌ Proof post failed: {str(e)[:180]}",show_alert=True)

@dp.callback_query(F.data == "key_purchase_channel_test")
async def key_purchase_channel_test(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    channel=get_setting("key_purchase_channel","").strip()
    if not channel:return await call.answer("❌ Key Purchase Channel is not configured.",show_alert=True)
    ok, info, target = await validate_channel_target(channel)
    if not ok:
        return await call.answer(f"❌ {info}",show_alert=True)
    try:
        await bot.send_message(target,"🔑 <b>VICKY X KEY PURCHASE CHANNEL TEST</b>\n\n✅ Key purchase posting is working.",parse_mode='HTML')
        await call.answer("✅ Test key-purchase post sent.",show_alert=True)
    except Exception as e:
        logger.exception(f"Key purchase channel test failed: {e}")
        await call.answer(f"❌ Post failed: {str(e)[:180]}",show_alert=True)

@dp.callback_query(F.data == "private_channel_test")
async def private_channel_test(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    channel=get_setting("private_data_channel","").strip()
    if not channel:return await call.answer("❌ Private data channel ID is not configured.",show_alert=True)
    ok, info, target = await validate_channel_target(channel)
    if not ok:
        return await call.answer(f"❌ {info}",show_alert=True)
    try:
        await bot.send_message(target,"🗄 <b>VICKY X PRIVATE DATA TEST</b>\n\n✅ Private data channel posting is working.",parse_mode='HTML')
        await call.answer("✅ Private channel test posted successfully.",show_alert=True)
    except Exception as e:
        logger.exception(f"Private channel test failed: {e}")
        await call.answer(f"❌ Private channel post failed: {str(e)[:180]}",show_alert=True)

@dp.callback_query(F.data == "admin_product_api_settings")
async def admin_product_api_settings(call: CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    kb=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"PanelStore API Key: {'SET' if get_setting('panelstore_api_key','') else 'NOT SET'}",callback_data="api_set_panelstore",style="primary")],
        [InlineKeyboardButton(text=f"BantiBhaiya API Key: {'SET' if get_setting('bantibhaiya_api_key','') else 'NOT SET'}",callback_data="api_set_banti",style="primary")],
        [InlineKeyboardButton(text=f"BantiBhaiya Master Key: {'SET' if get_setting('bantibhaiya_master_key','') else 'NOT SET'}",callback_data="api_set_banti_master",style="primary")],
        [InlineKeyboardButton(text="🔍 API Diagnostics",callback_data="api_diag",style="success")],
        [InlineKeyboardButton(text="Back to Admin",callback_data="admin_panel_back",icon_custom_emoji_id=get_emoji_icon("back"),style="danger")]
    ])
    await call.message.edit_text("🔑 <b>PRODUCT API SETTINGS</b>\n\nConfigure provider credentials used by API-mode plans. Each product plan stores its own provider + PID + duration.",reply_markup=kb,parse_mode='HTML')

@dp.callback_query(F.data.in_({"api_set_panelstore","api_set_banti","api_set_banti_master"}))
async def api_set_prompt(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    setting={"api_set_panelstore":"panelstore_api_key","api_set_banti":"bantibhaiya_api_key","api_set_banti_master":"bantibhaiya_master_key"}[call.data]
    await state.update_data(api_setting=setting); await call.message.edit_text(f"🔐 Send value for <code>{setting}</code>\n\n💡 Channel setting ho to target channel ka koi bhi message <b>Forward</b> karo; bot automatically uska <b>-100... Channel ID</b> detect kar lega.:",reply_markup=admin_back_kb(),parse_mode='HTML'); await state.set_state(AdminStates.api_settings)

@dp.message(AdminStates.api_settings)
async def api_save_setting(m:Message,state:FSMContext):
    data=await state.get_data(); setting=data.get("api_setting")
    if not setting:return await state.clear()
    set_setting(setting,m.text.strip()); await state.clear(); await m.answer("✅ API credential saved.",reply_markup=admin_kb(),parse_mode='HTML')

@dp.callback_query(F.data == "api_diag")
async def api_diag(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    ps=bool(get_setting("panelstore_api_key","")); bk=bool(get_setting("bantibhaiya_api_key","")); bm=bool(get_setting("bantibhaiya_master_key",""))
    plans=db_query("SELECT COUNT(*) FROM products WHERE UPPER(delivery_mode)='API'",fetchone=True)[0]
    await call.message.edit_text(f"🔍 <b>API DIAGNOSTICS</b>\n\nPanelStore key: {'✅' if ps else '❌'}\nBantiBhaiya key: {'✅' if bk else '❌'}\nBantiBhaiya master: {'✅' if bm else '❌'}\nAPI plans: <b>{plans}</b>\n\nIf an API purchase fails, the bot now returns the provider HTTP/status error without deducting wallet balance.",reply_markup=admin_back_kb(),parse_mode='HTML')

# ==============================================================================
# FULL BUTTON DESIGNER — USER + ADMIN + INNER MENUS
# Telegram only supports primary/success/danger styles; "crime" is kept as a
# semantic alias and is rendered as danger so it never breaks Telegram markup.
# ==============================================================================
BUTTON_DESIGNER_GROUPS = {
    "user": [
        ("🛒 Product Store", "menu_shop"),
        ("👤 My Profile", "menu_profile"),
        ("💰 Add Balance", "menu_add_balance"),
        ("🔑 All History", "menu_orders"),
        ("🔗 Referral", "menu_referral"),
        ("🧾 Payment Proof", "menu_payment_proof"),
        ("🎧 Support", "menu_support"),
        ("🎁 Ludo Spin", "menu_spin_landing"),
        ("📥 Download Files", "menu_all_files"),
        ("👑 VIP", "menu_vip_dash"),
        ("👑 Reseller Panel", "menu_reseller_dash"),
        ("🎫 My Tickets", "my_tickets"),
        ("🎟 Open Ticket", "open_ticket"),
        ("🎫 Redeem Coupon", "redeem_coupon"),
    ],
    "admin": [
        ("📊 Dashboard / Statistics", "admin_view_stats"),
        ("👤 User Control", "admin_user_control_start"),
        ("📢 Broadcast Web App", "admin_open_broadcast_web"),
        ("🌐 User Web App", "admin_open_user_web"),
        ("👑 Reseller Web App", "admin_open_reseller_web"),
        ("🔑 Keys Manager Web App", "admin_open_keys_web"),
        ("🌐 Web App URL", "admin_webapp_url"),
        ("🛒 Product Manager", "admin_product_manager"),
        ("➕ Add Product", "admin_add_prod"),
        ("📦 Manage Products", "admin_manage_prods"),
        ("👑 Reseller Management", "admin_reseller_menu"),
        ("🎰 Spin Settings", "admin_spin_menu"),
        ("🎟 Create Coupon", "admin_create_coupon"),
        ("📢 Broadcast", "admin_broadcast_btn"),
        ("🎫 View Tickets", "admin_view_tickets"),
        ("📹 Payment Proof Settings", "admin_payment_proof_settings"),
        ("🔗 All Files Link", "admin_set_all_files"),
        ("🎨 Edit All Emojis", "admin_edit_emojis"),
        ("💳 Paytm Merchant", "admin_paytm_setup"),
        ("🪙 Binance Setup", "admin_setup_binance"),
        ("🔑 Product APIs", "admin_product_api_settings"),
        ("🎨 Button Designer", "admin_button_designer"),
        ("✏️ Edit UI Texts", "admin_edit_ui_menu"),
        ("📝 Edit Reseller Price", "admin_edit_reseller_price"),
        ("💰 Reseller Fee", "admin_set_reseller_fee"),
        ("💳 Reseller Min Balance", "admin_set_reseller_min"),
        ("📞 Support Links", "admin_set_support_links"),
        ("🎨 Category Emojis", "admin_set_category_emojis"),
        ("🖼 Panel Emojis", "admin_set_panel_emojis"),
        ("🗄 Private Data Channel", "admin_private_channel"),
        ("🔑 Key Purchase Channel", "admin_key_purchase_channel"),
        ("📢 Purchase Channel", "admin_purchase_channel"),
        ("🧾 Payment Proof Link", "admin_payment_proof_link"),
        ("⚙️ Telegram Settings", "admin_set_telegram"),
        ("📥 Download User List", "admin_download_userlist"),
        ("🔙 Back to Admin", "admin_panel_back"),
    ],
    "product": [
        ("🛍 Product Buy", "buy_"),
        ("📂 Category", "cat_"),
        ("📱 Panel", "pnl_"),
        ("🔙 Back", "back_main"),
        ("❌ Out of Stock", "ignore_stock_click"),
        ("✏️ Edit Product", "edit_p_"),
        ("➕ Add Product Category", "addprod_cat_"),
        ("⚙️ API Provider", "choose_provider_"),
        ("🔄 Toggle Product", "toggle_p_"),
        ("🗑 Delete Product", "delete_p_"),
        ("🗑 Delete Key", "delkey_p_"),
        ("📅 Edit Days", "edit_days_panel_"),
        ("➕ Add New Plan", "add_plan_for_panel_"),
        ("🗑 Delete Plan", "delete_plan_"),
        ("🔌 Provider Select", "set_provider_"),
        ("📲 Android ID Toggle", "toggle_android_id_"),
        ("🧾 API / Manual Mode", "prod_mode_api_"),
        ("🧾 API / Manual Mode", "addprod_mode_"),
    ],
    "payment": [
        ("🛍️ Payment Proof Bot Button", "payment_proof_cta"),
        ("💳 INR Payment", "gateway_inr"),
        ("🪙 Crypto Payment", "gateway_crypto"),
        ("🔄 Verify Payment", "verify_"),
        ("💵 Pay ₹50", "pay_50"),
        ("💵 Pay ₹100", "pay_100"),
        ("💵 Pay ₹200", "pay_200"),
        ("💵 Pay ₹500", "pay_500"),
        ("🔢 Deposit Keypad", "custom_deposit_keypad"),
        ("🧹 Keypad Clear", "kp_clear"),
        ("⌫ Keypad Backspace", "kp_backspace"),
        ("✅ Keypad Confirm", "kp_confirm"),
    ],
    "reseller": [
        ("👑 Become Reseller", "execute_reseller_upgrade"),
        ("➕ Add Funds", "reseller_make"),
        ("➖ Remove Funds", "reseller_remove"),
        ("👀 View Reseller", "reseller_view"),
        ("⬆️ Upgrade Reseller", "execute_reseller_upgrade"),
        ("⬇️ Downgrade Reseller", "admin_reseller_menu"),
        ("📝 Edit Reseller Price", "edit_reseller_"),
    ],
    "admin_user": [
        ("➕ Add Funds", "usrctrl_add_"),
        ("➖ Minus Funds", "usrctrl_min_"),
        ("🔨 Ban / Unban", "usrctrl_ban_"),
        ("⚠️ Warn User", "usrctrl_warn_"),
        ("🌟 Give / Remove VIP", "usrctrl_vip_"),
        ("✅ Confirm Ban", "confirm_ban_"),
        ("❌ Cancel", "admin_user_control_start"),
    ],
    "settings": [
        ("🎨 Edit Emoji", "edit_emoji_"),
        ("📝 Edit UI Start", "edit_ui_start"),
        ("💰 Edit Add Balance", "edit_ui_add_balance"),
        ("📥 Edit Download", "edit_ui_download"),
        ("🎲 Edit Dice", "edit_ui_dice"),
        ("⭐ Edit VIP", "edit_ui_vip"),
        ("🗂 Category Emoji", "set_cat_emoji_"),
        ("📱 Panel Emoji", "set_panel_emoji_"),
        ("🎨 API Settings", "api_diag"),
        ("⚙️ Bot Status", "admin_toggle_bot"),
        ("⭐ VIP System", "admin_toggle_vip_sys"),
        ("👑 Reseller System", "admin_toggle_reseller_sys"),
    ],
}

BUTTON_GROUP_LABELS = {
    "user": "👤 USER MENU BUTTONS",
    "admin": "🛡 ADMIN PANEL BUTTONS",
    "product": "🛒 PRODUCT / PANEL / PLAN BUTTONS",
    "payment": "💳 PAYMENT / DEPOSIT BUTTONS",
    "reseller": "👑 RESELLER BUTTONS",
    "admin_user": "👤 ADMIN → USER CONTROL BUTTONS",
    "settings": "⚙️ SETTINGS / INNER MENU BUTTONS",
}

def _designer_menu_kb() -> InlineKeyboardMarkup:
    rows=[]
    for key,label in BUTTON_GROUP_LABELS.items():
        rows.append([InlineKeyboardButton(text=label, callback_data=f"designer_group_{key}", style="primary")])
    rows.append([InlineKeyboardButton(text="🎨 ALL BOT BUTTONS — USER + ADMIN + INNER MENUS", callback_data="designer_group_all", style="success")])
    rows.append([InlineKeyboardButton(text="🔙 Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def _designer_items(group: str):
    if group == "all":
        seen=set(); out=[]
        for g in BUTTON_GROUP_LABELS:
            for item in BUTTON_DESIGNER_GROUPS[g]:
                if item[1] not in seen:
                    seen.add(item[1]); out.append(item)
        return out
    return BUTTON_DESIGNER_GROUPS.get(group, [])

def _designer_default_style(group: str, target: str) -> str:
    # Show the same style the actual bot button already uses when no custom
    # override has been saved. This prevents successful buttons from appearing
    # as "default" in Button Designer.
    if group in {"user", "admin"}:
        return "success"
    if target in {"back_main", "admin_panel_back", "ignore_stock_click"} or target.startswith("delete_") or target.startswith("delkey_"):
        return "danger"
    return "primary"

def _designer_list_kb(group: str) -> InlineKeyboardMarkup:
    rows=[]
    for label,target in _designer_items(group):
        t,st,e=_button_cfg(target)
        shown_name=t or label
        shown_style=st or _designer_default_style(group, target)
        emoji_mark=" • emoji" if e else ""
        rows.append([InlineKeyboardButton(text=f"{shown_name} · {shown_style}{emoji_mark}", callback_data=f"design_btn_{target}", style="success" if shown_style=="success" else ("danger" if shown_style in {"danger","crime"} else "primary"))])
    rows.append([InlineKeyboardButton(text="🔙 Button Categories", callback_data="admin_button_designer", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _designer_show_editor(call: CallbackQuery, target: str):
    t,st,e=_button_cfg(target)
    group_label=""
    for g,items in BUTTON_DESIGNER_GROUPS.items():
        if any(x[1]==target for x in items): group_label=BUTTON_GROUP_LABELS.get(g,""); break
    current_name=t or "Default name"
    current_style=st or _designer_default_style(group_label and next((g for g,items in BUTTON_DESIGNER_GROUPS.items() if BUTTON_GROUP_LABELS.get(g)==group_label), ""), target)
    current_emoji=e or "Default emoji"
    current_url = get_setting(f"btn_url_{target}", "") or (
        get_setting("btn_url_payment_proof_cta", "") if target == "payment_proof_cta" else "Default / N/A"
    )
    designer_rows = [
        [InlineKeyboardButton(text="🔵 Primary", callback_data=f"design_style_primary:{target}", style="primary"), InlineKeyboardButton(text="🟢 Success", callback_data=f"design_style_success:{target}", style="success")],
        [InlineKeyboardButton(text="🔴 Danger", callback_data=f"design_style_danger:{target}", style="danger"), InlineKeyboardButton(text="🟣 Crime", callback_data=f"design_style_crime:{target}", style="danger")],
        [InlineKeyboardButton(text="✏️ Change Name", callback_data=f"design_name:{target}", style="primary"), InlineKeyboardButton(text="😀 Change Emoji", callback_data=f"design_emoji:{target}", style="primary")],
    ]
    if target == "payment_proof_cta":
        designer_rows.append([InlineKeyboardButton(text="🔗 Change Link", callback_data=f"design_url:{target}", style="primary")])
    designer_rows += [
        [InlineKeyboardButton(text="♻️ Reset Design", callback_data=f"design_reset:{target}", style="primary")],
        [InlineKeyboardButton(text="🔙 All Buttons", callback_data="admin_button_designer", style="danger")],
    ]
    kb=InlineKeyboardMarkup(inline_keyboard=designer_rows)
    text=(f"🎨 <b>EDIT BUTTON</b>\n\n"
          f"<b>Key:</b> <code>{target}</code>\n"
          f"<b>Name:</b> {current_name}\n"
          f"<b>Style:</b> {current_style}\n"
          f"<b>Custom Emoji:</b> <code>{current_emoji}</code>\n"
          f"<b>Link:</b> <code>{current_url}</code>\n\n"
          f"<b>Section:</b> {group_label or 'Inner Menu'}\n\n"
          "Choose style, name, custom emoji or link. For Payment Proof, the default link opens the bot with /start automatically.")
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "admin_button_designer")
async def admin_button_designer(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    await call.message.edit_text(
        "🎨 <b>ALL BUTTON UI MANAGER</b>\n\n"
        "Every user, admin and inner-menu button can be customized here.\n\n"
        "Each button: <b>text • style • custom emoji</b>\n"
        "Crime is accepted as a visual alias for Telegram's danger style.",
        reply_markup=_designer_menu_kb(), parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("designer_group_"))
async def designer_group(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    group=call.data.split("designer_group_",1)[1]
    label="ALL BOT BUTTONS — USER + ADMIN + INNER MENUS" if group=="all" else BUTTON_GROUP_LABELS.get(group,"BUTTONS")
    await call.message.edit_text(f"🎨 <b>{label}</b>\n\nTap a button to edit its name, style or custom emoji.", reply_markup=_designer_list_kb(group), parse_mode="HTML")

@dp.callback_query(F.data.startswith("design_btn_"))
async def button_designer_prompt(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    target=call.data.split("design_btn_",1)[1]
    await state.clear()
    await _designer_show_editor(call,target)

@dp.callback_query(F.data.startswith("design_style_"))
async def button_designer_style(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    raw=call.data.split("design_style_",1)[1]
    style,target=raw.split(":",1)
    set_setting(f"btn_style_{target}", style)
    await call.answer(f"Style saved: {style}")
    await _designer_show_editor(call,target)

@dp.callback_query(F.data.startswith("design_name:"))
async def button_designer_name(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    target=call.data.split("design_name:",1)[1]
    await state.update_data(button_target=target, button_edit_field="name")
    await call.message.edit_text(f"✏️ <b>CHANGE BUTTON NAME</b>\n\nKey: <code>{target}</code>\n\nSend the new button name.\nSend <code>none</code> to restore the default name.", reply_markup=admin_back_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.button_design_config)

@dp.callback_query(F.data.startswith("design_url:"))
async def button_designer_url(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    target=call.data.split("design_url:",1)[1]
    if target != "payment_proof_cta":
        await call.answer("Link customization is currently enabled for Payment Proof button only.", show_alert=True)
        return
    current = get_setting("btn_url_payment_proof_cta", "https://t.me/Vickystor_bot?start=purchased")
    await state.update_data(button_target=target, button_edit_field="url")
    await call.message.edit_text(
        f"🔗 <b>CHANGE BUTTON LINK</b>\n\nKey: <code>{target}</code>\n\n"
        f"Current: <code>{current}</code>\n\n"
        "Send a Telegram bot deep-link or normal URL.\n"
        "Default deep-link automatically triggers <code>/start purchased</code> when the user taps it.\n"
        "Send <code>none</code> to restore the default bot link.",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminStates.button_design_config)

@dp.callback_query(F.data.startswith("design_emoji:"))
async def button_designer_emoji(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    target=call.data.split("design_emoji:",1)[1]
    await state.update_data(button_target=target, button_edit_field="emoji")
    await call.message.edit_text(f"😀 <b>CHANGE CUSTOM EMOJI</b>\n\nKey: <code>{target}</code>\n\nSend the numeric Telegram custom emoji ID.\nSend <code>none</code> to remove the custom emoji.", reply_markup=admin_back_kb(), parse_mode="HTML")
    await state.set_state(AdminStates.button_design_config)

@dp.callback_query(F.data.startswith("design_reset:"))
async def button_designer_reset(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    target=call.data.split("design_reset:",1)[1]
    reset_keys = (f"btn_text_{target}",f"btn_style_{target}",f"btn_emoji_{target}",f"btn_url_{target}",f"btn_text_prefix_{target}",f"btn_style_prefix_{target}",f"btn_emoji_prefix_{target}")
    if target == "payment_proof_cta":
        reset_keys = reset_keys + ("btn_url_payment_proof_cta",)
    for key in reset_keys:
        db_query("DELETE FROM settings WHERE key=?",(key,))
    await call.answer("Button reset")
    await _designer_show_editor(call,target)

@dp.message(AdminStates.button_design_config)
async def button_designer_save(m:Message,state:FSMContext):
    if m.from_user.id!=ADMIN_ID:return
    data=await state.get_data(); target=data.get("button_target",""); field=data.get("button_edit_field","")
    value=(m.text or "").strip()
    if not target:return await state.clear()
    if field=="name":
        set_setting(f"btn_text_{target}", "" if value.lower()=="none" else value)
        await state.clear(); await m.answer("✅ Button name saved.",reply_markup=admin_kb(),parse_mode='HTML'); return
    if field=="emoji":
        if value.lower()!="none" and not value.isdigit():
            return await m.answer("❌ Custom Emoji ID must be numeric, or send none.")
        set_setting(f"btn_emoji_{target}", "" if value.lower()=="none" else value)
        await state.clear(); await m.answer("✅ Custom emoji saved.",reply_markup=admin_kb(),parse_mode='HTML'); return
    if field=="url":
        if target != "payment_proof_cta":
            await state.clear()
            return await m.answer("❌ Link customization is available for the Payment Proof button only.", reply_markup=admin_kb(), parse_mode='HTML')
        set_setting("btn_url_payment_proof_cta", "https://t.me/Vickystor_bot?start=purchased" if value.lower()=="none" else value)
        await state.clear(); await m.answer("✅ Button link saved.",reply_markup=admin_kb(),parse_mode='HTML'); return
    # Legacy 3-part editor remains supported.
    parts=[x.strip() for x in value.split("|",2)]
    if len(parts)!=3:return await m.answer("❌ Format: NAME | STYLE | EMOJI_ID")
    name,style,emoji=parts; style="" if style.lower()=="none" else style.lower(); emoji="" if emoji.lower()=="none" else emoji
    if style and style not in {"primary","success","danger","crime"}:return await m.answer("❌ Style must be primary, success, danger or crime.")
    if emoji and not emoji.isdigit():return await m.answer("❌ Emoji ID must be numeric or none.")
    set_setting(f"btn_text_{target}",name); set_setting(f"btn_style_{target}",style); set_setting(f"btn_emoji_{target}",emoji)
    await state.clear(); await m.answer("✅ Button design saved.",reply_markup=admin_kb(),parse_mode='HTML')

@dp.callback_query(F.data == "admin_paytm_setup")
async def admin_paytm_setup(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    current=f"MID: {get_setting('paytm_mid','Not set')}\nWebsite: {get_setting('paytm_website','WEBSTAGING')}\nCallback: {get_setting('paytm_callback_url','Not set')}"
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Set Merchant ID",callback_data="paytm_set_mid",style="primary")],[InlineKeyboardButton(text="Set Merchant Key",callback_data="paytm_set_key",style="primary")],[InlineKeyboardButton(text="Toggle Production / Staging",callback_data="paytm_toggle_env",style="primary")],[InlineKeyboardButton(text="Set Callback URL",callback_data="paytm_set_callback",style="primary")],[InlineKeyboardButton(text="Test Paytm Config",callback_data="paytm_test",style="success")],[InlineKeyboardButton(text="Back to Admin",callback_data="admin_panel_back",icon_custom_emoji_id=get_emoji_icon("back"),style="danger")]])
    await call.message.edit_text(f"💳 <b>PAYTM MERCHANT SETUP</b>\n\n{current}\n\nCreate Link uses AES checksum auth and payment status is verified server-to-server.",reply_markup=kb,parse_mode='HTML')

@dp.callback_query(F.data.in_({"paytm_set_mid","paytm_set_key","paytm_set_callback"}))
async def paytm_set_prompt(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    setting={"paytm_set_mid":"paytm_mid","paytm_set_key":"paytm_merchant_key","paytm_set_callback":"paytm_callback_url"}[call.data]; await state.update_data(paytm_setting=setting)
    await call.message.edit_text(f"✏️ Send value for <code>{setting}</code>",reply_markup=admin_back_kb(),parse_mode='HTML'); await state.set_state(AdminStates.paytm_setup)

@dp.message(AdminStates.paytm_setup)
async def paytm_save_setting(m:Message,state:FSMContext):
    data=await state.get_data(); setting=data.get("paytm_setting")
    if not setting:return await state.clear()
    set_setting(setting,m.text.strip()); await state.clear(); await m.answer("✅ Paytm setting saved.",reply_markup=admin_kb(),parse_mode='HTML')

@dp.callback_query(F.data == "paytm_toggle_env")
async def paytm_toggle_env(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    cur=get_setting("paytm_website","WEBSTAGING").upper(); set_setting("paytm_website","DEFAULT" if cur=="WEBSTAGING" else "WEBSTAGING"); await admin_paytm_setup(call)

@dp.callback_query(F.data == "paytm_test")
async def paytm_test(call:CallbackQuery):
    if call.from_user.id!=ADMIN_ID:return
    if not get_setting("paytm_mid","") or not get_setting("paytm_merchant_key",""):return await call.answer("❌ MID / Merchant Key missing.",show_alert=True)
    await call.answer("✅ Credentials are present. Use a small test payment to validate the live merchant account.",show_alert=True)

@dp.callback_query(F.data == "admin_private_channel")
async def admin_private_channel(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    await state.update_data(channel_setting="private_data_channel"); await call.message.edit_text(f"🗄 <b>Private Data Channel</b>\n\nCurrent: <code>{get_setting('private_data_channel','Not set')}</code>\n\n<b>Easy setup:</b> jis channel me bot Admin hai, us channel ka koi bhi message yahan <b>Forward</b> karo — bot automatically Channel ID nikal lega.\n\nYa manually channel ID (e.g. <code>-100...</code>) / @channelusername bhej sakte ho.\n\nAfter saving, use the Test button in this menu to verify Telegram can actually receive the post.",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🧪 Test Current Channel",callback_data="private_channel_test",style="success")],[InlineKeyboardButton(text="Back to Admin",callback_data="admin_panel_back",icon_custom_emoji_id=get_emoji_icon("back"),style="danger")]]),parse_mode='HTML'); await state.set_state(AdminStates.wait_for_all_files_link)

@dp.callback_query(F.data == "admin_key_purchase_channel")
async def admin_key_purchase_channel(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    current = get_setting("key_purchase_channel","Not set")
    await state.update_data(channel_setting="key_purchase_channel")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 Test Current Channel", callback_data="key_purchase_channel_test", style="success")],
        [InlineKeyboardButton(text="Back to Admin", callback_data="admin_panel_back", icon_custom_emoji_id=get_emoji_icon("back"), style="danger")]
    ])
    await call.message.edit_text(
        f"🔑 <b>KEY PURCHASE CHANNEL</b>\n\nCurrent: <code>{current}</code>\n\n"
        "<b>Easy setup:</b> jis channel me bot Admin hai, us channel ka koi bhi message yahan <b>Forward</b> karo — bot automatically Channel ID nikal lega.\n\nYa channel ID (e.g. <code>-1001234567890</code>), @username, or a public Telegram channel URL bhejo. "
        "The bot must be an admin with permission to post.\n\n"
        "Every successful key purchase will be sent here with the <b>actual key</b>. "
        "This channel is separate from Payment Proof and Private Data.",
        reply_markup=kb, parse_mode='HTML'
    )
    await state.set_state(AdminStates.wait_for_all_files_link)

@dp.callback_query(F.data == "admin_purchase_channel")
async def admin_purchase_channel(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    await state.update_data(channel_setting="purchase_channel_link"); await call.message.edit_text(f"📢 <b>Purchase / Store Channel Link</b>\n\nCurrent: <code>{get_setting('purchase_channel_link','Not set')}</code>\n\nSend invite/public URL. After purchase the user gets an Open/Join button. Telegram bots cannot silently join users to channels.",reply_markup=admin_back_kb(),parse_mode='HTML'); await state.set_state(AdminStates.wait_for_all_files_link)

@dp.callback_query(F.data == "admin_payment_proof_link")
async def admin_payment_proof_link(call:CallbackQuery,state:FSMContext):
    if call.from_user.id!=ADMIN_ID:return
    await call.message.edit_text(f"🧾 <b>Payment Proof Link</b>\n\nCurrent: <code>{get_setting('payment_proof_link','Not set')}</code>\n\nSend the public channel URL or private invite link used by the user-facing Payment Proof button.",reply_markup=admin_back_kb(),parse_mode='HTML')
    await state.update_data(channel_setting="payment_proof_link"); await state.set_state(AdminStates.wait_for_all_files_link)

@dp.callback_query(F.data == "admin_setup_binance")
async def setup_binance_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID: return
    await call.message.edit_text("🪙 <b>CRYPTO NODE INIT: Step 1/3</b>\nInput Master <b>Binance API Key</b>:\n<i>(Type /cancel to halt protocol)</i>", reply_markup=admin_back_kb(), parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_api)

@dp.message(AdminStates.wait_for_binance_api)
async def setup_binance_api(m: Message, state: FSMContext):
    if m.text == '/cancel':
        await state.clear()
        return await m.answer("Sequence aborted.", reply_markup=admin_kb(), parse_mode='HTML')
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_api', ?)", (m.text.strip(),))
    await m.answer("🪙 <b>CRYPTO NODE INIT: Step 2/3</b>\nNow inject the highly secure <b>Binance Secret Key</b>:", parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_secret)

@dp.message(AdminStates.wait_for_binance_secret)
async def setup_binance_secret(m: Message, state: FSMContext):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_secret', ?)", (m.text.strip(),))
    await m.answer("🪙 <b>CRYPTO NODE INIT: Step 3/3</b>\nFinal variable: Set the public <b>USDT Deposit Address (TRC20/BEP20)</b>\nUsers will broadcast to this ledger:", parse_mode='HTML')
    await state.set_state(AdminStates.wait_for_binance_address)

@dp.message(AdminStates.wait_for_binance_address)
async def setup_binance_address(m: Message, state: FSMContext):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('binance_address', ?)", (m.text.strip(),))
    await m.answer("✅ <b>Blockchain node synchronized.</b> Crypto gateway is fully armed.", reply_markup=admin_kb(), parse_mode='HTML')
    await state.clear()

# ==============================================================================
# 22. BOOTSTRAPPING & MAIN
# ==============================================================================
async def main() -> None:
    init_db()
    logger.info("Initializing DB structure...")
    migrate_categories()
    asyncio.create_task(auto_verify_task())

    # Start the built-in WebApp server without allowing a broken/missing aiohttp.web
    # package to crash the Telegram bot itself.
    web_runner = None
    try:
        web_app = build_webapp()
        web_runner = aiohttp_web.AppRunner(web_app)
        await web_runner.setup()
        try:
            port = int(get_setting("webapp_port", os.getenv("WEBAPP_PORT", "8080")) or 8080)
        except Exception:
            port = 8080
        bind_host = os.getenv("WEBAPP_HOST", "0.0.0.0")
        web_site = aiohttp_web.TCPSite(web_runner, bind_host, port)
        await web_site.start()
        logger.info("WebApp server listening on %s:%s", bind_host, port)
    except Exception as web_err:
        logger.exception("WebApp server disabled until aiohttp.web is available: %s", web_err)
        if web_runner is not None:
            try: await web_runner.cleanup()
            except Exception: pass
        web_runner = None

    logger.info("Paytm Auto-Verifier Daemon Running in Background.")
    logger.info("🚀 CORE SYSTEM IS FULLY OPERATIONAL...")
    try:
        await dp.start_polling(bot)
    except Exception as err:
        logger.error(f"Critical System Failure in Polling: {err}")
    finally:
        if web_runner is not None:
            try: await web_runner.cleanup()
            except Exception: pass
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("System shutting down gracefully. Goodbye.")
