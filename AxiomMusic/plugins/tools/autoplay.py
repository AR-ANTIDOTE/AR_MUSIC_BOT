import re
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ButtonStyle
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from AxiomMusic import app
from AxiomMusic.misc import SUDOERS, db
from AxiomMusic.utils.database import (
    autoplay_off, autoplay_on, is_autoplay,
    get_autoplay_lang, set_autoplay_lang,
    get_autoplay_mood, set_autoplay_mood
)
from AxiomMusic.utils.stream.autoplay import queue_autoplay_tracks
from AxiomMusic.utils.decorators.admins import ActualAdminCB, AdminActual
from config import BANNED_USERS

AUTOPLAY_RE = re.compile(
    r"^[!/.](?P<command>autoplay|aplay|auto)(?:@\w+)?"
    r"(?:\s+(?P<state>on|off|enable|disable|enabled|disabled))?\s*$",
    re.IGNORECASE,
)
ON_STATES = {"on", "enable", "enabled"}
OFF_STATES = {"off", "disable", "disabled"}

LANGUAGES = {
    "auto": "Auto Detect",
    "hindi": "Hindi",
    "english": "English",
    "punjabi": "Punjabi",
    "tamil": "Tamil",
    "telugu": "Telugu",
    "kannada": "Kannada",
    "malayalam": "Malayalam",
    "bengali": "Bengali",
    "marathi": "Marathi",
    "gujarati": "Gujarati"
}

MOODS = {
    "any": "Any Mood",
    "happy": "Happy",
    "sad": "Sad",
    "romantic": "Romantic",
    "workout": "Workout",
    "chill": "Chill",
    "bhajan": "Bhajan / Devotional"
}

def parse_autoplay_state(message: Message):
    text = (message.text or message.caption or "").strip()
    match = AUTOPLAY_RE.match(text)
    if not match:
        return None
    state = match.group("state")
    return state.lower() if state else None

async def can_toggle_autoplay(chat_id: int, user_id: int) -> bool:
    if user_id in SUDOERS:
        return True
    try:
        member = await app.get_chat_member(chat_id, user_id)
    except Exception:
        return True
    if member.status == ChatMemberStatus.OWNER:
        return True
    privileges = getattr(member, "privileges", None)
    return bool(
        member.status == ChatMemberStatus.ADMINISTRATOR
        and privileges
        and (
            getattr(privileges, "can_manage_video_chats", False)
            or getattr(privileges, "can_manage_chat", False)
        )
    )

def autoplay_markup(status: bool):
    if status:
        button_text = "ENABLED ✅"
        toggle_state = "off"
    else:
        button_text = "DISABLED ❌"
        toggle_state = "on"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(button_text, callback_data=f"autoplay_toggle|{toggle_state}")],
        [InlineKeyboardButton("Language", callback_data="autoplay_lang")],
        [InlineKeyboardButton("Mood", callback_data="autoplay_mood")]
    ])

def language_markup(current_lang: str):
    buttons = []
    row = []
    for lang_code, lang_name in LANGUAGES.items():
        display_name = f"✅ {lang_name}" if lang_code == current_lang else lang_name
        row.append(InlineKeyboardButton(display_name, callback_data=f"autoplay_setlang|{lang_code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("Back", callback_data="autoplay_back")])
    return InlineKeyboardMarkup(buttons)

def mood_markup(current_mood: str):
    buttons = []
    row = []
    for mood_code, mood_name in MOODS.items():
        display_name = f"✅ {mood_name}" if mood_code == current_mood else mood_name
        row.append(InlineKeyboardButton(display_name, callback_data=f"autoplay_setmood|{mood_code}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("Back", callback_data="autoplay_back")])
    return InlineKeyboardMarkup(buttons)

def autoplay_text(status: bool, lang: str, mood: str):
    current = "ENABLED ✅" if status else "DISABLED ❌"
    lang_name = LANGUAGES.get(lang, "Auto Detect")
    mood_name = MOODS.get(mood, "Any Mood")
    return (
        "<b> AUTOPLAY SETTINGS</b>\n\n"
        f"<b>Status:</b> {current}\n"
        f"<b>Language:</b> {lang_name}\n"
        f"<b>Mood:</b> {mood_name}\n\n"
        "<b>Commands:</b> <code>/autoplay on</code> | <code>/autoplay off</code>"
    )

@app.on_message(filters.command(["autoplay", "aplay", "ap"], prefixes=["/", "!", "."]) & filters.group & ~BANNED_USERS)
@AdminActual
async def autoplay_command(_, message: Message, __):
    if not message.from_user:
        return await message.reply_text("Please use this command from a user account.")

    chat_id = message.chat.id
    requested_state = parse_autoplay_state(message)

    if requested_state in ON_STATES | OFF_STATES:
        if not await can_toggle_autoplay(chat_id, message.from_user.id):
            return await message.reply_text("Only admins can change autoplay mode.")
        status = requested_state in ON_STATES
        if status:
            await autoplay_on(chat_id)
            current_queue = db.get(chat_id)
            if current_queue:
                await queue_autoplay_tracks(chat_id, current_queue[0])
        else:
            await autoplay_off(chat_id)
    else:
        status = await is_autoplay(chat_id)
    
    lang = await get_autoplay_lang(chat_id)
    mood = await get_autoplay_mood(chat_id)

    await message.reply_text(
        autoplay_text(status, lang, mood),
        reply_markup=autoplay_markup(status),
        disable_web_page_preview=True,
    )

@app.on_callback_query(filters.regex(r"^autoplay_toggle\|(on|off)$") & ~BANNED_USERS)
@ActualAdminCB
async def autoplay_callback(_, callback_query: CallbackQuery, __):
    state = callback_query.data.split("|", 1)[1]
    chat_id = callback_query.message.chat.id

    if state == "on":
        await autoplay_on(chat_id)
        status = True
        alert = "Autoplay enabled successfully."
    else:
        await autoplay_off(chat_id)
        status = False
        alert = "Autoplay disabled successfully."

    await callback_query.answer(alert, show_alert=True)
    
    lang = await get_autoplay_lang(chat_id)
    mood = await get_autoplay_mood(chat_id)

    await callback_query.edit_message_text(
        autoplay_text(status, lang, mood),
        reply_markup=autoplay_markup(status),
        disable_web_page_preview=True,
    )

@app.on_callback_query(filters.regex(r"^autoplay_lang$") & ~BANNED_USERS)
@ActualAdminCB
async def autoplay_lang_menu(_, callback_query: CallbackQuery, __):
    chat_id = callback_query.message.chat.id
    current_lang = await get_autoplay_lang(chat_id)
    
    await callback_query.edit_message_text(
        "<b>Select Autoplay Language</b>\n\nChoose the language for autoplay songs:",
        reply_markup=language_markup(current_lang),
        disable_web_page_preview=True,
    )

@app.on_callback_query(filters.regex(r"^autoplay_setlang\|(.+)$") & ~BANNED_USERS)
@ActualAdminCB
async def autoplay_set_language(_, callback_query: CallbackQuery, __):
    lang = callback_query.data.split("|", 1)[1]
    chat_id = callback_query.message.chat.id
    
    await set_autoplay_lang(chat_id, lang)
    await callback_query.answer(f"Language set to {LANGUAGES[lang]}", show_alert=True)
    
    status = await is_autoplay(chat_id)
    mood = await get_autoplay_mood(chat_id)
    
    await callback_query.edit_message_text(
        autoplay_text(status, lang, mood),
        reply_markup=autoplay_markup(status),
        disable_web_page_preview=True,
    )

@app.on_callback_query(filters.regex(r"^autoplay_mood$") & ~BANNED_USERS)
@ActualAdminCB
async def autoplay_mood_menu(_, callback_query: CallbackQuery, __):
    chat_id = callback_query.message.chat.id
    current_mood = await get_autoplay_mood(chat_id)
    
    await callback_query.edit_message_text(
        "<b>Select Autoplay Mood</b>\n\nChoose the mood for autoplay songs:",
        reply_markup=mood_markup(current_mood),
        disable_web_page_preview=True,
    )

@app.on_callback_query(filters.regex(r"^autoplay_setmood\|(.+)$") & ~BANNED_USERS)
@ActualAdminCB
async def autoplay_set_mood(_, callback_query: CallbackQuery, __):
    mood = callback_query.data.split("|", 1)[1]
    chat_id = callback_query.message.chat.id
    
    await set_autoplay_mood(chat_id, mood)
    await callback_query.answer(f"Mood set to {MOODS[mood]}", show_alert=True)
    
    status = await is_autoplay(chat_id)
    lang = await get_autoplay_lang(chat_id)
    
    await callback_query.edit_message_text(
        autoplay_text(status, lang, mood),
        reply_markup=autoplay_markup(status),
        disable_web_page_preview=True,
    )

@app.on_callback_query(filters.regex(r"^autoplay_back$") & ~BANNED_USERS)
@ActualAdminCB
async def autoplay_back(_, callback_query: CallbackQuery, __):
    chat_id = callback_query.message.chat.id
    status = await is_autoplay(chat_id)
    lang = await get_autoplay_lang(chat_id)
    mood = await get_autoplay_mood(chat_id)
    
    await callback_query.edit_message_text(
        autoplay_text(status, lang, mood),
        reply_markup=autoplay_markup(status),
        disable_web_page_preview=True,
    )
