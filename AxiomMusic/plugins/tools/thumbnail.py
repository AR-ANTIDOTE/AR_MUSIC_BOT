from pyrogram import filters
from pyrogram.types import Message

from AxiomMusic import app
from AxiomMusic.utils.database import (
    thumb_on,
    thumb_off,
    is_thumbmode,
)


@app.on_message(filters.command("thumbnail") & filters.group)
async def thumbnail_cmd(_, message: Message):

    chat_id = message.chat.id

    # ----------------------------
    # STATUS CHECK
    # ----------------------------
    if len(message.command) < 2:

        status = await is_thumbmode(chat_id)

        return await message.reply_text(
            f"<b>𝚻ʜ꧊‌𝛖ϻβηᴧιℓ 𝚺ᴛᴀᴛᴜs:</b> {'Enabled ✅' if status else 'Disabled ❌'}\n\n"
            "Usᴧɢє:\n"
            "/thumbnail on\n"
            "/thumbnail off"
        )

    option = message.command[1].lower()

    # ----------------------------
    # ENABLE THUMBNAIL
    # ----------------------------
    if option == "on":

        await thumb_on(chat_id)

        return await message.reply_text(
            "<b>𝚻ʜ꧊‌𝛖ϻβηᴧιℓ 𝙴ɴᴀʙʟᴇᴅ ✅</b>"
        )

    # ----------------------------
    # DISABLE THUMBNAIL
    # ----------------------------
    elif option == "off":

        await thumb_off(chat_id)

        return await message.reply_text(
            "<b>𝚻ʜ꧊‌𝛖ϻβηᴧιℓ 𝙳ɪsᴀʙʟᴇᴅ ❌</b>"
        )

    # ----------------------------
    # INVALID ARGUMENT
    # ----------------------------
    else:

        return await message.reply_text(
            "Usᴧɢє:\n"
            "/thumbnail on\n"
            "/thumbnail off"
        )
