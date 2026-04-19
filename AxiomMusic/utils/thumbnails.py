import os
import re
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from py_yt import VideosSearch
from config import YOUTUBE_IMG_URL
from AxiomMusic import app

# cache folder
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)


# ─────────────────────────────
# 🎨 THUMBNAIL RENDER (IMPROVED UI)
# ─────────────────────────────
def _make_thumb(raw_path, title, channel, duration_text, player_username, cache_path):

    base = Image.open("AxiomMusic/assets/template.png").convert("RGBA")
    draw = ImageDraw.Draw(base)

    # 🔥 Fonts (bigger + clean)
    font_title = ImageFont.truetype("AxiomMusic/assets/font2.ttf", 55)
    font_artist = ImageFont.truetype("AxiomMusic/assets/font.ttf", 36)
    font_time = ImageFont.truetype("AxiomMusic/assets/font.ttf", 30)

    # ─────────────
    # 🎵 ALBUM ART (BIGGER + CENTERED)
    # ─────────────
    try:
        ART_SIZE = 240

        art = Image.open(raw_path).resize((ART_SIZE, ART_SIZE))

        mask = Image.new("L", (ART_SIZE, ART_SIZE), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, ART_SIZE, ART_SIZE), 45, fill=255
        )

        # adjusted position for better alignment
        base.paste(art, (120, 410), mask)

    except Exception as e:
        print(f"Error drawing art: {e}")

    # ─────────────
    # 📝 TITLE & CHANNEL
    # ─────────────
    title = re.sub(r"\W+", " ", title)

    draw.text((420, 410), title[:28], fill="white", font=font_title)
    draw.text((420, 480), channel[:32], fill=(200, 200, 200), font=font_artist)

    # ─────────────
    # ⏱️ TIME (FIXED ALIGNMENT)
    # ─────────────

    # LEFT TIME (start time)
    draw.text((420, 550), "0:00", fill=(200, 200, 200), font=font_time)

    # RIGHT TIME (duration)
    draw.text((1080, 550), duration_text, fill=(200, 200, 200), font=font_time)

    # ─────────────
    # 🔊 VOLUME KNOB (SMOOTH GLOW)
    # ─────────────
    vx, vy = 1115, 360

    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)

    gdraw.ellipse((vx-16, vy-16, vx+16, vy+16), fill=(255, 255, 255, 120))
    base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(10)))

    draw = ImageDraw.Draw(base)
    draw.ellipse((vx-10, vy-10, vx+10, vy+10), fill=(220, 220, 220))

    # ─────────────
    # ✨ FINAL TOUCH
    # ─────────────
    base = ImageEnhance.Sharpness(base).enhance(1.4)
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
