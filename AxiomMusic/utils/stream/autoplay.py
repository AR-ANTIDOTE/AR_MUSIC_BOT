import asyncio
import random
import re
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay, get_autoplay_lang, get_autoplay_mood, set_autoplay_lang, set_autoplay_mood
from AxiomMusic.utils.stream.queue import put_queue

# ==========================================
# CONFIGURATION
# ==========================================
AUTOPLAY_BATCH_SIZE = 20  # Kitne songs ek baar mein queue mein add kare
AUTOPLAY_REFETCH_THRESHOLD = 4  # Queue mein itne songs bache toh naye fetch kare
_autoplay_fetching = {}  # Track kare ki kaunsa chat fetch kar raha hai
PLAYED_HISTORY = {}  # Har chat ki played songs ki history

# ==========================================
# AUTO-DETECTION FUNCTIONS
# ==========================================

def detect_language_from_title(title: str) -> str:
    """
    Song title se language detect kare
    Returns: hindi, english, punjabi, tamil, telugu, kannada, malayalam, bengali, auto
    """
    if not title:
        return "auto"
    
    title_lower = title.lower()
    
    # Punjabi indicators (Punjabi words/artists)
    punjabi_indicators = [
        'cheema y', 'randhawa', 'jatt', 'munde', 'kudi', 'guru', 'diljit', 'sidhu', 'moosewala', 'apun', 'bhangra', 
        'punjabi', 'randha', 'maan', 'cheema', 'bhuller', 'gill', 'sandhu'
    ]
    if any(word in title_lower for word in punjabi_indicators):
        return "punjabi"
    
    # Tamil indicators (Tamil words/artists/industry)
    tamil_indicators = [
        'tamil', 'kollywood', 'ar rahman', 'anirudh', 'yuvan', 'harris', 
        'vijay', 'ajith', 'rajini', 'kamal', 'sivakarthikeyan'
    ]
    if any(word in title_lower for word in tamil_indicators):
        return "tamil"
    
    # Telugu indicators
    telugu_indicators = [
        'telugu', 'tollywood', 'thaman', 'dsp', 'ss thaman', 'mahesh', 
        'pawan', 'prabhas', 'allu', 'jr ntr'
    ]
    if any(word in title_lower for word in telugu_indicators):
        return "telugu"
    
    # Kannada indicators
    kannada_indicators = ['kannada', 'sandalwood', 'sudeep', 'yash', 'darshan']
    if any(word in title_lower for word in kannada_indicators):
        return "kannada"
    
    # Malayalam indicators
    malayalam_indicators = ['malayalam', 'mollywood', 'mohanlal', 'mammootty']
    if any(word in title_lower for word in malayalam_indicators):
        return "malayalam"
    
    # Bengali indicators
    bengali_indicators = ['bengali', 'tollywood bengali', 'jeet', 'dev']
    if any(word in title_lower for word in bengali_indicators):
        return "bengali"
    
    # English indicators (Western artists/genres)
    english_indicators = [
        'alan walker', 'dharia', 'justin', 'remix', 'feat', 'ft.', 'official video', 'lyric video', 'audio',
        'billboard', 'spotify', 'apple music', 'pop', 'rock', 'hip hop', 'rap'
    ]
    if any(word in title_lower for word in english_indicators):
        # Check if it's actually English (no Hindi words)
        hindi_words = ['hai', 'hum', 'tum', 'dil', 'pyaar', 'ishq', 'mohabbat', 'sanam', 're', 'tera', 'meri']
        if not any(word in title_lower for word in hindi_words):
            return "english"
    
    # Default to Hindi for Indian songs
    return "hindi"

def detect_mood_from_title(title: str) -> str:
    """
    Song title se mood detect kare
    Returns: romantic, sad, happy, workout, chill, bhajan, any
    """
    if not title:
        return "any"
    
    title_lower = title.lower()
    
    # Romantic indicators
    romantic_words = [
        'love', 'pyaar', 'ishq', 'mohabbat', 'romantic', 'dil', 'heart', 
        'sanam', 'humma', 'tera', 'meri', 'tu', 'main', 'hum', 'tum'
    ]
    if any(word in title_lower for word in romantic_words):
        return "romantic"
    
    # Sad indicators
    sad_words = [
        'heart boroken', 'arijit sad song', 'jubin sad song', 'ultra lofi sad song', 'sad', 'dard', 'judaa', 'tanha', 'alone', 'broken', 'tears', 'rona', 
        'yaadein', 'yaad', 'fakir', 'beparwah', 'adhura'
    ]
    if any(word in title_lower for word in sad_words):
        return "sad"
    
    # Happy/Party indicators
    happy_words = [
        'arijit happt mood songs', 'party', 'dance', 'nacho', 'bhangra', 'celebration', 'happy', 'item', 
        'swag', 'jashn', 'mubarak', 'badhai'
    ]
    if any(word in title_lower for word in happy_words):
        return "happy"
    
    # Devotional/Bhajan indicators
    devotional_words = [
        'bhajan', 'aarti', 'stotram', 'mantra', 'shiv', 'krishna', 'ram', 
        'hanuman', 'devotional', 'stuti', 'prayer', 'god', 'bhakti'
    ]
    if any(word in title_lower for word in devotional_words):
        return "bhajan"
    
    # Workout/High energy indicators
    workout_words = ['workout', 'gym', 'motivation', 'energy', 'power', 'beast', 'pump']
    if any(word in title_lower for word in workout_words):
        return "workout"
    
    # Chill/Relaxing indicators
    chill_words = ['chill', 'relax', 'lofi', 'acoustic', 'unplugged', 'soft', 'slow']
    if any(word in title_lower for word in chill_words):
        return "chill"
    
    return "any"

def extract_artist_from_title(title: str) -> str:
    """
    Song title se artist name extract kare
    Patterns: "Song | Artist", "Song - Artist", "Song by Artist", "Song feat. Artist"
    """
    if not title:
        return ""
    
    # Common patterns for artist name
    patterns = [
        r'\|\s*([^\|]+)$',      # After last |
        r'\s-\s([^-]+)$',       # After last -
        r'\sby\s+(.+)$',        # After "by"
        r'\sfeat\.\s+(.+)$',    # After "feat."
        r'\sft\.\s+(.+)$',      # After "ft."
    ]
    
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            artist = match.group(1).strip()
            # Clean up artist name (remove brackets, extra info)
            artist = re.sub(r'\(.*?\)', '', artist)
            artist = re.sub(r'\[.*?\]', '', artist)
            artist = artist.split('|')[0].strip()
            # Remove common suffixes
            artist = re.sub(r'\s*(official|video|audio|lyrics|hd|4k).*$', '', artist, flags=re.IGNORECASE)
            artist = artist.strip()
            
            # Validate artist name (should be reasonable length)
            if len(artist) > 2 and len(artist) < 50:
                return artist
    
    return ""

# ==========================================
# SEARCH STRATEGY BUILDER
# ==========================================

def build_search_queries(lang: str, mood: str, artist: str) -> list:
    """
    Language, mood, aur artist ke basis pe search queries banaye
    Returns list of search queries (priority order mein)
    """
    queries = []
    
    # ==========================================
    # LAYER 1: ARTIST-BASED (50% priority)
    # ==========================================
    if artist and len(artist) > 2:
        # Artist ke songs with language filter
        if lang == "hindi":
            queries.extend([
                f"{artist} hindi songs",
                f"{artist} bollywood songs",
                f"{artist} latest songs",
                f"{artist} romantic songs",
                f"{artist} hits",
            ])
        elif lang == "punjabi":
            queries.extend([
                f"{artist} punjabi songs",
                f"{artist} latest punjabi",
                f"{artist} punjabi hits",
            ])
        elif lang == "english":
            queries.extend([
                f"{artist} songs",
                f"{artist} latest",
                f"{artist} hits",
                f"{artist} best songs",
            ])
        elif lang == "tamil":
            queries.extend([
                f"{artist} tamil songs",
                f"{artist} kollywood songs",
            ])
        elif lang == "telugu":
            queries.extend([
                f"{artist} telugu songs",
                f"{artist} tollywood songs",
            ])
        else:
            queries.extend([
                f"{artist} songs",
                f"{artist} latest",
            ])
    
    # ==========================================
    # LAYER 2: LANGUAGE + MOOD (30% priority)
    # ==========================================
    if lang == "hindi":
        if mood == "romantic":
            queries.extend([
                "arijit singh romantic",
                "hindi love songs 2024",
                "bollywood romantic songs",
                "hindi romantic hits",
                "new hindi love songs",
            ])
        elif mood == "sad":
            queries.extend([
                "hindi sad songs",
                "bollywood sad songs",
                "heartbreak songs hindi",
                "emotional hindi songs",
                "sad bollywood hits",
            ])
        elif mood == "happy":
            queries.extend([
                "hindi party songs",
                "bollywood dance songs",
                "hindi happy songs",
                "party bollywood hits",
                "dance numbers hindi",
            ])
        elif mood == "bhajan":
            queries.extend([
                "hindi bhajan",
                "bhakti songs hindi",
                "devotional hindi songs",
                "aarti sangrah",
                "shiv bhajan",
                "krishna bhajan",
            ])
        elif mood == "workout":
            queries.extend([
                "hindi workout songs",
                "bollywood gym songs",
                "hindi motivation songs",
                "high energy bollywood",
            ])
        elif mood == "chill":
            queries.extend([
                "hindi chill songs",
                "bollywood acoustic",
                "hindi lofi songs",
                "soft bollywood songs",
            ])
        else:  # any mood
            queries.extend([
                "latest hindi songs 2024",
                "bollywood hits 2024",
                "new hindi songs",
                "trending bollywood",
                "hindi chartbusters",
            ])
    
    elif lang == "punjabi":
        if mood == "chill":
            queries.extend([
                "punjabi chill songs",
                "punjabi soft songs",
                "punjabi acoustic",
                "punjabi lofi",
            ])
        elif mood == "happy":
            queries.extend([
                "punjabi party songs",
                "punjabi dance songs",
                "bhangra songs",
                "punjabi hits party",
            ])
        elif mood == "romantic":
            queries.extend([
                "punjabi romantic songs",
                "punjabi love songs",
                "punjabi sad romantic",
            ])
        else:
            queries.extend([
                "latest punjabi songs 2024",
                "punjabi hits 2024",
                "new punjabi songs",
                "trending punjabi",
            ])
    
    elif lang == "english":
        if mood == "romantic":
            queries.extend([
                "english love songs",
                "romantic english songs",
                "english romantic hits",
                "love ballads english",
            ])
        elif mood == "sad":
            queries.extend([
                "english sad songs",
                "sad english songs",
                "heartbreak english songs",
                "emotional english songs",
            ])
        elif mood == "happy":
            queries.extend([
                "english party songs",
                "upbeat english songs",
                "english dance songs",
                "happy english songs",
            ])
        elif mood == "workout":
            queries.extend([
                "english workout songs",
                "gym music english",
                "high energy english",
                "motivation english songs",
            ])
        else:
            queries.extend([
                "latest english songs 2024",
                "pop hits 2024",
                "english chartbusters",
                "trending english songs",
            ])
    
    elif lang == "tamil":
        if mood == "romantic":
            queries.extend(["tamil romantic songs", "kollywood love songs"])
        elif mood == "sad":
            queries.extend(["tamil sad songs", "kollywood emotional"])
        else:
            queries.extend([
                "latest tamil songs 2024",
                "kollywood hits 2024",
                "new tamil songs",
                "tamil chartbusters",
            ])
    
    elif lang == "telugu":
        if mood == "romantic":
            queries.extend(["telugu romantic songs", "tollywood love songs"])
        elif mood == "sad":
            queries.extend(["telugu sad songs", "tollywood emotional"])
        else:
            queries.extend([
                "latest telugu songs 2024",
                "tollywood hits 2024",
                "new telugu songs",
                "telugu chartbusters",
            ])
    
    else:  # auto or unknown language
        queries.extend([
            "latest songs 2024",
            "trending music 2024",
            "popular songs",
            "top hits 2024",
        ])
    
    # ==========================================
    # LAYER 3: MOOD-ONLY FALLBACK (15% priority)
    # ==========================================
    if mood == "romantic":
        queries.extend(["love songs 2024", "romantic hits"])
    elif mood == "sad":
        queries.extend(["sad songs 2024", "emotional songs"])
    elif mood == "happy":
        queries.extend(["happy songs 2024", "party songs"])
    elif mood == "bhajan":
        queries.extend(["bhajan 2024", "devotional songs"])
    elif mood == "workout":
        queries.extend(["workout music", "gym songs"])
    elif mood == "chill":
        queries.extend(["chill music", "relaxing songs"])
    
    # ==========================================
    # LAYER 4: GENERIC FALLBACK (5% priority)
    # ==========================================
    queries.extend([
        "trending songs 2024",
        "popular music 2024",
        "top hits",
    ])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_queries = []
    for q in queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)
    
    return unique_queries

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def extract_song_name(title: str) -> str:
    """
    Title se sirf song name extract kare (movie/album name hatake)
    Example: "Sanam Re Title Song | Pulkit Samrat" -> "sanam re"
    """
    if not title:
        return ""
    
    title = title.lower()
    
    # Remove brackets and content
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    
    # Split by common separators and take first part
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
    Check kare ki do titles same song hain ya nahi
    Returns True agar 70% words match karein
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
    """
    Check kare ki song bad hai ya nahi (jukebox, mashup, etc.)
    Returns True agar song reject karna chahiye
    """
    if not title:
        return True
    
    title_lower = title.lower()
    
    # Bad keywords
    bad_words = [
        'jukebox', 'mashup', 'mix', 'album', 'compilation', 
        'playlist', 'full movie', 'medley', 'collection', 
        'non stop', '1 hour', '60 min', 'all songs'
    ]
    
    for word in bad_words:
        if word in title_lower:
            return True
    
    # Duration check: 1.5 min to 15 min
    if duration_sec < 90 or duration_sec > 900:
        return True
    
    return False

# ==========================================
# FAST PARALLEL FETCHING
# ==========================================

async def fetch_song_from_query(query: str, history: list, queued_vids: set) -> dict:
    """
    Ek query se ek song fetch kare
    Returns song dict ya None
    """
    try:
        result, vidid = await YouTube.track(query)
        
        if result and vidid and vidid not in queued_vids:
            # Check history for duplicates
            for played in history:
                if played.get("vidid") == vidid:
                    return None
                if is_same_song(played.get("title", ""), result.get("title", "")):
                    return None
            
            # Check if song is bad
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
    """
    Main function: Autoplay songs fetch karke queue mein add kare
    Returns: Kitne songs add kiye
    """
    # Validation checks
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
    
    # ==========================================
    # AUTO-DETECTION
    # ==========================================
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
        LOGGER(__name__).info(f"[AutoPlay] Auto-detected language: {lang} (from: {seed_title[:40]})")
    else:
        lang = user_lang
    
    if user_mood == "any":
        mood = detected_mood
        await set_autoplay_mood(chat_id, mood)
        LOGGER(__name__).info(f"[AutoPlay] Auto-detected mood: {mood} (from: {seed_title[:40]})")
    else:
        mood = user_mood
    
    LOGGER(__name__).info(f"[AutoPlay] Strategy - Lang: {lang}, Mood: {mood}, Artist: {detected_artist}")
    
    # ==========================================
    # INITIALIZE HISTORY
    # ==========================================
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
        
        # ==========================================
        # BUILD SEARCH QUERIES
        # ==========================================
        search_queries = build_search_queries(lang, mood, detected_artist)
        LOGGER(__name__).info(f"[AutoPlay] Search queries: {search_queries[:5]}")
        
        # ==========================================
        # FAST PARALLEL FETCHING
        # ==========================================
        # Top 10 queries ko parallel fetch kare
        tasks = []
        for query in search_queries[:10]:
            tasks.append(fetch_song_from_query(query, history, queued_vids))
        
        # Execute all fetches in parallel (bahut fast)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect successful results
        for result in results:
            if isinstance(result, dict) and result:
                candidates.append(result)
                if len(candidates) >= limit * 2:
                    break
        
        LOGGER(__name__).info(f"[AutoPlay] Found {len(candidates)} candidates from search")
        
        # ==========================================
        # FALLBACK: RELATED VIDEOS
        # ==========================================
        # Agar search se kam songs mile toh related videos try kare
        if len(candidates) < 3 and seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
            try:
                related_list = await YouTube.get_related_streams(seed_video_id)
                LOGGER(__name__).info(f"[AutoPlay] Fallback: Got {len(related_list)} related videos")
                
                for rel in related_list[:5]:
                    rel_id = rel.get("id")
                    rel_title = rel.get("title", "")
                    rel_dur = rel.get("duration", 0)
                    
                    if not rel_id or rel_id in queued_vids:
                        continue
                    
                    if is_bad_song(rel_title, rel_dur):
                        continue
                    
                    # Check history
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
        
        LOGGER(__name__).info(f"[AutoPlay] Total candidates: {len(candidates)}")
        
        # Shuffle for variety
        random.shuffle(candidates)

        # ==========================================
        # ADD TO QUEUE
        # ==========================================
        for candidate in candidates:
            if added >= limit:
                break
                
            next_id = candidate.get("id")
            if not next_id or next_id in queued_vids:
                continue
            
            # Get full details
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
            
            # Final validation
            if is_bad_song(title, duration_sec):
                continue
            
            # Check history one more time
            is_dup = False
            for played in history:
                if is_same_song(played.get("title", ""), title):
                    is_dup = True
                    break
            
            if is_dup:
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
                history.append({"vidid": next_vidid, "title": title})
                queued_vids.add(next_vidid)
                added += 1
                
                LOGGER(__name__).info(f"[AutoPlay] ✓ ADDED: {title[:50]}")
                
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Queue error: {e}")

        LOGGER(__name__).info(f"[AutoPlay] Total added: {added}")
        return added
        
    except Exception as e:
        LOGGER(__name__).error(f"[AutoPlay] Critical error: {e}")
        return 0
    finally:
        _autoplay_fetching[chat_id] = False

async def maybe_refetch_autoplay(chat_id: int, seed_track: dict):
    """
    Check kare ki queue mein kam songs hain toh naye fetch kare
    """
    if not seed_track:
        return
        
    current_queue = len(db.get(chat_id, []))
    
    if current_queue <= AUTOPLAY_REFETCH_THRESHOLD:
        LOGGER(__name__).info(f"[AutoPlay] Trigger - Queue: {current_queue}/{AUTOPLAY_REFETCH_THRESHOLD}")
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
