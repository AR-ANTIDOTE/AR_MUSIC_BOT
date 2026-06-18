import asyncio
import random
import re
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay
from AxiomMusic.utils.stream.queue import put_queue

AUTOPLAY_BATCH_SIZE = 10
AUTOPLAY_REFETCH_THRESHOLD = 3
_autoplay_fetching = {}
PLAYED_HISTORY = {}

def extract_song_name(title: str) -> str:
    """
    Extract ONLY the song name, removing movie/album name and noise
    Example: "Sanam Re Title Song | Pulkit Samrat" -> "title song"
    Example: "Hua Hain Aaj Pehli Baar | SANAM RE" -> "hua hain aaj pehli baar"
    """
    if not title:
        return ""
    
    # Lowercase
    title = title.lower()
    
    # Remove brackets
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    
    # Split by common separators and take FIRST part (song name)
    for sep in [' | ', ' - ', ' by ', ' from ', ' ft. ', ' feat. ']:
        if sep in title:
            title = title.split(sep)[0]
            break
    
    # Remove noise words
    noise = {
        'official', 'video', 'audio', 'full', 'song', 'title', 'hd', 
        '4k', '8k', '1080p', '720p', 'new', 'latest', 'lyrics', 
        'lyrical', 'with', 'feat', 'featuring', 'ft', 'the', 'a', 'of'
    }
    
    words = title.split()
    words = [w for w in words if w not in noise]
    
    # Remove non-alphanumeric
    cleaned = ''.join(c for c in ' '.join(words) if c.isalnum() or c.isspace())
    cleaned = ' '.join(cleaned.split()).strip()
    
    return cleaned

def is_same_song(title1: str, title2: str) -> bool:
    """
    Check if two titles are the same song by comparing extracted song names
    """
    song1 = extract_song_name(title1)
    song2 = extract_song_name(title2)
    
    if not song1 or not song2:
        return False
    
    # Exact match
    if song1 == song2:
        return True
    
    # Word overlap check
    words1 = set(song1.split())
    words2 = set(song2.split())
    
    if not words1 or not words2:
        return False
    
    # Common words
    common = words1 & words2
    
    # If 70% words match, it's the same song
    similarity = len(common) / min(len(words1), len(words2))
    return similarity >= 0.7

def is_bad_song(title: str, duration_sec: int) -> bool:
    """Reject jukebox, mashup, compilation"""
    if not title:
        return True
    
    title_lower = title.lower()
    
    bad_words = [
        'jukebox', 'mashup', 'mix', 'album', 'compilation', 
        'playlist', 'full movie', 'medley', 'collection', 
        'non stop', '1 hour', '60 min', 'all songs'
    ]
    
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
        LOGGER(__name__).info(f"[AutoPlay] Already fetching for {chat_id}")
        return 0

    _autoplay_fetching[chat_id] = True
    added = 0
    original_chat_id = seed_track.get("chat_id", chat_id)
    requester_id = seed_track.get("user_id", 0)
    streamtype = seed_track.get("streamtype", "audio")
    seed_video_id = seed_track.get("vidid")
    seed_title = seed_track.get("title", "")
    
    # Initialize history
    if chat_id not in PLAYED_HISTORY:
        PLAYED_HISTORY[chat_id] = []
    
    history = PLAYED_HISTORY[chat_id]
    
    # Add current song to history
    if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
        history.append({
            "vidid": seed_video_id,
            "title": seed_title,
            "song_name": extract_song_name(seed_title)
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
                LOGGER(__name__).info(f"[AutoPlay] Got {len(related_list)} related from Piped")
                
                for rel in related_list:
                    rel_id = rel.get("id")
                    rel_title = rel.get("title", "")
                    rel_dur = rel.get("duration", 0)
                    
                    if not rel_id:
                        continue
                    
                    if rel_id in queued_vids:
                        continue
                    
                    if is_bad_song(rel_title, rel_dur):
                        LOGGER(__name__).info(f"[AutoPlay] Rejected (bad): {rel_title[:50]}")
                        continue
                    
                    # Check if same song
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
                    
                    candidates.append({
                        "id": rel_id,
                        "title": rel_title,
                        "duration": rel_dur,
                        "source": "related"
                    })
                    LOGGER(__name__).info(f"[AutoPlay] ✓ Candidate: {rel_title[:50]}")
                    
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Related error: {e}")

        # Method 2: Fallback search
        if len(candidates) < limit and seed_title:
            song_name = extract_song_name(seed_title)
            
            search_queries = []
            if song_name:
                words = song_name.split()[:3]
                if words:
                    main_query = ' '.join(words)
                    search_queries = [
                        main_query,
                        f"{main_query} song",
                    ]
            
            for query in search_queries:
                if len(candidates) >= limit * 2:
                    break
                    
                try:
                    result, vidid = await YouTube.track(query)
                    
                    if result and vidid and vidid not in queued_vids:
                        is_dup = False
                        for played in history:
                            if played.get("vidid") == vidid or is_same_song(played.get("title", ""), result.get("title", "")):
                                is_dup = True
                                break
                        
                        if not is_dup and not is_bad_song(result.get("title", ""), 0):
                            candidates.append({
                                "id": vidid,
                                "title": result.get("title"),
                                "duration": 0,
                                "source": "search"
                            })
                            LOGGER(__name__).info(f"[AutoPlay] Found via search: {result.get('title', '')[:40]}")
                            
                except Exception as e:
                    LOGGER(__name__).error(f"[AutoPlay] Search error: {e}")

        LOGGER(__name__).info(f"[AutoPlay] Total valid candidates: {len(candidates)}")
        random.shuffle(candidates)

        # Add to queue
        for candidate in candidates:
            if added >= limit:
                break
                
            next_id = candidate.get("id")
            if not next_id or next_id in queued_vids:
                continue
            
            try:
                title, duration_min, duration_sec, _, next_vidid = await YouTube.details(next_id, videoid=True)
                if not title:
                    title = candidate.get("title", "Unknown")
                if not duration_min:
                    duration_min = "0:00"
            except Exception:
                title = candidate.get("title", "Unknown")
                duration_min = "0:00"
                duration_sec = candidate.get("duration", 0)
                next_vidid = next_id
            
            if is_bad_song(title, duration_sec):
                continue
            
            is_dup = False
            for played in history:
                if is_same_song(played.get("title", ""), title):
                    is_dup = True
                    break
            
            if is_dup:
                continue
            
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
                
                history.append({
                    "vidid": next_vidid,
                    "title": title,
                    "song_name": extract_song_name(title)
                })
                queued_vids.add(next_vidid)
                added += 1
                
                LOGGER(__name__).info(f"[AutoPlay] ✓ ADDED: {title[:50]}")
                
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Queue error: {e}")

        if added > 0:
            try:
                await app.send_message(
                    original_chat_id,
                    f"<b>♬ Autoplay added {added} fresh song(s)</b>"
                )
            except:
                pass
        
        LOGGER(__name__).info(f"[AutoPlay] Total added: {added}")
        return added
        
    except Exception as e:
        LOGGER(__name__).error(f"[AutoPlay] Critical: {e}")
        return 0
    finally:
        _autoplay_fetching[chat_id] = False

async def maybe_refetch_autoplay(chat_id: int, seed_track: dict):
    if not seed_track:
        return
        
    current_queue = len(db.get(chat_id, []))
    
    if current_queue <= AUTOPLAY_REFETCH_THRESHOLD:
        LOGGER(__name__).info(f"[AutoPlay] Trigger - Queue: {current_queue}/{AUTOPLAY_REFETCH_THRESHOLD}")
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
