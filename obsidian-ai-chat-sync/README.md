# Obsidian AI Chat Sync

Claude / ChatGPT / Gemini のチャット履歴を **Obsidian の Markdown ノートに自動変換**し、
サービス別インデックス（MOC）からリンクする仕組みです。

> ⚠️ **重要**: Claude / ChatGPT / Gemini には「チャット履歴を取得できる公開 API」が
> ありません。そのため本ツールは、各サービスの**公式エクスポート機能**で書き出した
> データを入力として使います（これが最も確実で安全な自動連携方法です）。

## 1. エクスポートを取得する

| サービス | 取得方法 | 出力ファイル |
|---|---|---|
| **ChatGPT** | 設定 → データコントロール → データのエクスポート | `conversations.json` |
| **Claude**  | Settings → Account → Export data | `conversations.json` |
| **Gemini**  | [Google Takeout](https://takeout.google.com/) → 「マイ アクティビティ」→ Gemini、形式を **JSON** に | `MyActivity.json` |

## 2. ファイルを配置する

`exports/` フォルダに入れます。ファイル名にサービス名を含めると判定が確実です：

```
exports/
├── claude_conversations.json
├── chatgpt_conversations.json
└── MyActivity.json          # Gemini (Takeout)
```

## 3. 実行する

```bash
python3 sync_chats.py --input ./exports --vault /path/to/ObsidianVault
```

- `--input` … エクスポート JSON の置き場所（既定 `./exports`）
- `--vault` … 出力先 Obsidian vault（既定 `./vault`）

## 4. 生成されるもの

```
<vault>/AI Chats/
├── AI Chats.md          # 全体トップ MOC
├── Claude.md            # Claude インデックス（新しい順）
├── ChatGPT.md
├── Gemini.md
├── Claude/<タイトル>.md   # 会話ごとのノート
├── ChatGPT/<タイトル>.md
└── Gemini/<タイトル>.md
```

各ノートには frontmatter（`service` / `created` / `source` / `tags`）が付き、
Obsidian のグラフビューやタグ検索でそのまま活用できます。Claude のノートには
元の会話 URL へのリンクも含まれます。

## 自動化（定期実行）

エクスポートを更新したら再実行するだけで差分が追加されます（同名は `(2)` で重複回避）。
cron で定期化する例：

```bash
# 毎日 8:00 に同期
0 8 * * * cd /path/to/obsidian-ai-chat-sync && python3 sync_chats.py --vault /path/to/ObsidianVault
```

> エクスポート自体の取得は各サービスとも手動操作（またはメール待ち）が必要なため、
> 「エクスポート JSON を `exports/` に置く」までが手作業、それ以降が自動です。

## 依存

Python 3.9+ のみ（標準ライブラリだけで動作します）。
