import os
import re
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from AxiomMusic import app

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)


# ─────────────────────────────
# 🎨 CLEAN THUMBNAIL RENDER
# ─────────────────────────────
def _make_thumb(raw_path, title, channel, duration_text, player_username, cache_path):

    # Load template
    base = Image.open("AxiomMusic/assets/template.png").convert("RGBA")
    WIDTH, HEIGHT = base.size

    draw = ImageDraw.Draw(base)

    # Fonts
    font_title = ImageFont.truetype("AxiomMusic/assets/font2.ttf", 50)
    font_artist = ImageFont.truetype("AxiomMusic/assets/font.ttf", 32)
    font_time = ImageFont.truetype("AxiomMusic/assets/font.ttf", 26)

    # ─────────────
    # 🎨 BACKGROUND BLUR
    # ─────────────
    try:
        bg = Image.open(raw_path).convert("RGBA").resize((WIDTH, HEIGHT))
        bg = bg.filter(ImageFilter.GaussianBlur(18))

        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 120))
        bg = Image.alpha_composite(bg, overlay)

        base = Image.alpha_composite(bg, base)
    except:
        pass

    draw = ImageDraw.Draw(base)

    # ─────────────
    # 🎵 ALBUM ART
    # ─────────────
    try:
        ART_SIZE = int(WIDTH * 0.18)

        art = Image.open(raw_path).resize((ART_SIZE, ART_SIZE))

        mask = Image.new("L", (ART_SIZE, ART_SIZE), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, ART_SIZE, ART_SIZE), 40, fill=255
        )

        art_x = int(WIDTH * 0.07)
        art_y = int(HEIGHT * 0.45)

        base.paste(art, (art_x, art_y), mask)

    except Exception as e:
        print("ART ERROR:", e)

    # ─────────────
    # 📝 TEXT (FIXED SAFE ZONE)
    # ─────────────
    title = re.sub(r"\W+", " ", title)

    text_x = int(WIDTH * 0.30)
    title_y = int(HEIGHT * 0.45)

    draw.text((text_x, title_y), title[:40], fill="white", font=font_title)
    draw.text((text_x, title_y + 70), channel[:35], fill=(200, 200, 200), font=font_artist)

    # ─────────────
    # ⏱️ TIME + PROGRESS BAR
    # ─────────────
    bar_x1 = text_x
    bar_x2 = int(WIDTH * 0.88)
    bar_y = int(HEIGHT * 0.68)

    draw.text((bar_x1, bar_y + 20), "0:00", fill=(200, 200, 200), font=font_time)
    draw.text((bar_x2 - 60, bar_y + 20), duration_text, fill=(200, 200, 200), font=font_time)

    # bar bg
    draw.line((bar_x1, bar_y, bar_x2, bar_y), fill=(120, 120, 120), width=5)

    # progress (30%)
    progress = int((bar_x2 - bar_x1) * 0.3)
    draw.line((bar_x1, bar_y, bar_x1 + progress, bar_y), fill="white", width=5)

    # knob
    draw.ellipse(
        (bar_x1 + progress - 7, bar_y - 7, bar_x1 + progress + 7, bar_y + 7),
        fill="white",
    )

    # ─────────────
    # 🔊 VOLUME DOT
    # ─────────────
    vx = int(WIDTH * 0.92)
    vy = int(HEIGHT * 0.42)

    draw.ellipse((vx - 6, vy - 6, vx + 6, vy + 6), fill=(220, 220, 220))

    # ─────────────
    # ✨ FINAL TOUCH
    # ─────────────
    base = ImageEnhance.Contrast(base).enhance(1.05)
    base = ImageEnhance.Sharpness(base).enhance(1.3)

    base.convert("RGB").save(cache_path)

    return cache_path


# ─────────────────────────────
# 🚀 MAIN FUNCTION
# ─────────────────────────────
async def get_thumb(videoid: str, player_username: str = None):

    if player_username is None:
        player_username = app.username

    cache_path = os.path.join(CACHE_DIR, f"{videoid}.png")
    if os.path.exists(cache_path):
        return cache_path

    try:
        results = VideosSearch(
            f"https://www.youtube.com/watch?v={videoid}", limit=1
        )
        search = await results.next()
        data = search["result"][0]

        title = data["title"]
        channel = data["channel"]["name"]
        duration = data.get("duration", "0:00")
        thumb_url = data["thumbnails"][0]["url"]

    except:
        return YOUTUBE_IMG_URL

    raw_path = os.path.join(CACHE_DIR, f"{videoid}.jpg")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumb_url) as resp:
                if resp.status == 200:
                    async with aiofiles.open(raw_path, "wb") as f:
                        await f.write(await resp.read())
                else:
                    return YOUTUBE_IMG_URL
    except:
        return YOUTUBE_IMG_URL

    result = _make_thumb(
        raw_path, title, channel, duration, player_username, cache_path
    )

    if os.path.exists(raw_path):
        os.remove(raw_path)

    return result
