import asyncio
import random
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay
from AxiomMusic.utils.stream.queue import put_queue

# --- UNLIMITED AUTOPLAY SETTINGS ---
AUTOPLAY_BATCH_SIZE = 15  # Fetch 15 songs at once
AUTOPLAY_REFETCH_THRESHOLD = 3  # Fetch new songs when only 3 left in queue
_autoplay_fetching = {}

# --- HISTORY TRACKER (Prevents repeats forever) ---
PLAYED_HISTORY = {}  # Format: {chat_id: set(vidid1, vidid2...)}

def autoplay_seed(track: dict) -> str:
    title = (track or {}).get("title") or "music"
    by = (track or {}).get("by") or ""
    if by and by not in ["Autoplay", "Unknown"]:
        return f"{title} {by}"
    return title

async def queue_autoplay_tracks(chat_id: int, seed_track: dict, limit: int = AUTOPLAY_BATCH_SIZE) -> int:
    if not seed_track or not await is_autoplay(seed_track.get("chat_id", chat_id)):
        return 0
    if _autoplay_fetching.get(chat_id):
        return 0

    _autoplay_fetching[chat_id] = True
    added = 0
    original_chat_id = seed_track.get("chat_id", chat_id)
    requester_id = seed_track.get("user_id", 0)
    streamtype = seed_track.get("streamtype", "audio")
    seed_video_id = seed_track.get("vidid")
    
    # Initialize history for this chat
    history = PLAYED_HISTORY.setdefault(chat_id, set())
    if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
        history.add(seed_video_id)
        
    seen = {item.get("vidid") for item in db.get(chat_id, [])}
    if seed_video_id:
        seen.add(seed_video_id)

    try:
        candidates = []
        
        # 1. Fetch ACTUAL related videos (15+ songs from Piped API)
        if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
            try:
                related_list = await YouTube.get_related_streams(seed_video_id)
                for rel in related_list:
                    if rel.get("id") and rel["id"] not in seen and rel["id"] not in history:
                        candidates.append(rel)
            except Exception as exc:
                LOGGER(__name__).warning(f"[AutoPlay] related lookup failed: {exc}")

        # 2. If not enough related songs, search for more
        if len(candidates) < limit:
            seed_query = autoplay_seed(seed_track)
            queries = [
                f"{seed_query} non stop mix",
                f"{seed_query} jukebox",
                f"{seed_query} full album",
                f"{seed_query} playlist"
            ]
            for query in queries:
                if len(candidates) >= limit * 2:
                    break
                try:
                    result, vidid = await YouTube.track(query)
                    if result and vidid and vidid not in seen and vidid not in history:
                        candidates.append({
                            "id": vidid,
                            "title": result.get("title"),
                            "duration": result.get("duration_min"),
                            "thumb": result.get("thumb")
                        })
                except Exception as exc:
                    LOGGER(__name__).warning(f"[AutoPlay] search failed for {query}: {exc}")

        # Shuffle to get random songs every time
        random.shuffle(candidates)

        for candidate in candidates:
            if added >= limit:
                break
            next_id = candidate.get("id")
            
            # Ensure NO REPEATS
            if not next_id or next_id in seen or next_id in history:
                continue
            
            try:
                title, duration_min, duration_sec, _, next_vidid = await YouTube.details(next_id, videoid=True)
            except Exception:
                title = candidate.get("title") or "Autoplay Track"
                duration_min = candidate.get("duration") or "0:00"
                duration_sec = candidate.get("duration") if isinstance(candidate.get("duration"), int) else 0
                next_vidid = next_id

            if not next_vidid or next_vidid in seen or next_vidid in history or str(duration_min) == "None":
                continue
            if duration_sec and duration_sec > config.DURATION_LIMIT:
                continue

            await put_queue(
                chat_id,
                original_chat_id,
                f"vid_{next_vidid}",
                title or "Autoplay Track",
                duration_min or "0:00",
                "Autoplay",
                next_vidid,
                requester_id,
                streamtype,
            )
            
            seen.add(next_vidid)
            history.add(next_vidid)  # Add to history - NEVER repeats
            added += 1

        if added:
            try:
                await app.send_message(
                    original_chat_id,
                    f"<b>♬ Autoplay added {added} more songs to queue. Total played: {len(history)}</b>"
                )
            except Exception:
                pass
        return added
    finally:
        _autoplay_fetching[chat_id] = False

async def maybe_refetch_autoplay(chat_id: int, seed_track: dict):
    # Keep fetching as long as queue is low - this makes it UNLIMITED
    current_queue = len(db.get(chat_id, []))
    if current_queue <= AUTOPLAY_REFETCH_THRESHOLD:
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
