import os
import re
import aiofiles
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from AxiomMusic import app

# ══════════════════════════════════════════════════════════════════
#  CACHE
# ══════════════════════════════════════════════════════════════════
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
#  CANVAS
# ══════════════════════════════════════════════════════════════════
W, H = 1280, 720

# ══════════════════════════════════════════════════════════════════
#  COLORS — pixel-scanned from reference image
# ══════════════════════════════════════════════════════════════════
BG_TOP         = ( 18,  27,  34)   # top-left background
BG_BOT         = ( 28,  37,  46)   # bottom background
TEXT_WHITE     = (254, 254, 254)   # song title color
ARTIST_GREY    = (212, 212, 212)   # artist name (slightly grey-white)
PLAYING_GREY   = (131, 138, 146)   # "Playing" label
DURATION_GREY  = (179, 180, 182)   # "Duration: …" text
BRAND_GREY     = (160, 165, 171)   # "Powered by …" text
CARD_BG        = (  0,   4,   6)   # card fill when no art

# ══════════════════════════════════════════════════════════════════
#  CARD GEOMETRY — pixel-scanned (1920x1080 source → 1280x720 output)
#  Source: left=180, right=828, top=220, bottom=898
#  Scale:  1280/1920 = 0.6667,  720/1080 = 0.6667
# ══════════════════════════════════════════════════════════════════
CARD_X   = 120   # 180  × 0.6667
CARD_Y   = 146   # 220  × 0.6667
CARD_R   = 552   # 828  × 0.6667
CARD_B   = 598   # 898  × 0.6667
CARD_RAD =  20   # rounded corner radius

# ══════════════════════════════════════════════════════════════════
#  TEXT POSITIONS — pixel-scanned from source, scaled to 1280x720
#  Playing: source y=347, x=905
#  Title:   source y=451, x=905
#  Artist:  source y=588, x=905
#  Duration:source y=667, x=905
#  Brand:   source y=971 / 1010, x=1626
# ══════════════════════════════════════════════════════════════════
TX        = 603   # 905 × 0.6667 — shared left x for all text
TY_LABEL  = 231   # "Playing" top
TY_TITLE  = 300   # Song title top
TY_ARTIST = 392   # Artist name top
TY_DUR    = 444   # Duration top
BRAND_Y1  = 647   # "Powered" line top
BRAND_Y2  = 673   # "by <name>" line top

# ══════════════════════════════════════════════════════════════════
#  FONT SIZES — derived from pixel heights in reference
#  Playing: rendered h=36px → ~32pt
#  Title:   rendered h=66px → ~62pt
#  Artist:  rendered h=24px → ~44pt (bold renders larger)
#  Duration:rendered h=24px → ~28pt
# ══════════════════════════════════════════════════════════════════
SZ_PLAYING  = 32
SZ_TITLE    = 62
SZ_ARTIST   = 44
SZ_DURATION = 28
SZ_BRAND    = 22

# ══════════════════════════════════════════════════════════════════
#  WAVE — bottom-right lighter bump
#  BG_BOT first appears at y=530 on right, y=556 on left
#  Large ellipse: bounding box tuned to match this curve
# ══════════════════════════════════════════════════════════════════
WAVE_ELLIPSE = (150, 420, 1380, 820)   # (x0,y0,x1,y1) bounding box


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────
def _trim(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    try:
        if font.getlength(text) <= max_w:
            return text
        for i in range(len(text) - 1, 0, -1):
            t = text[:i] + "…"
            if font.getlength(t) <= max_w:
                return t
    except Exception:
        pass
    return text[:12] + "…"


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


# ═══════════════════════════════════════════════════════════════════
#  CORE RENDERER
# ═══════════════════════════════════════════════════════════════════
async def get_thumb(videoid: str, player_username: str = None):
    if player_username is None:
        player_username = app.username

    cache_path = os.path.join(CACHE_DIR, f"{videoid}_thumb.png")
    if os.path.exists(cache_path):
        return cache_path

    # Fetch YouTube metadata
    try:
        results = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        search = await results.next()   # ✅ await allowed now

        data = search.get("result", [])[0]

        title = re.sub(r"\W+", " ", data.get("title", "Unknown")).strip().title()
        thumb_url = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        duration = data.get("duration")
        channel = data.get("channel", {}).get("name", "YouTube")

    except Exception:
        title, thumb_url, duration, channel = "Unknown", YOUTUBE_IMG_URL, None, "YouTube"

    is_live = not duration or str(duration).lower() in {"live", "live now", ""}
    duration_text = "LIVE" if is_live else (duration or "Unknown")

    # Download thumbnail
    raw_path = os.path.join(CACHE_DIR, f"raw_{videoid}.jpg")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(raw_path, "wb") as f:
                        await f.write(await resp.read())
                else:
                    return YOUTUBE_IMG_URL
    except Exception:
        return YOUTUBE_IMG_URL

    # Render thumbnail
    try:
        result = _make_thumb(raw_path, title, channel, duration_text, player_username, cache_path)
    except Exception:
        result = YOUTUBE_IMG_URL

    try:
        os.remove(raw_path)
    except Exception:
        pass

    return result
