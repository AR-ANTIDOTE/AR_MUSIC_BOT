import asyncio
import random
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay
from AxiomMusic.utils.stream.queue import put_queue

AUTOPLAY_BATCH_SIZE = 10
AUTOPLAY_REFETCH_THRESHOLD = 3
_autoplay_fetching = {}
PLAYED_HISTORY = {}

def is_same_song(title1: str, title2: str) -> bool:
    """
    Check if two titles are basically the same song
    Example: "Sanam Re" and "Sanam Re 8K" = SAME
    """
    if not title1 or not title2:
        return False
    
    # Convert to lowercase and remove special chars
    t1 = ''.join(c for c in title1.lower() if c.isalnum() or c.isspace())
    t2 = ''.join(c for c in title2.lower() if c.isalnum() or c.isspace())
    
    # Split into words
    words1 = set(t1.split())
    words2 = set(t2.split())
    
    # Remove common words
    common_words = {'related singer songs','song', 'video', 'audio', 'official', 'full', 'hd', '4k', '8k', 'new', 'title'}
    words1 = words1 - common_words
    words2 = words2 - common_words
    
    # If 70% words match, it's the same song
    if not words1 or not words2:
        return False
    
    intersection = words1 & words2
    similarity = len(intersection) / min(len(words1), len(words2))
    
    return similarity >= 0.7

def is_bad_song(title: str, duration_sec: int) -> bool:
    """Reject jukebox/mix/compilation"""
    if not title:
        return True
    
    title_lower = title.lower()
    bad_words = ['jukebox', 'mix', 'album', 'mashup', 'compilation', 'playlist', 'full movie', 'medley', 'collection']
    
    for word in bad_words:
        if word in title_lower:
            return True
    
    # Duration: 1.5 min to 15 min
    if duration_sec < 90 or duration_sec > 900:
        return True
    
    return False

async def queue_autoplay_tracks(chat_id: int, seed_track: dict, limit: int = AUTOPLAY_BATCH_SIZE) -> int:
    if not seed_track or not await is_autoplay(chat_id):
        return 0
        
    if _autoplay_fetching.get(chat_id):
        return 0

    _autoplay_fetching[chat_id] = True
    added = 0
    original_chat_id = seed_track.get("chat_id", chat_id)
    requester_id = seed_track.get("user_id", 0)
    streamtype = seed_track.get("streamtype", "audio")
    seed_video_id = seed_track.get("vidid")
    seed_title = seed_track.get("title", "")
    
    # Init history for this chat
    if chat_id not in PLAYED_HISTORY:
        PLAYED_HISTORY[chat_id] = []  # List of titles
    
    history = PLAYED_HISTORY[chat_id]
    
    # Add current song to history
    if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
        history.append({
            "vidid": seed_video_id,
            "title": seed_title
        })
    
    # Get current queue
    current_queue = db.get(chat_id, [])
    queued_vids = {item.get("vidid") for item in current_queue if item.get("vidid")}
    
    LOGGER(__name__).info(f"[AutoPlay] Queue={len(current_queue)}, History={len(history)}")

    try:
        candidates = []
        
        # Method 1: Get related streams from Piped API
        if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
            try:
                related_list = await YouTube.get_related_streams(seed_video_id)
                LOGGER(__name__).info(f"[AutoPlay] Got {len(related_list)} related")
                
                for rel in related_list:
                    rel_id = rel.get("id")
                    rel_title = rel.get("title", "")
                    rel_dur = rel.get("duration", 0)
                    
                    # Skip if no ID
                    if not rel_id:
                        continue
                    
                    # Skip if already in queue
                    if rel_id in queued_vids:
                        continue
                    
                    # Skip if bad song (jukebox, etc)
                    if is_bad_song(rel_title, rel_dur):
                        LOGGER(__name__).info(f"[AutoPlay] Rejected (bad): {rel_title[:50]}")
                        continue
                    
                    # CRITICAL: Check if same as ANY previously played song
                    is_duplicate = False
                    for played in history:
                        if played.get("vidid") == rel_id:
                            is_duplicate = True
                            break
                        if is_same_song(played.get("title", ""), rel_title):
                            is_duplicate = True
                            LOGGER(__name__).info(f"[AutoPlay] REJECTED (same as {played.get('title', '')[:30]}): {rel_title[:50]}")
                            break
                    
                    if is_duplicate:
                        continue
                    
                    # Valid candidate!
                    candidates.append({
                        "id": rel_id,
                        "title": rel_title,
                        "duration": rel_dur
                    })
                    LOGGER(__name__).info(f"[AutoPlay] ✓ Candidate: {rel_title[:50]}")
                    
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Related error: {e}")

        LOGGER(__name__).info(f"[AutoPlay] Total valid candidates: {len(candidates)}")
        
        # Shuffle for variety
        random.shuffle(candidates)

        # Add to queue
        for candidate in candidates:
            if added >= limit:
                break
                
            next_id = candidate.get("id")
            next_title = candidate.get("title")
            
            if not next_id or next_id in queued_vids:
                continue
            
            # Get full details
            try:
                title, duration_min, duration_sec, _, next_vidid = await YouTube.details(next_id, videoid=True)
                if not title:
                    title = next_title
                if not duration_min:
                    duration_min = "0:00"
            except Exception:
                title = next_title
                duration_min = "0:00"
                duration_sec = candidate.get("duration", 0)
                next_vidid = next_id
            
            # Final check
            if is_bad_song(title, duration_sec):
                continue
            
            # Check if same as any played song
            is_dup = False
            for played in history:
                if is_same_song(played.get("title", ""), title):
                    is_dup = True
                    break
            
            if is_dup:
                continue
            
            # ADD TO QUEUE
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
                
                # Add to history
                history.append({
                    "vidid": next_vidid,
                    "title": title
                })
                queued_vids.add(next_vidid)
                added += 1
                
                LOGGER(__name__).info(f"[AutoPlay] ✓✓ ADDED: {title[:50]}")
                
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Queue error: {e}")

        if added > 0:
            try:
                await app.send_message(
                    original_chat_id,
                    f"<b>♬ Autoplay added {added} new song(s)</b>"
                )
            except:
                pass
        
        LOGGER(__name__).info(f"[AutoPlay] Total added: {added}")
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
    
    if current_queue <= AUTOPLAY_REFETCH_THRESHOLD:
        LOGGER(__name__).info(f"[AutoPlay] Trigger - Queue: {current_queue}")
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
