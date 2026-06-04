import sys
import os
import json
from datetime import datetime

sys.path.append(os.path.dirname(__file__))

from generate_script import generate_script
from review_script import review_script, get_improvement_feedback
from generate_voice import generate_voice
from create_video import create_video
from upload_youtube import upload_to_youtube

MAX_REVIEW_LOOPS = 3
PASS_SCORE = 50  # 最高約65点なので50点を合格ラインに設定


def run_pipeline(theme: str = None):
    print("=" * 50)
    print("「人生は七色」自動投稿パイプライン 開始")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    # ① 台本生成
    print("\n【ステップ1】台本生成")
    script_data = generate_script(theme)
    print(f"[台本冒頭] {script_data['script'][:150]}")

    # ② 7人レビュー（最大3ループ）
    print("\n【ステップ2】7人レビュー採点")
    review_result = None

    for loop in range(1, MAX_REVIEW_LOOPS + 1):
        print(f"\n--- レビューループ {loop}/{MAX_REVIEW_LOOPS} ---")
        review_result = review_script(script_data)

        if review_result["passed"]:
            print(f"✅ ループ{loop}で合格！次のステップへ進みます。")
            break

        if loop < MAX_REVIEW_LOOPS:
            feedback = get_improvement_feedback(review_result["results"])
            if feedback:
                print(f"❌ 不合格。フィードバックをもとに台本を改善します...")
                script_data = improve_script(script_data, feedback)
            else:
                print(f"⚠️ フィードバックなし。台本をそのまま続行します。")
        else:
            verdict = review_result["verdict"]
            if verdict == "再生成":
                print(f"❌ {MAX_REVIEW_LOOPS}ループ終了。採点役が「再生成」判定のため今日はスキップします。")
                save_log(script_data, review_result, status="skipped")
                return
            else:
                print(f"⚠️ {MAX_REVIEW_LOOPS}ループ終了。スコア不足ですが投稿を続行します。")

    # ③ ElevenLabs音声生成
    print("\n【ステップ3】音声生成（ElevenLabs）")
    audio_path = generate_voice(script_data)

    # ④ 動画合成
    print("\n【ステップ4】動画合成")
    video_path = create_video(script_data, audio_path)

    # ⑤ YouTube投稿
    print("\n【ステップ5】YouTube投稿")
    video_url = upload_to_youtube(script_data, video_path)

    # 完了ログ
    save_log(script_data, review_result, status="uploaded", video_url=video_url)

    print("\n" + "=" * 50)
    print("✅ パイプライン完了！")
    print(f"動画URL: {video_url}")
    print(f"タイトル: {script_data['title']}")
    print(f"スコア: {review_result['score']['total']:.1f}点")
    print("=" * 50)


def improve_script(script_data: dict, feedback: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    print("[台本改善] レビューフィードバックをもとに台本を改善中...")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=6000,
        messages=[{
            "role": "user",
            "content": f"""以下の台本をレビューフィードバックをもとに改善してください。

【元の台本タイトル】
{script_data['title']}

【元の台本】
{script_data['script']}

【レビューフィードバック】
{feedback}

改善した台本をJSONで返してください。
必ず以下の形式で返してください：
{{"title": "タイトル", "script": "改善した台本本文（記号なし・ナレーション文章のみ）"}}

重要：scriptはナレーターが読む文章のみ。記号・見出し・演出メモは不要。5000文字以内。""",
        }],
    )

    text = response.content[0].text
    try:
        text = text.replace("```json", "").replace("```", "").strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        improved = json.loads(text[start:end])
        if improved.get("script"):
            import re
            script = improved["script"]
            script = re.sub(r"[☆◆●■▶︎①②③④⑤]", "", script)
            script = re.sub(r"【[^】]*】", "", script)
            script = script[:5000]
            script_data["script"] = script
            print(f"[台本改善完了] 文字数: {len(script)}")
        if improved.get("title"):
            script_data["title"] = improved["title"]
    except Exception as e:
        print(f"[台本改善エラー] {e} → 元の台本を使用")

    return script_data


def save_log(script_data: dict, review_result, status: str, video_url: str = None):
    os.makedirs("logs", exist_ok=True)
    log = {
        "date": datetime.now().isoformat(),
        "status": status,
        "title": script_data.get("title", ""),
        "score": review_result["score"]["total"] if review_result else 0,
        "verdict": review_result["verdict"] if review_result else "",
        "video_url": video_url,
    }
    filename = f"logs/log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"[ログ保存] {filename}")


if __name__ == "__main__":
    theme = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline(theme)
