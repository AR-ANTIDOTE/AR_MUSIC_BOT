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


import random
import asyncio
import math
import config
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from AxiomMusic.utils.formatters import time_to_seconds
from AxiomMusic import app
from pyrogram.enums import ButtonStyle
from AxiomMusic.utils.stream.thumbnail import get_thumbnail_status
from AxiomMusic.utils.database import is_autoplay

def random_style():
    return random.choice([
        ButtonStyle.SUCCESS,
        ButtonStyle.DANGER,
        ButtonStyle.PRIMARY
    ])
            
def track_markup(_, videoid, user_id, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}", style=random_style(),
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}", style=random_style(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}", style=ButtonStyle.DANGER,
            )
        ],
    ]
    return buttons


def stream_markup_timer(_, chat_id, played, dur):
    print(f"DEBUG: stream_markup_timer called for {chat_id}")
    # played_sec = time_to_seconds(played)
    # duration_sec = time_to_seconds(dur)
    # percentage = (played_sec / duration_sec) * 100
    # ufff = math.floor(percentage)
    
    # # Determine bar and color based on progress
    # if 0 < ufff <= 10:
    #     bar = "┃┊♡—————————┊┃"
    #     bar_style = ButtonStyle.PRIMARY
    # elif 10 < ufff < 20:
    #     bar = "┃┊—♡————————┊┃"
    #     bar_style = ButtonStyle.SUCCESS
    # elif 20 <= ufff < 30:
    #     bar = "┃┊——♡———————┊┃"
    #     bar_style = ButtonStyle.DANGER
    # elif 30 <= ufff < 40:
    #     bar = "┃┊———♡——————┊┃"
    #     bar_style = ButtonStyle.PRIMARY
    # elif 40 <= ufff < 50:
    #     bar = "┃┊————♡—————┊┃"
    #     bar_style = ButtonStyle.SUCCESS
    # elif 50 <= ufff < 60:
    #     bar = "┃┊—————♡————┊┃"
    #     bar_style = ButtonStyle.DANGER
    # elif 60 <= ufff < 70:
    #     bar = "┃┊——————♡———┊┃"
    #     bar_style = ButtonStyle.PRIMARY
    # elif 70 <= ufff < 80:
    #     bar = "┃┊———————♡——┊┃"
    #     bar_style = ButtonStyle.SUCCESS
    # elif 80 <= ufff < 95:
    #     bar = "┃┊————————♡—┊┃"
    #     bar_style = ButtonStyle.DANGER
    # else:
    #     bar = "┃┊—————————♡┊┃"
    #     bar_style = ButtonStyle.PRIMARY

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            autoplay_status = loop.create_task(is_autoplay(chat_id))
        else:
            autoplay_status = loop.run_until_complete(is_autoplay(chat_id))
    except:
        autoplay_status = False
    
    autoplay_text = "𝐀ᴜᴛᴏᴘʟᴀʏ | 𝐎‌ɴ" if autoplay_status else "𝐀ᴜᴛᴏᴘʟᴀʏ | 𝐎‌ғғ"
    autoplay_style = ButtonStyle.SUCCESS if autoplay_status else ButtonStyle.DANGER
    
    thumb_status = get_thumbnail_status(chat_id)

    thumb_text = (
        "𝐓‌ʜᴜᴍʙ | 𝐎‌ɴ"
        if thumb_status == "on"
        else "𝐓‌ʜᴜᴍʙ | 𝐎‌ғғ"
    )
    
    thumb_style = (
        ButtonStyle.SUCCESS
        if thumb_status == "on"
        else ButtonStyle.DANGER
    ) 
    buttons = [
        # [
        #     InlineKeyboardButton(
        #         text=f"{played} {bar} {dur}",
        #         url=f"https://t.me/{app.username}?startgroup=true",
        #         style=bar_style,
        #     )
        # ],
        [
            InlineKeyboardButton("⪻ -𝟸5s", callback_data="seek_backward_25", style=random_style()),
            # InlineKeyboardButton(text="II", callback_data=f"ADMIN Resume|{chat_id}", style=random_style()),
            # InlineKeyboardButton(text="▷", callback_data=f"ADMIN Pause|{chat_id}", style=random_style()),
            InlineKeyboardButton(text="↻", callback_data=f"ADMIN Replay|{chat_id}", style=random_style()),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}", style=random_style()),
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}", style=random_style()),
            InlineKeyboardButton("+𝟸5s ⪼", callback_data="seek_forward_25", style=random_style()),
        ],
        [
            InlineKeyboardButton(text=thumb_text, callback_data=f"THUMBTOGGLE|{chat_id}", style=thumb_style),
            InlineKeyboardButton(text=autoplay_text, callback_data=f"autoplay_from_player|{chat_id}", style=autoplay_style),
        ],
        # [
        #     InlineKeyboardButton("⪻ -𝟸5s", callback_data="seek_backward_25", style=random_style()),
        #     InlineKeyboardButton(text="↻", callback_data=f"ADMIN Replay|{chat_id}", style=random_style()),
        #     InlineKeyboardButton("+𝟸5s ⪼", callback_data="seek_forward_25", style=random_style()),
        # ]
    ]
    return buttons


def stream_markup(_, chat_id):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            autoplay_status = loop.create_task(is_autoplay(chat_id))
        else:
            autoplay_status = loop.run_until_complete(is_autoplay(chat_id))
    except:
        autoplay_status = False
    
    autoplay_text = "𝐀ᴜᴛᴏᴘʟᴀʏ | 𝐎‌ɴ" if autoplay_status else "𝐀ᴜᴛᴏᴘʟᴀʏ | 𝐎‌ғғ"
    autoplay_style = ButtonStyle.SUCCESS if autoplay_status else ButtonStyle.DANGER
    
    thumb_status = get_thumbnail_status(chat_id)

    thumb_text = (
        "𝐓‌ʜᴜᴍʙ | 𝐎‌ɴ"
        if thumb_status == "on"
        else "𝐓‌ʜᴜᴍʙ | 𝐎‌ғғ"
    )
    
    thumb_style = (
        ButtonStyle.SUCCESS
        if thumb_status == "on"
        else ButtonStyle.DANGER
    )    
    buttons = [
        [
            InlineKeyboardButton(text="II", callback_data=f"ADMIN Resume|{chat_id}", style=random_style()),
            InlineKeyboardButton(text="▷", callback_data=f"ADMIN Pause|{chat_id}", style=random_style()),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ADMIN Skip|{chat_id}", style=random_style()),
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}", style=random_style()),
        ],
        [
            InlineKeyboardButton(text=thumb_text, callback_data=f"THUMBTOGGLE|{chat_id}", style=thumb_style),
            InlineKeyboardButton(text=autoplay_text, callback_data=f"autoplay_from_player|{chat_id}", style=autoplay_style),
        ],
        [
            InlineKeyboardButton("⪻ -𝟸5s", callback_data="seek_backward_25", style=random_style()),
            InlineKeyboardButton(text="↻", callback_data=f"ADMIN Replay|{chat_id}", style=random_style()),
            InlineKeyboardButton("+𝟸5s ⪼", callback_data="seek_forward_25", style=random_style()),
        ]
    ]
    return buttons


def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MaanavPlaylists {videoid}|{user_id}|{ptype}|a|{channel}|{fplay}", style=random_style(),
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MaanavPlaylists {videoid}|{user_id}|{ptype}|v|{channel}|{fplay}", style=random_style(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}", style=ButtonStyle.DANGER,
            ),
        ],
    ]
    return buttons


def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_3"],
                callback_data=f"LiveStream {videoid}|{user_id}|{mode}|{channel}|{fplay}", style=random_style(),
            ),
        ],
        [
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {videoid}|{user_id}", style=ButtonStyle.DANGER,
            ),
        ],
    ]
    return buttons


def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    query = f"{query[:20]}"
    buttons = [
        [
            InlineKeyboardButton(
                text=_["P_B_1"],
                callback_data=f"MusicStream {videoid}|{user_id}|a|{channel}|{fplay}", style=random_style(),
            ),
            InlineKeyboardButton(
                text=_["P_B_2"],
                callback_data=f"MusicStream {videoid}|{user_id}|v|{channel}|{fplay}", style=random_style(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="◁",
                callback_data=f"slider B|{query_type}|{query}|{user_id}|{channel}|{fplay}", style=random_style(),
            ),
            InlineKeyboardButton(
                text=_["CLOSE_BUTTON"],
                callback_data=f"forceclose {query}|{user_id}", style=ButtonStyle.DANGER,
            ),
            InlineKeyboardButton(
                text="▷",
                callback_data=f"slider F|{query_type}|{query}|{user_id}|{channel}|{fplay}", style=random_style(),
            ),
        ],
    ]
    return buttons
