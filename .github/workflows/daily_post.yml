name: 毎日自動投稿

on:
  schedule:
    - cron: "0 11 * * *"
  workflow_dispatch:

jobs:
  auto-post:
    runs-on: ubuntu-latest
    timeout-minutes: 90

    steps:
      - name: リポジトリをチェックアウト
        uses: actions/checkout@v4

      - name: Python 3.11 をセットアップ
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: 依存ライブラリをインストール
        run: |
          pip install -r nanahiro-auto/requirements.txt
          sudo apt-get update && sudo apt-get install -y ffmpeg imagemagick
          sudo sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml

      - name: パイプライン実行
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          ELEVENLABS_API_KEY: ${{ secrets.ELEVENLABS_API_KEY }}
          ELEVENLABS_VOICE_ID: ${{ secrets.ELEVENLABS_VOICE_ID }}
          PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY }}
          YOUTUBE_CREDENTIALS: ${{ secrets.YOUTUBE_CREDENTIALS }}
        run: |
          cd nanahiro-auto/scripts
          python main.py

      - name: ログを保存
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: pipeline-logs-${{ github.run_number }}
          path: |
            nanahiro-auto/logs/
            nanahiro-auto/output/*.json
          retention-days: 30
