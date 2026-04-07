# 商圏分析ツール

飲食店出店検討者向けの商圏分析ツール。住所を入力すると、商圏内の人口・競合・駅情報を集約し、6業態の出店適性スコアを算出します。

## 機能

- 商圏内の **人口・年齢構成・世帯数**（e-Stat 500mメッシュ）
- **競合店舗** の分布と業態別カウント（OpenStreetMap）
- **最寄り駅** 3件と事業者情報（OpenStreetMap）
- **公示地価**（不動産情報ライブラリAPI）
- 6業態（居酒屋／カフェ／ラーメン／定食・ファミレス／フレンチ・イタリアン／焼肉）の **出店適性スコア**
- 複数候補地の **比較レーダーチャート**
- **PDFレポート** 出力

## セットアップ

```bash
# 1. 仮想環境作成
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Mac/Linux

# 2. 依存パッケージインストール
pip install -r requirements.txt

# 3. 環境変数ファイル作成
copy env.example .env  # Windows
# cp env.example .env  # Mac/Linux

# 4. .envにAPIキーを設定（下記参照）

# 5. 起動
streamlit run app.py
```

## APIキー設定

### e-Stat API（必須 — 人口データ）
1. https://www.e-stat.go.jp/api/ でユーザー登録（無料）
2. アプリケーションIDを発行
3. `.env` の `ESTAT_APP_ID` に設定

### 不動産情報ライブラリAPI（任意 — 公示地価）
1. https://www.reinfolib.mlit.go.jp/api/request/ で利用申請（無料、発行まで約5営業日）
2. `.env` の `REINFOLIB_API_KEY` に設定

## デプロイ（Streamlit Community Cloud）

1. GitHubにリポジトリをpush
2. https://share.streamlit.io/ でGitHubリポジトリを接続
3. Secrets設定で `ESTAT_APP_ID` を登録
4. デプロイ完了後、共有URLを取得
