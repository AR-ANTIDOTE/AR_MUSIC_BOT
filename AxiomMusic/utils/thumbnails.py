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
def _make_thumb(
    raw_path:        str,
    title:           str,
    channel:         str,
    duration_text:   str,
    player_username: str,
    cache_path:      str,
) -> str:

    REG  = "AxiomMusic/assets/font.ttf"
    BOLD = "AxiomMusic/assets/font2.ttf"

    # ── 1. GRADIENT BACKGROUND ───────────────────────────────────
    # Exact two-tone: BG_TOP at top → BG_BOT at bottom
    bg   = Image.new("RGBA", (W, H))
    draw = ImageDraw.Draw(bg)
    for y in range(H):
        t = y / (H - 1)
        r = int(BG_TOP[0] + (BG_BOT[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOT[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOT[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b, 255))

    # ── 2. WAVE — bottom bump (BG_BOT ellipse, soft edges) ───────
    # In reference: BG_BOT color forms a smooth elliptical bump
    # rising from y≈530 right-side to y≈556 left-side
    wave = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(wave).ellipse(WAVE_ELLIPSE, fill=(*BG_BOT, 255))
    bg.alpha_composite(wave.filter(ImageFilter.GaussianBlur(32)))
    draw = ImageDraw.Draw(bg)

    # ── 3. FONTS ─────────────────────────────────────────────────
    f_label   = _font(REG,  SZ_PLAYING)
    f_title   = _font(BOLD, SZ_TITLE)
    f_artist  = _font(BOLD, SZ_ARTIST)
    f_dur     = _font(REG,  SZ_DURATION)
    f_brand   = _font(BOLD, SZ_BRAND)

    MAX_W = W - TX - 40  # max text width before ellipsis

    # ── 4. TEXT: "Playing" label ──────────────────────────────────
    draw.text((TX, TY_LABEL), "Playing", fill=PLAYING_GREY, font=f_label)

    # ── 5. TEXT: Song title (large bold white) ────────────────────
    draw.text((TX, TY_TITLE), _trim(title, f_title, MAX_W),
              fill=TEXT_WHITE, font=f_title)

    # ── 6. TEXT: Artist / Channel (medium bold, slightly grey-white)
    draw.text((TX, TY_ARTIST), _trim(channel, f_artist, MAX_W),
              fill=ARTIST_GREY, font=f_artist)

    # ── 7. TEXT: Duration ─────────────────────────────────────────
    draw.text((TX, TY_DUR), f"Duration: {duration_text}",
              fill=DURATION_GREY, font=f_dur)

    # ── 8. TEXT: "Powered by Maanav" — bottom right, right-aligned ─
    line1 = "© @AxiomBots"
    line2 = f"AxiomMusic"
    l1w   = int(f_brand.getlength(line1))
    l2w   = int(f_brand.getlength(line2))
    mbw   = max(l1w, l2w)
    bx    = W - mbw - 48          # right margin = 48px
    draw.text((bx + (mbw - l1w), BRAND_Y1), line1, fill=BRAND_GREY, font=f_brand)
    draw.text((bx + (mbw - l2w), BRAND_Y2), line2, fill=BRAND_GREY, font=f_brand)

    # ── 9. CARD SHADOW ────────────────────────────────────────────
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (CARD_X + 10, CARD_Y + 10, CARD_R + 10, CARD_B + 10),
        radius=CARD_RAD, fill=(0, 0, 0, 150),
    )
    bg.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))
    draw = ImageDraw.Draw(bg)

    # ── 10. CARD BACKGROUND ───────────────────────────────────────
    draw.rounded_rectangle(
        (CARD_X, CARD_Y, CARD_R, CARD_B),
        radius=CARD_RAD, fill=(*CARD_BG, 255),
    )

    # ── 11. ALBUM ART inside card ─────────────────────────────────
    try:
        art_w = CARD_R - CARD_X   # 432px
        art_h = CARD_B - CARD_Y   # 452px
        art   = Image.open(raw_path).convert("RGB").resize(
            (art_w, art_h), Image.LANCZOS
        )
        mask = Image.new("L", (art_w, art_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, art_w - 1, art_h - 1), radius=CARD_RAD, fill=255,
        )
        bg.paste(art, (CARD_X, CARD_Y), mask)
    except Exception:
        pass   # card BG already drawn

    # ── 12. SAVE ──────────────────────────────────────────────────
    bg.convert("RGB").save(cache_path, "PNG")
    return cache_path


# ═══════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════
async def get_thumb(videoid: str, player_username: str = None) -> str:
    if player_username is None:
        player_username = app.username

    cache_path = os.path.join(CACHE_DIR, f"{videoid}_thumb.png")
    if os.path.exists(cache_path):
        return cache_path

    # Fetch YouTube metadata
    try:
        results   = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        search    = await results.next()
        data      = search.get("result", [])[0]
        title     = re.sub(r"\W+", " ", data.get("title", "Unknown")).strip().title()
        thumb_url = data.get("thumbnails", [{}])[0].get("url", YOUTUBE_IMG_URL)
        duration  = data.get("duration")
        channel   = data.get("channel", {}).get("name", "YouTube")
    except Exception:
        title, thumb_url, duration, channel = "Unknown", YOUTUBE_IMG_URL, None, "YouTube"

    is_live       = not duration or str(duration).lower() in {"live", "live now", ""}
    duration_text = "LIVE" if is_live else (duration or "Unknown")

    # Download art
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

    # Render
    try:
        result = _make_thumb(raw_path, title, channel, duration_text, player_username, cache_path)
    except Exception:
        result = YOUTUBE_IMG_URL

    try:
        os.remove(raw_path)
    except Exception:
        pass

    return result
