"""
監視・通知モジュール（チャート分析専用版・修正済）
感情分析なし、テクニカル分析のみを監視
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import requests
import sqlite3

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import trading_config, db_config

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Discord通知クラス"""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    def send_notification(self, message: str) -> bool:
        """
        Discordに通知を送信

        Args:
            message: 送信メッセージ

        Returns:
            成功時True
        """
        if not self.webhook_url:
            logger.warning("Discord Webhook URLが設定されていません")
            return False

        try:
            data = {"content": message}
            response = requests.post(self.webhook_url, json=data)

            if response.status_code == 200:
                logger.info("Discord通知を送信しました")
                return True
            else:
                logger.error(f"Discord通知送信失敗: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Discord通知エラー: {e}")
            return False

    def send_technical_summary_notification(self, signals: Dict[str, Any], trades: List[Dict[str, Any]]) -> bool:
        """
        テクニカル分析サマリー通知を送信

        Args:
            signals: すべてのシグナル
            trades: 実行された取引

        Returns:
            成功時True
        """
        # 強い買いシグナルの数
        buy_signals = sum(1 for s in signals.values() if s.get("action") == "buy")
        sell_signals = sum(1 for s in signals.values() if s.get("action") == "sell")

        message = f"""
📊 **テクニカル分析サマリー** - {datetime.now().strftime('%Y-%m-%d %H:%M')}

🟢 **買いシグナル**: {buy_signals}銘柄
🔴 **売りシグナル**: {sell_signals}銘柄
📋 **実行取引**: {len(trades)}件

---

**トップ3買いシグナル**:
"""

        # 上位3つの買いシグナルを表示（シグナルスコア順）
        buy_sorted = sorted(
            [(s, v) for s, v in signals.items() if v.get("action") == "buy"],
            key=lambda x: x[1].get("signal_score", 0),
            reverse=True
        )[:3]

        for i, (symbol, signal) in enumerate(buy_sorted, 1):
            message += f"\n{i}. **{symbol}** - シグナルスコア: {signal.get('signal_score', 0):.1f}, 予測勝率: {signal.get('win_rate', 0):.1%}, 価格: ¥{signal.get('current_price', 0):,.2f}"

        if not buy_sorted:
            message += "\n（なし）"

        return self.send_notification(message)

    def send_trade_notification(self, trade: Dict[str, Any], signal: Dict[str, Any]) -> bool:
        """
        取引通知を送信

        Args:
            trade: 取引データ
            signal: シグナルデータ

        Returns:
            成功時True
        """
        emoji_map = {
            "buy": "🟢",
            "sell": "🔴",
        }

        emoji = emoji_map.get(trade["side"], "⚪")

        message = f"""
{emoji} **取引実行**
- 銘柄: {trade['symbol']}
- アクション: {trade['side'].upper()}
- 数量: {trade['quantity']:.8f}
- 価格: ¥{trade['price']:,.2f}
- 予測勝率: {signal.get('win_rate', 0):.1%}
- シグナルスコア: {signal.get('signal_score', 0):.1f}
- 時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        return self.send_notification(message)

    def send_technical_summary_notification(self, signals: Dict[str, Any], trades: List[Dict[str, Any]]) -> bool:
        """
        テクニカル分析サマリー通知を送信（エイリアス）

        Args:
            signals: すべてのシグナル
            trades: 実行された取引

        Returns:
            成功時True
        """
        return self.send_technical_summary_notification(signals, trades)

    def send_error_notification(self, error: str) -> bool:
        """
        エラー通知を送信

        Args:
            error: エラーメッセージ

        Returns:
            成功時True
        """
        message = f"""
⚠️ **エラー発生**
{error}
時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        return self.send_notification(message)


class TradeMonitor:
    """取引監視クラス"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or db_config.DB_PATH

    def check_stop_loss(self) -> List[Dict[str, Any]]:
        """
        損切りチェック

        Returns:
            損切りが必要な取引のリスト
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 未決済の取引を取得
            cursor.execute("""
            SELECT * FROM trades
            WHERE status = 'executed' AND profit_loss IS NULL
            ORDER BY timestamp DESC
            """)

            open_trades = cursor.fetchall()
            conn.close()

            need_stop_loss = []

            for trade in open_trades:
                # 現在価格を取得（仮）
                # 実際にはAPIから取得する
                current_price = trade[5]  # 取引価格を仮使用

                # 損失率計算
                if trade[3] == "buy":  # 買い注文
                    loss_pct = ((current_price - trade[5]) / trade[5]) * 100
                else:  # 売り注文
                    loss_pct = ((trade[5] - current_price) / trade[5]) * 100

                # 損切りチェック
                if loss_pct < -trading_config.STOP_LOSS * 100:
                    need_stop_loss.append({
                        "order_id": trade[1],
                        "symbol": trade[2],
                        "side": trade[3],
                        "quantity": trade[4],
                        "price": trade[5],
                        "loss_pct": loss_pct,
                    })

            return need_stop_loss

        except Exception as e:
            logger.error(f"損切りチェックエラー: {e}")
            return []

    def calculate_daily_pnl(self) -> Dict[str, Any]:
        """
        日次損益を計算

        Returns:
            日次損益情報
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 今日の取引を取得
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit_loss), 0) as total_profit,
                COALESCE(MIN(profit_loss), 0) as max_loss
            FROM trades
            WHERE DATE(timestamp) = ? AND profit_loss IS NOT NULL
            """, (today,))

            result = cursor.fetchone()

            conn.close()

            return {
                "date": today,
                "total_trades": result[0] or 0,
                "wins": result[1] or 0,
                "losses": result[2] or 0,
                "total_profit": result[3] or 0,
                "max_loss": result[4] or 0,
                "win_rate": (result[1] / result[0]) if result[0] > 0 else 0,
            }

        except Exception as e:
            logger.error(f"日次損益計算エラー: {e}")
            return {}

    def calculate_weekly_pnl(self) -> Dict[str, Any]:
        """
        週次損益を計算

        Returns:
            週次損益情報
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 今週の取引を取得
            cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit_loss), 0) as total_profit,
                COALESCE(MIN(profit_loss), 0) as max_loss
            FROM trades
            WHERE DATE(timestamp) >= date('now', 'weekday 0', '-7 days') AND profit_loss IS NOT NULL
            """)

            result = cursor.fetchone()

            conn.close()

            return {
                "total_trades": result[0] or 0,
                "wins": result[1] or 0,
                "losses": result[2] or 0,
                "total_profit": result[3] or 0,
                "max_loss": result[4] or 0,
                "win_rate": (result[1] / result[0]) if result[0] > 0 else 0,
            }

        except Exception as e:
            logger.error(f"週次損益計算エラー: {e}")
            return {}

    def get_technical_performance_summary(self) -> str:
        """
        テクニカル分析のみのパフォーマンスサマリーを取得

        Returns:
            サマリー文字列
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 今日の取引統計
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit_loss), 0) as total_profit,
                COALESCE(MIN(profit_loss), 0) as max_loss
            FROM trades
            WHERE DATE(timestamp) = ? AND profit_loss IS NOT NULL
            """, (today,))

            daily_result = cursor.fetchone()

            # 今週の取引統計
            cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit_loss), 0) as total_profit,
                COALESCE(MIN(profit_loss), 0) as max_loss
            FROM trades
            WHERE DATE(timestamp) >= date('now', 'weekday 0', '-7 days') AND profit_loss IS NOT NULL
            """)

            weekly_result = cursor.fetchone()

            # 全体のテクニカル指標（平均）
            cursor.execute("""
            SELECT
                AVG(signal_score) as avg_signal_score,
                AVG(rsi) as avg_rsi,
                AVG(macd_histogram) as avg_macd_histogram,
                AVG(change_pct) as avg_change_pct
            FROM trades
            WHERE signal_score IS NOT NULL
            """)

            technical_result = cursor.fetchone()

            conn.close()

            summary = f"""
📊 **テクニカル分析パフォーマンスサマリー**

📅 **今日** ({daily_result[0] if daily_result else 'N/A'}):
- 取引数: {daily_result[0] or 0}件
- 勝利: {daily_result[1] or 0} / 敗北: {daily_result[2] or 0}
- 勝率: {(daily_result[1] / daily_result[0] * 100 if daily_result[0] else 0):.1f}%
- 総損益: ¥{daily_result[3] or 0:,.0f}
- 最大損失: ¥{daily_result[4] or 0:,.0f}

📊 **今週**:
- 取引数: {weekly_result[0] or 0}件
- 勝利: {weekly_result[1] or 0} / 敗北: {weekly_result[2] or 0}
- 勝率: {(weekly_result[1] / weekly_result[0] * 100 if weekly_result[0] else 0):.1f}%
- 総損益: ¥{weekly_result[3] or 0:,.0f}
- 最大損失: ¥{weekly_result[4] or 0:,.0f}

📊 **全体テクニカル指標**:
- 平均シグナルスコア: {technical_result[0] or 0:.2f}
- 平均RSI: {technical_result[1] or 0:.2f}
- 平均MACDヒストグラム: {technical_result[2] or 0:.2f}
- 平均変動率: {technical_result[3] or 0:.2f}%
"""

            return summary

    def get_performance_summary(self) -> str:
        """
        パフォーマンスサマリーを取得（エイリアス）

        Returns:
            サマリー文字列
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 今日の取引統計
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(profit_loss), 0) as total_profit,
                COALESCE(MIN(profit_loss), 0) as max_loss
            FROM trades
            WHERE DATE(timestamp) = ? AND profit_loss IS NOT NULL
            """, (today,))

            result = cursor.fetchone()

            conn.close()

            summary = f"""
📈 **パフォーマンスサマリー**

📅 **今日** ({today}):
- 取引数: {result[0] or 0}件
- 勝利: {result[1] or 0} / 敗北: {result[2] or 0}
- 勝率: {(result[1] / result[0] * 100 if result[0] else 0):.1f}%
- 総損益: ¥{result[3] or 0:,.0f}
- 最大損失: ¥{result[4] or 0:,.0f}

📊 **今週**:
- 取引数: 0件
- 勝利: 0 / 敗北: 0
- 勝率: 0.0%
- 総損益: ¥0
- 最大損失: ¥0
"""

            return summary

        except Exception as e:
            logger.error(f"パフォーマンスサマリー取得エラー: {e}")
            return ""
