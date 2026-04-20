# -----------------------------------------------
# 🔸 AxiomMusic Project
# 🔹 Developed & Maintained by: Axiom Bots (https://t.me/axiombots)
# 📅 Copyright © 2026 – All Rights Reserved
#
# 📖 License:
# This source code is open for educational and non-commercial use ONLY.
# You are required to retain this credit in all copies or substantial portions of this file.
# Commercial use, redistribution, or removal of this notice is strictly prohibited
# without prior written permission from the author.
#
# ❤️ Made with dedication and love by AxiomBots
# -----------------------------------------------


from pyrogram import filters, enums
from pyrogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from pyrogram.errors.exceptions.bad_request_400 import (
    ChatAdminRequired,
    UserAdminInvalid
)
import random
from logging import getLogger
from AxiomMusic import LOGGER
from config import LOGGER_ID as LOG_GROUP_ID
from AxiomMusic.misc import SUDOERS
from AxiomMusic import app
from AxiomMusic.helper.admin_check import admin_check, admin_filter
from config import OWNER_ID
from pyrogram.types import *
from pyrogram.types import ChatPermissions
from pyrogram.errors.exceptions.bad_request_400 import BadRequest
from pyrogram.enums import ChatType, ChatMemberStatus

LOGGER = getLogger(__name__)

kickpic = [
    "https://files.catbox.moe/m4fx24.jpg",
    "https://files.catbox.moe/m4fx24.jpg",
    "https://files.catbox.moe/m4fx24.jpg",
]

button = [
    [
        InlineKeyboardButton(text="ᴜᴘᴅᴀᴛᴇs", url="https://t.me/Axiombots"),
        InlineKeyboardButton(" ⌯ ᴅᴇᴠᴇʟᴏᴘᴇʀ ⌯ ", url="tg://user?id=7169279112")
    ]
]

def mention(user, name, mention=True):
    if mention:
        return f"[{name}](tg://user?id={user})"
    else:
        return f"[{name}](tg://openmessage?user_id={user})"

async def get_userid_from_username(username):
    try:
        user = await app.get_users(username)
    except:
        return None
    return [user.id, user.first_name]

async def bans_user(user_id, first_name, admin_id, admin_name, chat_id, message):
    try:
        await app.ban_chat_member(chat_id, user_id)
        await app.unban_chat_member(chat_id, user_id)
    except ChatAdminRequired:
        return "I need ban rights to perform this action.", False
    except UserAdminInvalid:
        return "I can't ban another admin!", False
    except Exception as e:
        if user_id == OWNER_ID:
            return "Why should I ban myself?", False
        return f"An error occurred: {e}", False

    user_mention = mention(user_id, first_name)
    admin_mention = mention(admin_id, admin_name)

    await app.send_message(
        LOG_GROUP_ID,
        f"<blockquote expandable><b>✧ {user_mention} ᴡᴀs ʙᴀɴɴᴇᴅ ʙʏ {admin_mention} ɪɴ {message.chat.title} </b></blockquote>"
    )

    ban_message = await message.reply_photo(
        photo=random.choice(kickpic),
        has_spoiler=True,
        caption=f"<blockquote expandable><b>✧ {user_mention} ᴡᴀs ʙᴀɴɴᴇᴅ ʙʏ {admin_mention}. </b></blockquote>"
    )
    return ban_message, True


@app.on_message(filters.command("ban", "fuck") & admin_filter)
async def ban_user_with_unban_button(client, message):
    chat = message.chat
    chat_id = message.chat.id
    admin_id = message.from_user.id
    admin_name = message.from_user.first_name
    member = await chat.get_member(admin_id)

    if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        if not member.privileges.can_restrict_members:
            return await message.reply_text(
                "<blockquote expandable><b>✧ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴜɴʙᴀɴ sᴏᴍᴇᴏɴᴇ. </b></blockquote>"
            )
    else:
        return await message.reply_text(
            "<blockquote expandable><b>✧ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴜɴʙᴀɴ sᴏᴍᴇᴏɴᴇ. </b></blockquote>"
        )

    if len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            first_name = "User"
        except ValueError:
            user_obj = await get_userid_from_username(message.command[1])
            if user_obj is None:
                return await message.reply_text(
                    "<blockquote expandable><b>✧ ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ. </b></blockquote>"
                )
            user_id = user_obj[0]
            first_name = user_obj[1]
    elif message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        first_name = message.reply_to_message.from_user.first_name
    else:
        return await message.reply_text(
            "<blockquote expandable><b>✧ ᴘʟᴇᴀsᴇ sᴘᴇᴄɪғʏ ᴀ ᴠᴀʟɪᴅ ᴜsᴇʀ ᴏʀ ʀᴇᴘʟʏ ᴛᴏ ᴛʜᴇɪʀ ᴍᴇssᴀɢᴇ. </b></blockquote>"
        )

    msg_text, result = await bans_user(user_id, first_name, admin_id, admin_name, chat_id, message)
    if not result:
        return await message.reply_text(msg_text)

    unban_button = [
        [InlineKeyboardButton("Ʋɴʙᴀɴ Ʋsᴇʀ", callback_data=f"unban_{user_id}")]
    ]

    await message.reply_text(
        f"ᴄʟɪᴄᴋ ʙᴇʟᴏᴡ ᴛᴏ ᴜɴʙᴀɴ {first_name}.",
        reply_markup=InlineKeyboardMarkup(unban_button),
    )


@app.on_message(filters.command("unban") & admin_filter)
async def unban_user(client, message):
    chat = message.chat
    chat_id = message.chat.id
    admin_id = message.from_user.id
    admin_name = message.from_user.first_name
    member = await chat.get_member(admin_id)

    if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
        if not member.privileges.can_restrict_members:
            return await message.reply_text(
                "<blockquote expandable><b>✧ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴜɴʙᴀɴ sᴏᴍᴇᴏɴᴇ. </b></blockquote>"
            )
    else:
        return await message.reply_text(
            "<blockquote expandable><b>✧ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ ᴜɴʙᴀɴ sᴏᴍᴇᴏɴᴇ. </b></blockquote>"
        )

    if len(message.command) > 1:
        try:
            user_id = int(message.command[1])
            first_name = "User"
        except ValueError:
            user_obj = await get_userid_from_username(message.command[1])
            if user_obj is None:
                return await message.reply_text(
                    "<blockquote expandable><b>✧ ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ. </b></blockquote>"
                )
            user_id = user_obj[0]
            first_name = user_obj[1]
    else:
        return await message.reply_text(
            "<blockquote expandable><b>✧ ᴘʟᴇᴀsᴇ sᴘᴇᴄɪғʏ ᴀ ᴠᴀʟɪᴅ ᴜsᴇʀ ᴛᴏ ᴜɴʙᴀɴ. </b></blockquote>"
        )

    try:
        await app.unban_chat_member(chat_id, user_id)

        user_mention = mention(user_id, first_name)
        admin_mention = mention(admin_id, admin_name)

        await message.reply_photo(
            photo=random.choice(kickpic),
            has_spoiler=True,
            caption=f"<blockquote expandable><b>✧ {user_mention} ᴡᴀs ᴜɴʙᴀɴɴᴇᴅ ʙʏ {admin_mention}. </b></blockquote>",
            reply_markup=InlineKeyboardMarkup(button),
        )

        await app.send_message(
            LOG_GROUP_ID,
            f"<blockquote expandable><b>✧ {user_mention} ᴡᴀs ᴜɴʙᴀɴɴᴇᴅ ʙʏ {admin_mention} ɪɴ {message.chat.title}. </b></blockquote>"
        )

    except Exception as e:
        await message.reply_text(
            f"<blockquote expandable><b>✧ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {e} </b></blockquote>"
        )


@app.on_callback_query(filters.regex(r"unban_(\d+)"))
async def unban_button_callback(client, callback_query):
    user_id = int(callback_query.matches[0].group(1))
    chat_id = callback_query.message.chat.id

    try:
        await app.unban_chat_member(chat_id, user_id)
        await callback_query.answer("ᴜsᴇʀ ʜᴀs ʙᴇᴇɴ ᴜɴʙᴀɴɴᴇᴅ!")
        await callback_query.message.edit_text("ᴛʜᴇ ᴜsᴇʀ ʜᴀs ʙᴇᴇɴ sᴜᴄᴄᴇssғᴜʟʟʏ ᴜɴʙᴀɴɴᴇᴅ.")
    except Exception as e:
        await callback_query.answer(f"Error: {e}")


@app.on_message(filters.command("kickme") & filters.group)
async def kickme_command(client, message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    chat_id = message.chat.id

    try:
        await app.ban_chat_member(chat_id, user_id)

        await message.reply_photo(
            photo=random.choice(kickpic),
            has_spoiler=True,
            caption=f"<blockquote expandable><b>✧ {user_name} ʜᴀs ᴋɪᴄᴋᴇᴅ ᴛʜᴇᴍsᴇʟᴠᴇs ᴏᴜᴛ ᴏғ ᴛʜᴇ ɢʀᴏᴜᴘ! </b></blockquote>",
            reply_markup=InlineKeyboardMarkup(button),
        )

        await app.send_message(
            LOG_GROUP_ID,
            f"<blockquote expandable><b>✧ {user_name} ᴜsᴇᴅ ᴛʜᴇ ᴋɪᴄᴋᴍᴇ ᴄᴏᴍᴍᴀɴᴅ ɪɴ {message.chat.title} </b></blockquote>"
        )

    except Exception as e:
        await message.reply_text(
            f"<blockquote expandable><b>✧ ᴀɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ: {e} </b></blockquote>"
        )
