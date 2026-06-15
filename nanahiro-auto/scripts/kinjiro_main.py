"""
金次郎プロモ動画パイプライン
Usage:
    python scripts/kinjiro_main.py
    python scripts/kinjiro_main.py --images-only
    python scripts/kinjiro_main.py --voice-only
    python scripts/kinjiro_main.py --video-only
"""
import sys
import os
import json
import glob
import argparse
from datetime import datetime
from pathlib import Path

sys.path.append(os.path.dirname(__file__))

from kinjiro_generate_images import generate_all_scene_images
from kinjiro_generate_voice import generate_kinjiro_voice
from kinjiro_create_video import create_kinjiro_video

LINE = "=" * 52
SCRIPT_JSON = os.path.join(os.path.dirname(__file__), "kinjiro_script.json")


def load_script() -> dict:
    with open(SCRIPT_JSON, encoding="utf-8") as f:
        return json.load(f)


def find_existing_images() -> list:
    paths = sorted(glob.glob("output/kinjiro_images/scene_*.jpg"))
    return paths


def find_latest_audio() -> str:
    files = sorted(glob.glob("output/kinjiro_voice_*.mp3"))
    return files[-1] if files else None


def run_pipeline(args):
    print(LINE)
    print("金次郎プロモ動画パイプライン 開始")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(LINE)

    script_data = load_script()
    print(f"スクリプト: {script_data['title']}")
    print(f"シーン数: {len(script_data['scenes'])}")

    images_only = args.images_only
    voice_only = args.voice_only
    video_only = args.video_only
    run_all = not (images_only or voice_only or video_only)

    image_paths = []
    audio_path = None

    # ① 画像生成
    if run_all or images_only:
        print(f"\n【ステップ1】シーン画像生成")
        image_paths = generate_all_scene_images(script_data)

    if video_only or (run_all and not image_paths):
        image_paths = find_existing_images()
        if not image_paths:
            print("[エラー] 画像ファイルが見つかりません。先に --images-only を実行してください。")
            if video_only:
                sys.exit(1)

    # ② 音声生成
    if run_all or voice_only:
        print(f"\n【ステップ2】ナレーション音声生成")
        audio_path = generate_kinjiro_voice(script_data)

    if video_only or (run_all and not audio_path):
        audio_path = find_latest_audio()
        if not audio_path:
            print("[エラー] 音声ファイルが見つかりません。先に --voice-only を実行してください。")
            if video_only:
                sys.exit(1)

    if images_only or voice_only:
        print(f"\n{LINE}")
        print("✅ 指定ステップ完了")
        return

    # ③ 動画合成
    if run_all or video_only:
        print(f"\n【ステップ3】動画合成")

        if not image_paths:
            image_paths = find_existing_images()
        if not audio_path:
            audio_path = find_latest_audio()

        scenes_count = len(script_data["scenes"])
        if len(image_paths) < scenes_count:
            print(f"  [警告] 画像数({len(image_paths)}) < シーン数({scenes_count}) → 不足分はプレースホルダーで補完")
            while len(image_paths) < scenes_count:
                image_paths.append(None)

        video_path = create_kinjiro_video(script_data, image_paths, audio_path)

        print(f"\n{LINE}")
        print("✅ パイプライン完了！")
        print(f"動画ファイル: {video_path}")
        print(LINE)

        return video_path


def main():
    parser = argparse.ArgumentParser(description="金次郎プロモ動画パイプライン")
    parser.add_argument("--images-only", action="store_true", help="画像生成のみ実行")
    parser.add_argument("--voice-only", action="store_true", help="音声生成のみ実行")
    parser.add_argument("--video-only", action="store_true", help="動画合成のみ実行（画像・音声は既存ファイルを使用）")
    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()
