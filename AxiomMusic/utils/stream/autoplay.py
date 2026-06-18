import asyncio
import random
import re
import config
from AxiomMusic import LOGGER, YouTube, app
from AxiomMusic.misc import db
from AxiomMusic.utils.database import is_autoplay, get_autoplay_lang, get_autoplay_mood, set_autoplay_lang, set_autoplay_mood
from AxiomMusic.utils.stream.queue import put_queue
from py_yt import VideosSearch

# ==========================================
# CONFIGURATION
# ==========================================
AUTOPLAY_BATCH_SIZE = 10
AUTOPLAY_REFETCH_THRESHOLD = 3
_autoplay_fetching = {}
PLAYED_HISTORY = {}
CHANNEL_INDEX = {}

# ==========================================
# SPECIAL UNICODE FONT CONVERTER (FIXED)
# ==========================================
def convert_to_special_font(text: str) -> str:
    font_map = {
        "a": "ᴧ",
        "b": "ʙ",
        "c": "ᴄ",
        "d": "ᴅ",
        "e": "є",
        "f": "ғ",
        "g": "ɢ",
        "h": "ʜ",
        "i": "ɪ",
        "j": "ᴊ",
        "k": "ᴋ",
        "l": "ʟ",
        "m": "ϻ",
        "n": "η",
        "o": "σ",
        "p": "ᴘ",
        "q": "ǫ",
        "r": "ꝛ",
        "s": "s",
        "t": "ᴛ",
        "u": "υ",
        "v": "ᴠ",
        "w": "ᴡ",
        "x": "x",
        "y": "ʏ",
        "z": "ᴢ",
        "A": "𝐀‌",
        "B": "𝐁‌",
        "C": "𝐂‌",
        "D": "𝐃‌",
        "E": "𝐄‌",
        "F": "𝐅‌",
        "G": "𝐆‌",
        "H": "𝐇‌",
        "I": "𝐈‌",
        "J": "𝐉‌",
        "K": "𝐊‌",
        "L": "𝐋‌",
        "M": "𝐌‌",
        "N": "𝐍‌",
        "O": "𝐎‌",
        "P": "𝐏‌",
        "Q": "𝐐‌",
        "R": "𝐑‌",
        "S": "𝐒‌",
        "T": "𝐓‌",
        "U": "𝐔‌",
        "V": "𝐕‌",
        "W": "𝐖‌",
        "X": "𝐗‌",
        "Y": "𝐘‌",
        "Z": "𝐙‌",
        "0": "𝟶",
        "1": "𝟷",
        "2": "𝟸",
        "3": "𝟹",
        "4": "𝟺",
        "5": "𝟻",
        "6": "𝟼",
        "7": "𝟽",
        "8": "𝟾",
        "9": "𝟿",
    }
    return ''.join([font_map.get(c, c) for c in text])

# ==========================================
# GLOBAL MUSIC DATABASE (20 Languages, 12 Moods)
# ==========================================
GLOBAL_MUSIC_DATABASE = {
    "hindi": {
        "romantic": ["Arijit Singh", "Shreya Ghoshal", "Jubin Nautiyal", "Armaan Malik", "T-Series"],
        "sad": ["Arijit Singh", "Jubin Nautiyal", "B Praak", "T-Series"],
        "happy": ["Neha Kakkar", "Tony Kakkar", "Mika Singh", "Badshah", "T-Series"],
        "party": ["Neha Kakkar", "Badshah", "Raftaar", "Yo Yo Honey Singh", "T-Series"],
        "chill": ["Anuv Jain", "Prateek Kuhad", "Ritviz", "T-Series Acoustic"],
        "workout": ["Badshah", "Raftaar", "Divine", "T-Series"],
        "bhajan": ["T-Series Bhakti Sagar", "Shemaroo Bhakti", "Gulshan Kumar"],
        "retro": ["Kishore Kumar", "Lata Mangeshkar", "Mohammed Rafi", "Asha Bhosle"],
        "rap": ["Divine", "Raftaar", "Badshah", "Emiway Bantai"],
        "acoustic": ["Anuv Jain", "Prateek Kuhad", "Ritviz"],
        "funk": [],
        "phonk": []
    },
    "english": {
        "romantic": ["Alan Walker", "Ed Sheeran", "Taylor Swift", "John Legend", "Sam Smith", "Shawn Mendes", "Adele"],
        "sad": ["Billie Eilish", "Lewis Capaldi", "Olivia Rodrigo", "Halsey", "The Weeknd"],
        "happy": ["Bruno Mars", "Pharrell Williams", "Justin Bieber", "Katy Perry", "Dua Lipa"],
        "party": ["David Guetta", "Calvin Harris", "Marshmello", "Martin Garrix", "The Chainsmokers"],
        "chill": ["Alan Walker", "Kygo", "Lofi Girl", "ChilledCow"],
        "workout": ["Eminem", "Imagine Dragons", "Post Malone", "Kanye West", "Travis Scott"],
        "bhajan": [],
        "retro": ["Michael Jackson", "Queen", "The Beatles", "Elton John", "Madonna"],
        "rap": ["Eminem", "Drake", "Kendrick Lamar", "Jay-Z", "Travis Scott"],
        "acoustic": ["Ed Sheeran", "John Mayer", "James Arthur", "Lewis Capaldi"],
        "funk": ["Bruno Mars", "Anderson .Paak", "Vulf", "Jamiroquai"],
        "phonk": ["Kordhell", "MoonDeity", "Dxrk", "Phonk Music"]
    },
    "punjabi": {
        "romantic": ["Guru Randhawa", "Diljit Dosanjh", "Hardy Sandhu", "Neha Kakkar"],
        "sad": ["Sidhu Moose Wala", "B Praak", "Jass Manak", "Karan Aujla"],
        "happy": ["Diljit Dosanjh", "Guru Randhawa", "Mankirt Aulakh", "Ninja"],
        "party": ["Badshah", "Raftaar", "Mika Singh", "Gippy Grewal"],
        "chill": ["AP Dhillon", "Shinda Kahlon", "Gurinder Gill"],
        "workout": ["Sidhu Moose Wala", "Karan Aujla", "Diljit Dosanjh"],
        "bhajan": ["Bhai Harjinder Singh", "Shemaroo Bhakti"],
        "retro": ["Gurdas Maan", "Surinder Kaur", "Mohammed Rafi"],
        "rap": ["Sidhu Moose Wala", "Karan Aujla", "Raftaar", "Divine"],
        "acoustic": ["AP Dhillon", "Shinda Kahlon"],
        "funk": [],
        "phonk": []
    },
    "brazilian": {
        "romantic": ["Anitta", "Luan Santana", "Gusttavo Lima"],
        "sad": ["Marília Mendonça", "Jorge & Mateus"],
        "happy": ["Anitta", "Luan Santana", "Wesley Safadão"],
        "party": ["MC Kevinho", "Anitta", "Alok", "Dennis DJ"],
        "chill": ["Bossa Nova Music", "Tom Jobim"],
        "workout": ["MC Kevinho", "Alok", "Brazilian Bass"],
        "bhajan": [],
        "retro": ["Tom Jobim", "Joao Gilberto", "Elis Regina"],
        "rap": ["Matuê", "Teto", "WIU", "Orochi"],
        "acoustic": ["Tom Jobim", "Joao Gilberto"],
        "funk": ["MC Kevinho", "MC Hariel", "KondZilla", "Matuê", "Funk Carioca"],
        "phonk": ["Brazilian Phonk", "Phonk Brasil", "Montagem"]
    },
    "russian": {
        "romantic": ["Zivert", "Artik & Asti"],
        "sad": ["Miyagi & Andy Panda", "JONY"],
        "happy": ["Zivert", "Artik & Asti", "Ivanushki International"],
        "party": ["Little Big", "Serebro", "DJ Smash"],
        "chill": ["Miyagi & Andy Panda", "JONY"],
        "workout": ["Phonk Russia", "Russian Bass"],
        "bhajan": [],
        "retro": ["Viktor Tsoi", "Kino", "Alla Pugacheva"],
        "rap": ["Basta", "Timati", "Oxxxymiron"],
        "acoustic": ["Miyagi & Andy Panda"],
        "funk": [],
        "phonk": ["Kordhell", "MoonDeity", "Russian Phonk", "Dxrk"]
    },
    "korean": {
        "romantic": ["HYBE LABELS", "SMTOWN", "JYP Entertainment", "BTS"],
        "sad": ["HYBE LABELS", "SMTOWN"],
        "happy": ["HYBE LABELS", "SMTOWN", "JYP Entertainment"],
        "party": ["HYBE LABELS", "SMTOWN", "YG Entertainment"],
        "chill": ["HYBE LABELS", "SMTOWN"],
        "workout": ["HYBE LABELS", "SMTOWN"],
        "bhajan": [],
        "retro": ["Seo Taiji and Boys"],
        "rap": ["HYBE LABELS", "YG Entertainment"],
        "acoustic": ["HYBE LABELS"],
        "funk": [],
        "phonk": []
    },
    "japanese": {
        "romantic": ["Sony Music Japan", "Avex", "King Records"],
        "sad": ["Sony Music Japan", "Avex"],
        "happy": ["Sony Music Japan", "Avex", "King Records"],
        "party": ["Sony Music Japan", "Avex"],
        "chill": ["Sony Music Japan", "Lofi Girl Japan"],
        "workout": ["Sony Music Japan"],
        "bhajan": [],
        "retro": ["City Pop Japan"],
        "rap": [],
        "acoustic": ["Sony Music Japan"],
        "funk": [],
        "phonk": []
    },
    "spanish": {
        "romantic": ["Sony Music Latin", "Universal Music Latino", "Shakira"],
        "sad": ["Sony Music Latin", "Universal Music Latino"],
        "happy": ["Sony Music Latin", "Universal Music Latino", "Bad Bunny", "J Balvin"],
        "party": ["Sony Music Latin", "Universal Music Latino", "Bad Bunny", "J Balvin"],
        "chill": ["Sony Music Latin"],
        "workout": ["Sony Music Latin", "Bad Bunny"],
        "bhajan": [],
        "retro": ["Selena", "Ricky Martin"],
        "rap": ["Bad Bunny", "J Balvin"],
        "acoustic": ["Sony Music Latin"],
        "funk": [],
        "phonk": []
    },
    "arabic": {
        "romantic": ["Rotana Music", "Mazzika", "Amr Diab"],
        "sad": ["Rotana Music", "Mazzika"],
        "happy": ["Rotana Music", "Mazzika", "Amr Diab"],
        "party": ["Rotana Music", "Mazzika"],
        "chill": ["Rotana Music"],
        "workout": [],
        "bhajan": [],
        "retro": ["Umm Kulthum", "Abdel Halim Hafez"],
        "rap": [],
        "acoustic": [],
        "funk": [],
        "phonk": []
    },
    "turkish": {
        "romantic": ["Netd Müzik", "DMC Music", "Tarkan"],
        "sad": ["Netd Müzik", "DMC Music"],
        "happy": ["Netd Müzik", "DMC Music", "Tarkan"],
        "party": ["Netd Müzik", "DMC Music"],
        "chill": ["Netd Müzik"],
        "workout": [],
        "bhajan": [],
        "retro": ["Baris Manco", "Sezen Aksu"],
        "rap": [],
        "acoustic": [],
        "funk": [],
        "phonk": []
    },
    "tamil": {
        "romantic": ["Sid Sriram", "Anirudh Ravichander", "AR Rahman", "Shreya Ghoshal"],
        "sad": ["Sid Sriram", "Anirudh Ravichander", "Yuvan Shankar Raja"],
        "happy": ["Anirudh Ravichander", "Yuvan Shankar Raja", "Harris Jayaraj"],
        "party": ["Anirudh Ravichander", "D Imman", "Harris Jayaraj"],
        "chill": ["Sid Sriram", "AR Rahman", "Pradeep Kumar"],
        "workout": ["Anirudh Ravichander", "D Imman"],
        "bhajan": ["T-Series Bhakti Tamil", "Shemaroo Bhakti"],
        "retro": ["SP Balasubrahmanyam", "KJ Yesudas", "S Janaki"],
        "rap": [],
        "acoustic": ["Sid Sriram", "Pradeep Kumar"],
        "funk": [],
        "phonk": []
    },
    "telugu": {
        "romantic": ["Sid Sriram", "Thaman S", "DSP", "Shreya Ghoshal"],
        "sad": ["Sid Sriram", "Thaman S", "MM Keeravani"],
        "happy": ["DSP", "Thaman S", "Devi Sri Prasad"],
        "party": ["DSP", "Thaman S", "Devi Sri Prasad"],
        "chill": ["Sid Sriram", "Thaman S"],
        "workout": ["DSP", "Thaman S"],
        "bhajan": ["T-Series Bhakti Telugu"],
        "retro": ["SP Balasubrahmanyam", "S Janaki"],
        "rap": [],
        "acoustic": ["Sid Sriram"],
        "funk": [],
        "phonk": []
    },
    "bengali": {
        "romantic": ["Arijit Singh", "Shreya Ghoshal", "Rupam Islam"],
        "sad": ["Arijit Singh", "Rupam Islam"],
        "happy": ["Rupam Islam", "Shreya Ghoshal"],
        "party": ["Rupam Islam"],
        "chill": ["Arijit Singh"],
        "workout": [],
        "bhajan": ["T-Series Bhakti Bengali"],
        "retro": ["Hemanta Mukherjee", "Sandhya Mukherjee"],
        "rap": [],
        "acoustic": ["Arijit Singh"],
        "funk": [],
        "phonk": []
    },
    "marathi": {
        "romantic": ["Ajay-Atul", "Sonu Nigam", "Shreya Ghoshal"],
        "sad": ["Ajay-Atul", "Sonu Nigam"],
        "happy": ["Ajay-Atul", "Shreya Ghoshal"],
        "party": ["Ajay-Atul"],
        "chill": ["Ajay-Atul"],
        "workout": [],
        "bhajan": ["T-Series Bhakti Marathi"],
        "retro": ["Lata Mangeshkar", "Asha Bhosle"],
        "rap": [],
        "acoustic": ["Ajay-Atul"],
        "funk": [],
        "phonk": []
    },
    "gujarati": {
        "romantic": ["T-Series Gujarati", "Gujarati Music"],
        "sad": ["T-Series Gujarati"],
        "happy": ["T-Series Gujarati", "Gujarati Music"],
        "party": ["T-Series Gujarati"],
        "chill": ["T-Series Gujarati"],
        "workout": [],
        "bhajan": ["T-Series Bhakti Gujarati"],
        "retro": [],
        "rap": [],
        "acoustic": [],
        "funk": [],
        "phonk": []
    },
    "bhojpuri": {
        "romantic": ["T-Series Bhojpuri", "Bhojpuri Music"],
        "sad": ["T-Series Bhojpuri"],
        "happy": ["T-Series Bhojpuri", "Bhojpuri Music"],
        "party": ["T-Series Bhojpuri", "Bhojpuri Music"],
        "chill": [],
        "workout": [],
        "bhajan": ["T-Series Bhakti Bhojpuri"],
        "retro": [],
        "rap": [],
        "acoustic": [],
        "funk": [],
        "phonk": []
    },
    "haryanvi": {
        "romantic": ["T-Series Haryanvi", "Haryanvi Hits"],
        "sad": ["T-Series Haryanvi"],
        "happy": ["T-Series Haryanvi", "Haryanvi Hits"],
        "party": ["T-Series Haryanvi", "Haryanvi Hits"],
        "chill": [],
        "workout": [],
        "bhajan": [],
        "retro": [],
        "rap": [],
        "acoustic": [],
        "funk": [],
        "phonk": []
    },
    "urdu": {
        "romantic": ["Coke Studio Pakistan", "Atif Aslam", "Ali Zafar"],
        "sad": ["Coke Studio Pakistan", "Atif Aslam"],
        "happy": ["Coke Studio Pakistan", "Ali Zafar"],
        "party": ["Coke Studio Pakistan"],
        "chill": ["Coke Studio Pakistan"],
        "workout": [],
        "bhajan": [],
        "retro": ["Nusrat Fateh Ali Khan", "Mehdi Hassan"],
        "rap": [],
        "acoustic": ["Coke Studio Pakistan"],
        "funk": [],
        "phonk": []
    },
    "french": {
        "romantic": ["NRJ Hits", "Skyrock", "Edith Piaf"],
        "sad": ["NRJ Hits", "Skyrock"],
        "happy": ["NRJ Hits", "Skyrock"],
        "party": ["NRJ Hits", "Skyrock"],
        "chill": ["NRJ Hits"],
        "workout": [],
        "bhajan": [],
        "retro": ["Edith Piaf", "Jacques Brel"],
        "rap": ["Skyrock"],
        "acoustic": [],
        "funk": [],
        "phonk": []
    },
    "chinese": {
        "romantic": ["Tencent Music", "Jay Chou", "Eason Chan"],
        "sad": ["Tencent Music", "Jay Chou"],
        "happy": ["Tencent Music", "Jay Chou"],
        "party": ["Tencent Music"],
        "chill": ["Tencent Music"],
        "workout": [],
        "bhajan": [],
        "retro": ["Teresa Teng"],
        "rap": [],
        "acoustic": ["Jay Chou"],
        "funk": [],
        "phonk": []
    }
}

# ==========================================
# CHANNEL VIDEO FETCHER (FIXED)
# ==========================================
async def fetch_channel_videos(channel_name: str, max_results: int = 20) -> list:
    try:
        search = VideosSearch(channel_name, limit=max_results)
        res = await search.next()
        
        results = []
        if not res or not res.get("result"):
            LOGGER(__name__).warning(f"[AutoPlay] No results for {channel_name}")
            return results
        
        for video in res["result"]:
            try:
                channel_info = video.get("channel", {})
                channel_title = channel_info.get("name", "").lower() if channel_info else ""
                
                # Filter to ensure it's from the correct channel/artist
                if channel_name.lower() not in ["t-series", "sony music", "zee music", "shemaroo", "rotana", "mazzika", "netd"]:
                    if channel_name.lower().split()[0] not in channel_title:
                        continue
                
                results.append({
                    "id": video.get("id"),
                    "title": video.get("title"),
                    "duration": video.get("duration"),
                    "channel": channel_title
                })
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Video parse error: {e}")
                continue
        
        return results
    except Exception as e:
        LOGGER(__name__).error(f"[AutoPlay] Channel fetch error for {channel_name}: {e}")
        return []

# ==========================================
# FILTER FUNCTIONS
# ==========================================
def filter_by_mood(videos: list, mood: str) -> list:
    if mood == "any" or not mood:
        return videos
    
    filtered = []
    mood_keywords = {
        "romantic": ['love', 'pyaar', 'ishq', 'mohabbat', 'romantic', 'dil', 'sanam', 'tera', 'meri', 'heart'],
        "sad": ['sad', 'dard', 'judaa', 'tanha', 'alone', 'broken', 'tears', 'heartbroken', 'cry'],
        "happy": ['party', 'dance', 'nacho', 'bhangra', 'celebration', 'happy', 'item', 'fun'],
        "party": ['party', 'club', 'dj', 'remix', 'dance', 'bass', 'rave'],
        "chill": ['chill', 'relax', 'lofi', 'acoustic', 'unplugged', 'soft', 'slow', 'ambient'],
        "workout": ['workout', 'gym', 'motivation', 'energy', 'power', 'beast', 'pump', 'fitness'],
        "bhajan": ['bhajan', 'aarti', 'stotram', 'mantra', 'shiv', 'krishna', 'ram', 'hanuman', 'devotional', 'god'],
        "retro": ['old', 'classic', 'vintage', '70s', '80s', '90s', 'retro'],
        "rap": ['rap', 'hip hop', 'freestyle', 'diss', 'flow', 'bars'],
        "acoustic": ['acoustic', 'unplugged', 'live acoustic', 'guitar', 'piano'],
        "funk": ['funk', 'carioca', 'baile', 'mc ', 'beat'],
        "phonk": ['phonk', 'drift', 'cowbell', 'brazilian phonk', 'russian phonk']
    }
    
    keywords = mood_keywords.get(mood, [])
    for video in videos:
        title = video.get("title", "").lower()
        if any(word in title for word in keywords):
            filtered.append(video)
    
    return filtered if filtered else videos

def filter_by_language(videos: list, lang: str) -> list:
    if lang == "auto" or not lang:
        return videos
    
    filtered = []
    lang_keywords = {
        "hindi": ['hindi', 'bollywood'],
        "punjabi": ['punjabi', 'jatt', 'munde', 'kudi', 'bhangra'],
        "english": ['english', 'pop', 'rock', 'hip hop'],
        "tamil": ['tamil', 'kollywood'],
        "telugu": ['telugu', 'tollywood'],
        "kannada": ['kannada', 'sandalwood'],
        "malayalam": ['malayalam', 'mollywood'],
        "bengali": ['bengali'],
        "marathi": ['marathi'],
        "gujarati": ['gujarati'],
        "bhojpuri": ['bhojpuri'],
        "haryanvi": ['haryanvi'],
        "urdu": ['urdu', 'pakistani'],
        "arabic": ['arabic'],
        "turkish": ['turkish'],
        "korean": ['korean', 'kpop'],
        "japanese": ['japanese', 'jpop', 'anime'],
        "spanish": ['spanish', 'latin'],
        "french": ['french'],
        "brazilian": ['brazilian', 'portuguese', 'funk carioca', 'sertanejo'],
        "russian": ['russian'],
        "chinese": ['chinese', 'mandopop']
    }
    
    keywords = lang_keywords.get(lang, [])
    for video in videos:
        title = video.get("title", "").lower()
        channel = video.get("channel", "").lower()
        
        if lang == "hindi":
            other_indian = ['punjabi', 'tamil', 'telugu', 'kannada', 'malayalam', 'bengali', 'marathi', 'gujarati', 'bhojpuri', 'haryanvi']
            if not any(word in title for word in other_indian) and not any(word in channel for word in other_indian):
                filtered.append(video)
        else:
            if any(word in title for word in keywords) or any(word in channel for word in keywords):
                filtered.append(video)
    
    return filtered if filtered else videos

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def extract_song_name(title: str) -> str:
    if not title: return ""
    title = title.lower()
    title = re.sub(r'\([^)]*\)', '', title)
    title = re.sub(r'\[[^\]]*\]', '', title)
    for sep in [' | ', ' - ', ' by ', ' from ', ' ft. ', ' feat. ']:
        if sep in title: title = title.split(sep)[0]
    noise = {'official', 'video', 'audio', 'full', 'song', 'title', 'hd', '4k', '8k', 'new', 'latest', 'lyrics', 'lyrical'}
    words = [w for w in title.split() if w not in noise]
    cleaned = ''.join(c for c in ' '.join(words) if c.isalnum() or c.isspace())
    return ' '.join(cleaned.split()).strip()

def is_same_song(title1: str, title2: str) -> bool:
    song1 = extract_song_name(title1)
    song2 = extract_song_name(title2)
    if not song1 or not song2: return False
    if song1 == song2: return True
    words1 = set(song1.split())
    words2 = set(song2.split())
    if not words1 or not words2: return False
    common = words1 & words2
    similarity = len(common) / min(len(words1), len(words2))
    return similarity >= 0.7

def is_bad_song(title: str, duration_sec: int) -> bool:
    if not title: return True
    title_lower = title.lower()
    bad_words = ['jukebox', 'mashup', 'mix', 'album', 'compilation', 'playlist', 'full movie', 'medley', 'non stop', '1 hour']
    for word in bad_words:
        if word in title_lower: return True
    if duration_sec < 90 or duration_sec > 900: return True
    return False

def duration_to_seconds(duration):
    if not duration:
        return 180

    if isinstance(duration, int):
        return duration

    try:
        parts = [int(x) for x in str(duration).split(":")]

        if len(parts) == 3:
            h, m, s = parts
            return h * 3600 + m * 60 + s

        if len(parts) == 2:
            m, s = parts
            return m * 60 + s

        if len(parts) == 1:
            return parts[0]

    except:
        pass

    return 180
    
# ==========================================
# MAIN AUTOPLAY FUNCTION (FIXED)
# ==========================================
# Replace the entire queue_autoplay_tracks function in AxiomMusic/utils/stream/autoplay.py

async def queue_autoplay_tracks(chat_id: int, seed_track: dict, limit: int = AUTOPLAY_BATCH_SIZE) -> int:
    if not seed_track or not await is_autoplay(chat_id): return 0
    if _autoplay_fetching.get(chat_id): return 0

    _autoplay_fetching[chat_id] = True
    added = 0
    original_chat_id = seed_track.get("chat_id", chat_id)
    requester_id = seed_track.get("user_id", 0)
    streamtype = seed_track.get("streamtype", "audio")
    seed_video_id = seed_track.get("vidid")
    seed_title = seed_track.get("title", "")
    
    lang = await get_autoplay_lang(chat_id)
    mood = await get_autoplay_mood(chat_id)
    if lang == "auto": lang = "hindi"
    if mood == "any": mood = "romantic"
    
    LOGGER(__name__).info(f"[AutoPlay] Lang: {lang}, Mood: {mood}")
    
    if chat_id not in PLAYED_HISTORY: PLAYED_HISTORY[chat_id] = []
    history = PLAYED_HISTORY[chat_id]
    if seed_video_id and seed_video_id not in ["telegram", "soundcloud"]:
        history.append({"vidid": seed_video_id, "title": seed_title})
    
    current_queue = db.get(chat_id, [])
    queued_vids = {item.get("vidid") for item in current_queue if item.get("vidid")}

    try:
        candidates = []
        channels = GLOBAL_MUSIC_DATABASE.get(lang, {}).get(mood, [])
        
        # Fallback to "any" mood if specific mood has no channels
        if not channels:
            channels = []
            for mood_list in GLOBAL_MUSIC_DATABASE.get(lang, {}).values():
                channels.extend(mood_list)
            LOGGER(__name__).info(f"[AutoPlay] No channels for {lang}/{mood}, using 'any' mood")
        
        # Fallback to Hindi if language has no channels
        if not channels:
            channels = GLOBAL_MUSIC_DATABASE.get("hindi", {}).get("any", [])
            LOGGER(__name__).info(f"[AutoPlay] No channels for {lang}, using Hindi")
        
        LOGGER(__name__).info(f"[AutoPlay] Using {len(channels)} channels: {channels[:3]}")
        
        for channel_name in channels:
            if len(candidates) >= limit * 2: break
            
            channel_key = f"{chat_id}_{channel_name}"
            start_index = CHANNEL_INDEX.get(channel_key, 0)
            
            videos = await fetch_channel_videos(channel_name, max_results=30)
            LOGGER(__name__).info(f"[AutoPlay] Channel {channel_name}: Got {len(videos)} videos")
            
            filtered_videos = filter_by_mood(videos, mood)
            filtered_videos = filter_by_language(filtered_videos, lang)
            LOGGER(__name__).info(f"[AutoPlay] After filter: {len(filtered_videos)} videos")
            
            # Add videos starting from index
            for i, video in enumerate(filtered_videos[start_index:], start=start_index):
                if len(candidates) >= limit * 2: break
                
                vid_id = video.get("id")
                vid_title = video.get("title")
                vid_duration = duration_to_seconds(video.get("duration"))
                
                if not vid_id:
                    LOGGER(__name__).warning(f"[AutoPlay] No video ID found")
                    continue
                
                if vid_id in queued_vids:
                    LOGGER(__name__).info(f"[AutoPlay] Already queued: {vid_id}")
                    continue
                
                is_duplicate = False
                for played in history:
                    if played.get("vidid") == vid_id:
                        is_duplicate = True
                        LOGGER(__name__).info(f"[AutoPlay] Duplicate vidid: {vid_id}")
                        break
                    if is_same_song(played.get("title", ""), vid_title):
                        is_duplicate = True
                        LOGGER(__name__).info(f"[AutoPlay] Duplicate song: {vid_title[:30]}")
                        break
                
                if is_duplicate:
                    continue
                
                # Check if bad song (skip duration check for now)
                if is_bad_song(vid_title, vid_duration if vid_duration else 180):
                    LOGGER(__name__).info(f"[AutoPlay] Bad song: {vid_title[:30]}")
                    continue
                
                candidates.append({
                    "id": vid_id,
                    "title": vid_title,
                    "duration": vid_duration
                })
                LOGGER(__name__).info(f"[AutoPlay] ✓ Candidate added: {vid_title[:50]}")
            
            CHANNEL_INDEX[channel_key] = start_index + len(filtered_videos)
        
        LOGGER(__name__).info(f"[AutoPlay] Total candidates before shuffle: {len(candidates)}")
        
        # Fallback: Search if not enough
        if len(candidates) < 3:
            LOGGER(__name__).info(f"[AutoPlay] Fallback to search (only {len(candidates)} candidates)")
            search_query = f"{lang} {mood} songs"
            try:
                result, vidid = await YouTube.track(search_query)
                if result and vidid and vidid not in queued_vids:
                    is_dup = False
                    for played in history:
                        if played.get("vidid") == vidid or is_same_song(played.get("title", ""), result.get("title", "")):
                            is_dup = True
                            break
                    if not is_dup and not is_bad_song(result.get("title", ""), 180):
                        candidates.append({
                            "id": vidid,
                            "title": result.get("title"),
                            "duration": 180
                        })
                        LOGGER(__name__).info(f"[AutoPlay] Fallback candidate: {result.get('title', '')[:50]}")
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Search error: {e}")
        
        if not candidates:
            LOGGER(__name__).error("[AutoPlay] NO CANDIDATES FOUND AT ALL!")
            return 0
        
        random.shuffle(candidates)

        # Add to queue
        for candidate in candidates:
            if added >= limit: break
            
            next_id = candidate.get("id")
            if not next_id or next_id in queued_vids: continue
            
            try:
                title, duration_min, duration_sec, _, next_vidid = await YouTube.details(next_id, videoid=True)
                if not title: title = candidate.get("title", "Unknown")
                if not duration_min: duration_min = "0:00"
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Details error: {e}")
                title = candidate.get("title", "Unknown")
                duration_min = "0:00"
                duration_sec = candidate.get("duration", 180)
                next_vidid = next_id
            
            if is_bad_song(title, duration_sec if duration_sec else 180):
                LOGGER(__name__).info(f"[AutoPlay] Final bad song check failed: {title[:30]}")
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
                    chat_id, original_chat_id, f"vid_{next_vidid}",
                    title, duration_min, "Autoplay", next_vidid,
                    requester_id, streamtype,
                )
                history.append({"vidid": next_vidid, "title": title})
                queued_vids.add(next_vidid)
                added += 1
                LOGGER(__name__).info(f"[AutoPlay] ✓✓✓ ADDED TO QUEUE: {title[:50]}")
            except Exception as e:
                LOGGER(__name__).error(f"[AutoPlay] Queue error: {e}")

        LOGGER(__name__).info(f"[AutoPlay] ✓✓✓ TOTAL ADDED: {added}")
        return added
    except Exception as e:
        LOGGER(__name__).error(f"[AutoPlay] Critical: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        _autoplay_fetching[chat_id] = False

async def maybe_refetch_autoplay(chat_id: int, seed_track: dict):
    if not seed_track: return
    current_queue = len(db.get(chat_id, []))
    if current_queue <= AUTOPLAY_REFETCH_THRESHOLD:
        LOGGER(__name__).info(f"[AutoPlay] Trigger - Queue: {current_queue}")
        asyncio.create_task(queue_autoplay_tracks(chat_id, seed_track))
