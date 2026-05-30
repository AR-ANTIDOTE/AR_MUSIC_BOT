from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from AxiomMusic import app
from AxiomMusic.misc import SUDOERS
from AxiomMusic.utils.database import (
    is_thumbmode,
    thumb_off,
    thumb_on,
)
from config import BANNED_USERS


THUMB_STATES = ["on", "off", "enable", "disable", "enabled", "disabled"]


async def can_toggle_thumbnail(chat_id: int, user_id: int) -> bool:
    if user_id in SUDOERS:
        return True

    try:
        member = await app.get_chat_member(chat_id, user_id)
    except Exception:
        return False

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


def thumbnail_markup(status: bool):
    toggle_text = "ᴅɪsᴀʙʟᴇ ❌" if status else "ᴇɴᴀʙʟᴇ ✅"
    toggle_state = "off" if status else "on"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    toggle_text,
                    callback_data=f"thumbnail_toggle|{toggle_state}",
                )
            ],
            [
                InlineKeyboardButton(
                    "⋞ ᴄʟᴏsє ⋟",
                    callback_data="close",
                )
            ],
        ]
    )


def thumbnail_text(status: bool):
    current = "ᴇɴᴀʙʟᴇᴅ ✅" if status else "ᴅɪsᴀʙʟᴇᴅ ❌"

    return (
        "<b>𝚻ʜ꧊‌𝛖ϻβηᴧιℓ 𝚺ᴇᴛᴛɪɴɢs</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ sᴛᴀᴛᴜs:</b> {current}\n\n"
        "<blockquote>"
        "Disabled hone par /play ke baad custom generated thumbnail "
        "PNG nahi banegi aur bot normal player image use karega."
        "</blockquote>\n\n"
        "<b>Commands:</b>\n"
        "<code>/thumb</code>\n"
        "<code>/thumb on</code>\n"
        "<code>/thumb off</code>"
    )


@app.on_message(
    filters.command(
        ["thumb", "thumbnail", "thum"],
        prefixes=["/", "!", "."],
    )
    & filters.group
    & ~BANNED_USERS
)
async def thumbnail_cmd(_, message: Message):
    if not message.from_user:
        return

    chat_id = message.chat.id

    state = None

    if len(message.command) > 1:
        state = message.command[1].lower()

    if state in ["on", "enable", "enabled"]:
        if not await can_toggle_thumbnail(
            chat_id,
            message.from_user.id,
        ):
            return await message.reply_text(
                "<b>Only admins can change thumbnail mode.</b>"
            )

        await thumb_on(chat_id)
        status = True

    elif state in ["off", "disable", "disabled"]:
        if not await can_toggle_thumbnail(
            chat_id,
            message.from_user.id,
        ):
            return await message.reply_text(
                "<b>Only admins can change thumbnail mode.</b>"
            )

        await thumb_off(chat_id)
        status = False

    else:
        status = await is_thumbmode(chat_id)

    await message.reply_text(
        thumbnail_text(status),
        reply_markup=thumbnail_markup(status),
        disable_web_page_preview=True,
    )


@app.on_callback_query(
    filters.regex(r"^thumbnail_toggle\|(on|off)$")
    & ~BANNED_USERS
)
async def thumbnail_callback(_, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    state = callback_query.data.split("|")[1]

    if not await can_toggle_thumbnail(
        chat_id,
        callback_query.from_user.id,
    ):
        return await callback_query.answer(
            "Only admins can change thumbnail mode.",
            show_alert=True,
        )

    if state == "on":
        await thumb_on(chat_id)
        status = True
        alert = "Thumbnail enabled ✅"
    else:
        await thumb_off(chat_id)
        status = False
        alert = "Thumbnail disabled ❌"

    await callback_query.answer(
        alert,
        show_alert=True,
    )

    await callback_query.edit_message_text(
        thumbnail_text(status),
        reply_markup=thumbnail_markup(status),
        disable_web_page_preview=True,
    )
