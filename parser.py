import requests
import json

def get_api():
    with open("config.json") as f:
        config = json.load(f)
    return config["api"]

def fetch_page(page):
    api = get_api()
    url = f"https://openbudget.uz/api/v2/info/votes/{api}?page={page}&size=12"

    try:
        r = requests.get(url, timeout=10)
        data = r.json()

        votes = []
        for v in data["content"]:
            votes.append((v["phoneNumber"], v["voteDate"]))

        return votes
    except:
        return []
