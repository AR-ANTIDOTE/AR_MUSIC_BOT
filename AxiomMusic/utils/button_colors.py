import random

# 🔥 jitne chahe utne colors add kar
COLOR_POOL = [
    "🔴","🟢","🔵","🟡","🟣","🟠",
    "🟥","🟩","🟦","🟨","🟪","🟧",
    "❤️","💚","💙","💛","💜","🧡",
    "⚫","⚪","🔶","🔷"
]

# 👉 ye current bot session ke colors store karega
BUTTON_COLOR_MAP = {}

def get_btn_color(key: str):
    """
    Har button ke liye ek fixed random color deta hai
    (jab tak bot restart na ho)
    """
    if key not in BUTTON_COLOR_MAP:
        BUTTON_COLOR_MAP[key] = random.choice(COLOR_POOL)
    return BUTTON_COLOR_MAP[key]
