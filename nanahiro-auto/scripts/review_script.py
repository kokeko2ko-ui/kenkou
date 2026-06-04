import anthropic
import os
import json

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

REVIEWERS = [
    {"id": 1, "name": "30代会社員・男性（倍速視聴）", "role": "guide", "weight": 1.2},
    {"id": 2, "name": "50代主婦（感動・共感層）", "role": "guide", "weight": 1.5},
    {"id": 3, "name": "20代大学生（即離脱テスト）", "role": "guide", "weight": 0.8},
    {"id": 4, "name": "感動系YouTubeヘビーユーザー", "role": "guide", "weight": 1.3},
    {"id": 5, "name": "感動に懐疑的な視聴者", "role": "guide", "weight": 1.0},
    {"id": 6, "name": "YouTube構成担当", "role": "guide", "weight": 1.2},
    {"id": 7, "name": "プロ編集者・最終判定", "role": "judge", "weight": 5.0},
]

GUIDE_PROMPT = """あなたは「{name}」として台本を評価します。
以下のJSONのみを返してください。他の文章は不要です。

{{"stars": 評価点数(1-5の整数), "feedback": "50文字以内の評価"}}

台本タイトル：{title}
台本：
{script}"""

JUDGE_PROMPT = """あなたは感動系YouTube動画のプロ編集者です。台本を総合評価してください。
以下のJSONのみを返してください。他の文章は不要です。

{{"stars": 評価点数(1-5の整数), "verdict": "投稿OK", "feedback": "100文字以内の総評", "improvements": ["改善点1", "改善点2"]}}

台本タイトル：{title}
台本：
{script}"""

ACTION_BONUS = 3
PASS_SCORE = 50  # main.py と合わせる（最高約65点）


def review_script(script_data: dict) -> dict:
    script_text = script_data.get("script", "")
    title = script_data.get("title", "")
    print(f"[レビュー開始] {title}")
    print(f"[レビュー] 台本文字数: {len(script_text)}文字")

    results = []
    for reviewer in REVIEWERS:
        print(f"  [{reviewer['id']}] {reviewer['name']} 採点中...")

        if reviewer["role"] == "judge":
            prompt = JUDGE_PROMPT.format(name=reviewer["name"], title=title, script=script_text)
        else:
            prompt = GUIDE_PROMPT.format(name=reviewer["name"], title=title, script=script_text)

        for attempt in range(3):
            try:
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300,
                    system="JSONのみで回答してください。```json などのコードブロックは使わないでください。",
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                text = text.replace("```json", "").replace("```", "").strip()
                start = text.find("{")
                end = text.rfind("}") + 1
                if start < 0:
                    raise ValueError("JSONが見つかりません")
                data = json.loads(text[start:end])
                data["stars"] = int(data.get("stars", 3))
                data.update({
                    "reviewer_id": reviewer["id"],
                    "reviewer_name": reviewer["name"],
                    "weight": reviewer["weight"],
                    "role": reviewer["role"],
                })
                results.append(data)
                print(f"  [{reviewer['id']}] ★{data['stars']}")
                break
            except Exception as e:
                if attempt == 2:
                    print(f"  [{reviewer['id']}] 3回失敗 → デフォルト3点")
                    results.append(_default_result(reviewer))

    score = calculate_score(results)
    judge = next((r for r in results if r["role"] == "judge"), None)
    verdict = judge.get("verdict", "投稿OK") if judge else "投稿OK"

    # ✅ バグ修正①：合格ラインを PASS_SCORE=50 に統一
    passed = score["total"] >= PASS_SCORE and verdict == "投稿OK"

    print(f"\n[採点結果] {score['total']:.1f}/{score['max_possible']:.1f}点 | {verdict} | {'✅合格' if passed else '❌不合格'}")
    return {
        "passed": passed,
        "score": score,
        "verdict": verdict,
        "results": results,
        "improvements": judge.get("improvements", []) if judge else [],
    }


def _default_result(reviewer: dict) -> dict:
    return {
        "reviewer_id": reviewer["id"],
        "reviewer_name": reviewer["name"],
        "weight": reviewer["weight"],
        "role": reviewer["role"],
        "stars": 3,
        "feedback": "採点エラー（デフォルト）",
        "verdict": "投稿OK" if reviewer["role"] == "judge" else None,
        "improvements": [],
    }


def calculate_score(results: list) -> dict:
    total = ACTION_BONUS
    # 最高スコア計算（全員★5の場合）
    max_possible = ACTION_BONUS + sum(5 * r["weight"] for r in REVIEWERS)
    breakdown = {}
    for r in results:
        stars = int(r.get("stars", 3))
        points = stars * r["weight"]
        total += points
        breakdown[r["reviewer_name"]] = {"stars": stars, "weight": r["weight"], "points": points}
    return {
        "total": round(total, 1),
        "max_possible": round(max_possible, 1),
        "breakdown": breakdown,
        "action_bonus": ACTION_BONUS,
    }


def get_improvement_feedback(results: list) -> str:
    # ✅ バグ修正②：dropout_points → feedback フィールドを使う
    guides = sorted(
        [r for r in results if r["role"] == "guide"],
        key=lambda x: x.get("stars", 3)
    )[:3]  # 低評価3人のフィードバックを使う

    parts = []
    for r in guides:
        fb = r.get("feedback", "")
        if fb and fb != "採点エラー（デフォルト）":
            parts.append(f"【{r['reviewer_name']}（★{r.get('stars',3)}）】\n- {fb}")

    judge = next((r for r in results if r["role"] == "judge"), None)
    if judge and judge.get("improvements"):
        parts.append("【編集者指示】\n" + "\n".join(f"- {i}" for i in judge["improvements"]))

    return "\n\n".join(parts)
