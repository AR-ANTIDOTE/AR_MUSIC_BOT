import asyncio
import random
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay
from AxiomMusic.utils.stream.queue import put_queue

AUTOPLAY_BATCH_SIZE = 10
AUTOPLAY_REFETCH_THRESHOLD = 2
_autoplay_fetching = {}
PLAYED_HISTORY = {}

# Keywords to avoid in Autoplay (prevents jukeboxes/mixes)
BAD_KEYWORDS = ["jukebox", "mix", "album", "compilation", "playlist", "full movie", "live concert", "non stop", "1 hour", "60 min"]

def is_valid_autoplay_song(title: str, duration_sec: int) -> bool:
    """Strict filter: Only allow normal songs (30s to 10 mins). No jukeboxes!"""
    if not title:
        return False
    title_lower = title.lower()
    for bad in BAD_KEYWORDS:
        if bad in title_lower:
            return False
    # Must be between 30 seconds and 10 minutes (600 seconds)
    if duration_sec < 30 or duration_sec > 600:
        return False
    return True

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
    
    history = PLAYED_HISTORY.setdefault(chat_id, set())
    if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
        history.add(seed_video_id)
        
    seen = {item.get("vidid") for item in db.get(chat_id, [])}
    if seed_video_id:
        seen.add(seed_video_id)
    all_played = seen.union(history)

    try:
        candidates = []
        
        # 1. Fetch ACTUAL related videos (Piped API)
        if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
            try:
                related_list = await YouTube.get_related_streams(seed_video_id)
                for rel in related_list:
                    rel_id = rel.get("id")
                    rel_dur = rel.get("duration", 0)
                    rel_title = rel.get("title", "")
                    # Apply strict filter here
                    if rel_id and rel_id not in all_played and is_valid_autoplay_song(rel_title, rel_dur):
                        candidates.append(rel)
            except Exception as exc:
                LOGGER(__name__).warning(f"[AutoPlay] related lookup failed: {exc}")

        # 2. Fallback search (ONLY IF Piped failed or gave < 5 songs)
        if len(candidates) < 5:
            seed_query = autoplay_seed(seed_track)
            # Search for just the song name, NO jukebox/mix
            queries = [
                f"{seed_query} song",
                f"{seed_query} audio",
                f"{seed_query} official video"
            ]
            for query in queries:
                if len(candidates) >= limit * 2:
                    break
                try:
                    result, vidid = await YouTube.track(query)
                    if result and vidid and vidid not in all_played:
                        # Calculate duration in seconds from string (e.g., "4:30")
                        dur_min_str = result.get("duration_min", "0:00")
                        dur_sec = 0
                        if dur_min_str:
                            parts = str(dur_min_str).split(":")
                            try:
                                if len(parts) == 2:
                                    dur_sec = int(parts[0]) * 60 + int(parts[1])
                                elif len(parts) == 3:
                                    dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                            except:
                                dur_sec = 0
                        
                        # Apply strict filter here too
                        if is_valid_autoplay_song(result.get("title", ""), dur_sec):
                            candidates.append({
                                "id": vidid,
                                "title": result.get("title"),
                                "duration": dur_min_str,
                                "duration_sec": dur_sec,
                                "thumb": result.get("thumb")
                            })
                except Exception as exc:
                    LOGGER(__name__).warning(f"[AutoPlay] search failed for {query}: {exc}")

        random.shuffle(candidates)

        for candidate in candidates:
            if added >= limit:
                break
            next_id = candidate.get("id")
            
            if not next_id or next_id in seen or next_id in history or next_id in all_played:
                continue
            
            try:
                title, duration_min, duration_sec, _, next_vidid = await YouTube.details(next_id, videoid=True)
            except Exception:
                title = candidate.get("title") or "Autoplay Track"
                duration_min = candidate.get("duration") or "0:00"
                duration_sec = candidate.get("duration_sec", 0)
                next_vidid = next_id

            # STRICT FILTER AGAIN before adding
            if not next_vidid or next_vidid in seen or next_vidid in history or next_vidid in all_played:
                continue
            if not is_valid_autoplay_song(title, duration_sec):
                continue

            try:
                await put_queue(
                    chat_id, original_chat_id, f"vid_{next_vidid}",
                    title or "Autoplay Track", duration_min or "0:00",
                    "Autoplay", next_vidid, requester_id, streamtype,
                )
                seen.add(next_vidid)
                history.add(next_vidid)
                all_played.add(next_vidid)
                added += 1  # Only increment if put_queue succeeds
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Failed to add {next_id} to queue: {e}")
                continue

        # ONLY SEND MESSAGE IF WE ACTUALLY ADDED SOMETHING SUCCESSFULLY
        if added > 0:
            try:
                await app.send_message(
                    original_chat_id,
                    f"<b>♬ Autoplay added {added} fresh song(s) to queue.</b>"
                )
            except Exception:
                pass
        
        return added
    finally:
        _autoplay_fetching[chat_id] = False

async def maybe_refetch_autoplay(chat_id: int, seed_track: dict):
    current_queue = len(db.get(chat_id, []))
    if current_queue <= AUTOPLAY_REFETCH_THRESHOLD:
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
        
