# 投資ボット設定ファイル（チャート分析専用版）
# Python 3.14対応版（dataclassのmutable型問題修正）

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class TradingConfig:
    """取引設定（チャート分析専用版）"""
    # 目標
    TARGET_ANNUAL_RETURN: float = 0.20  # 年率20%（最低目標）
    TARGET_WIN_RATE: float = 0.55      # 目標勝率55%

    # 取引ルール
    TRADE_INTERVAL_HOURS: int = 1      # 1時間ごと
    CONFIDENCE_THRESHOLD: float = 0.70 # 信頼度閾値70%（上げた）

    # リスクリワード（より攻め的）
    RISK_REWARD_RATIO: float = 1.5     # リスクリワード比1.5:1
    PROFIT_TARGET: float = 0.03       # 利益目標+3%
    STOP_LOSS: float = 0.015          # 損切り-1.5%

    # リスク管理
    MAX_POSITION_SIZE: float = 0.30   # 1通貨最大30%
    MAX_DAILY_LOSS: float = 0.04      # 1日最大損失4%（より厳格）
    MAX_DAILY_TRADES: int = 20        # 1日最大取引数20回
    MAX_CONSECUTIVE_LOSSES: int = 3  # 連続損失3回でその日は取引停止

    # 取引モード
    TRADING_MODE: str = "swing"  # "swing" (スイングトレード) or "day" (デイトレード)

    # 分析モード（感情分析なし）
    ANALYSIS_MODE: str = "technical_only"  # "technical_only" or "full"

    # 取引対象（フィールドデフォルトファクトリを使用）
    cryptos: List[str] = field(default_factory=list)

    def __post_init__(self):
        # bitFlyer 主要通貨（ペア）
        if not self.cryptos:
            self.cryptos = [
                "BTC_JPY",    # ビットコイン
                "ETH_JPY",    # イーサリアム
                "XRP_JPY",    # リップル
                "BCH_JPY",    # ビットコインキャッシュ
                "LTC_JPY",    # ライトコイン
            ]

@dataclass
class APIConfig:
    """API設定"""
    # bitFlyer API
    BITFLYER_API_KEY: str = ""
    BITFLYER_API_SECRET: str = ""

    # X (Twitter) API（今回は無効化）
    TWITTER_BEARER_TOKEN: str = ""
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    TWITTER_ACCESS_TOKEN: str = ""
    TWITTER_ACCESS_SECRET: str = ""

    # OpenAI API（感情分析用、今回は無効化）
    OPENAI_API_KEY: str = ""

    # Discord Webhook（通知用）
    DISCORD_WEBHOOK_URL: str = ""

@dataclass
class AnalysisConfig:
    """分析設定（チャート分析専用版）"""
    # ニュースソース（今回は無効化）
    news_sources: List[str] = field(default_factory=list)

    # SNS監視キーワード（今回は無効化）
    twitter_keywords: List[str] = field(default_factory=list)

    # テクニカル指標
    MA_PERIODS: List[int] = field(default_factory=list)
    RSI_PERIOD: int = 14
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9

    # 高度なテクニカル指標
    USE_BOLLINGER_BANDS: bool = True
    USE_ATR: bool = True
    USE_SUPPORT_RESISTANCE: bool = True
    USE_STOCHASTIC: bool = True
    USE_WILLIAMS: bool = True
    USE_MOMENTUM: bool = True
    USE_VOLUME: bool = True

    # アンサンブル戦略（テクニカルのみ）
    USE_ENSEMBLE: bool = True
    MIN_CONSENSUS: float = 0.7  # 70%以上の戦略が一致した場合のみ取引

    # テクニカル戦略（種類を増やす）
    TECHNICAL_STRATEGIES: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.news_sources = []  # 無効化
        self.twitter_keywords = []  # 無効化

        if not self.MA_PERIODS:
            # さらに多くの移動平均線
            self.MA_PERIODS = [5, 10, 20, 50, 100, 200]

        if not self.TECHNICAL_STRATEGIES:
            # テクニカル戦略のリスト
            self.TECHNICAL_STRATEGIES = [
                "trend_following",      # トレンドフォロー
                "mean_reversion",       # 平均回帰
                "momentum",            # モメンタム
                "breakout",             # ブレイクアウト
                "support_resistance",   # サポート/レジスタンス
                "multi_timeframe",      # マルチタイムフレーム
                "volume_price",        # 出来高/価格分析
            ]

@dataclass
class DatabaseConfig:
    """データベース設定"""
    DB_PATH: str = "data/investment_bot.db"
    BACKUP_PATH: str = "data/backups/"

# グローバル設定
trading_config = TradingConfig()
api_config = APIConfig()
analysis_config = AnalysisConfig()
db_config = DatabaseConfig()

def load_env():
    """環境変数から設定を読み込み"""
    import dotenv
    from pathlib import Path

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        dotenv.load_dotenv(env_path)

    # bitFlyer API
    api_config.BITFLYER_API_KEY = os.getenv("BITFLYER_API_KEY", "")
    api_config.BITFLYER_API_SECRET = os.getenv("BITFLYER_API_SECRET", "")

    # Twitter API（今回は無効化）
    # api_config.TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

    # OpenAI API（今回は無効化）
    # api_config.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

    # Discord
    api_config.DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# モジュール読み込み時に環境変数をロード
load_env()
