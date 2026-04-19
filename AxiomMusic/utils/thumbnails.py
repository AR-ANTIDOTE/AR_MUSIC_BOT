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
def _make_thumb(raw_path, title, channel, duration_text, player_username, cache_path):

    from PIL import Image, ImageDraw, ImageFilter

    W, H = 1280, 720

    REG  = "AxiomMusic/assets/font.ttf"
    BOLD = "AxiomMusic/assets/font2.ttf"

    f_title = _font(BOLD, 28)
    f_small = _font(REG, 22)
    f_tiny  = _font(REG, 18)

    # ───────── BACKGROUND (REAL FIX) ─────────
    bg = Image.open(raw_path).convert("RGB").resize((W, H))
    bg = bg.filter(ImageFilter.GaussianBlur(60))

    overlay = Image.new("RGBA", (W, H), (0,0,0,160))
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(bg)

    # ───────── WAVES (MATCH STYLE) ─────────
    wave = Image.new("RGBA", (W, H), (0,0,0,0))
    wd = ImageDraw.Draw(wave)

    for i in range(5):
        wd.ellipse((900-100*i, 150-100*i, 900+100*i, 150+100*i),
                   outline=(255,255,255,80), width=4)

        wd.ellipse((300-100*i, 600-100*i, 300+100*i, 600+100*i),
                   outline=(255,255,255,60), width=4)

    bg = Image.alpha_composite(bg, wave)

    # ───────── MAIN CARD (FIXED POSITION) ─────────
    cx, cy = 440, 140
    CARD_W, CARD_H = 400, 420

    # shadow
    shadow = Image.new("RGBA", (W, H), (0,0,0,0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (cx+10, cy+10, cx+CARD_W+10, cy+CARD_H+10),
        radius=40,
        fill=(0,0,0,200)
    )
    bg = Image.alpha_composite(bg, shadow.filter(ImageFilter.GaussianBlur(25)))

    # card
    card = Image.new("RGBA", (CARD_W, CARD_H), (235,235,235,255))
    mask = Image.new("L", (CARD_W, CARD_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0,0,CARD_W,CARD_H), radius=40, fill=255)
    bg.paste(card, (cx, cy), mask)

    # ───────── ALBUM IMAGE (CORRECT SIZE) ─────────
    art = Image.open(raw_path).convert("RGB").resize((240,240))
    m = Image.new("L", (240,240), 0)
    ImageDraw.Draw(m).rounded_rectangle((0,0,240,240), radius=30, fill=255)
    bg.paste(art, (cx+30, cy+30), m)

    draw = ImageDraw.Draw(bg)

    # ───────── MUSIC ICON ─────────
    draw.ellipse((cx-20, cy-30, cx+40, cy+30), fill=(80,80,80))
    draw.text((cx-5, cy-15), "♪", fill="white", font=f_small)

    # ───────── PILLS (FIXED ALIGNMENT) ─────────
    def pill(x, y, text):
        pad = 14
        tw = int(f_small.getlength(text))
        w = tw + pad*2
        h = 38

        shape = Image.new("RGBA", (w, h), (255,255,255,255))
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle((0,0,w,h), radius=18, fill=255)
        bg.paste(shape, (x,y), m)

        draw.text((x+pad, y+8), text, fill=(0,0,0), font=f_small)

    px = cx + 260
    py = cy + 60

    pill(px, py, _trim(title, f_small, 180))
    pill(px, py+55, channel)
    pill(px, py+110, "52M views")

    # ───────── PLAY BUTTON ─────────
    draw.ellipse((px+100, py-45, px+150, py+5), fill=(0,0,0))
    draw.polygon([(px+115, py-30), (px+115, py-10), (px+135, py-20)], fill=(255,255,255))

    # ───────── PLAYER BAR (FIXED) ─────────
    bx, by = cx + 40, cy + 300
    bw, bh = 300, 80

    bar = Image.new("RGBA", (bw, bh), (255,255,255,255))
    m = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(m).rounded_rectangle((0,0,bw,bh), radius=30, fill=255)
    bg.paste(bar, (bx,by), m)

    draw = ImageDraw.Draw(bg)

    # progress line
    draw.line((bx+30, by+25, bx+260, by+25), fill=(150,150,150), width=3)
    draw.ellipse((bx+110, by+20, bx+120, by+30), fill=(0,0,0))

    # time
    draw.text((bx+20, by+5), "0:00", font=f_tiny, fill=(100,100,100))
    draw.text((bx+230, by+5), duration_text, font=f_tiny, fill=(100,100,100))

    # controls
    draw.text((bx+70, by+45), "⏮", font=f_small, fill=(0,0,0))
    draw.text((bx+130, by+45), "⏸", font=f_small, fill=(0,0,0))
    draw.text((bx+190, by+45), "⏭", font=f_small, fill=(0,0,0))

    # ───────── SAVE ─────────
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
