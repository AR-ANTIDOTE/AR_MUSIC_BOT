import asyncio
import os
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch, Playlist
import aiohttp

API_URL = os.environ.get("SHRUTI_API_URL", "https://api.shrutibots.site")
API_KEY = os.environ.get("SHRUTI_API_KEY", "ShrutiBotsx7llDDmWnF986ygx9seT")
DOWNLOAD_DIR = "downloads"

def time_to_seconds(time):
    stringt = str(time)
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(stringt.split(":"))))

async def download_song(link: str) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0: return file_path
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/download", params={"url": video_id, "type": "audio", "api_key": API_KEY}, timeout=aiohttp.ClientTimeout(total=300)) as resp:
                if resp.status != 200: return None
                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072): f.write(chunk)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0: return file_path
        return None
    except Exception:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        return None

async def download_video(link: str) -> str:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if not video_id or len(video_id) < 3: return None
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0: return file_path
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_URL}/download", params={"url": video_id, "type": "video", "api_key": API_KEY}, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                if resp.status != 200: return None
                with open(file_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(131072): f.write(chunk)
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0: return file_path
        return None
    except Exception:
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass
        return None

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message: messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK: return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        res = await results.next()
        if not res.get("result"): return None, None, 0, None, None
        result = res["result"][0]
        title = result["title"]
        duration_min = result["duration"]
        thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        vidid = result["id"]
        duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid: link = self.base + link
        if "&" in link: link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        res = await results.next()
        if not res.get("result"): return None, None
        result = res["result"][0]
        track_details = {
            "title": result["title"], "link": result["link"], "vidid": result["id"],
            "duration_min": result["duration"], "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, result["id"]

    async def download(self, link: str, mystic, video: Union[bool, str] = None, videoid: Union[bool, str] = None, songaudio: Union[bool, str] = None, songvideo: Union[bool, str] = None, format_id: Union[bool, str] = None, title: Union[bool, str] = None) -> str:
        if videoid: link = self.base + link
        try:
            if video: downloaded_file = await download_video(link)
            else: downloaded_file = await download_song(link)
            if downloaded_file: return downloaded_file, True
            return None, False
        except Exception: return None, False

    # --- NEW ROBUST RELATED VIDEOS METHOD (PIPED API) ---
    async def get_related_streams(self, video_id: str):
        # Piped API instances (YouTube open-source frontend, 100% reliable)
        PIPED_INSTANCES = [
            "https://pipedapi.kavin.rocks",
            "https://pipedapi.adminforge.de",
            "https://api.piped.projectsegfau.lt",
            "https://pipedapi.in.projectsegfau.lt"
        ]
        for instance in PIPED_INSTANCES:
            try:
                url = f"{instance}/streams/{video_id}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            related = data.get("relatedStreams", [])
                            results = []
                            for item in related[:20]: # Fetch top 20 related
                                vid_url = item.get("url", "")
                                if "v=" in vid_url:
                                    vid_id = vid_url.split("v=")[-1].split("&")[0]
                                else:
                                    vid_id = vid_url.replace("/watch?v=", "").strip("/")
                                
                                if vid_id:
                                    results.append({
                                        "id": vid_id,
                                        "title": item.get("title"),
                                        "duration": item.get("duration"), # in seconds
                                        "thumb": item.get("thumbnail")
                                    })
                            if results:
                                return results
            except Exception:
                continue
        
        # Fallback to py_yt if all Piped instances are down
        try:
            details = await self.details(video_id, videoid=True)
            if details and details[0]:
                title = details[0]
                results = VideosSearch(f"{title} mix", limit=10)
                res = await results.next()
                if res.get("result"):
                    return [{
                        "id": item["id"],
                        "title": item["title"],
                        "duration": int(time_to_seconds(item.get("duration", "0:00"))) if item.get("duration") else 0,
                        "thumb": item["thumbnails"][0]["url"].split("?")[0]
                    } for item in res["result"]]
        except Exception:
            pass
        return []

YouTube = YouTubeAPI()
