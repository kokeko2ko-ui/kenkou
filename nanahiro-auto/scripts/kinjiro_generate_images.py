"""
シーン画像生成モジュール
Higgsfield API or Stability AI を使用してシーン画像を生成
"""
import os
import json
import requests
import time
from datetime import datetime
from pathlib import Path

HIGGSFIELD_API_KEY = os.environ.get("HIGGSFIELD_API_KEY", "")
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

OUTPUT_DIR = Path("output/kinjiro_images")


def _download_image(url: str, path: str) -> bool:
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            with open(path, "wb") as f:
                f.write(response.content)
            return os.path.getsize(path) > 1000
    except Exception as e:
        print(f"  [ダウンロードエラー] {e}")
    return False


def generate_image_stability(prompt: str, output_path: str) -> bool:
    """Stability AI でシーン画像を生成 (STABILITY_API_KEY が必要)"""
    if not STABILITY_API_KEY:
        return False
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "text_prompts": [
            {"text": prompt + ", high quality, cinematic, professional", "weight": 1},
            {"text": "blurry, low quality, ugly, cartoon, anime", "weight": -1},
        ],
        "cfg_scale": 7,
        "height": 720,
        "width": 1280,
        "samples": 1,
        "steps": 30,
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        if response.status_code == 200:
            data = response.json()
            import base64
            image_data = base64.b64decode(data["artifacts"][0]["base64"])
            with open(output_path, "wb") as f:
                f.write(image_data)
            print(f"  [Stability] 生成完了: {output_path}")
            return True
        else:
            print(f"  [Stability] エラー: {response.status_code}")
    except Exception as e:
        print(f"  [Stability] 例外: {e}")
    return False


def search_pexels_image(query: str, output_path: str) -> bool:
    """Pexels でフォールバック画像を取得"""
    if not PEXELS_API_KEY:
        return False
    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 3, "orientation": "landscape"}
    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        data = response.json()
        photos = data.get("photos", [])
        if photos:
            img_url = photos[0]["src"]["large2x"]
            if _download_image(img_url, output_path):
                print(f"  [Pexels] フォールバック取得: {output_path}")
                return True
    except Exception as e:
        print(f"  [Pexels] 例外: {e}")
    return False


def make_placeholder_image(text: str, output_path: str) -> str:
    """テキストカード画像を生成（最終フォールバック）"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np

        img = Image.new("RGB", (1280, 720), color=(20, 20, 50))
        draw = ImageDraw.Draw(img)

        font_candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font = None
        for fc in font_candidates:
            if os.path.exists(fc):
                try:
                    font = ImageFont.truetype(fc, 36)
                    break
                except Exception:
                    continue
        if font is None:
            font = ImageFont.load_default()

        lines = []
        words = text.split()
        current = ""
        for word in words:
            if len(current) + len(word) + 1 > 30:
                lines.append(current.strip())
                current = word
            else:
                current += " " + word
        if current:
            lines.append(current.strip())

        total_h = len(lines) * 50
        y = (720 - total_h) // 2
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
            except AttributeError:
                tw, _ = draw.textsize(line, font=font)
            x = (1280 - tw) // 2
            draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
            y += 50

        img.save(output_path, "JPEG", quality=85)
        print(f"  [プレースホルダー] 生成: {output_path}")
        return output_path
    except Exception as e:
        print(f"  [プレースホルダーエラー] {e}")
        return None


def generate_scene_image(scene: dict, index: int) -> str:
    """1シーンの画像を生成（優先順位：Stability → Pexels → プレースホルダー）"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(OUTPUT_DIR / f"scene_{index:02d}.jpg")

    if os.path.exists(output_path) and os.path.getsize(output_path) > 5000:
        print(f"  [キャッシュ] シーン{index}: {output_path}")
        return output_path

    prompt = scene.get("image_prompt", scene.get("visual_description", ""))
    pexels_query = scene.get("pexels_query", "Japan urban scene")
    scene_name = scene.get("name", f"シーン{index}")

    print(f"\n[シーン{index}] {scene_name}")
    print(f"  プロンプト: {prompt[:80]}...")

    if generate_image_stability(prompt, output_path):
        return output_path

    if search_pexels_image(pexels_query, output_path):
        return output_path

    result = make_placeholder_image(scene_name + "\n" + prompt[:60], output_path)
    return result or output_path


def generate_all_scene_images(script_data: dict) -> list:
    """全シーンの画像を生成してパスリストを返す"""
    scenes = script_data.get("scenes", [])
    print(f"\n[画像生成] {len(scenes)}シーンを処理中...")

    image_paths = []
    for i, scene in enumerate(scenes, start=1):
        path = generate_scene_image(scene, i)
        image_paths.append(path)
        time.sleep(0.5)

    successful = [p for p in image_paths if p and os.path.exists(p)]
    print(f"\n[画像生成完了] {len(successful)}/{len(scenes)} シーン成功")
    return image_paths


if __name__ == "__main__":
    script_path = os.path.join(os.path.dirname(__file__), "kinjiro_script.json")
    with open(script_path, encoding="utf-8") as f:
        script_data = json.load(f)

    paths = generate_all_scene_images(script_data)
    for i, p in enumerate(paths, 1):
        print(f"  シーン{i:02d}: {p}")
