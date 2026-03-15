
import requests

BASE = "https://openbudget.uz/api/v2/info/votes/69b6f9b83d01cb2096d874bf"

def fetch_page(page):
    url = f"{BASE}?page={page}&size=12"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        out = []
        for v in data["content"]:
            out.append((v["phoneNumber"], v["voteDate"]))
        return out
    except:
        return []
