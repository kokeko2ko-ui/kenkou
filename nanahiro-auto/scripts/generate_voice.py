import os
import requests
from datetime import datetime

ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")  # 後で設定


def list_voices() -> list:
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    response = requests.get(url, headers=headers)
    voices = response.json().get("voices", [])
    for v in voices:
        print(f"  {v['voice_id']} - {v['name']}")
    return voices


def generate_voice(script_data: dict) -> str:
    script_text = script_data.get("script", "")
    title = script_data.get("title", "audio")

    if not VOICE_ID:
        print("[警告] ELEVENLABS_VOICE_IDが未設定です。利用可能なボイス一覧:")
        list_voices()
        raise ValueError("ELEVENLABS_VOICE_IDをGitHub Secretsに設定してください")

    # ナレーション本文のみ抽出（演出メモ・記号を除去）
    clean_text = clean_script(script_text)

    print(f"[音声生成] テキスト文字数: {len(clean_text)}")
    print(f"[音声生成] ボイスID: {VOICE_ID}")

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

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise Exception(f"ElevenLabs APIエラー: {response.status_code} - {response.text}")

    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"

    with open(filename, "wb") as f:
        f.write(response.content)

    print(f"[音声生成完了] 保存先: {filename}")
    return filename


def clean_script(text: str) -> str:
    import re
    # 演出メモ（【】で囲まれた部分）を除去
    text = re.sub(r"【[^】]*】", "", text)
    # （）内の読み方指示を除去
    text = re.sub(r"（[^）]*）", "", text)
    # 余分な空白・改行を整理
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


if __name__ == "__main__":
    print("利用可能なElevenLabsボイス一覧:")
    list_voices()
