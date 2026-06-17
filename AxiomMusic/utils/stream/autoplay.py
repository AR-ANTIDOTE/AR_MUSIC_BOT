import asyncio
import random
import re
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay
from AxiomMusic.utils.stream.queue import put_queue

AUTOPLAY_BATCH_SIZE = 100
AUTOPLAY_REFETCH_THRESHOLD = 5
_autoplay_fetching = {}
PLAYED_HISTORY = {}

BAD_KEYWORDS = [
    "jukebox", "mix", "album", "compilation", "playlist", 
    "lofi", "slowed", "reverb", "sped up", "8d", "bass boosted", 
    "remix", "mashup", "cover", "acoustic", "unplugged", "live",
    "lyrics", "lyrical", "full video", "official video", "video"
]

def clean_title(title: str) -> str:
    """Aggressively clean title to get ONLY the song name"""
    if not title: 
        return ""
    
    # Remove everything in brackets/parentheses
    title = re.sub(r'\s*\(.*?\)\s*', ' ', title)
    title = re.sub(r'\s*\[.*?\]\s*', ' ', title)
    title = re.sub(r'\s*\{.*?\}\s*', ' ', title)
    
    # Remove common separators and everything after
    for separator in [' - ', ' | ', ' ft. ', ' feat. ', ' from ', ' by ']:
        title = title.split(separator)[0]
    
    # Remove numbers and special chars at the end
    title = re.sub(r'\s+(official|video|audio|hd|4k|mp3).*$', '', title, flags=re.IGNORECASE)
    
    # Clean up
    title = re.sub(r'[^a-z0-9\s]', '', title.lower())
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title

def is_valid_song(title: str, duration_sec: int) -> bool:
    if not title or len(title) < 3:
        return False
    
    title_lower = title.lower()
    
    # Reject bad keywords
    for bad in BAD_KEYWORDS:
        if bad in title_lower:
            return False
    
    # Duration: 2 mins to 8 mins
    if duration_sec < 120 or duration_sec > 480:
        return False
    
    return True

async def queue_autoplay_tracks(chat_id: int, seed_track: dict, limit: int = AUTOPLAY_BATCH_SIZE) -> int:
    if not seed_track:
        return 0
    
    if not await is_autoplay(chat_id):
        return 0
        
    if _autoplay_fetching.get(chat_id):
        LOGGER(__name__).info(f"[AutoPlay] Already fetching for chat {chat_id}")
        return 0

    _autoplay_fetching[chat_id] = True
    added = 0
    original_chat_id = seed_track.get("chat_id", chat_id)
    requester_id = seed_track.get("user_id", 0)
    streamtype = seed_track.get("streamtype", "audio")
    seed_video_id = seed_track.get("vidid")
    
    # Initialize history
    if chat_id not in PLAYED_HISTORY:
        PLAYED_HISTORY[chat_id] = set()
    
    history = PLAYED_HISTORY[chat_id]
    
    # Add current song to history
    if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
        history.add(seed_video_id)
        seed_title = clean_title(seed_track.get("title", ""))
        if seed_title:
            history.add(f"TITLE:{seed_title}")
    
    # Get current queue
    current_queue = db.get(chat_id, [])
    queued_vids = {item.get("vidid") for item in current_queue if item.get("vidid")}
    
    LOGGER(__name__).info(f"[AutoPlay] Chat {chat_id}: Queue has {len(current_queue)} songs, History has {len(history)} items")

    try:
        candidates = []
        
        # Method 1: Get related streams
        if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
            try:
                LOGGER(__name__).info(f"[AutoPlay] Fetching related streams for {seed_video_id}")
                related_list = await YouTube.get_related_streams(seed_video_id)
                LOGGER(__name__).info(f"[AutoPlay] Got {len(related_list)} related streams")
                
                for rel in related_list:
                    rel_id = rel.get("id")
                    rel_title = rel.get("title", "")
                    rel_dur = rel.get("duration", 0)
                    
                    if not rel_id:
                        continue
                    
                    # Check if already played or queued
                    if rel_id in history or rel_id in queued_vids:
                        continue
                    
                    # Validate song
                    if not is_valid_song(rel_title, rel_dur):
                        continue
                    
                    # Check cleaned title
                    base_title = clean_title(rel_title)
                    if f"TITLE:{base_title}" in history:
                        LOGGER(__name__).info(f"[AutoPlay] Skipping duplicate: {rel_title}")
                        continue
                    
                    candidates.append({
                        "id": rel_id,
                        "title": rel_title,
                        "duration": rel_dur,
                        "source": "related"
                    })
                    
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Related fetch error: {e}")

        # Method 2: Search if not enough candidates
        if len(candidates) < limit:
            seed_query = seed_track.get("title", "")
            if seed_query:
                # Extract just the song name
                clean_query = clean_title(seed_query)
                if clean_query:
                    search_queries = [
                        f"arijit singh song",
                        f"atif aslam song",
                        f"shreya ghosal popular song",
                        f"{clean_query} song",
                        f"{clean_query} hindi song",
                    ]
                    
                    for query in search_queries:
                        if len(candidates) >= limit * 2:
                            break
                            
                        try:
                            LOGGER(__name__).info(f"[AutoPlay] Searching: {query}")
                            result, vidid = await YouTube.track(query)
                            
                            if result and vidid:
                                if vidid not in history and vidid not in queued_vids:
                                    dur_str = result.get("duration_min", "0:00")
                                    dur_sec = 0
                                    try:
                                        parts = dur_str.split(":")
                                        if len(parts) == 2:
                                            dur_sec = int(parts[0]) * 60 + int(parts[1])
                                    except:
                                        pass
                                    
                                    if is_valid_song(result.get("title", ""), dur_sec):
                                        base_title = clean_title(result.get("title", ""))
                                        if f"TITLE:{base_title}" not in history:
                                            candidates.append({
                                                "id": vidid,
                                                "title": result.get("title"),
                                                "duration": dur_sec,
                                                "source": "search"
                                            })
                        except Exception as e:
                            LOGGER(__name__).error(f"[AutoPlay] Search error for {query}: {e}")

        LOGGER(__name__).info(f"[AutoPlay] Total candidates found: {len(candidates)}")
        
        # Shuffle for variety
        random.shuffle(candidates)

        # Add to queue
        for candidate in candidates:
            if added >= limit:
                break
                
            next_id = candidate.get("id")
            next_title = candidate.get("title")
            
            if not next_id:
                continue
            
            # Double check
            if next_id in history or next_id in queued_vids:
                continue
            
            # Get full details
            try:
                title, duration_min, duration_sec, _, next_vidid = await YouTube.details(next_id, videoid=True)
                if not title:
                    title = next_title
                if not duration_min:
                    duration_min = "0:00"
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Details error for {next_id}: {e}")
                continue
            
            # Final validation
            if not next_vidid or not is_valid_song(title, duration_sec):
                continue
            
            base_title = clean_title(title)
            if f"TITLE:{base_title}" in history:
                continue
            
            # Add to queue
            try:
                await put_queue(
                    chat_id,
                    original_chat_id,
                    f"vid_{next_vidid}",
                    title,
                    duration_min,
                    "Autoplay",
                    next_vidid,
                    requester_id,
                    streamtype,
                )
                
                # Update history
                history.add(next_vidid)
                history.add(f"TITLE:{base_title}")
                queued_vids.add(next_vidid)
                added += 1
                
                LOGGER(__name__).info(f"[AutoPlay] Added: {title[:50]}")
                
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Queue error: {e}")
                continue

        if added > 0:
            msg = f"<b>♬ Autoplay added {added} fresh song(s) to queue.</b>\n"
            msg += f"<i>Total played: {len(history)//2} | Queue: {len(queued_vids)}</i>"
            try:
                await app.send_message(original_chat_id, msg)
            except Exception:
                pass
        
        LOGGER(__name__).info(f"[AutoPlay] Chat {chat_id}: Added {added} songs")
        return added
        
    except Exception as e:
        LOGGER(__name__).error(f"[AutoPlay] Critical error: {e}")
        return 0
    finally:
        _autoplay_fetching[chat_id] = False

async def maybe_refetch_autoplay(chat_id: int, seed_track: dict):
    if not seed_track:
        return
        
    current_queue = len(db.get(chat_id, []))
    
    LOGGER(__name__).info(f"[AutoPlay] Check - Chat {chat_id}: Queue size = {current_queue}, Threshold = {AUTOPLAY_REFETCH_THRESHOLD}")
    
    if current_queue <= AUTOPLAY_REFETCH_THRESHOLD:
        LOGGER(__name__).info(f"[AutoPlay] Triggering fetch for chat {chat_id}")
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
