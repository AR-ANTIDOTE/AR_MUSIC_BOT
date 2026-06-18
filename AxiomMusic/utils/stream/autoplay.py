import asyncio
import random
import re
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay, get_autoplay_lang, get_autoplay_mood, set_autoplay_lang, set_autoplay_mood
from AxiomMusic.utils.stream.queue import put_queue

AUTOPLAY_BATCH_SIZE = 5
AUTOPLAY_REFETCH_THRESHOLD = 2
_autoplay_fetching = {}
PLAYED_HISTORY = {}

# ==========================================
# AUTO-DETECTION FUNCTIONS
# ==========================================

def detect_language_from_title(title: str) -> str:
    """Detect language from song title"""
    if not title:
        return "auto"
    
    title_lower = title.lower()
    
    # Punjabi indicators
    punjabi_words = ['jatt', 'munde', 'kudi', 'guru', 'diljit', 'sidhu', 'apun', 'bhangra', 'punjabi']
    if any(word in title_lower for word in punjabi_words):
        return "punjabi"
    
    # Tamil indicators
    tamil_words = ['tamil', 'kollywood', 'ar rahman', 'anirudh', 'yuvan', 'harris']
    if any(word in title_lower for word in tamil_words):
        return "tamil"
    
    # Telugu indicators
    telugu_words = ['telugu', 'tollywood', 'thaman', 'dsp', 'ss thaman']
    if any(word in title_lower for word in telugu_words):
        return "telugu"
    
    # English indicators
    english_words = ['remix', 'feat', 'ft.', 'official video', 'lyric video', 'audio']
    if any(word in title_lower for word in english_words):
        # Check if it's actually English (no Hindi words)
        hindi_words = ['hai', 'hum', 'tum', 'dil', 'pyaar', 'ishq', 'mohabbat', 'sanam', 're']
        if not any(word in title_lower for word in hindi_words):
            return "english"
    
    # Default to Hindi for Indian songs
    return "hindi"

def detect_mood_from_title(title: str) -> str:
    """Detect mood from song title"""
    if not title:
        return "any"
    
    title_lower = title.lower()
    
    # Romantic indicators
    romantic_words = ['love', 'pyaar', 'ishq', 'mohabbat', 'romantic', 'dil', 'heart', 'sanam', 'humma']
    if any(word in title_lower for word in romantic_words):
        return "romantic"
    
    # Sad indicators
    sad_words = ['sad', 'dard', 'judaa', 'tanha', 'alone', 'broken', 'tears', 'rona', 'yaadein']
    if any(word in title_lower for word in sad_words):
        return "sad"
    
    # Happy/Party indicators
    happy_words = ['party', 'dance', 'nacho', 'bhangra', 'celebration', 'happy', 'item', 'swag']
    if any(word in title_lower for word in happy_words):
        return "happy"
    
    # Devotional indicators
    devotional_words = ['bhajan', 'aarti', 'stotram', 'mantra', 'shiv', 'krishna', 'ram', 'hanuman', 'devotional', 'stuti']
    if any(word in title_lower for word in devotional_words):
        return "bhajan"
    
    # Workout indicators
    workout_words = ['workout', 'gym', 'motivation', 'energy', 'power', 'beast']
    if any(word in title_lower for word in workout_words):
        return "workout"
    
    return "any"

def extract_artist_from_title(title: str) -> str:
    """Extract artist name from title"""
    if not title:
        return ""
    
    # Common patterns: "Song Name | Artist Name" or "Song Name - Artist Name"
    patterns = [
        r'\|\s*([^\|]+)$',  # After last |
        r'\s-\s([^-]+)$',   # After last -
        r'\sby\s+(.+)$',    # After "by"
        r'\sfeat\.\s+(.+)$', # After "feat."
        r'\sft\.\s+(.+)$',  # After "ft."
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            artist = match.group(1).strip()
            # Clean up artist name
            artist = re.sub(r'\(.*?\)', '', artist)
            artist = re.sub(r'\[.*?\]', '', artist)
            artist = artist.split('|')[0].strip()
            if len(artist) > 2 and len(artist) < 50:
                return artist
    
    return ""

# ==========================================
# SEARCH STRATEGY
# ==========================================

def build_search_queries(lang: str, mood: str, artist: str) -> list:
    """Build search queries based on language, mood, and artist"""
    queries = []
    
    # Layer 1: Artist-based (50% of songs)
    if artist and len(artist) > 2:
        if lang == "hindi":
            queries.extend([
                f"{artist} hindi songs",
                f"{artist} bollywood songs",
                f"{artist} latest songs",
            ])
        elif lang == "punjabi":
            queries.extend([
                f"{artist} punjabi songs",
                f"{artist} latest punjabi",
            ])
        elif lang == "english":
            queries.extend([
                f"{artist} songs",
                f"{artist} latest",
                f"{artist} hits",
            ])
        else:
            queries.extend([
                f"{artist} songs",
                f"{artist} latest",
            ])
    
    # Layer 2: Language + Mood (30% of songs)
    if lang == "hindi":
        if mood == "romantic":
            queries.extend(["arijit singh romantic", "hindi love songs 2024", "bollywood romantic"])
        elif mood == "sad":
            queries.extend(["hindi sad songs", "bollywood sad songs", "heartbreak songs hindi"])
        elif mood == "happy":
            queries.extend(["hindi party songs", "bollywood dance songs", "hindi happy songs"])
        elif mood == "bhajan":
            queries.extend(["hindi bhajan", "bhakti songs", "devotional hindi"])
        else:
            queries.extend(["latest hindi songs 2024", "bollywood hits", "hindi songs"])
    
    elif lang == "punjabi":
        if mood == "chill":
            queries.extend(["punjabi chill", "punjabi soft songs", "punjabi acoustic"])
        elif mood == "happy":
            queries.extend(["punjabi party songs", "punjabi dance", "bhangra songs"])
        else:
            queries.extend(["latest punjabi songs 2024", "punjabi hits", "punjabi songs"])
    
    elif lang == "english":
        if mood == "romantic":
            queries.extend(["english love songs", "romantic english songs", "english romantic hits"])
        elif mood == "sad":
            queries.extend(["english sad songs", "sad english songs", "heartbreak english"])
        elif mood == "happy":
            queries.extend(["english party songs", "upbeat english songs", "english dance"])
        else:
            queries.extend(["latest english songs 2024", "pop hits 2024", "english songs"])
    
    elif lang == "tamil":
        queries.extend(["latest tamil songs 2024", "kollywood hits", "tamil songs"])
    
    elif lang == "telugu":
        queries.extend(["latest telugu songs 2024", "tollywood hits", "telugu songs"])
    
    else:  # auto or unknown
        queries.extend(["latest songs 2024", "trending music", "popular songs"])
    
    # Layer 3: Mood-only fallback (15%)
    if mood == "romantic":
        queries.extend(["love songs", "romantic hits"])
    elif mood == "sad":
        queries.extend(["sad songs", "emotional songs"])
    elif mood == "happy":
        queries.extend(["happy songs", "party songs"])
    elif mood == "bhajan":
        queries.extend(["bhajan", "devotional songs"])
    
    # Layer 4: Generic fallback (5%)
    queries.extend(["trending songs 2024", "popular music"])
    
    return queries

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def extract_song_name(title: str) -> str:
    """Extract ONLY the song name"""
    if not title:
        return ""
    
    title = title.lower()
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    
    for sep in [' | ', ' - ', ' by ', ' from ', ' ft. ', ' feat. ']:
        if sep in title:
            title = title.split(sep)[0]
            break
    
    noise = {'official', 'video', 'audio', 'full', 'song', 'title', 'hd', '4k', '8k', 'new', 'latest', 'lyrics', 'lyrical'}
    words = [w for w in title.split() if w not in noise]
    cleaned = ''.join(c for c in ' '.join(words) if c.isalnum() or c.isspace())
    return ' '.join(cleaned.split()).strip()

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
    """Reject bad songs"""
    if not title:
        return True
    
    title_lower = title.lower()
    bad_words = ['jukebox', 'mashup', 'mix', 'album', 'compilation', 'playlist', 'full movie', 'medley', 'non stop', '1 hour']
    
    for word in bad_words:
        if word in title_lower:
            return True
    
    if duration_sec < 90 or duration_sec > 900:
        return True
    
    return False

# ==========================================
# FAST PARALLEL FETCHING
# ==========================================

async def fetch_song_from_query(query: str, history: list, queued_vids: set) -> dict:
    """Fetch a single song from a query"""
    try:
        result, vidid = await YouTube.track(query)
        
        if result and vidid and vidid not in queued_vids:
            # Check history
            for played in history:
                if played.get("vidid") == vidid or is_same_song(played.get("title", ""), result.get("title", "")):
                    return None
            
            if not is_bad_song(result.get("title", ""), 0):
                return {
                    "id": vidid,
                    "title": result.get("title"),
                    "duration": 0
                }
    except Exception as e:
        LOGGER(__name__).error(f"[AutoPlay] Fetch error for '{query}': {e}")
    
    return None

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
    
    # Auto-detect language, mood, artist from current song
    detected_lang = detect_language_from_title(seed_title)
    detected_mood = detect_mood_from_title(seed_title)
    detected_artist = extract_artist_from_title(seed_title)
    
    # Get user-set language and mood
    user_lang = await get_autoplay_lang(chat_id)
    user_mood = await get_autoplay_mood(chat_id)
    
    # Auto-set if user hasn't set explicitly
    if user_lang == "auto":
        lang = detected_lang
        await set_autoplay_lang(chat_id, lang)
        LOGGER(__name__).info(f"[AutoPlay] Auto-detected language: {lang}")
    else:
        lang = user_lang
    
    if user_mood == "any":
        mood = detected_mood
        await set_autoplay_mood(chat_id, mood)
        LOGGER(__name__).info(f"[AutoPlay] Auto-detected mood: {mood}")
    else:
        mood = user_mood
    
    LOGGER(__name__).info(f"[AutoPlay] Strategy - Lang: {lang}, Mood: {mood}, Artist: {detected_artist}")
    
    # Initialize history
    if chat_id not in PLAYED_HISTORY:
        PLAYED_HISTORY[chat_id] = []
    
    history = PLAYED_HISTORY[chat_id]
    
    # Add current song to history
    if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
        history.append({"vidid": seed_video_id, "title": seed_title})
    
    # Get current queue
    current_queue = db.get(chat_id, [])
    queued_vids = {item.get("vidid") for item in current_queue if item.get("vidid")}

    try:
        candidates = []
        
        # Build search queries
        search_queries = build_search_queries(lang, mood, detected_artist)
        LOGGER(__name__).info(f"[AutoPlay] Search queries: {search_queries[:5]}")
        
        # FAST PARALLEL FETCHING - Fetch multiple songs at once
        tasks = []
        for query in search_queries[:10]:  # Top 10 queries
            tasks.append(fetch_song_from_query(query, history, queued_vids))
        
        # Execute all fetches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict) and result:
                candidates.append(result)
                if len(candidates) >= limit * 2:
                    break
        
        LOGGER(__name__).info(f"[AutoPlay] Total candidates: {len(candidates)}")
        
        # If still not enough, try related videos as fallback
        if len(candidates) < 3 and seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
            try:
                related_list = await YouTube.get_related_streams(seed_video_id)
                LOGGER(__name__).info(f"[AutoPlay] Fallback: Got {len(related_list)} related")
                
                for rel in related_list[:5]:
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
                    
                    if not is_duplicate:
                        candidates.append({
                            "id": rel_id,
                            "title": rel_title,
                            "duration": rel_dur
                        })
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Related fallback error: {e}")
        
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
                
                history.append({"vidid": next_vidid, "title": title})
                queued_vids.add(next_vidid)
                added += 1
                
                LOGGER(__name__).info(f"[AutoPlay] ✓ ADDED: {title[:50]}")
                
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
        LOGGER(__name__).info(f"[AutoPlay] Trigger - Queue: {current_queue}/{AUTOPLAY_REFETCH_THRESHOLD}")
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
