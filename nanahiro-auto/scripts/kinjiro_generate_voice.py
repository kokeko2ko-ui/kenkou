"""
金次郎プロモ動画用音声生成
複数キャラクターのセリフをナレーション形式でまとめて生成
"""
import os
import json
import requests
from datetime import datetime

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "")


def build_narrator_text(script_data: dict) -> str:
    """ナレーター用テキストを構築（キャラクターセリフを自然なナレーションに統合）"""
    narrator_script = script_data.get("narrator_script", "")
    if narrator_script:
        return narrator_script

    # フォールバック：シーンのセリフを連結
    lines = []
    for scene in script_data.get("scenes", []):
        for dialogue in scene.get("dialogue", []):
            speaker = dialogue.get("speaker", "narrator")
            line = dialogue.get("line", "")
            if speaker == "narrator":
                lines.append(line)
            else:
                character_map = {
                    "もっちゃん": "もっちゃんは叫んだ",
                    "けい": "けいは叫んだ",
                    "さとし": "さとしは言った",
                    "いださん": "いださんは吠えた",
                    "えいちゃん": "えいちゃんは怒鳴った",
                    "all": "5人は叫んだ",
                    "all_elegant": "5人は優雅に言った",
                }
                prefix = character_map.get(speaker, f"{speaker}は言った")
                lines.append(f"「{line}」と{prefix}。")

    return "".join(lines)


def generate_kinjiro_voice(script_data: dict) -> str:
    """ElevenLabs でナレーション音声を生成"""
    if not ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEYが設定されていません")
    if not VOICE_ID:
        raise ValueError("ELEVENLABS_VOICE_IDが設定されていません")

    text = build_narrator_text(script_data)
    text = text[:4000]

    print(f"[音声生成] テキスト文字数: {len(text)}")
    print(f"[音声生成] 冒頭: {text[:80]}")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.4,
            "similarity_boost": 0.75,
            "style": 0.5,
            "use_speaker_boost": True,
        },
    }

    response = requests.post(url, headers=headers, json=payload, timeout=120)

    if response.status_code != 200:
        raise Exception(f"ElevenLabs APIエラー: {response.status_code} - {response.text[:200]}")

    os.makedirs("output", exist_ok=True)
    filename = f"output/kinjiro_voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"

    with open(filename, "wb") as f:
        f.write(response.content)

    print(f"[音声生成完了] 保存先: {filename}")
    return filename


if __name__ == "__main__":
    script_path = os.path.join(os.path.dirname(__file__), "kinjiro_script.json")
    with open(script_path, encoding="utf-8") as f:
        script_data = json.load(f)

    print("ナレーターテキスト:")
    print(build_narrator_text(script_data)[:300])
    print("...")

    voice_path = generate_kinjiro_voice(script_data)
    print(f"音声ファイル: {voice_path}")
