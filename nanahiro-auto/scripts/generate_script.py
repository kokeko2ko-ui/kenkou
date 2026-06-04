import anthropic
import os
import json
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

THEMES = [
    "親子の絆・知られざる犠牲",
    "スポーツ逆転劇・見捨てられた選手の復活",
    "見下され逆転・無名の献身",
    "命・生死の選択・臓器提供",
    "老人・弱者が社会を動かす",
    "手紙・日記の発見・死後の真実",
    "奇跡・運命の逆転",
]

SYSTEM_PROMPT = """あなたは感動系YouTubeチャンネル「人生は七色」の台本ライターです。
顔出しなし・ナレーション読み上げ型の動画台本を作成します。

【チャンネルスタイル】
- 第三者視点でナレーション
- 高齢者・主婦層をメインターゲット
- 冒頭は「侮辱・見下し・絶望」から始まる逆転構造
- 台本は5000文字以内で作成すること（厳守）

【台本構成（5段階）】
①フック（〜1分）：音・映像描写のみ。謎の提示
②背景（2〜3分）：主人公の日常・転落前
③試練・選択（3〜4分）：感情の谷。苦労・屈辱
④真実の発覚（2〜3分）：感情の頂点
⑤余韻・締め（1〜2分）：視聴者への語りかけ＋CTA

【必須要素】
- 感情ピーク3か所
- 離脱防止フック3か所
- 具体的な数字・固有名詞・五感の描写
- テーマを直接言わない

【締め文言（固定）】
このチャンネルでは、忙しい毎日の中で忘れかけている「大切なこと」をお届けしています。
チャンネル登録とベルマークで、次の話もあなたのもとに届けます。

出力はJSON形式で返してください：
{
  "title": "タイトル【実話・感動】",
  "subtitle": "サブ案【実話】",
  "theme": "テーマ",
  "script": "台本本文（5000文字以内）",
  "tags": ["タグ1"...（30個）],
  "description": "YouTube説明文",
  "thumbnail_prompt": "サムネイルプロンプト"
}"""


def generate_script(theme: str = None) -> dict:
    if not theme:
        import random
        theme = random.choice(THEMES)

    print(f"[台本生成] テーマ: {theme}")

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"テーマ「{theme}」で台本を作成してください。海外実話ベースで日本人向けにアレンジ。5000文字以内で。必ずJSON形式で返してください。",
        }],
    )

    text = response.content[0].text
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        data = json.loads(text[start:end])
    except Exception as e:
        print(f"[警告] JSONパース失敗: {e}")
        data = {
            "title": f"{theme}の物語【実話・感動】",
            "subtitle": f"{theme}【実話】",
            "theme": theme,
            "script": text,
            "tags": [],
            "description": "",
            "thumbnail_prompt": "",
        }

    # 5000文字を超えていたらトリム
    if len(data.get("script", "")) > 5000:
        data["script"] = data["script"][:5000]
        print(f"[台本生成] 5000文字を超えたためトリムしました")

    data["generated_at"] = datetime.now().isoformat()
    data["theme_selected"] = theme

    os.makedirs("output", exist_ok=True)
    filename = f"output/script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[台本生成完了] 文字数: {len(data['script'])} | 保存先: {filename}")
    return data


if __name__ == "__main__":
    result = generate_script()
    print(f"タイトル: {result['title']}")
    print(f"文字数: {len(result['script'])}")
