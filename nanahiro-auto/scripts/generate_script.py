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

【重要】台本（script）はナレーターが読み上げる文章のみを書いてください。
- 記号（☆、◆、●など）は一切使わない
- 【フック】【背景】などの見出しは一切書かない
- 演出メモ・ト書きは一切書かない
- ナレーターが声に出して読む文章だけを書く
- 句読点は「。」「、」のみ使用

【チャンネルスタイル】
- 第三者視点でナレーション
- 高齢者・主婦層をメインターゲット
- 冒頭は謎めいた場面描写から始める（説明ゼロ）
- 台本は5000文字以内

【構成】
冒頭（約500文字）：謎の場面描写。何が起きているかわからない状態から始める
背景（約1500文字）：主人公の日常・転落前の様子
試練（約1500文字）：苦労・屈辱・葛藤
真実（約1000文字）：感情のピーク。知られざる事実の発覚
余韻（約500文字）：静かな締め＋CTA

【締め文言（必ず最後に入れる）】
このチャンネルでは、忙しい毎日の中で忘れかけている大切なことをお届けしています。チャンネル登録とベルマークで、次の話もあなたのもとに届けます。それではまた、心に響くお話でお会いしましょう。

出力はJSON形式で返してください：
{
  "title": "タイトル【実話・感動】",
  "subtitle": "サブ案【実話】",
  "theme": "テーマ",
  "script": "ナレーション本文のみ（記号・見出しなし・5000文字以内）",
  "tags": ["タグ1", "タグ2",...（30個）],
  "description": "YouTube説明文",
  "thumbnail_prompt": "サムネイルプロンプト（日本語）"
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
            "content": f"テーマ「{theme}」で台本を作成してください。海外実話ベースで日本人向けにアレンジ。ナレーション本文のみ・記号なし・5000文字以内。必ずJSON形式で返してください。",
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

    # 記号・見出しを除去
    import re
    script = data.get("script", "")
    script = re.sub(r"[☆◆●■▶︎①②③④⑤]", "", script)
    script = re.sub(r"【[^】]*】", "", script)
    script = re.sub(r"〈[^〉]*〉", "", script)
    script = re.sub(r"\n{3,}", "\n\n", script)
    script = script.strip()

    # 5000文字を超えていたらトリム
    if len(script) > 5000:
        script = script[:5000]
        print(f"[台本生成] 5000文字を超えたためトリムしました")

    data["script"] = script
    data["generated_at"] = datetime.now().isoformat()
    data["theme_selected"] = theme

    os.makedirs("output", exist_ok=True)
    filename = f"output/script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[台本生成完了] 文字数: {len(data['script'])} | 保存先: {filename}")
    print(f"[台本冒頭] {data['script'][:100]}")
    return data


if __name__ == "__main__":
    result = generate_script()
    print(f"タイトル: {result['title']}")
    print(f"文字数: {len(result['script'])}")
    print(f"冒頭: {result['script'][:200]}")
