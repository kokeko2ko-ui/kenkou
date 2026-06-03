import anthropic
import os
import json

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

REVIEWERS = [
    {"id": 1, "name": "30代会社員・男性（倍速視聴）", "role": "guide", "weight": 1.2,
     "prompt": "あなたは30代の会社員男性です。通勤中に1.5倍速でYouTubeを見ています。この台本を読んで、冒頭15秒で引き込まれるか、テンポが鈍い箇所を教えてください。必ずJSON形式のみで返してください。{\"stars\": 数字, \"dropout_points\": [\"箇所\"], \"feedback\": \"総評\"}"},
    {"id": 2, "name": "50代主婦（感動・共感層）", "role": "guide", "weight": 1.5,
     "prompt": "あなたは50代の主婦です。家族・努力・逆転の話に感情移入します。感動できるか評価してください。必ずJSON形式のみで返してください。{\"stars\": 数字, \"dropout_points\": [\"箇所\"], \"feedback\": \"総評\"}"},
    {"id": 3, "name": "20代大学生（即離脱テスト）", "role": "guide", "weight": 0.8,
     "prompt": "あなたは20代の大学生です。テンポが遅いと即離脱します。冗長な箇所を教えてください。必ずJSON形式のみで返してください。{\"stars\": 数字, \"dropout_points\": [\"箇所\"], \"feedback\": \"総評\"}"},
    {"id": 4, "name": "感動系YouTubeヘビーユーザー", "role": "guide", "weight": 1.3,
     "prompt": "あなたは感動系YouTubeを毎日見ています。既視感やベタな展開を指摘してください。必ずJSON形式のみで返してください。{\"stars\": 数字, \"dropout_points\": [\"箇所\"], \"feedback\": \"総評\"}"},
    {"id": 5, "name": "感動に懐疑的な視聴者", "role": "guide", "weight": 1.0,
     "prompt": "あなたは感動系動画に懐疑的です。嘘くさい箇所を指摘してください。必ずJSON形式のみで返してください。{\"stars\": 数字, \"dropout_points\": [\"箇所\"], \"feedback\": \"総評\"}"},
    {"id": 6, "name": "YouTube構成担当", "role": "guide", "weight": 1.2,
     "prompt": "あなたはYouTube動画構成のプロです。フック・山場・転機・余韻・CTAを評価してください。必ずJSON形式のみで返してください。{\"stars\": 数字, \"dropout_points\": [\"箇所\"], \"feedback\": \"総評\"}"},
    {"id": 7, "name": "プロ編集者・最終判定", "role": "judge", "weight": 5.0,
     "prompt": "あなたは感動系YouTube動画のプロ編集者です。総合評価してください。必ずJSON形式のみで返してください。{\"stars\": 数字, \"verdict\": \"投稿OK\", \"improvements\": [\"改善点\"], \"strengths\": [\"良い点\"], \"feedback\": \"総評\"}"},
]

ACTION_BONUS = 3


def review_script(script_data: dict) -> dict:
    script_text = script_data.get("script", "")
    title = script_data.get("title", "")
    print(f"[レビュー開始] タイトル: {title}")

    results = []
    for reviewer in REVIEWERS:
        print(f"  [{reviewer['id']}] {reviewer['name']} 採点中...")
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                system="JSONのみで回答してください。説明文や前置きは不要です。",
                messages=[{"role": "user", "content": f"{reviewer['prompt']}\n\n台本：{script_text[:3000]}"}],
            )
            text = response.content[0].text.strip()
            start = text.find("{")
            end = text.rfind("}") + 1
            data = json.loads(text[start:end]) if start >= 0 else {}
            data.update({"reviewer_id": reviewer["id"], "reviewer_name": reviewer["name"],
                         "weight": reviewer["weight"], "role": reviewer["role"]})
            if isinstance(data.get("stars"), str):
                data["stars"] = int(data["stars"])
            results.append(data)
            print(f"  [{reviewer['id']}] ★{data.get('stars',3)}")
        except Exception as e:
            print(f"  [{reviewer['id']}] エラー: {e} → デフォルト3点")
            results.append({"reviewer_id": reviewer["id"], "reviewer_name": reviewer["name"],
                            "weight": reviewer["weight"], "role": reviewer["role"], "stars": 3,
                            "dropout_points": [], "feedback": "採点エラー",
                            "verdict": "投稿OK" if reviewer["role"] == "judge" else None,
                            "improvements": [], "strengths": []})

    score = calculate_score(results)
    judge = next((r for r in results if r["role"] == "judge"), None)
    verdict = judge.get("verdict", "投稿OK") if judge else "投稿OK"
    passed = score["total"] >= 105 and verdict == "投稿OK"

    print(f"\n[採点結果] {score['total']:.1f}/125点 | {verdict} | {'✅合格' if passed else '❌不合格'}")
    return {"passed": passed, "score": score, "verdict": verdict, "results": results,
            "improvements": judge.get("improvements", []) if judge else []}


def calculate_score(results):
    total = ACTION_BONUS
    breakdown = {}
    for r in results:
        stars = r.get("stars", 3)
        try:
            stars = int(stars)
        except:
            stars = 3
        points = stars * r["weight"]
        total += points
        breakdown[r["reviewer_name"]] = {"stars": stars, "weight": r["weight"], "points": points}
    return {"total": round(total, 1), "breakdown": breakdown, "action_bonus": ACTION_BONUS}


def get_improvement_feedback(results):
    low = sorted([r for r in results if r["role"] == "guide"], key=lambda x: x.get("stars", 3))[:2]
    parts = []
    for r in low:
        pts = r.get("dropout_points", [])
        if pts:
            parts.append(f"【{r['reviewer_name']}】\n" + "\n".join(f"- {p}" for p in pts))
    judge = next((r for r in results if r["role"] == "judge"), None)
    if judge and judge.get("improvements"):
        parts.append("【編集者指示】\n" + "\n".join(f"- {i}" for i in judge["improvements"]))
    return "\n\n".join(parts)
