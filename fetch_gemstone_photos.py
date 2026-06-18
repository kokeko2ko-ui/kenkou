import requests
import os

API_KEY = "327pHJXVOIuIAnJslEABItujDtsHJgV2ge7unHp2ab3jVBYzlmllkQ1B"
HEADERS = {"Authorization": API_KEY}
OUTPUT_DIR = "gemstone_photos"

QUERIES = {
    "ruby": "ruby gemstone",
    "sapphire": "sapphire gemstone",
    "diamond": "diamond gemstone",
    "gold": "gold bar",
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

for name, query in QUERIES.items():
    resp = requests.get(
        "https://api.pexels.com/v1/search",
        headers=HEADERS,
        params={"query": query, "per_page": 1, "orientation": "landscape"},
    )
    resp.raise_for_status()
    data = resp.json()

    if not data["photos"]:
        print(f"[{name}] 写真が見つかりませんでした")
        continue

    photo = data["photos"][0]
    url = photo["src"]["large"]
    photographer = photo["photographer"]
    photo_id = photo["id"]

    img_resp = requests.get(url)
    img_resp.raise_for_status()

    filename = os.path.join(OUTPUT_DIR, f"{name}_{photo_id}.jpg")
    with open(filename, "wb") as f:
        f.write(img_resp.content)

    print(f"[{name}] 保存: {filename}  (撮影者: {photographer})")
    print(f"         URL: {photo['url']}")

print("\n完了！")
