import asyncio
import random
import re
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay, get_autoplay_lang, get_autoplay_mood
from AxiomMusic.utils.stream.queue import put_queue

AUTOPLAY_BATCH_SIZE = 10
AUTOPLAY_REFETCH_THRESHOLD = 3
_autoplay_fetching = {}
PLAYED_HISTORY = {}

def get_language_query(lang: str, mood: str) -> list:
    """Get search queries based on language and mood"""
    queries = []
    
    # Language-based base queries
    if lang == "hindi":
        base_queries = ["latest hindi songs 2024", "bollywood hits", "hindi romantic songs"]
    elif lang == "punjabi":
        base_queries = ["latest punjabi songs 2024", "punjabi hits", "punjabi party songs"]
    elif lang == "english":
        base_queries = ["latest english songs 2024", "pop hits", "english top charts"]
    elif lang == "tamil":
        base_queries = ["latest tamil songs 2024", "kollywood hits", "tamil romantic songs"]
    elif lang == "telugu":
        base_queries = ["latest telugu songs 2024", "tollywood hits", "telugu romantic songs"]
    elif lang == "kannada":
        base_queries = ["latest kannada songs 2024", "sandalwood hits"]
    elif lang == "malayalam":
        base_queries = ["latest malayalam songs 2024", "mollywood hits"]
    elif lang == "bengali":
        base_queries = ["latest bengali songs 2024", "bengali hits"]
    elif lang == "marathi":
        base_queries = ["latest marathi songs 2024", "marathi hits"]
    elif lang == "gujarati":
        base_queries = ["latest gujarati songs 2024", "gujarati hits"]
    else:
        base_queries = ["latest songs 2024", "trending music"]
    
    # Mood-based additional queries
    if mood == "happy":
        mood_queries = ["happy songs", "party songs", "upbeat songs", "dance songs"]
    elif mood == "sad":
        mood_queries = ["sad songs", "heartbreak songs", "emotional songs", "sad romantic"]
    elif mood == "romantic":
        mood_queries = ["romantic songs", "love songs", "romantic hits"]
    elif mood == "workout":
        mood_queries = ["workout songs", "gym songs", "high energy songs", "motivational songs"]
    elif mood == "chill":
        mood_queries = ["chill songs", "relaxing music", "lofi songs", "acoustic songs"]
    elif mood == "bhajan":
        mood_queries = ["bhajan", "devotional songs", "spiritual songs", "bhakti geet", "aarti"]
    else:
        mood_queries = []
    
    # Combine base + mood queries
    queries = base_queries + mood_queries
    return queries

def extract_song_name(title: str) -> str:
    """Extract ONLY the song name, removing movie/album name"""
    if not title:
        return ""
    
    title = title.lower()
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    
    for sep in [' | ', ' - ', ' by ', ' from ', ' ft. ', ' feat. ']:
        if sep in title:
            title = title.split(sep)[0]
            break
    
    noise = {
        'official', 'video', 'audio', 'full', 'song', 'title', 'hd', 
        '4k', '8k', '1080p', '720p', 'new', 'latest', 'lyrics', 
        'lyrical', 'with', 'feat', 'featuring', 'ft', 'the', 'a', 'of'
    }
    
    words = title.split()
    words = [w for w in words if w not in noise]
    
    cleaned = ''.join(c for c in ' '.join(words) if c.isalnum() or c.isspace())
    cleaned = ' '.join(cleaned.split()).strip()
    
    return cleaned

def is_same_song(title1: str, title2: str) -> bool:
    """Check if two titles are the same song"""
    song1 = extract_song_name(title1)
    song2 = extract_song_name(title2)
    
    if not song1 or not song2:
        return False
    
    if song1 == song2:
        return True
    
    words1 = set(song1.split())
    words2 = set(song2.split())
    
    if not words1 or not words2:
        return False
    
    common = words1 & words2
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
    
    # Get language and mood
    lang = await get_autoplay_lang(chat_id)
    mood = await get_autoplay_mood(chat_id)
    
    # Determine if we should use related videos or language/mood search
    use_related = (lang == "auto" and mood == "any")
    
    LOGGER(__name__).info(f"[AutoPlay] Language: {lang}, Mood: {mood}, Use Related: {use_related}")
    
    # Initialize history
    if chat_id not in PLAYED_HISTORY:
        PLAYED_HISTORY[chat_id] = []
    
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

    try:
        candidates = []
        
        # Method 1: Get related streams from Piped API ONLY if language=auto AND mood=any
        if use_related and seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
            try:
                related_list = await YouTube.get_related_streams(seed_video_id)
                LOGGER(__name__).info(f"[AutoPlay] Got {len(related_list)} related from Piped")
                
                for rel in related_list:
                    rel_id = rel.get("id")
                    rel_title = rel.get("title", "")
                    rel_dur = rel.get("duration", 0)
                    
                    if not rel_id or rel_id in queued_vids:
                        continue
                    
                    if is_bad_song(rel_title, rel_dur):
                        continue
                    
                    is_duplicate = False
                    for played in history:
                        if played.get("vidid") == rel_id or is_same_song(played.get("title", ""), rel_title):
                            is_duplicate = True
                            break
                    
                    if is_duplicate:
                        continue
                    
                    candidates.append({
                        "id": rel_id,
                        "title": rel_title,
                        "duration": rel_dur
                    })
                    
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Related error: {e}")

        # Method 2: Search based on language and mood (ALWAYS run if not using related)
        search_queries = get_language_query(lang, mood)
        LOGGER(__name__).info(f"[AutoPlay] Search queries: {search_queries}")
        
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
                            "duration": 0
                        })
                        LOGGER(__name__).info(f"[AutoPlay] Found: {result.get('title', '')[:40]}")
                        
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Search error: {e}")

        LOGGER(__name__).info(f"[AutoPlay] Total candidates: {len(candidates)}")
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
                    "title": title
                })
                queued_vids.add(next_vidid)
                added += 1
                
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Queue error: {e}")

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
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
