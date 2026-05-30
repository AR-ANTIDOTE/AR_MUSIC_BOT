#c/utils/inline/start.py‎
#+6
#-44
#Lines changed: 6 additions & 44 deletions
#Original file line number	Diff line number	Diff line change
#@@ -1,19 +1,5 @@
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
from pyrogram.types import InlineKeyboardButton
from pyrogram.enums import ButtonStyle
import config
from AxiomMusic import app

#@@ -22,15 +8,9 @@ def start_panel(_):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_1"],
                url=f"https://t.me/{app.username}?startgroup=true",
            )
        ],
        [
            InlineKeyboardButton(
                text=_["S_B_2"],
                url=config.SUPPORT_CHANNEL,
                text=_["S_B_1"], url=f"https://t.me/{app.username}?startgroup=true"
            ),
            InlineKeyboardButton(text=_["S_B_2"], url=config.SUPPORT_CHAT),
        ],
    ]
    return buttons
# @@ -39,31 +19,13 @@ def start_panel(_):
def private_panel(_):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["S_B_3"],
                url=f"https://t.me/{app.username}?startgroup=true",
            ),
        ],
        [
            InlineKeyboardButton(text=_["S_B_5"], user_id=config.OWNER_ID),
            InlineKeyboardButton(text="📼ʏᴛ-ᴀᴘɪ", callback_data="api_status"),
            InlineKeyboardButton(text=_["S_B_3"], url=f"https://t.me/{app.username}?startgroup=true", style=Buttonstyle.PRIMARY)
        ],
        [
            InlineKeyboardButton(
                text=_["S_B_6"],
                url=config.SUPPORT_CHAT,
            ),
            InlineKeyboardButton(
                text=_["S_B_2"],
                url=config.SUPPORT_CHANNEL,
            ),
            InlineKeyboardButton(text=_["S_B_2"], url=config.SUPPORT_CHAT, style=Buttonstyle.SECONDARY),
        ],
        [
            InlineKeyboardButton(
                text=_["S_B_4"],
                callback_data="settings_back_helper",
            ),
            InlineKeyboardButton(text=_["S_B_4"], callback_data="settings_back_helper", style=Buttonstyle.PRIMARY),
        ],
    ]
    return buttons
