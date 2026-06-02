import os
import json
import pickle
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def get_youtube_client():
    creds_json = os.environ.get("YOUTUBE_CREDENTIALS")
    if not creds_json:
        raise ValueError("YOUTUBE_CREDENTIALSがGitHub Secretsに設定されていません")

    creds_data = json.loads(creds_json)
    creds = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=creds_data.get("client_id"),
        client_secret=creds_data.get("client_secret"),
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(script_data: dict, video_path: str) -> str:
    title = script_data.get("title", "動画")[:100]
    description = script_data.get("description", "")
    tags = script_data.get("tags", [])

    print(f"[YouTube投稿] タイトル: {title}")

    youtube = get_youtube_client()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags[:30],
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "ja",
        },
        "status": {
            "privacyStatus": "private",  # 最初はプライベートで確認
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

    print(f"[YouTube投稿] アップロード中...")
    request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  アップロード進捗: {int(status.progress() * 100)}%")

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    print(f"[YouTube投稿完了] URL: {video_url}")
    print(f"[YouTube投稿] ※現在プライベート設定です。確認後に公開に変更してください。")

    return video_url


if __name__ == "__main__":
    print("YouTube投稿モジュールです。main.pyから呼び出してください。")
    print("初回セットアップにはYOUTUBE_CREDENTIALSのGitHub Secrets設定が必要です。")
