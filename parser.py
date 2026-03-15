import json
import logging
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
DEFAULT_API  = "69b7058e3d01cb2096d890ab"

# ─── Config ───────────────────────────────────────────────────────────────────
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

# ─── Fetch ────────────────────────────────────────────────────────────────────
def fetch_page(page: int, size: int = 50) -> list[tuple]:
    """
    OpenBudget API dan bir sahifani oladi.
    Qaytaradi: [(phone, date), ...] yoki [] (xatolik/oxiri bo'lsa)
    """
    api = get_api()
    url = f"https://openbudget.uz/api/v2/info/votes/{api}"
    params = {"page": page, "size": size}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        logger.warning(f"Sahifa {page}: so'rov vaqti tugadi (timeout).")
        return []
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Sahifa {page}: HTTP xatolik — {e}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Sahifa {page}: tarmoq xatolik — {e}")
        return []
    except ValueError as e:
        logger.error(f"Sahifa {page}: JSON parse xatolik — {e}")
        return []

    # Turli API javob formatlarini qo'llab-quvvatlash
    content = None
    if isinstance(data, dict):
        content = data.get("content") or data.get("data") or data.get("items")
    elif isinstance(data, list):
        content = data

    if not content:
        return []  # bo'sh sahifa = oxirgi

    votes = []
    for item in content:
        try:
            phone = item.get("phoneNumber") or item.get("phone", "")
            date  = item.get("voteDate")  or item.get("date",  "")
            if phone:
                votes.append((str(phone), str(date)))
        except Exception as e:
            logger.debug(f"Item parse xatolik: {e} — {item}")
            continue

    logger.debug(f"Sahifa {page}: {len(votes)} ta ovoz olindi.")
    return votes
