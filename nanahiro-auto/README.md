# 人生は七色 - 自動投稿パイプライン

YouTube チャンネル「人生は七色」の毎日自動投稿システムです。

## 全体の流れ

```
① 台本生成（Claude API）
↓
② 品質チェック（7人レビューアー × 最大3ループ）
↓
③ 音声生成（ElevenLabs API）
↓
④ 動画合成（Pexels + FFmpeg）
↓
⑤ YouTube投稿（YouTube Data API）
```

## セットアップ

### 1. GitHub Secrets に以下を登録

| キー名 | 内容 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude APIキー |
| `ELEVENLABS_API_KEY` | ElevenLabs APIキー |
| `ELEVENLABS_VOICE_ID` | 使用するボイスのID |
| `PEXELS_API_KEY` | Pexels APIキー（無料） |
| `YOUTUBE_CREDENTIALS` | YouTube OAuth2認証情報（JSON） |

### 2. GitHub Secrets の設定方法

1. GitHubのリポジトリページを開く
2. `Settings` → `Secrets and variables` → `Actions`
3. `New repository secret` をクリック
4. 各キーを登録

### 3. ElevenLabsのボイスIDを確認

```bash
pip install -r requirements.txt
ELEVENLABS_API_KEY=your_key python scripts/generate_voice.py
```

出力されたボイス一覧からお好みのIDを `ELEVENLABS_VOICE_ID` に設定。

### 4. YouTube認証情報の取得

1. [Google Cloud Console](https://console.cloud.google.com) でプロジェクト作成
2. YouTube Data API v3 を有効化
3. OAuth 2.0 クライアントIDを作成
4. 認証情報をJSON形式で `YOUTUBE_CREDENTIALS` に設定

## 手動実行

GitHub の `Actions` タブ → `毎日自動投稿` → `Run workflow`

## 自動実行スケジュール

毎日 **日本時間 20:00** に自動実行されます。

## ログ確認

実行後、`Actions` タブから実行ログとアーティファクトを確認できます。

## 7人レビューシステム

| # | レビューアー | 役割 | 重み |
|---|---|---|---|
| ① | 30代会社員・男性 | 冒頭・テンポチェック | 1.2 |
| ② | 50代主婦 | 感動の深さ | 1.5 |
| ③ | 20代大学生 | 耐久テスト | 0.8 |
| ④ | 感動系ヘビーユーザー | 既視感チェック | 1.3 |
| ⑤ | 懐疑的な視聴者 | 嘘くさチェック | 1.0 |
| ⑥ | YouTube構成担当 | 構成チェック | 1.2 |
| ⑦ | プロ編集者 | 最終判定（×5倍） | 5.0 |

合格条件：スコア105点以上 かつ ⑦が「投稿OK」判定
