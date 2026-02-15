# 投資ボット（bitFlyer + 仮想通貨）

年利20%以上を目標に、ニュース・SNS・チャートデータを分析して自動取引を行うシステム。

## 特徴

- **情報収集**: ニュース、Twitter、チャートデータを1時間ごとに収集
- **感情分析**: ニュースとツイートの感情を分析
- **テクニカル分析**: RSI、MACD、移動平均線など
- **機械学習**: 過去の取引結果から学習して勝率を予測
- **自動取引**: bitFlyer APIで自動売買
- **リスク管理**: 損切り、日次損失限度、日次取引数制限
- **通知**: Discordに取引状況を通知

## 目標

- **年利20%以上** を達成（最低目標）
- **勝率55%以上** で取引実行
- **リスクリワード比2:1**
- **利益目標+2.5% / 損切り-1.2%**

## 対象通貨（bitFlyer）

- BTC_JPY: ビットコイン
- ETH_JPY: イーサリアム
- XRP_JPY: リップル
- BCH_JPY: ビットコインキャッシュ
- LTC_JPY: ライトコイン

## 取引戦略

### ボラティリティを活用

仮想通貨の高いボラティリティを活用して、年利20%を達成。

```
1日0.08%（年利20% / 250日）
1日20回の取引なら、1回あたり0.004%の期待値

でも、仮想通貨は±10%動くこともあるから、
より大きな利益も可能！
```

### 取引ルール

| 項目 | 設定値 |
|------|--------|
| 目標勝率 | 55%以上 |
| 利益目標 | +2.5% |
| 損切り | -1.2% |
| 1通貨最大ポジション | 残高の40% |
| 日次最大損失 | 残高の5% |
| 日次最大取引数 | 20回 |

### リスクリワード比2:1

```
利益: +2.5%
損失: -1.2%

1回の勝ちで2回分の負けをカバー！
```

## 年利20%達成のための戦略

### 1. 高頻度取引

- 1時間ごとに実行（24時間/日）
- 1日20回まで取引可能

### 2. ボラティリティ活用

- 仮想通貨は±10%変動することも
- 損切り-1.2%でリスクを最小化
- 利益目標+2.5%で利益を最大化

### 3. 機械学習による勝率予測

- 過去の取引結果から学習
- 勝率55%以上でのみ取引実行

### 4. 分散投資

- 5通貨に分散（BTC、ETH、XRP、BCH、LTC）
- 1通貨最大40%（より分散）

## インストール

### 1. Python環境構築

```bash
cd investment-bot
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. 環境変数設定

`.env.example` を `.env` にコピーして、必要なAPIキーを設定:

```bash
cp .env.example .env
```

`.env` を編集:

```bash
# bitFlyer API
BITFLYER_API_KEY=your_bitflyer_api_key
BITFLYER_API_SECRET=your_bitflyer_api_secret

# X (Twitter) API
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_SECRET=your_twitter_access_secret

# OpenAI API（感情分析用、オプション）
OPENAI_API_KEY=your_openai_api_key

# Discord Webhook（通知用）
DISCORD_WEBHOOK_URL=your_discord_webhook_url
```

### 3. bitFlyer API取得

1. bitFlyerにログイン
2. API利用申請
3. APIキーとAPI Secretを取得

## 使用方法

### ドライランモード（テスト）

実際には注文せず、シミュレーションのみ実行:

```bash
python main.py --dry-run
```

### 本番モード

実際に注文を実行:

```bash
python main.py --live --notify
```

### 通知付き

通知を送る:

```bash
python main.py --dry-run --notify
```

## OpenClaw Cronでの定期実行

OpenClawのcron機能で1時間ごとに実行:

```bash
openclaw cron add --job '{
  "name": "investment-bot-hourly",
  "schedule": {
    "kind": "every",
    "everyMs": 3600000
  },
  "payload": {
    "kind": "agentTurn",
    "message": "cd /Users/yudai/.openclaw/workspace/investment-bot && python main.py --dry-run --notify",
    "model": "zai/glm-4.7"
  },
  "sessionTarget": "main"
}'
```

## ディレクトリ構成

```
investment-bot/
├── config.py          # 設定ファイル
├── main.py            # メイン実行ファイル
├── requirements.txt   # 依存パッケージ
├── .env.example       # 環境変数テンプレート
├── .env               # 環境変数（gitには含めない）
├── data/              # データ保存
│   ├── investment_bot.db
│   ├── win_rate_model.pkl
│   └── scaler.pkl
├── logs/              # ログ
└── src/
    ├── collector.py   # 情報収集
    ├── analyzer.py    # 分析・予測
    ├── predictor.py   # 勝率予測・学習
    ├── trader.py      # 取引実行（bitFlyer API）
    └── monitor.py     # 監視・通知
```

## 取引ルール詳細

### シグナル判定

- **買いシグナル**: 勝率55%以上、シグナルスコア2以上
- **売りシグナル**: 勝率55%以上、シグナルスコア-2以下
- **ホールド**: 条件を満たさない場合はスキップ

### リスク管理

- **1通貨最大ポジション**: 残高の40%
- **日次最大損失**: 残高の5%（達したらその日の取引停止）
- **日次最大取引数**: 20件（達したらその日の取引停止）
- **損切り**: -1.2%で自動売却
- **利益目標**: +2.5%

### 感情分析

ニュースとツイートの感情を分析:
- ポジティブ: 上昇、好調、買い、増収、増益、回復、改善 など
- ネガティブ: 下落、不調、売り、減収、減益、悪化、低下、リスク など

### テクニカル分析

- **RSI**: 30未満=売られすぎ（買いシグナル）、70超=買われすぎ（売りシグナル）
- **MACD**: ヒストグラムがプラス=買い、マイナス=売り
- **移動平均線**: 現在価格と移動平均線の位置関係、傾き

## モデル学習

過去の取引結果から機械学習モデル（RandomForest）で勝率を予測。

学習データが10件以上溜まると自動で学習開始。その後は10回ごとに再学習。

## パフォーマンス追跡

データベースに以下を記録:
- 取引履歴
- 日次統計
- 機械学習用データ

パフォーマンスサマリーを定期的に通知。

## 年利20%達成のためのポイント

### 1. 高頻度取引で機会を増やす

- 1日20回の取引で、勝率55%でも期待値がプラス
- ボラティリティの高い仮想通貨は、頻繁な取引に適している

### 2. 損切りを徹底

- -1.2%で損切り
- 大きな損失を回避

### 3. 利益目標は控えめに

- +2.5%の利益目標
- 頻繁に利益を確定

### 4. 分散投資

- 5通貨に分散
- 1通貨の暴落の影響を最小化

### 5. 機械学習の活用

- 勝率55%以上でのみ取引
- 低い勝率の取引をスキップ

## 注意事項

⚠️ **重要**: 本番運用前には十分なテストを行ってください。

- 最初は必ず **ドライランモード** で動作確認
- 小額からスタート（例: 1万円〜5万円）
- 定期的にパフォーマンスを監視
- 損失が拡大した場合は即座に運用停止
- 投資は自己責任

## 免責事項

このボットは教育・研究目的です。実際の取引による損失に対して責任を負いかねます。投資は自己責任で行ってください。

## ライセンス

MIT

---

作成日: 2026-02-14
バージョン: 2.0.0 (bitFlyer + 仮想通貨版)
