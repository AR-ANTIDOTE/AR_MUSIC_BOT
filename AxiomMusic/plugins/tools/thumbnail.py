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
    if len(message.command) < 2:
        status = await is_thumbnail(message.chat.id)

        return await message.reply_text(
            f"<b>𝚻ʜ꧊‌𝛖ϻβηᴧιℓ 𝛅𝞃ᴧ𝞃𝛖s:</b> {'Enabled' if status else 'Disabled'}\n\n"
            "Usᴧɢє:\n"
            "/thumbnail on\n"
            "/thumbnail off"
        )

    option = message.command[1].lower()

    if option == "on":
        await thumbnail_on(message.chat.id)

        return await message.reply_text(
            "<b>𝚻ʜ꧊‌𝛖ϻβηᴧιℓ 𝚺ηᴧβℓє∂.</b>"
        )

    elif option == "off":
        await thumbnail_off(message.chat.id)

        return await message.reply_text(
            "<b>𝚻ʜ꧊‌𝛖ϻβηᴧιℓ ∂ιsᴧβℓє∂.</b>"
        )

    else:
        return await message.reply_text(
            "Usᴧɢє:\n"
            "/thumbnail on\n"
            "/thumbnail off"
        )
