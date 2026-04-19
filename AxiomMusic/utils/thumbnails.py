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
# 🎨 ADVANCED THUMBNAIL RENDER
# ─────────────────────────────
def _make_thumb(raw_path, title, channel, duration_text, player_username, cache_path):

    base = Image.open("AxiomMusic/assets/template.png").convert("RGBA")
    draw = ImageDraw.Draw(base)

    # 🔥 Fonts
    font_title = ImageFont.truetype("AxiomMusic/assets/font2.ttf", 58)
    font_artist = ImageFont.truetype("AxiomMusic/assets/font.ttf", 36)
    font_time = ImageFont.truetype("AxiomMusic/assets/font.ttf", 30)

    # ─────────────
    # 🎨 BACKGROUND BLUR (GLASS EFFECT)
    # ─────────────
    try:
        bg = Image.open(raw_path).resize(base.size).filter(ImageFilter.GaussianBlur(25))
        dark_overlay = Image.new("RGBA", base.size, (0, 0, 0, 140))
        bg = Image.alpha_composite(bg.convert("RGBA"), dark_overlay)
        base = Image.alpha_composite(bg, base)
        draw = ImageDraw.Draw(base)
    except:
        pass

    # ─────────────
    # 🎵 ALBUM ART (BIG + CENTERED)
    # ─────────────
    try:
        ART_SIZE = 260
        art = Image.open(raw_path).resize((ART_SIZE, ART_SIZE))

        mask = Image.new("L", (ART_SIZE, ART_SIZE), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, ART_SIZE, ART_SIZE), 50, fill=255
        )

        # Glow effect
        glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.rounded_rectangle(
            (110, 400, 110 + ART_SIZE, 400 + ART_SIZE),
            50,
            fill=(255, 255, 255, 40),
        )

        base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(15)))

        base.paste(art, (110, 400), mask)

    except Exception as e:
        print(e)

    # ─────────────
    # 📝 TITLE & CHANNEL
    # ─────────────
    title = re.sub(r"\W+", " ", title)

    draw.text((420, 400), title[:30], fill="white", font=font_title)
    draw.text((420, 480), channel[:35], fill=(210, 210, 210), font=font_artist)

    # ─────────────
    # ⏱️ TIME + PROGRESS BAR
    # ─────────────

    # time text
    draw.text((420, 560), "0:00", fill=(200, 200, 200), font=font_time)
    draw.text((1080, 560), duration_text, fill=(200, 200, 200), font=font_time)

    # progress bar
    bar_x1, bar_y = 420, 530
    bar_x2 = 1100

    # background bar
    draw.line((bar_x1, bar_y, bar_x2, bar_y), fill=(100, 100, 100), width=6)

    # progress (fake 30%)
    progress = int((bar_x2 - bar_x1) * 0.3)
    draw.line((bar_x1, bar_y, bar_x1 + progress, bar_y), fill=(255, 255, 255), width=6)

    # knob
    draw.ellipse(
        (bar_x1 + progress - 8, bar_y - 8, bar_x1 + progress + 8, bar_y + 8),
        fill="white",
    )

    # ─────────────
    # 🔊 VOLUME KNOB (ENHANCED)
    # ─────────────
    vx, vy = 1115, 360

    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((vx-18, vy-18, vx+18, vy+18), fill=(255, 255, 255, 120))

    base = Image.alpha_composite(base, glow.filter(ImageFilter.GaussianBlur(12)))
    draw = ImageDraw.Draw(base)

    draw.ellipse((vx-10, vy-10, vx+10, vy+10), fill=(230, 230, 230))

    # ─────────────
    # ✨ FINAL ENHANCEMENT
    # ─────────────
    base = ImageEnhance.Contrast(base).enhance(1.1)
    base = ImageEnhance.Sharpness(base).enhance(1.5)

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
