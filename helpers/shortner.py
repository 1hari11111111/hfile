"""
URL Shortener Helper
Picks a random *active* shortener from DB and calls its API.
Multiple shorteners can be active simultaneously; one is chosen at random
so link traffic is distributed evenly across all active APIs.

Supports response keys: shortenedUrl / short_url / result / shortlink / short
Falls back to the original URL on any error.
"""
import random
import aiohttp
from database.database import shortener_col


def get_active_shorteners() -> list:
    """Return all active shortener configs (list may be empty)."""
    return list(shortener_col.find({"active": True}, {"_id": 0}))


def pick_random_shortener() -> dict | None:
    """Pick one active shortener at random, or None if none are active."""
    active = get_active_shorteners()
    return random.choice(active) if active else None


async def get_shortlink(original_url: str) -> str:
    """
    Shorten `original_url` using a randomly selected active shortener.
    Returns the shortened URL, or `original_url` if anything fails.
    """
    try:
        shortener = pick_random_shortener()
        if not shortener:
            return original_url

        api_url = shortener["api_url"].rstrip("/")
        api_key = shortener["api_key"]

        request_url = f"{api_url}/api?api={api_key}&url={original_url}"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                request_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return original_url
                data = await resp.json(content_type=None)

        for key in ("shortenedUrl", "short_url", "result", "shortlink", "short"):
            if key in data and data[key]:
                return str(data[key])

        return original_url

    except Exception as e:
        print(f"[Shortener] Error: {e}")
        return original_url
