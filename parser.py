import json
import logging
import time
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_FILE = "config.json"
DEFAULT_API = "69b7058e3d01cb2096d890ab"

def get_api() -> str:
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
    api    = get_api()
    url    = f"https://openbudget.uz/api/v2/info/votes/{api}"
    params = {"page": page, "size": size}

    data = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(
                url, params=params,
                timeout=30,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
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
            logger.warning(f"Sahifa {page}: HTTP xato — {e}")
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

    content = None
    if isinstance(data, dict):
        content = data.get("content") or data.get("data") or data.get("items")
    elif isinstance(data, list):
        content = data

    if not content:
        return []

    votes = []
    for item in content:
        try:
            phone = item.get("phoneNumber") or item.get("phone", "")
            date  = item.get("voteDate")    or item.get("date",  "")
            if phone:
                votes.append((str(phone), str(date)))
        except Exception as e:
            logger.debug(f"Item parse xato: {e}")
            continue

    logger.info(f"Sahifa {page}: {len(votes)} ta ovoz olindi.")
    return votes
