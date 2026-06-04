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

STAR = "★"
LINE = "=" * 52
THIN = "ー" * 26


def run_pipeline(theme: str = None):
    print(LINE)
    print("「人生は七色」自動投稿パイプライン 開始")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(LINE)

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

    print("\n" + LINE)
    print("✅ パイプライン完了！")
    print(f"動画URL: {video_url}")
    print(f"タイトル: {script_data['title']}")
    print(f"スコア: {review_result['score']['total']:.1f}点")
    print(LINE)


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
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ─── 既存：機械用JSONログ ───
    log = {
        "date": datetime.now().isoformat(),
        "status": status,
        "title": script_data.get("title", ""),
        "script": script_data.get("script", ""),  # 台本全文も保存
        "score": review_result["score"]["total"] if review_result else 0,
        "max_possible": review_result["score"]["max_possible"] if review_result else 0,
        "verdict": review_result["verdict"] if review_result else "",
        "video_url": video_url,
    }
    json_path = f"logs/log_{timestamp}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"[ログ保存] {json_path}")

    # ─── 追加：人間用テキストレポート ───
    txt_path = f"logs/script_{timestamp}.txt"
    _save_human_report(txt_path, script_data, review_result, status, video_url, timestamp)
    print(f"[台本保存] {txt_path}")


def _save_human_report(
    path: str,
    script_data: dict,
    review_result,
    status: str,
    video_url: str,
    timestamp: str,
):
    title = script_data.get("title", "（タイトルなし）")
    script = script_data.get("script", "")
    score_total = review_result["score"]["total"] if review_result else 0
    score_max   = review_result["score"].get("max_possible", 65.0) if review_result else 65.0
    verdict     = review_result["verdict"] if review_result else "ー"
    breakdown   = review_result["score"].get("breakdown", {}) if review_result else {}
    improvements = review_result.get("improvements", []) if review_result else []

    # 判定アイコン
    status_icon = {"uploaded": "✅ 投稿済み", "skipped": "⏭️ スキップ"}.get(status, f"⚠️ {status}")
    verdict_icon = "✅ 投稿OK" if verdict == "投稿OK" else f"❌ {verdict}"

    lines = []
    lines.append(LINE)
    lines.append("🎬  人生は七色 ー 台本レポート")
    lines.append(LINE)
    lines.append(f"📅 日時      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"📝 タイトル  : {title}")
    lines.append(f"📊 スコア    : {score_total:.1f} / {score_max:.1f} 点")
    lines.append(f"🏁 判定      : {verdict_icon}")
    lines.append(f"📌 ステータス: {status_icon}")
    if video_url:
        lines.append(f"🔗 動画URL   : {video_url}")
    lines.append(LINE)

    # 台本全文
    lines.append("")
    lines.append("【台本全文】")
    lines.append(THIN)
    lines.append(script)
    lines.append(THIN)

    # レビュー詳細
    if breakdown:
        lines.append("")
        lines.append("【レビュー詳細】")
        EMOJI = ["①","②","③","④","⑤","⑥","⑦"]
        for i, (name, detail) in enumerate(breakdown.items()):
            stars_str = STAR * detail["stars"] + "☆" * (5 - detail["stars"])
            role_tag = "👑 " if i == 6 else "   "
            lines.append(
                f"{role_tag}{EMOJI[i]} {name:<22}  {stars_str}  "
                f"×{detail['weight']}  → {detail['points']:.1f}点"
            )
            # feedbackがあれば表示（review_resultのresultsから取得）
            if review_result:
                result = next(
                    (r for r in review_result["results"] if r["reviewer_name"] == name), None
                )
                if result and result.get("feedback") and result["feedback"] != "採点エラー（デフォルト）":
                    lines.append(f"       └ {result['feedback']}")

    # 編集者コメント
    if improvements:
        lines.append("")
        lines.append("【編集者コメント】")
        for imp in improvements:
            lines.append(f"  - {imp}")

    lines.append("")
    lines.append(LINE)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    theme = sys.argv[1] if len(sys.argv) > 1 else None
    run_pipeline(theme)
