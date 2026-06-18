import asyncio
import random
import re
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay
from AxiomMusic.utils.stream.queue import put_queue

AUTOPLAY_BATCH_SIZE = 8
AUTOPLAY_REFETCH_THRESHOLD = 2
_autoplay_fetching = {}
PLAYED_HISTORY = {}

def clean_title(title: str) -> str:
    """Extract main song name by removing noise"""
    if not title:
        return ""
    
    # Remove brackets and their content
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    
    # Remove common words
    noise_words = [
        'official', 'video', 'audio', 'full', 'song', 'title', 'hd', 
        '4k', '8k', 'new', 'latest', 'lyrics', 'lyrical', 'with', 
        'feat', 'featuring', 'ft', 'from', 'by'
    ]
    for word in noise_words:
        title = title.replace(word, '')
    
    # Split by separators and take first part
    for sep in [' - ', ' | ', ' by ', ' from ']:
        if sep in title:
            title = title.split(sep)[0]
            break
    
    # Clean special chars
    title = re.sub(r'[^a-z0-9\s]', '', title.lower())
    title = ' '.join(title.split()).strip()
    
    return title

def is_bad_song(title: str, duration_sec: int) -> bool:
    """Reject unwanted content"""
    if not title:
        return True
    
    title_lower = title.lower()
    
    # Reject these
    bad_words = [
        'jukebox', 'mix', 'album', 'compilation', 'playlist', 
        'full movie', 'medley', 'collection', 'mashup', 'non stop',
        '1 hour', '60 min', '90 min'
    ]
    
    for word in bad_words:
        if word in title_lower:
            return True
    
    # Duration: 1.5 min to 12 min
    if duration_sec < 90 or duration_sec > 720:
        return True
    
    return False

def is_same_song(title1: str, title2: str) -> bool:
    """Check if two titles are the same song"""
    clean1 = clean_title(title1)
    clean2 = clean_title(title2)
    
    if not clean1 or not clean2:
        return False
    
    # Split into words
    words1 = set(clean1.split())
    words2 = set(clean2.split())
    
    if not words1 or not words2:
        return False
    
    # Check if they share at least 2 important words
    intersection = words1 & words2
    if len(intersection) >= 2:
        return True
    
    # Check if one contains the other (for short titles)
    if len(clean1) > 5 and clean1 in clean2:
        return True
    if len(clean2) > 5 and clean2 in clean1:
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
            "clean": clean_title(seed_title)
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
                    
                    # Skip if already in queue
                    if rel_id in queued_vids:
                        continue
                    
                    # Skip if bad song
                    if is_bad_song(rel_title, rel_dur):
                        LOGGER(__name__).info(f"[AutoPlay] Rejected (bad): {rel_title[:50]}")
                        continue
                    
                    # Check if same as any played song
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
                    
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Related error: {e}")

        # Method 2: Smart fallback search
        if len(candidates) < limit and seed_title:
            clean_seed = clean_title(seed_title)
            
            # Extract artist name if possible
            artist = ""
            for sep in [' - ', ' | ', ' by ']:
                if sep in seed_title:
                    parts = seed_title.split(sep)
                    if len(parts) > 1:
                        artist = parts[-1].strip()
                        # Clean artist name
                        artist = re.sub(r'[^a-z0-9\s]', '', artist.lower()).strip()
                    break
            
            # Build search queries
            search_queries = []
            if clean_seed:
                search_queries.append(clean_seed)
            if artist and len(artist) > 3:
                search_queries.append(f"{artist} songs")
            
            # Add generic queries if needed
            if len(search_queries) < 2:
                search_queries.extend([
                    "latest hindi songs 2026",
                    "popular bollywood songs"
                ])
            
            for query in search_queries[:3]:  # Limit to 3 queries
                if len(candidates) >= limit * 2:
                    break
                    
                try:
                    result, vidid = await YouTube.track(query)
                    
                    if result and vidid:
                        if vidid not in queued_vids:
                            # Check history
                            is_dup = False
                            for played in history:
                                if played.get("vidid") == vidid or is_same_song(played.get("title", ""), result.get("title", "")):
                                    is_dup = True
                                    break
                            
                            if not is_dup:
                                dur_str = result.get("duration_min", "0:00")
                                dur_sec = 0
                                try:
                                    parts = str(dur_str).split(":")
                                    if len(parts) == 2:
                                        dur_sec = int(parts[0]) * 60 + int(parts[1])
                                except:
                                    pass
                                
                                if not is_bad_song(result.get("title", ""), dur_sec):
                                    candidates.append({
                                        "id": vidid,
                                        "title": result.get("title"),
                                        "duration": dur_sec,
                                        "source": "search"
                                    })
                                    LOGGER(__name__).info(f"[AutoPlay] Found via search: {result.get('title', '')[:40]}")
                                    
                except Exception as e:
                    LOGGER(__name__).error(f"[AutoPlay] Search error for {query}: {e}")

        LOGGER(__name__).info(f"[AutoPlay] Total valid candidates: {len(candidates)}")
        
        if not candidates:
            LOGGER(__name__).warning(f"[AutoPlay] No candidates found for chat {chat_id}")
            return 0
        
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
            
            # Final validation
            if is_bad_song(title, duration_sec):
                continue
            
            # Final duplicate check
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
                    "title": title,
                    "clean": clean_title(title)
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
                    f"<b>♬ Autoplay added {added} fresh song(s) to queue</b>"
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
        LOGGER(__name__).info(f"[AutoPlay] Trigger - Queue: {current_queue}/{AUTOPLAY_REFETCH_THRESHOLD}")
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
