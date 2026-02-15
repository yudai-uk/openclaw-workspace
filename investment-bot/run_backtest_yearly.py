"""
チャート分析専用バックテストシステム（年ごとの分析）
感情分析なし、テクニカル分析のみ
各年ごとにバックテストを行い、最適な投資手法を確立する
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
import yfinance as yf
import time

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import trading_config
from src.analyzer import AdvancedTechnicalAnalyzer

logger = logging.getLogger(__name__)


class ChartBacktesterYearly:
    """チャート分析専用バックテストクラス（年ごとの分析）"""

    def __init__(self):
        self.symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY", "BCH-JPY", "LTC-JPY"]
        self.technical_analyzer = AdvancedTechnicalAnalyzer()

    def fetch_historical_data(self, period: str = "5y", interval: str = "1d") -> Dict[str, pd.DataFrame]:
        """
        過去のデータを取得

        Args:
            period: データ期間（デフォルト5年）
            interval: データ間隔（デフォルト1日）

        Returns:
            シンボルごとのデータフレーム
        """
        logger.info(f"過去{period}分のデータを取得開始（{interval}）")

        data = {}

        for symbol in self.symbols:
            try:
                logger.info(f"シンボル: {symbol}")

                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period, interval=interval)

                if hist.empty:
                    logger.warning(f"  データなし: {symbol}")
                    continue

                data[symbol] = hist
                logger.info(f"  データ取得: {len(hist)}件")

            except Exception as e:
                logger.error(f"データ取得エラー ({symbol}): {e}")

        logger.info(f"データ取得完了: {len(data)}シンボル")
        return data

    def run_backtest(self, df: pd.DataFrame, strategy_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        バックテストを実行

        Args:
            df: チャートデータ
            strategy_name: 戦略名
            params: 戦略パラメータ

        Returns:
            バックテスト結果
        """
        logger.info(f"バックテスト開始: {strategy_name}")

        # シミュレーション実行
        result = self._simulate_trades(df, params)

        logger.info(f"バックテスト完了: {strategy_name}")
        return result

    def _simulate_trades(self, df: pd.DataFrame, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        取引をシミュレート（ボラティリティ・ブレイクアウト戦略 + デバッグログ版）

        戦略ロジック:
        1. エントリー（買い）: 価格が過去50日間の最高値を更新した時 (High > High_50[前日])
        2. エグジット（売り）: 価格がSMA50を下回った時、または利益目標/損切りに達した時。

        Args:
            df: チャートデータ
            params: 取引パラメータ

        Returns:
            取引結果
        """
        # パラメータ設定
        profit_target = params.get("profit_target", trading_config.PROFIT_TARGET) if params else trading_config.PROFIT_TARGET
        stop_loss = params.get("stop_loss", trading_config.STOP_LOSS) if params else trading_config.STOP_LOSS
        strategy_name = params.get("strategy_name", "default") if params else "default"

        # 初期資金
        initial_capital = 10000
        capital = initial_capital

        trades = []
        position = None
        win_count = 0
        loss_count = 0

        logger.info(f"ボラティリティ・ブレイクアウト戦略でバックテストを実行中... (利益目標: {profit_target*100:.1f}%, 損切り: {stop_loss*100:.1f}%)")

        # テクニカル指標計算（SMA50と50日高値）
        df['sma_50'] = df['Close'].rolling(window=50).mean()
        df['high_50'] = df['High'].rolling(window=50).max()

        # 取引シミュレーション
        for i in range(50, len(df)):
            current_date = df.index[i]
            current_price = df['Close'].iloc[i]
            current_high = df['High'].iloc[i]
            current_low = df['Low'].iloc[i]

            # ポジションがある場合
            if position is not None:
                entry_price = position['entry_price']
                entry_date = position['entry_date']

                # 利益目標または損切りに達した場合
                # Highが利益目標を超えた -> 利確
                # Lowがストップロスを下回った -> 損切
                # または SMA50 を下回った -> トレンド崩壊でエグジット
                hit_profit_target = (current_high - entry_price) / entry_price >= profit_target
                hit_stop = (current_low - entry_price) / entry_price <= stop_loss
                hit_sma = current_price < df['sma_50'].iloc[i]

                should_close = hit_profit_target or hit_stop or hit_sma

                if should_close:
                    # 決済価格と勝敗判定
                    reason = ""
                    if hit_stop:
                        # ストップロス = 確実な負け
                        exit_price = entry_price * (1 + stop_loss)
                        change_pct = stop_loss
                        loss_count += 1
                        reason = "stop_loss"
                    elif hit_profit_target:
                        # 利益目標 = 確実な勝ち
                        exit_price = entry_price * (1 + profit_target)
                        change_pct = profit_target
                        win_count += 1
                        reason = "profit_target"
                    else:
                        # トレンド崩壊での決済は終値ベース
                        exit_price = current_price
                        change_pct = (exit_price - entry_price) / entry_price
                        if change_pct > 0:
                            win_count += 1
                        else:
                            loss_count += 1
                        reason = "trend_break_sma50"

                    profit = change_pct * position['quantity'] * entry_price
                    capital += profit

                    # デバッグログ：各取引の詳細を出力
                    logger.info(f"  取引クローズ: {df.index.name} | 理由: {reason} | エントリー: {entry_price:.2f} | エグジット: {exit_price:.2f} | 変動: {change_pct*100:.2f}% | 利益: {profit:.2f} | 残高: {capital:.2f}")

                    trade = {
                        "entry_date": entry_date,
                        "exit_date": current_date,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "change_pct": change_pct * 100,
                        "profit": profit,
                        "capital": capital,
                    }

                    trades.append(trade)

                    position = None

            # 新規ポジションオープン
            else:
                # シグナル判定
                # 1. 買いシグナル: 50日新高値更新
                prev_high_50 = df['high_50'].iloc[i-1]
                is_new_high = current_high > prev_high_50

                # 売りシグナルはポジションなし時は発生しないので、新規ポジションは買いのみ考慮
                # 強力なブレイクアウト（新高値）時のみエントリー
                if is_new_high and capital > 0:
                    position_size = capital * 0.4  # 40%を投資
                    quantity = position_size / current_price

                    position = {
                        "symbol": df.index.name,
                        "entry_price": current_price,
                        "quantity": quantity,
                        "entry_date": current_date,
                        "type": "long"
                    }

                    capital -= position_size
                    
                    # デバッグログ：エントリー
                    logger.info(f"  新規エントリー: {df.index.name} | 価格: {current_price:.2f} | 数量: {quantity:.4f} | 投資額: {position_size:.2f} | 残高: {capital:.2f}")

        # 最終結果
        final_capital = capital

        # 最後のポジションをクローズ（あれば）
        if position is not None:
            final_price = df['Close'].iloc[-1]
            change_pct = (final_price - position['entry_price']) / position['entry_price']
            profit = change_pct * position['quantity'] * position['entry_price']
            final_capital += profit
            logger.info(f"  最終クローズ: {df.index.name} | 価格: {final_price:.2f} | 変動: {change_pct*100:.2f}%")

        # 統計計算
        total_trades = len(trades)
        win_rate = win_count / total_trades if total_trades > 0 else 0
        avg_profit = sum(t['profit'] for t in trades) / total_trades if total_trades > 0 else 0
        max_profit = max(t['profit'] for t in trades) if trades else 0
        max_loss = min(t['profit'] for t in trades) if trades else 0

        # 年利計算
        if len(df) > 0:
            first_date = df.index[0]
            last_date = df.index[-1]
            days = (last_date - first_date).days
            years = days / 365.25

            if years > 0:
                total_return = (final_capital / initial_capital) - 1
                annual_return = ((1 + total_return) ** (1 / years)) - 1
            else:
                annual_return = 0
        else:
            annual_return = 0

        result = {
            "strategy": strategy_name,
            "initial_capital": initial_capital,
            "final_capital": final_capital,
            "total_return": (final_capital / initial_capital) - 1,
            "annual_return": annual_return,
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "avg_profit": avg_profit,
            "max_profit": max_profit,
            "max_loss": max_loss,
            "trades": trades,
            "params": params,
        }

        return result


def main():
    """メイン処理"""
    # ログ設定
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("チャート分析専用バックテスト開始（5年間）")
    logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    backtester = ChartBacktesterYearly()

    # ===== ステップ1: データ取得 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ1: 過去5年間のデータを取得")
    logger.info("=" * 80)

    data = backtester.fetch_historical_data(period="5y", interval="1d")

    if not data:
        logger.error("データが取得できませんでした")
        return

    # ===== ステップ2: 5年間のバックテスト =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ2: 5年間のバックテスト（デフォルトパラメータ）")
    logger.info("=" * 80)

    all_results = {}

    for symbol, df in data.items():
        logger.info(f"\n--- {symbol} バックテスト開始 ---")

        # デフォルトパラメータ
        result = backtester.run_backtest(df, "2025_default")

        all_results[f"{symbol}_2025_default"] = result

        logger.info(f"年利: {result['annual_return']*100:.2f}%")
        logger.info(f"勝率: {result['win_rate']*100:.1f}%")
        logger.info(f"取引数: {result['total_trades']}")
        logger.info(f"最終資金: ¥{result['final_capital']:,.0f}")

    # ===== ステップ3: サマリー表示 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ3: サマリー表示")
    logger.info("=" * 80)

    print(f"\n{'=' * 80}")
    print(f"チャート分析専用バックテスト結果（5年間）")
    print(f"{'=' * 80}")

    # 年利20%以上の戦略を抽出
    profitable_strategies = {
        key: result for key, result in all_results.items()
        if result['annual_return'] >= 0.20
    }

    if profitable_strategies:
        print(f"\n年利20%以上の戦略: {len(profitable_strategies)}件")

        # 最も良い戦略を表示
        best_overall = max(profitable_strategies.items(), key=lambda x: x[1]['annual_return'])
        symbol = best_overall[0].split('_')[0]

        print(f"\n最適戦略: {symbol}_2025_default")
        print(f"  年利: {best_overall[1]['annual_return']*100:.2f}%")
        print(f"  勝率: {best_overall[1]['win_rate']*100:.1f}%")
        print(f"  取引数: {best_overall[1]['total_trades']}")
        print(f"  最終資金: ¥{best_overall[1]['final_capital']:,.0f}")
        print(f"  平均利益: ¥{best_overall[1]['avg_profit']:,.0f}")
        print(f"  最大利益: ¥{best_overall[1]['max_profit']:,.0f}")
        print(f"  最大損失: ¥{best_overall[1]['max_loss']:,.0f}")
    else:
        print(f"\n年利20%以上の戦略: 0件")
        print(f"年利が最も高い戦略を表示します")

        if all_results:
            best_overall = max(all_results.items(), key=lambda x: x[1]['annual_return'])
            symbol = best_overall[0].split('_')[0]

            print(f"\n最適戦略（年利最大）: {symbol}_2025_default")
            print(f"  年利: {best_overall[1]['annual_return']*100:.2f}%")
            print(f"  勝率: {best_overall[1]['win_rate']*100:.1f}%")
            print(f"  取引数: {best_overall[1]['total_trades']}")
            print(f"  最終資金: ¥{best_overall[1]['final_capital']:,.0f}")
            print(f"  平均利益: ¥{best_overall[1]['avg_profit']:,.0f}")
            print(f"  最大利益: ¥{best_overall[1]['max_profit']:,.0f}")
            print(f"  最大損失: ¥{best_overall[1]['max_loss']:,.0f}")

    # 年利ランキング
    print(f"\n年利ランキング（上位5位）:")
    sorted_results = sorted(all_results.items(), key=lambda x: x[1]['annual_return'], reverse=True)[:5]
    for i, (key, result) in enumerate(sorted_results, 1):
        symbol = key.split('_')[0]
        print(f"  {i}. {symbol}_2025_default: 年利{result['annual_return']*100:.2f}%, 勝率{result['win_rate']*100:.1f}%, 取引数{result['total_trades']}")

    logger.info("\n" + "=" * 80)
    logger.info("5年間バックテスト完了")
    logger.info("=" * 80)

    # Discord通知（あれば）
    # TODO: Discord通知機能を実装


if __name__ == "__main__":
    main()
