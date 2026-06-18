# -----------------------------------------------
# 🔸 AxiomMusic Project
# 🔹 Developed & Maintained by: Axiom Bots (https://t.me/axiombots)
# 📅 Copyright © 2026 – All Rights Reserved
# -----------------------------------------------

import asyncio
from typing import Union
from AxiomMusic.misc import db
from AxiomMusic.utils.formatters import check_duration, seconds_to_min
from config import autoclean, time_to_seconds


async def put_queue(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    user_id,
    stream,
    forceplay: Union[bool, str] = None,
):
    title = title.title()
    try:
        duration_in_seconds = time_to_seconds(duration) - 3
    except:
        duration_in_seconds = 0
        
    if not user or str(user).strip().lower() in ["", "none", "null", "-"]:
        try:
            from AxiomMusic import app
            member = await app.get_users(user_id)
            user = " ".join(
                filter(None, [member.first_name, member.last_name])
            ).strip() or "Unknown"
        except:
            user = "Unknown"

    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "user_id": user_id,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": duration_in_seconds,
        "played": 0,
    }
    if forceplay:
        check = db.get(chat_id)
        if check:
            check.insert(0, put)
        else:
            db[chat_id] = []
            db[chat_id].append(put)
    else:
        db[chat_id].append(put)
    autoclean.append(file)

    # AUTOPLAY TRIGGER - Single clean block
    try:
        from AxiomMusic.utils.database import is_autoplay
        from AxiomMusic.utils.stream.autoplay import maybe_refetch_autoplay
        
        if await is_autoplay(chat_id):
            asyncio.create_task(maybe_refetch_autoplay(
                chat_id,
                {
                    "chat_id": original_chat_id,
                    "user_id": user_id,
                    "streamtype": stream,
                    "vidid": vidid,
                    "title": title,
                    "by": user
                }
            ))
    except Exception:
        pass


async def put_queue_index(
    chat_id,
    original_chat_id,
    file,
    title,
    duration,
    user,
    vidid,
    user_id,
    stream,
    forceplay: Union[bool, str] = None,
):
    if "20.212.146.162" in vidid:
        try:
            dur = await asyncio.get_event_loop().run_in_executor(
                None, check_duration, vidid
            )
            duration = seconds_to_min(dur)
        except:
            duration = "ᴜʀʟ sᴛʀᴇᴀᴍ"
            dur = 0
    else:
        dur = 0
        
    if not user or str(user).strip().lower() in ["", "none", "null", "-"]:
        try:
            from AxiomMusic import app
            member = await app.get_users(user_id)
            user = member.first_name
        except:
            user = "Unknown"

    put = {
        "title": title,
        "dur": duration,
        "streamtype": stream,
        "by": user,
        "user_id": user_id,
        "chat_id": original_chat_id,
        "file": file,
        "vidid": vidid,
        "seconds": dur,
        "played": 0,
    }
    if forceplay:
        check = db.get(chat_id)
        if check:
            check.insert(0, put)
        else:
            db[chat_id] = []
            db[chat_id].append(put)
    else:
        db[chat_id].append(put)
