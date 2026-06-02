import anthropic
import os
import json

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

REVIEWERS = [
    {
        "id": 1,
        "name": "30代会社員・男性（倍速視聴）",
        "role": "guide",
        "weight": 1.2,
        "prompt": """あなたは30代の会社員男性です。毎朝の通勤電車でYouTubeを1.5倍速で見ています。
忙しいので、テンポが遅いとすぐ飛ばします。

この台本を読んで、以下を教えてください：
1. 何秒目・どのセリフで「飛ばしたくなった」か（具体的に）
2. 冒頭15秒で引き込まれたか
3. 1.5倍速で追いつけないテンポの鈍化箇所

星1〜5で評価し、必ず「離脱しそうな箇所」を具体的なセリフで指摘してください。
JSON形式で返してください：{"stars": 数字, "dropout_points": ["箇所1", ...], "feedback": "総評"}""",
    },
    {
        "id": 2,
        "name": "50代主婦（感動・共感層）",
        "role": "guide",
        "weight": 1.5,
        "prompt": """あなたは50代の主婦です。家族・努力・人生逆転の話に強く感情移入します。
このチャンネルのメインターゲットです。

この台本を読んで、以下を教えてください：
1. 感情移入が切れた瞬間（どのセリフで「あれ？」と思ったか）
2. 涙が出そうになった場面
3. 「家族に話したい」と思ったか

星1〜5で評価し、感動が薄れた箇所を具体的に指摘してください。
JSON形式で返してください：{"stars": 数字, "dropout_points": ["箇所1", ...], "feedback": "総評"}""",
    },
    {
        "id": 3,
        "name": "20代大学生（即離脱テスト）",
        "role": "guide",
        "weight": 0.8,
        "prompt": """あなたは20代の大学生です。動画のテンポが少しでも遅いと即離脱します。
TikTokやReels世代です。

この台本を読んで、冗長だと感じた箇所を秒数・セリフで具体的に教えてください。
「ここいらない」「ここ長い」という感覚を正直に。

星1〜5で評価してください。
JSON形式で返してください：{"stars": 数字, "dropout_points": ["箇所1", ...], "feedback": "総評"}""",
    },
    {
        "id": 4,
        "name": "感動系YouTubeヘビーユーザー",
        "role": "guide",
        "weight": 1.3,
        "prompt": """あなたは感動系YouTubeを毎日何本も見ているヘビーユーザーです。
似たような動画を大量に見ているので、「またこのパターン」とすぐわかります。

この台本を読んで、以下を教えてください：
1. 「これ見たことある」と感じた既視感のある展開
2. ベタすぎて感動できなかった場面
3. 「このチャンネルらしい」と感じた独自性

星1〜5で評価してください。
JSON形式で返してください：{"stars": 数字, "dropout_points": ["箇所1", ...], "feedback": "総評"}""",
    },
    {
        "id": 5,
        "name": "感動に懐疑的な視聴者",
        "role": "guide",
        "weight": 1.0,
        "prompt": """あなたは感動系動画に懐疑的な視聴者です。
「嘘くさい」「泣かせに来てる」「作り物っぽい」をすぐ見抜きます。

この台本を読んで、以下を正直に教えてください：
1. 「嘘くさい」と感じた瞬間
2. 「泣かせようとしてる感」が出ていた箇所
3. ご都合展開・不自然な展開

星1〜5で評価してください。
JSON形式で返してください：{"stars": 数字, "dropout_points": ["箇所1", ...], "feedback": "総評"}""",
    },
    {
        "id": 6,
        "name": "YouTube構成担当",
        "role": "guide",
        "weight": 1.2,
        "prompt": """あなたはYouTubeの動画構成のプロです。
フック・山場・転機・余韻・CTAの流れを専門的に評価します。

この台本を読んで、以下を教えてください：
1. フックが機能していない箇所
2. 山場・転機の配置が弱い箇所
3. CTAが不自然な箇所
4. 離脱防止フックが弱い箇所

星1〜5で評価してください。
JSON形式で返してください：{"stars": 数字, "dropout_points": ["箇所1", ...], "feedback": "総評"}""",
    },
    {
        "id": 7,
        "name": "プロ編集者・最終判定",
        "role": "judge",
        "weight": 5.0,
        "prompt": """あなたは感動系YouTube動画の敏腕プロ編集者です。
動画全体の完成度を最終判定します。

この台本を読んで、総合的に評価してください：
1. 投稿していいか（OK / 要修正 / 再生成）
2. 最も改善すべき点（1〜3点）
3. 良かった点

★1〜5で評価し、必ず「投稿OK」「要修正」「再生成」のいずれかを明示してください。
JSON形式で返してください：
{"stars": 数字, "verdict": "投稿OK|要修正|再生成", "improvements": ["改善点1", ...], "strengths": ["良い点1", ...], "feedback": "総評"}""",
    },
]

ACTION_BONUS = 3


def review_script(script_data: dict) -> dict:
    script_text = script_data.get("script", "")
    title = script_data.get("title", "")

    print(f"[レビュー開始] タイトル: {title}")
    print(f"[レビュー] 7人のレビューアーが採点中...")

    results = []
    for reviewer in REVIEWERS:
        print(f"  [{reviewer['id']}] {reviewer['name']} 採点中...")
        try:
            response = client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": f"{reviewer['prompt']}\n\n---\n台本タイトル：{title}\n\n{script_text[:6000]}",
                    }
                ],
            )
            text = response.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            data = json.loads(text[start:end])
            data["reviewer_id"] = reviewer["id"]
            data["reviewer_name"] = reviewer["name"]
            data["weight"] = reviewer["weight"]
            data["role"] = reviewer["role"]
            results.append(data)
            print(f"  [{reviewer['id']}] ★{data['stars']} - {data.get('feedback','')[:50]}...")
        except Exception as e:
            print(f"  [{reviewer['id']}] エラー: {e}")
            results.append({
                "reviewer_id": reviewer["id"],
                "reviewer_name": reviewer["name"],
                "weight": reviewer["weight"],
                "role": reviewer["role"],
                "stars": 3,
                "dropout_points": [],
                "feedback": "採点エラー",
            })

    score = calculate_score(results)
    judge = next((r for r in results if r["role"] == "judge"), None)
    verdict = judge.get("verdict", "要修正") if judge else "要修正"

    passed = score["total"] >= 105 and verdict == "投稿OK"

    print(f"\n[採点結果]")
    print(f"  合計スコア: {score['total']:.1f} / 125点")
    print(f"  最終判定: {verdict}")
    print(f"  合否: {'✅ 合格' if passed else '❌ 不合格'}")

    return {
        "passed": passed,
        "score": score,
        "verdict": verdict,
        "results": results,
        "improvements": judge.get("improvements", []) if judge else [],
    }


def calculate_score(results: list) -> dict:
    total = ACTION_BONUS
    breakdown = {}

    for r in results:
        points = r["stars"] * r["weight"]
        total += points
        breakdown[r["reviewer_name"]] = {
            "stars": r["stars"],
            "weight": r["weight"],
            "points": points,
        }

    return {"total": round(total, 1), "breakdown": breakdown, "action_bonus": ACTION_BONUS}


def get_improvement_feedback(results: list) -> str:
    low_reviewers = sorted(
        [r for r in results if r["role"] == "guide"],
        key=lambda x: x["stars"]
    )[:2]

    feedback_parts = []
    for r in low_reviewers:
        points = r.get("dropout_points", [])
        if points:
            feedback_parts.append(
                f"【{r['reviewer_name']}からの指摘】\n" + "\n".join(f"- {p}" for p in points)
            )

    judge = next((r for r in results if r["role"] == "judge"), None)
    if judge:
        improvements = judge.get("improvements", [])
        if improvements:
            feedback_parts.append(
                "【プロ編集者からの改善指示】\n" + "\n".join(f"- {i}" for i in improvements)
            )

    return "\n\n".join(feedback_parts)


if __name__ == "__main__":
    sample = {
        "title": "テスト台本【実話・感動】",
        "script": "これはテスト用の台本です。" * 100,
    }
    result = review_script(sample)
    print(json.dumps(result["score"], ensure_ascii=False, indent=2))
