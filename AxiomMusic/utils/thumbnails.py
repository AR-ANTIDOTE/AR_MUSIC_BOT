import os
import math
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# ================= CONFIG ================= #

CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

FONT_BOLD = "arial.ttf"
FONT_REG = "arial.ttf"

WIDTH = 1280
HEIGHT = 720

PINK = (255, 0, 150)

# ========================================== #

# ---------- DOWNLOAD IMAGE ---------- #
async def download_image(url, path):
    if os.path.exists(path):
        return path

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(path, mode="wb")
                await f.write(await resp.read())
                await f.close()
    return path


# ---------- TIME FORMAT ---------- #
def format_time(seconds: int):
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02}:{s:02}"


# ---------- NEON BORDER ---------- #
def draw_neon(draw, box, radius=30):
    x1, y1, x2, y2 = box

    # glow layers
    for i in range(12):
        draw.rounded_rectangle(
            [x1 - i, y1 - i, x2 + i, y2 + i],
            radius=radius,
            outline=(PINK[0], PINK[1], PINK[2], 25),
            width=2
        )

    # main border
    draw.rounded_rectangle(box, radius=radius, outline=PINK, width=4)


# ---------- PROGRESS BAR ---------- #
def draw_progress(draw, x, top, bottom, progress):
    # background
    draw.line((x, top, x, bottom), fill=(180, 180, 180, 80), width=6)

    # current point
    current_y = bottom - int((bottom - top) * progress)

    # progress fill
    draw.line((x, current_y, x, bottom), fill=PINK, width=6)

    # glowing dot
    draw.ellipse((x - 10, current_y - 10, x + 10, current_y + 10), fill=PINK)


# ---------- DP CIRCLE ---------- #
def add_circle_dp(base, dp_path):
    try:
        dp = Image.open(dp_path).convert("RGB").resize((80, 80))

        mask = Image.new("L", (80, 80), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, 80, 80), fill=255)

        dp.putalpha(mask)

        base.paste(dp, (260, 420), dp)
    except:
        pass


# ---------- MAIN FUNCTION ---------- #
async def generate_thumbnail(
    title: str,
    channel: str,
    views: str,
    duration: int,
    current: int,
    thumb_url: str,
    dp_url: str = None,
    output: str = "final.png"
):

    thumb_path = os.path.join(CACHE_DIR, "thumb.jpg")
    dp_path = os.path.join(CACHE_DIR, "dp.png")

    await download_image(thumb_url, thumb_path)

    if dp_url:
        await download_image(dp_url, dp_path)

    # ---------- BASE ---------- #
    base = Image.new("RGB", (WIDTH, HEIGHT), (10, 20, 25))

    # ---------- BACKGROUND BLUR ---------- #
    bg = Image.open(thumb_path).resize((WIDTH, HEIGHT))
    bg = bg.filter(ImageFilter.GaussianBlur(30))
    enhancer = ImageEnhance.Brightness(bg)
    bg = enhancer.enhance(0.4)

    base.paste(bg, (0, 0))

    draw = ImageDraw.Draw(base)

    # ---------- MAIN THUMB ---------- #
    thumb = Image.open(thumb_path).resize((800, 400))
    base.paste(thumb, (250, 120))

    box = (250, 120, 1050, 520)

    draw_neon(draw, box)

    # ---------- PROGRESS ---------- #
    progress = current / duration if duration else 0
    draw_progress(draw, 120, 100, 620, progress)

    # ---------- FONTS ---------- #
    try:
        font_title = ImageFont.truetype(FONT_BOLD, 42)
        font_small = ImageFont.truetype(FONT_REG, 28)
    except:
        font_title = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # ---------- TEXT ---------- #
    title = title[:45]

    draw.text((300, 550), title, font=font_title, fill="white")
    draw.text((300, 600), f"{channel} | {views}", font=font_small, fill=(180, 180, 180))

    # ---------- TIME ---------- #
    draw.text((50, 60), format_time(current), font=font_small, fill=PINK)
    draw.text((50, 640), format_time(duration), font=font_small, fill=PINK)

    # ---------- DP ---------- #
    if dp_url:
        add_circle_dp(base, dp_path)

    # ---------- SAVE ---------- #
    base.save(output)
    return output
