#!/usr/bin/env python3
"""
Obsidian AI Chat Sync
=====================

Claude / ChatGPT / Gemini のチャット履歴を Obsidian の Markdown ノートに変換し、
サービス別のインデックス（MOC = Map of Content）からリンクする自動連携スクリプト。

各サービスには会話履歴を取得する公開 API が無いため、公式エクスポート機能で
書き出したファイルを入力として使います。

入力ファイルの置き場所（--input フォルダ、既定 ./exports）:
  - ChatGPT : conversations.json     (設定 → データのエクスポート)
  - Claude  : conversations.json     (設定 → データのエクスポート) ※ファイル名に "claude" を含めると確実
  - Gemini  : MyActivity.json        (Google Takeout → マイ アクティビティ)

出力（--vault フォルダ、既定 ./vault）:
  - AI Chats/Claude/<タイトル>.md
  - AI Chats/ChatGPT/<タイトル>.md
  - AI Chats/Gemini/<タイトル>.md
  - AI Chats/Claude.md, ChatGPT.md, Gemini.md   (各サービスのインデックス)
  - AI Chats/AI Chats.md                          (全体のトップ MOC)

使い方:
  python sync_chats.py --input ./exports --vault ./vault
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


# ----------------------------------------------------------------------------
# ユーティリティ
# ----------------------------------------------------------------------------

_INVALID = re.compile(r'[\\/:*?"<>|#\^\[\]]+')


def slugify(title: str, fallback: str = "untitled") -> str:
    """ファイル名・Wiki リンクとして安全な文字列に変換する。"""
    title = (title or "").strip()
    title = _INVALID.sub(" ", title)
    title = re.sub(r"\s+", " ", title).strip()
    title = title[:120].strip()
    return title or fallback


def to_iso(ts) -> str:
    """エポック秒 / ISO 文字列を 'YYYY-MM-DD HH:MM' に正規化する。"""
    if ts is None:
        return ""
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError, OverflowError):
        return str(ts)


class Conversation:
    """サービス非依存の会話表現。"""

    def __init__(self, service: str, title: str, created: str, url: str = ""):
        self.service = service
        self.title = title or "Untitled"
        self.created = created
        self.url = url
        self.messages: list[tuple[str, str]] = []  # (role, text)

    def add(self, role: str, text: str) -> None:
        text = (text or "").strip()
        if text:
            self.messages.append((role, text))


# ----------------------------------------------------------------------------
# 各サービスのパーサ
# ----------------------------------------------------------------------------

def parse_chatgpt(data) -> Iterable[Conversation]:
    """ChatGPT の conversations.json をパースする。"""
    for conv in data:
        title = conv.get("title") or "Untitled"
        created = to_iso(conv.get("create_time"))
        c = Conversation("ChatGPT", title, created)

        mapping = conv.get("mapping", {})
        # create_time 順にメッセージを並べる
        nodes = [n for n in mapping.values() if n.get("message")]
        nodes.sort(key=lambda n: n["message"].get("create_time") or 0)
        for node in nodes:
            msg = node["message"]
            role = msg.get("author", {}).get("role", "unknown")
            parts = msg.get("content", {}).get("parts", []) or []
            text = "\n".join(p for p in parts if isinstance(p, str))
            if role == "system" and not text:
                continue
            c.add(role, text)
        if c.messages:
            yield c


def parse_claude(data) -> Iterable[Conversation]:
    """Claude の conversations.json をパースする。"""
    for conv in data:
        title = conv.get("name") or conv.get("title") or "Untitled"
        created = to_iso(conv.get("created_at"))
        uuid = conv.get("uuid", "")
        url = f"https://claude.ai/chat/{uuid}" if uuid else ""
        c = Conversation("Claude", title, created, url)

        for msg in conv.get("chat_messages", []):
            role = msg.get("sender", "unknown")  # "human" / "assistant"
            # 新形式は content[].text、旧形式は text フィールド
            text = msg.get("text", "")
            if not text:
                parts = msg.get("content", []) or []
                text = "\n".join(
                    p.get("text", "") for p in parts if isinstance(p, dict)
                )
            c.add(role, text)
        if c.messages:
            yield c


_TAG = re.compile(r"<[^>]+>")
_HTML_ENT = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
             "&quot;": '"', "&#39;": "'"}


def strip_html(html: str) -> str:
    """safeHtmlItem の HTML を素朴に Markdown 風プレーンテキストへ変換する。"""
    if not html:
        return ""
    html = re.sub(r"</(p|h[1-6]|li|ul|ol)>", "\n", html)
    html = re.sub(r"<li[^>]*>", "- ", html)
    html = re.sub(r"<h[1-6][^>]*>", "### ", html)
    text = _TAG.sub("", html)
    for ent, ch in _HTML_ENT.items():
        text = text.replace(ent, ch)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_gemini(item: dict) -> bool:
    header = (item.get("header", "") or "").lower()
    if "gemini" in header or "bard" in header:
        return True
    return any(
        "gemini" in p.lower() or "bard" in p.lower()
        for p in item.get("products", []) or []
    )


def parse_gemini(data) -> Iterable[Conversation]:
    """Gemini (Google Takeout マイアクティビティ) の JSON をパースする。

    Takeout はスレッドを保持しないため、同じ日付のやり取りを 1 ノートに
    まとめる（プロンプトと safeHtmlItem の応答をセクションとして並べる）。
    """
    # 日付ごとにエントリをまとめる（古い順）
    by_day: dict[str, list[dict]] = {}
    for item in data:
        if not _is_gemini(item):
            continue
        time = item.get("time", "")
        day = str(time)[:10] or "unknown"
        by_day.setdefault(day, []).append(item)

    for day in sorted(by_day):
        items = sorted(by_day[day], key=lambda x: x.get("time", ""))
        # その日の最初のプロンプトをタイトルに添えて見分けやすくする
        first_raw = items[0].get("title", "")
        first_prompt = re.sub(r"^(Prompted|Asked|入力)\s*:?\s*", "", first_raw).strip()
        snippet = first_prompt.split("\n")[0][:30]
        day_title = f"{day}｜{snippet}" if snippet else day
        c = Conversation("Gemini", day_title, to_iso(items[0].get("time")))
        for item in items:
            raw = item.get("title", "")
            prompt = re.sub(r"^(Prompted|Asked|入力)\s*:?\s*", "", raw).strip()
            c.add("human", prompt)
            for sub in item.get("safeHtmlItem", []) or []:
                c.add("assistant", strip_html(sub.get("html", "")))
            for sub in item.get("subtitles", []) or []:
                c.add("assistant", sub.get("name", ""))
        if c.messages:
            yield c


PARSERS = {
    "chatgpt": parse_chatgpt,
    "claude": parse_claude,
    "gemini": parse_gemini,
}


def detect_service(path: Path, data) -> str | None:
    """ファイル名と中身からサービスを推定する。"""
    name = path.name.lower()
    if "claude" in name:
        return "claude"
    if "chatgpt" in name or "openai" in name:
        return "chatgpt"
    if "myactivity" in name or "gemini" in name or "bard" in name:
        return "gemini"

    # 中身で推定
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            if "chat_messages" in first or "uuid" in first:
                return "claude"
            if "mapping" in first:
                return "chatgpt"
            if "header" in first and "title" in first:
                return "gemini"
    return None


# ----------------------------------------------------------------------------
# ノート生成
# ----------------------------------------------------------------------------

ROLE_LABEL = {
    "user": "🧑 User",
    "human": "🧑 User",
    "assistant": "🤖 Assistant",
    "model": "🤖 Assistant",
    "system": "⚙️ System",
}


def write_note(vault: Path, conv: Conversation) -> str:
    """1 会話のノートを書き出し、Wiki リンク用のノート名を返す。"""
    folder = vault / "AI Chats" / conv.service
    folder.mkdir(parents=True, exist_ok=True)

    base = slugify(conv.title)
    note_name = base
    path = folder / f"{base}.md"
    i = 2
    while path.exists():
        note_name = f"{base} ({i})"
        path = folder / f"{note_name}.md"
        i += 1

    lines = ["---"]
    lines.append(f"service: {conv.service}")
    lines.append(f'title: "{conv.title.replace(chr(34), chr(39))}"')
    if conv.created:
        lines.append(f"created: {conv.created}")
    if conv.url:
        lines.append(f"source: {conv.url}")
    lines.append("tags: [ai-chat, " + conv.service.lower() + "]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {conv.title}")
    lines.append("")
    if conv.url:
        lines.append(f"🔗 [元の会話を開く]({conv.url})")
        lines.append("")

    for role, text in conv.messages:
        lines.append(f"## {ROLE_LABEL.get(role, role)}")
        lines.append("")
        lines.append(text)
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return note_name


def write_index(vault: Path, service: str, entries: list[tuple[str, str]]) -> None:
    """サービス別インデックス（新しい順）を書き出す。"""
    folder = vault / "AI Chats"
    folder.mkdir(parents=True, exist_ok=True)
    entries = sorted(entries, key=lambda e: e[1], reverse=True)

    lines = ["---", f"tags: [ai-chat, moc]", "---", "", f"# {service} チャット", ""]
    lines.append(f"全 {len(entries)} 件\n")
    for note_name, created in entries:
        date = f"`{created}` " if created else ""
        lines.append(f"- {date}[[{service}/{note_name}|{note_name}]]")
    lines.append("")
    (folder / f"{service}.md").write_text("\n".join(lines), encoding="utf-8")


def write_top_moc(vault: Path, counts: dict[str, int]) -> None:
    """全体トップの MOC を書き出す。"""
    folder = vault / "AI Chats"
    lines = ["---", "tags: [ai-chat, moc]", "---", "", "# 🤖 AI Chats", ""]
    lines.append("Claude / ChatGPT / Gemini のチャット履歴インデックス。\n")
    for service in ("Claude", "ChatGPT", "Gemini"):
        n = counts.get(service, 0)
        lines.append(f"- [[{service}]] — {n} 件")
    lines.append("")
    lines.append(f"_最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}_")
    (folder / "AI Chats.md").write_text("\n".join(lines), encoding="utf-8")


# ----------------------------------------------------------------------------
# メイン
# ----------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="AI チャット履歴を Obsidian ノートに同期する")
    ap.add_argument("--input", default="./exports", help="エクスポート JSON の置き場所")
    ap.add_argument("--vault", default="./vault", help="出力先 Obsidian vault")
    args = ap.parse_args()

    input_dir = Path(args.input)
    vault = Path(args.vault)

    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)
        print(f"⚠️  入力フォルダを作成しました: {input_dir}")
        print("   各サービスのエクスポート JSON をここに置いて再実行してください。")
        return

    by_service: dict[str, list[tuple[str, str]]] = {
        "Claude": [], "ChatGPT": [], "Gemini": []
    }
    total = 0

    for path in sorted(input_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"❌ 読み込み失敗: {path.name} ({e})")
            continue

        service = detect_service(path, data)
        if not service:
            print(f"⚠️  サービス判定不可、スキップ: {path.name}")
            continue

        print(f"📥 {path.name} → {service}")
        for conv in PARSERS[service](data):
            note_name = write_note(vault, conv)
            by_service[conv.service].append((note_name, conv.created))
            total += 1

    counts = {}
    for service, entries in by_service.items():
        if entries:
            write_index(vault, service, entries)
        counts[service] = len(entries)

    write_top_moc(vault, counts)

    print(f"\n✅ 完了: {total} 件の会話を出力 → {vault / 'AI Chats'}")
    for service, n in counts.items():
        print(f"   - {service}: {n} 件")


if __name__ == "__main__":
    main()
