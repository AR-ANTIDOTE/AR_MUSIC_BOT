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

from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from unidecode import unidecode
from AxiomMusic import app
from AxiomMusic.misc import SUDOERS
from AxiomMusic.utils.database import (
    get_active_chats,
    get_active_video_chats,
    remove_active_chat,
    remove_active_video_chat,
)


@app.on_message(filters.command(["activevc", "activevoice","vc"]) & SUDOERS)
async def activevc(_, message: Message):
    mystic = await message.reply_text("<blockquote expandable><b>✧ ɢᴇᴛᴛɪɴɢ ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs ʟɪsᴛ... </b></blockquote>")
    served_chats = await get_active_chats()
    text = ""
    j = 0
    for x in served_chats:
        try:
            title = (await app.get_chat(x)).title
        except:
            await remove_active_chat(x)
            continue
        try:
            if (await app.get_chat(x)).username:
                user = (await app.get_chat(x)).username
                text += f"<blockquote expandable><b>✧ {j + 1}. <a href=https://t.me/{user}>{unidecode(title).upper()}</a></b></blockquote>\n"
            else:
                text += (
                    f"<blockquote expandable><b>✧ {j + 1}. {unidecode(title).upper()} </b></blockquote>\n"
                )
            j += 1
        except:
            continue
    if not text:
        await mystic.edit_text(f"<blockquote expandable><b>✧ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs ᴏɴ {app.mention}. </b></blockquote>")
    else:
        await mystic.edit_text(
            f"<blockquote expandable><b>✧ ʟɪsᴛ ᴏғ ᴄᴜʀʀᴇɴᴛʟʏ ᴀᴄᴛɪᴠᴇ ᴠᴏɪᴄᴇ ᴄʜᴀᴛs :\n\n{text} </b></blockquote>",
            disable_web_page_preview=True,
        )


@app.on_message(filters.command(["activev", "activevideo","vvc"]) & SUDOERS)
async def activevi_(_, message: Message):
    mystic = await message.reply_text("<blockquote expandable><b>✧ ɢᴇᴛᴛɪɴɢ ᴀᴄᴛɪᴠᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs ʟɪsᴛ... </b></blockquote>")
    served_chats = await get_active_video_chats()
    text = ""
    j = 0
    for x in served_chats:
        try:
            title = (await app.get_chat(x)).title
        except:
            await remove_active_video_chat(x)
            continue
        try:
            if (await app.get_chat(x)).username:
                user = (await app.get_chat(x)).username
                text += f"<blockquote expandable><b>✧ {j + 1}. <a href=https://t.me/{user}>{unidecode(title).upper()}</a> [<code>{x}</code>] </b></blockquote>\n"
            else:
                text += (
                    f"<blockquote expandable><b>✧ {j + 1}. {unidecode(title).upper()} [<code>{x}</code>] </b></blockquote>\n"
                )
            j += 1
        except:
            continue
    if not text:
        await mystic.edit_text(f"<blockquote expandable><b>✧ ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs ᴏɴ {app.mention}. </b></blockquote>")
    else:
        await mystic.edit_text(
            f"<blockquote expandable><b>✧ ʟɪsᴛ ᴏғ ᴄᴜʀʀᴇɴᴛʟʏ ᴀᴄᴛɪᴠᴇ ᴠɪᴅᴇᴏ ᴄʜᴀᴛs :\n\n{text} </b></blockquote>",
            disable_web_page_preview=True,
        )

@app.on_message(filters.command(["ac","av"]) & SUDOERS)
async def start(client: Client, message: Message):
    ac_audio = str(len(await get_active_chats()))
    ac_video = str(len(await get_active_video_chats()))
    await message.reply_text(f"<blockquote expandable><b>✧ <u>ᴀᴄᴛɪᴠᴇ ᴄʜᴀᴛs ɪɴғᴏ</u> :\n\nᴠᴏɪᴄᴇ : {ac_audio}\nᴠɪᴅᴇᴏ  : {ac_video} </b></blockquote>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✯ ᴄʟᴏsᴇ ✯', callback_data=f"close")]]))
