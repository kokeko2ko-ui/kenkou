import os
import requests
from datetime import datetime

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")


def generate_voice(script_data: dict) -> str:
    script_text = script_data.get("script", "")

    if not ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEYが設定されていません")
    if not VOICE_ID:
        raise ValueError("ELEVENLABS_VOICE_IDが設定されていません")

    clean_text = clean_script(script_text)
    # ElevenLabsは1リクエスト最大4000文字
    clean_text = clean_text[:4000]

    print(f"[音声生成] テキスト文字数: {len(clean_text)}")
    print(f"[音声生成] ボイスID: {VOICE_ID[:8]}...")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": clean_text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8,
            "style": 0.3,
            "use_speaker_boost": True,
        },
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)

    if response.status_code != 200:
        raise Exception(f"ElevenLabs APIエラー: {response.status_code} - {response.text[:200]}")

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"

    with open(filename, "wb") as f:
        f.write(response.content)

    print(f"[音声生成完了] 保存先: {filename}")
    return filename


def clean_script(text: str) -> str:
    import re
    text = re.sub(r"【[^】]*】", "", text)
    text = re.sub(r"（[^）]*）", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
