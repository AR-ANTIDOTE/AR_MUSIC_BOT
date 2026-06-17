import asyncio
import random
import re
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay
from AxiomMusic.utils.stream.queue import put_queue

AUTOPLAY_BATCH_SIZE = 10
AUTOPLAY_REFETCH_THRESHOLD = 2
_autoplay_fetching = {}

# --- HISTORY STRUCTURE (Stores both Video IDs and Cleaned Titles) ---
# Format: { chat_id: {"vids": set(), "titles": set()} }
PLAYED_HISTORY = {}

# Keywords that indicate a version/mix/jukebox (Instant Reject)
BAD_KEYWORDS = [
    "jukebox", "mix", "album", "compilation", "playlist", 
    "lofi", "slowed", "reverb", "sped up", "8d", "bass boosted", 
    "remix", "mashup", "cover", "acoustic", "unplugged", "live performance"
]

def get_base_title(title: str) -> str:
    """
    Extracts the core song name to prevent duplicate versions.
    Example: 'Sanam Re - Lofi Flip - Arijit Singh' -> 'sanam re'
    """
    if not title: return ""
    # 1. Split by separators to get the main part (before artist name or extra info)
    parts = re.split(r'\s[-|]\s|\sft\.\s|\sfeat\.\s|\sfrom\s', title, flags=re.IGNORECASE)
    main_part = parts[0]
    
    # 2. Remove content in brackets/parentheses (e.g., "(Official Video)", "(Lofi Flip)")
    main_part = re.sub(r'\(.*?\)', '', main_part)
    main_part = re.sub(r'\[.*?\]', '', main_part)
    
    # 3. Clean up special chars and whitespace
    main_part = re.sub(r'[^a-z0-9\s]', '', main_part.lower())
    main_part = re.sub(r'\s+', ' ', main_part).strip()
    
    return main_part

def is_valid_autoplay_song(title: str, duration_sec: int) -> bool:
    """Strict filter: No jukeboxes, no versions, correct duration."""
    if not title: return False
    title_lower = title.lower()
    
    # Check for bad keywords (Lofi, Jukebox, etc.)
    for bad in BAD_KEYWORDS:
        if bad in title_lower:
            return False
            
    # Duration check: 30s to 10 mins (Avoids 1-hour compilations)
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
    
    # Initialize history for this chat
    history = PLAYED_HISTORY.setdefault(chat_id, {"vids": set(), "titles": set()})
    
    # Add current seed track to history (Both ID and Base Title)
    if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
        history["vids"].add(seed_video_id)
        history["titles"].add(get_base_title(seed_track.get("title")))
        
    seen = {item.get("vidid") for item in db.get(chat_id, [])}
    if seed_video_id:
        seen.add(seed_video_id)

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
                    
                    # --- STRICT FILTERS ---
                    if not rel_id or rel_id in seen or rel_id in history["vids"]:
                        continue
                    if not is_valid_autoplay_song(rel_title, rel_dur):
                        continue
                    
                    # --- DUPLICATE TITLE CHECK ---
                    base_title = get_base_title(rel_title)
                    if base_title in history["titles"]:
                        continue # Rejects "Sanam Re Lofi" if "Sanam Re" is already played
                        
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
                    if result and vidid and vidid not in seen and vidid not in history["vids"]:
                        # Calculate duration in seconds from string (e.g., "4:30")
                        dur_min_str = result.get("duration_min", "0:00")
                        dur_sec = 0
                        if dur_min_str:
                            parts = str(dur_min_str).split(":")
                            try:
                                if len(parts) == 2: dur_sec = int(parts[0]) * 60 + int(parts[1])
                                elif len(parts) == 3: dur_sec = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                            except: dur_sec = 0
                        
                        # Apply strict filters
                        if not is_valid_autoplay_song(result.get("title", ""), dur_sec):
                            continue
                        
                        base_title = get_base_title(result.get("title", ""))
                        if base_title in history["titles"]:
                            continue
                            
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
            
            if not next_id or next_id in seen or next_id in history["vids"]:
                continue
            
            try:
                title, duration_min, duration_sec, _, next_vidid = await YouTube.details(next_id, videoid=True)
            except Exception:
                title = candidate.get("title") or "Autoplay Track"
                duration_min = candidate.get("duration") or "0:00"
                duration_sec = candidate.get("duration_sec", 0)
                next_vidid = next_id

            # FINAL VERIFICATION
            if not next_vidid or next_vidid in seen or next_vidid in history["vids"]:
                continue
            if not is_valid_autoplay_song(title, duration_sec):
                continue
            
            base_title = get_base_title(title)
            if base_title in history["titles"]:
                continue # Final check to prevent duplicates

            try:
                await put_queue(
                    chat_id, original_chat_id, f"vid_{next_vidid}",
                    title or "Autoplay Track", duration_min or "0:00",
                    "Autoplay", next_vidid, requester_id, streamtype,
                )
                
                # --- ADD TO HISTORY ---
                seen.add(next_vidid)
                history["vids"].add(next_vidid)
                history["titles"].add(base_title) # Crucial: Saves cleaned title
                added += 1
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Failed to add {next_id} to queue: {e}")
                continue

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
