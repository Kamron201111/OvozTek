import json
import logging
import time
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
DEFAULT_API = "69b708d53d01cb2096d89700"

def get_api() -> str:
    """config.json dan API ID o'qiydi. Fayl yo'q bo'lsa default qaytaradi."""
    try:
        path = Path(CONFIG_FILE)
        if path.exists():
            with path.open() as f:
                data = json.load(f)
                api = data.get("api", "").strip()
                if api:
                    return api
    except Exception as e:
        logger.warning(f"config.json o'qishda xatolik: {e}")
    return DEFAULT_API

def fetch_page(page: int, size: int = 50) -> list[tuple]:
    """
    OpenBudget API dan bir sahifani oladi.
    3 marta urinib ko'radi (timeout bo'lsa).
    Qaytaradi: [(phone, date), ...] yoki []
    """
    api    = get_api()
    url    = f"https://openbudget.uz/api/v2/info/votes/{api}"
    params = {"page": page, "size": size}

    data = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(
                url,
                params=params,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "uz-UZ,uz;q=0.9",
                    "Referer": "https://openbudget.uz/",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            break

        except requests.exceptions.Timeout:
            logger.warning(f"Sahifa {page}: timeout (urinish {attempt}/3)")
            if attempt < 3:
                time.sleep(2 * attempt)
            else:
                return []

        except requests.exceptions.HTTPError as e:
            logger.warning(f"Sahifa {page}: HTTP xato {resp.status_code} — {e}")
            return []

        except requests.exceptions.RequestException as e:
            logger.error(f"Sahifa {page}: tarmoq xato — {e}")
            if attempt < 3:
                time.sleep(3)
            else:
                return []

        except ValueError as e:
            logger.error(f"Sahifa {page}: JSON parse xato — {e}")
            return []

    if data is None:
        return []

    # API javob formatini aniqlash
    content = None
    if isinstance(data, dict):
        content = (
            data.get("content")
            or data.get("data")
            or data.get("items")
            or data.get("votes")
        )
    elif isinstance(data, list):
        content = data

    if not content:
        logger.info(f"Sahifa {page}: bo'sh — yuklash tugadi.")
        return []

    votes = []
    for item in content:
        try:
            phone = (
                item.get("phoneNumber")
                or item.get("phone")
                or item.get("phone_number")
                or ""
            )
            date = (
                item.get("voteDate")
                or item.get("date")
                or item.get("vote_date")
                or ""
            )
            if phone:
                votes.append((str(phone).strip(), str(date).strip()))
        except Exception as e:
            logger.debug(f"Item parse xato: {e}")
            continue

    logger.info(f"Sahifa {page}: {len(votes)} ta ovoz olindi.")
    return votes
