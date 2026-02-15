"""
改善版取引実行モジュール（bitFlyer API + ダイナミックポジションサイジング）
短期取引（スイングトレード/デイトレード）に対応
感情分析なし、テクニカル分析のみ
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import hmac
import hashlib
import time
import requests
import sqlite3
import numpy as np

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import trading_config, db_config

logger = logging.getLogger(__name__)


class BitFlyerApiClient:
    """bitFlyer APIクライアント"""

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.bitflyer.com/v1"

        # APIキーが有効な場合のみ認証テスト
        if self.api_key and self.api_secret and self.api_key != "" and self.api_secret != "":
            self._test_connection()
        else:
            logger.warning("bitFlyer APIキーが設定されていないため、認証をスキップします")

    def _get_headers(self, method: str, endpoint: str, body: str = ""):
        """bitFlyer API認証ヘッダーを生成"""
        timestamp = str(time.time())
        text = timestamp + method + endpoint + body
        sign = hmac.new(
            self.api_secret.encode('utf-8'),
            text.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return {
            'ACCESS-KEY': self.api_key,
            'ACCESS-TIMESTAMP': timestamp,
            'ACCESS-SIGN': sign,
            'Content-Type': 'application/json',
        }

    def _test_connection(self):
        """API接続テスト"""
        try:
            headers = self._get_headers('GET', '/me/getbalance')
            response = requests.get(
                self.base_url + "/me/getbalance",
                headers=headers
            )

            if response.status_code == 200:
                logger.info("bitFlyer API認証成功")
                return True
            else:
                raise Exception(f"認証失敗: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"bitFlyer API接続テストエラー: {e}")
            raise

    def get_balance(self) -> Dict[str, Any]:
        """
        残高を取得

        Returns:
            残高情報の辞書 {currency: amount}
        """
        try:
            if not self.api_key or not self.api_secret:
                raise Exception("未認証")

            headers = self._get_headers('GET', '/me/getbalance')
            response = requests.get(
                self.base_url + "/me/getbalance",
                headers=headers
            )

            if response.status_code == 200:
                balances = response.json()
                # 日本円の残高を取得
                jpy_balance = next((b for b in balances if b['currency_code'] == 'JPY'), {'amount': 0})
                return {"available_balance": jpy_balance['amount']}
            else:
                raise Exception(f"残高取得失敗: {response.status_code}")

        except Exception as e:
            logger.error(f"残高取得エラー: {e}")
            return {}

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        保有ポジションを取得

        Returns:
            ポジションのリスト
        """
        try:
            if not self.api_key or not self.api_secret:
                raise Exception("未認証")

            headers = self._get_headers('GET', '/me/getpositions')
            response = requests.get(
                self.base_url + "/me/getpositions",
                headers=headers
            )

            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"ポジション取得失敗: {response.status_code}")

        except Exception as e:
            logger.error(f"ポジション取得エラー: {e}")
            return []

    def get_current_price(self, product_code: str) -> float:
        """
        現在価格を取得

        Args:
            product_code: 取引ペア（例: BTC_JPY）

        Returns:
            現在価格
        """
        try:
            url = f"{self.base_url}/ticker"
            params = {"product_code": product_code}

            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                return float(data.get('ltp', 0))
            else:
                logger.error(f"価格取得失敗: {response.status_code}")
                return 0

        except Exception as e:
            logger.error(f"価格取得エラー: {e}")
            return 0

    def place_order(self, product_code: str, side: str, size: float, order_type: str = "MARKET") -> Dict[str, Any]:
        """
        注文を実行

        Args:
            product_code: 取引ペア（例: BTC_JPY）
            side: "BUY" or "SELL"
            size: 注文サイズ（BTC/ETH等）
            order_type: "MARKET" or "LIMIT"

        Returns:
            注文結果の辞書
        """
        try:
            if not self.api_key or not self.api_secret:
                raise Exception("未認証")

            # 注文データ
            order_data = {
                "product_code": product_code,
                "side": side,
                "size": size,
                "order_type": order_type,
            }

            endpoint = "/me/sendchildorder"
            body = str(order_data)
            headers = self._get_headers('POST', endpoint, body)

            response = requests.post(
                self.base_url + endpoint,
                headers=headers,
                json=order_data
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"注文成功: {product_code} {side} {size} (Child Order ID: {result.get('child_order_acceptance_id')})")
                return result
            else:
                raise Exception(f"注文失敗: {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"注文実行エラー: {e}")
            raise

    def cancel_order(self, product_code: str, child_order_id: str) -> bool:
        """
        注文をキャンセル

        Args:
            product_code: 取引ペア
            child_order_id: 注文ID

        Returns:
            成功時True
        """
        try:
            if not self.api_key or not self.api_secret:
                raise Exception("未認証")

            endpoint = "/me/cancelchildorder"
            body = str({"product_code": product_code, "child_order_id": child_order_id})
            headers = self._get_headers('POST', endpoint, body)

            response = requests.post(
                self.base_url + endpoint,
                headers=headers,
                json={"product_code": product_code, "child_order_id": child_order_id}
            )

            if response.status_code == 200:
                logger.info(f"注文キャンセル成功: {child_order_id}")
                return True
            else:
                raise Exception(f"注文キャンセル失敗: {response.status_code}")

        except Exception as e:
            logger.error(f"注文キャンセルエラー: {e}")
            return False


class TradeManager:
    """取引マネージャー（改善版：感情分析なし）"""

    def __init__(self, api_key: str = None, api_secret: str = None, dry_run: bool = True, trading_mode: str = "swing"):
        if api_key and api_secret and api_key != "" and api_secret != "":
            self.api_client = BitFlyerApiClient(api_key, api_secret)
        else:
            self.api_client = None

        self.dry_run = dry_run
        self.trading_mode = trading_mode  # "swing" or "day"
        self.db_path = db_config.DB_PATH

        # データベース初期化
        self._init_database()

    def _init_database(self):
        """データベースを初期化"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 取引記録テーブル（改善版、感情分析なし）
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                order_type TEXT,
                status TEXT,
                timestamp TEXT,
                profit_loss REAL,
                signal_score REAL,
                rsi REAL,
                macd_histogram REAL,
                ma5_slope REAL,
                ma10_slope REAL,
                ma20_slope REAL,
                ma50_slope REAL,
                ma5_pct REAL,
                ma10_pct REAL,
                ma20_pct REAL,
                ma50_pct REAL,
                change_pct REAL,
                ensemble_signal TEXT,
                result INTEGER
            )
            """)

            # 日次統計テーブル
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_trades INTEGER,
                wins INTEGER,
                losses INTEGER,
                total_profit REAL,
                max_loss REAL
            )
            """)

            # 取引モード別統計
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS mode_stats (
                mode TEXT PRIMARY KEY,
                total_trades INTEGER,
                wins INTEGER,
                losses INTEGER,
                total_profit REAL
            )
            """)

            conn.commit()
            conn.close()

            logger.info("データベース初期化完了")

        except Exception as e:
            logger.error(f"データベース初期化エラー: {e}")

    def execute_trades(self, signals: Dict[str, Any], account_balance: float = None) -> List[Dict[str, Any]]:
        """
        シグナルに基づいて取引を実行（改善版：感情分析なし）

        Args:
            signals: 各通貨のシグナル（テクニカル分析のみ）
            account_balance: 口座残高（Noneなら自動取得）

        Returns:
            実行した取引のリスト
        """
        logger.info("=== 取引実行開始（改善版：感情分析なし）===")
        logger.info(f"取引モード: {self.trading_mode}")

        executed_trades = []

        # 残高取得
        if account_balance is None and self.api_client:
            balance_data = self.api_client.get_balance()
            account_balance = balance_data.get("available_balance", 0)

        # 日次損失チェック
        if not self._check_daily_loss_limit():
            logger.warning("日次損失限度額に達したため、取引を停止します")
            return executed_trades

        # 日次取引数チェック
        if not self._check_daily_trade_limit():
            logger.warning("日次取引数の上限に達したため、取引を停止します")
            return executed_trades

        # 連続損失チェック
        consecutive_losses = self._get_consecutive_losses()
        if consecutive_losses >= trading_config.MAX_CONSECUTIVE_LOSSES:
            logger.warning(f"連続{consecutive_losses}回の損失のため、今日の取引を停止します")
            return executed_trades

        for symbol, signal in signals.items():
            # 取引アクション確認
            action = signal.get("action")

            if action not in ["buy", "sell"]:
                continue

            # 勝率チェック
            win_rate = signal.get("win_rate", 0)
            if win_rate < trading_config.TARGET_WIN_RATE:
                logger.info(f"{symbol}: 勝率{win_rate:.1%}が閾値{trading_config.TARGET_WIN_RATE:.1%}未満のためスキップ")
                continue

            # 信頼度チェック
            confidence = signal.get("signal_score", 0) / 10
            if confidence < trading_config.CONFIDENCE_THRESHOLD:
                logger.info(f"{symbol}: 信頼度{confidence:.2f}が閾値未満のためスキップ")
                continue

            # 取引実行
            try:
                trade = self._execute_trade(symbol, signal, account_balance)
                if trade:
                    executed_trades.append(trade)
            except Exception as e:
                logger.error(f"{symbol}の取引実行エラー: {e}")

        logger.info(f"=== 取引実行完了: {len(executed_trades)}件 ===")

        return executed_trades

    def _execute_trade(self, symbol: str, signal: Dict[str, Any], account_balance: float) -> Optional[Dict[str, Any]]:
        """
        1件の取引を実行（改善版：感情分析なし、ダイナミックポジションサイジング）

        Args:
            symbol: 通貨ペア（例: BTC_JPY）
            signal: シグナルデータ（テクニカル分析のみ）
            account_balance: 口座残高（JPY）

        Returns:
            取引結果（失敗時None）
        """
        action = signal.get("action")
        technical = signal.get("technical", {})
        current_price = signal.get("current_price")

        logger.info(f"\n--- {symbol} 取引 ({self.trading_mode}モード)---")
        logger.info(f"アクション: {action}")
        logger.info(f"現在価格: ¥{current_price:,.2f}")
        logger.info(f"予測勝率: {signal.get('win_rate', 0):.1%}")

        # ボラティリティに基づいてポジションサイズを計算
        volatility = self._calculate_volatility_from_technical(technical)
        position_size = self._calculate_dynamic_position_size(account_balance, current_price, volatility, signal)

        if position_size <= 0:
            logger.info("取引サイズが0のためスキップ")
            return None

        logger.info(f"取引数量: {position_size:.8f}")
        logger.info(f"ポジション比率: {(position_size * current_price) / account_balance * 100:.1f}%")

        # ドライランなら注文をスキップ
        if self.dry_run:
            logger.info("【ドライラン】注文をスキップします")

            trade = {
                "order_id": f"dryrun_{int(datetime.now().timestamp())}",
                "symbol": symbol,
                "side": action,
                "quantity": position_size,
                "price": current_price,
                "order_type": "MARKET",
                "status": "dry_run",
                "timestamp": datetime.now().isoformat(),
                "profit_loss": None,
                "signal_score": signal.get("signal_score", 0),
                "rsi": technical.get("rsi", 50),
                "macd_histogram": technical.get("macd_histogram", 0),
                "ma5_slope": technical.get("ma5_slope", 0),
                "ma10_slope": technical.get("ma10_slope", 0),
                "ma20_slope": technical.get("ma20_slope", 0),
                "ma50_slope": technical.get("ma50_slope", 0),
                "ma5_pct": technical.get("ma5_pct", 0),
                "ma10_pct": technical.get("ma10_pct", 0),
                "ma20_pct": technical.get("ma20_pct", 0),
                "ma50_pct": technical.get("ma50_pct", 0),
                "change_pct": signal.get("change_pct", 0),
                "ensemble_signal": signal.get("ensemble_signal", "neutral"),
                "result": None,
            }

            # データベースに記録
            self._record_trade(trade)

            return trade

        # APIクライアントがないならスキップ
        if not self.api_client:
            logger.warning("APIクライアントが設定されていないため、注文をスキップします")
            return None

        # 注文実行
        try:
            side = "BUY" if action == "buy" else "SELL"
            result = self.api_client.place_order(
                product_code=symbol,
                side=side,
                size=position_size,
                order_type="MARKET",
            )

            trade = {
                "order_id": result.get("child_order_acceptance_id"),
                "symbol": symbol,
                "side": action,
                "quantity": position_size,
                "price": current_price,
                "order_type": "MARKET",
                "status": "executed",
                "timestamp": datetime.now().isoformat(),
                "profit_loss": None,
                "signal_score": signal.get("signal_score", 0),
                "rsi": technical.get("rsi", 50),
                "macd_histogram": technical.get("macd_histogram", 0),
                "ma5_slope": technical.get("ma5_slope", 0),
                "ma10_slope": technical.get("ma10_slope", 0),
                "ma20_slope": technical.get("ma20_slope", 0),
                "ma50_slope": technical.get("ma50_slope", 0),
                "ma5_pct": technical.get("ma5_pct", 0),
                "ma10_pct": technical.get("ma10_pct", 0),
                "ma20_pct": technical.get("ma20_pct", 0),
                "ma50_pct": technical.get("ma50_pct", 0),
                "change_pct": signal.get("change_pct", 0),
                "ensemble_signal": signal.get("ensemble_signal", "neutral"),
                "result": None,
            }

            # データベースに記録
            self._record_trade(trade)

            return trade

        except Exception as e:
            logger.error(f"注文実行エラー: {e}")
            return None

    def _calculate_volatility_from_technical(self, technical: Dict[str, Any]) -> float:
        """
        テクニカル分析からボラティリティを計算

        Args:
            technical: テクニカル分析結果

        Returns:
            ボラティリティ (0.0 ~ 1.0)
        """
        # ATR（ボラティリティ指標）を使用
        atr = technical.get("atr", 0)
        current_price = technical.get("current_price", 0)

        if atr > 0 and current_price > 0:
            # ATR / 価格 = ボラティリティの推定
            volatility = (atr / current_price) * 10  # スケーリング調整
            return min(1.0, max(0.0, volatility))
        else:
            # デフォルト：仮想通貨はボラティリティが高い
            return 0.3

    def _calculate_dynamic_position_size(self, account_balance: float, price: float, volatility: float, signal: Dict[str, Any]) -> float:
        """
        ダイナミックポジションサイジング

        Args:
            account_balance: 口座残高（JPY）
            price: 1単位あたりの価格（JPY）
            volatility: ボラティリティ (0.0 ~ 1.0)
            signal: シグナルデータ

        Returns:
            取引数量（BTC/ETH等）
        """
        if not account_balance or not price:
            return 0

        # ボラティリティに基づいて基本ポジション比率を決定
        if volatility > 0.3:  # 高ボラティリティ
            base_position_ratio = 0.15  # 15%（より保守的）
        elif volatility > 0.2:  # 中ボラティリティ
            base_position_ratio = 0.25  # 25%
        else:  # 低ボラティリティ
            base_position_ratio = 0.35  # 35%

        # シグナル強度による調整
        signal_score = signal.get("signal_score", 0)
        signal_strength = abs(signal_score) / 10  # 0.0 ~ 1.0

        # 強いシグナルの場合、ポジションを少し増やす
        adjusted_ratio = base_position_ratio * (1 + signal_strength * 0.2)

        # 最大ポジションサイズの制限
        adjusted_ratio = min(adjusted_ratio, trading_config.MAX_POSITION_SIZE)

        # 取引サイズ計算（仮想通貨は小数も可能）
        max_position_value = account_balance * adjusted_ratio
        quantity = max_position_value / price

        # スイングトレードでは、より大きなポジションを取る可能性がある
        if self.trading_mode == "day":
            # デイトレードでは、より大きなポジションを取る
            quantity *= 1.3  # 30%増加

        return max(0, quantity)

    def _check_daily_loss_limit(self) -> bool:
        """
        日次損失限度額をチェック

        Returns:
            許可時True
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 今日の損失を計算
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
            SELECT COALESCE(SUM(profit_loss), 0)
            FROM trades
            WHERE DATE(timestamp) = ? AND profit_loss IS NOT NULL AND profit_loss < 0
            """, (today,))

            today_loss = abs(cursor.fetchone()[0])

            conn.close()

            # 損失限度額を計算（初期残高の4%と仮定、より保守的）
            loss_limit = 10000 * trading_config.MAX_DAILY_LOSS  # 1万円と仮定

            if today_loss >= loss_limit:
                logger.warning(f"本日の損失{today_loss:.0f}円が限度額{loss_limit:.0f}円に達しました")
                return False

            return True

        except Exception as e:
            logger.error(f"日次損失チェックエラー: {e}")
            return True  # エラー時は許可（保守的）

    def _check_daily_trade_limit(self) -> bool:
        """
        日次取引数の上限をチェック

        Returns:
            許可時True
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 今日の取引数を計算
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
            SELECT COUNT(*)
            FROM trades
            WHERE DATE(timestamp) = ?
            """, (today,))

            today_trades = cursor.fetchone()[0]

            conn.close()

            if today_trades >= trading_config.MAX_DAILY_TRADES:
                logger.warning(f"本日の取引数{today_trades}が上限{trading_config.MAX_DAILY_TRADES}に達しました")
                return False

            return True

        except Exception as e:
            logger.error(f"日次取引数チェックエラー: {e}")
            return True  # エラー時は許可

    def _get_consecutive_losses(self) -> int:
        """
        連続損失回数を取得

        Returns:
            連続損失回数
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 最近の取引結果を取得（今日のみ）
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
            SELECT result
            FROM trades
            WHERE DATE(timestamp) = ? AND result IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 10
            """, (today,))

            results = cursor.fetchall()
            conn.close()

            # 連続損失をカウント
            consecutive_losses = 0
            for result in results:
                if result[0] == 0:  # 負け
                    consecutive_losses += 1
                else:  # 勝ち
                    break

            return consecutive_losses

        except Exception as e:
            logger.warning(f"連続損失チェックエラー: {e}")
            return 0

    def _record_trade(self, trade: Dict[str, Any]):
        """
        取引を記録

        Args:
            trade: 取引データ
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
            INSERT INTO trades (
                order_id, symbol, side, quantity, price, order_type, status, timestamp, profit_loss,
                signal_score, rsi, macd_histogram,
                ma5_slope, ma10_slope, ma20_slope, ma50_slope,
                ma5_pct, ma10_pct, ma20_pct, ma50_pct, change_pct, ensemble_signal, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade["order_id"],
                trade["symbol"],
                trade["side"],
                trade["quantity"],
                trade["price"],
                trade["order_type"],
                trade["status"],
                trade["timestamp"],
                trade.get("profit_loss"),
                trade.get("signal_score", 0),
                trade.get("rsi", 50),
                trade.get("macd_histogram", 0),
                trade.get("ma5_slope", 0),
                trade.get("ma10_slope", 0),
                trade.get("ma20_slope", 0),
                trade.get("ma50_slope", 0),
                trade.get("ma5_pct", 0),
                trade.get("ma10_pct", 0),
                trade.get("ma20_pct", 0),
                trade.get("ma50_pct", 0),
                trade.get("change_pct", 0),
                trade.get("ensemble_signal", "neutral"),
                trade.get("result"),
            ))

            conn.commit()
            conn.close()

            logger.info(f"取引を記録しました: {trade['symbol']} {trade['side']} {trade['quantity']:.8f}")

        except Exception as e:
            logger.error(f"取引記録エラー: {e}")


if __name__ == "__main__":
    # テスト実行
    import logging
    logging.basicConfig(level=logging.INFO)

    # スイングトレードモード
    manager = TradeManager(dry_run=True, trading_mode="swing")

    # テストシグナル（テクニカル分析のみ）
    test_signals = {
        "BTC_JPY": {
            "symbol": "BTC_JPY",
            "current_price": 10000000.0,
            "change_pct": 2.5,
            "win_rate": 0.70,  # 勝率70%（閾値55%以上）
            "signal_score": 7.0,  # シグナルスコア7.0（閾値7.0以上）
            "action": "buy",
            "technical": {
                "rsi": 25,  # 売られすぎ
                "macd_histogram": 500,  # 買い
                "ma5_slope": 500,  # 上昇トレンド
                "ma10_slope": 300,
                "ma20_slope": 100,
                "ma50_slope": 50,
                "ma5_pct": 1.5,  # 上方乖離
                "ma10_pct": 0.5,
                "ma20_pct": -0.5,
                "ma50_pct": -2.5,
                "atr": 20000.0,  # ATR（ボラティリティ）
            },
            "ensemble_signal": "strong_buy",
        }
    }

    trades = manager.execute_trades(test_signals, account_balance=10000)
    print(f"\n実行された取引: {len(trades)}件")
