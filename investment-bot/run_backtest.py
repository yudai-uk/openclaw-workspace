"""
チャート分析専用バックテストシステム
過去5年間のデータを使って、最適な投資手法を確立する
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
import yfinance as yf

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import trading_config
from src.analyzer import AdvancedTechnicalAnalyzer

logger = logging.getLogger(__name__)


class ChartBacktester:
    """チャート分析専用バックテストクラス"""

    def __init__(self):
        self.symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY", "BCH-JPY", "LTC-JPY"]
        self.technical_analyzer = AdvancedTechnicalAnalyzer()

    def fetch_historical_data(self, period: str = "5y") -> Dict[str, pd.DataFrame]:
        """
        過去のデータを取得

        Args:
            period: データ期間

        Returns:
            シンボルごとのデータフレーム
        """
        logger.info(f"過去{period}分のデータを取得開始")

        data = {}

        for symbol in self.symbols:
            try:
                logger.info(f"シンボル: {symbol}")

                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period, interval="1d")

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

        # テクニカル指標計算
        technical = self.technical_analyzer.analyze({
            "symbol": df.index.name,
            "data": df.to_dict('records'),
            "current_price": df['Close'].iloc[-1],
            "change_pct": ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2]) * 100 if len(df) > 1 else 0,
        })

        # シグナルスコアと予測勝率を取得
        signal_score = technical.get("signal_score", 0)
        win_rate = technical.get("win_rate", 0.5)
        ensemble_signal = technical.get("ensemble_signal", "neutral")

        # 取引実行（シミュレーション）
        result = self._simulate_trades(df, technical, params)

        logger.info(f"バックテスト完了: {strategy_name}")
        return result

    def _simulate_trades(self, df: pd.DataFrame, technical: Dict[str, Any], params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        取引をシミュレート

        Args:
            df: チャートデータ
            technical: テクニカル分析結果
            params: 取引パラメータ

        Returns:
            取引結果
        """
        # パラメータ設定
        profit_target = params.get("profit_target", trading_config.PROFIT_TARGET) if params else trading_config.PROFIT_TARGET
        stop_loss = params.get("stop_loss", trading_config.STOP_LOSS) if params else trading_config.STOP_LOSS

        # 初期資金
        initial_capital = 10000
        capital = initial_capital

        trades = []
        position = None
        win_count = 0
        loss_count = 0

        # 過去のシグナルスコアを取得
        signal_scores = []
        for i in range(len(df)):
            if i >= 50:  # 最低50件必要
                # テクニカル指標計算
                sub_df = df.iloc[:i+1]
                sub_technical = self.technical_analyzer.analyze({
                    "symbol": df.index.name,
                    "data": sub_df.to_dict('records'),
                    "current_price": sub_df['Close'].iloc[-1],
                    "change_pct": ((sub_df['Close'].iloc[-1] - sub_df['Close'].iloc[-2]) / sub_df['Close'].iloc[-2]) * 100 if len(sub_df) > 1 else 0,
                })
                signal_scores.append(sub_technical.get("signal_score", 0))

        # 取引シミュレーション
        for i in range(50, len(df)):
            current_date = df.index[i]
            current_price = df['Close'].iloc[i]
            signal_score = signal_scores[i] if i < len(signal_scores) else 0

            # 予測勝率
            win_rate = 0.5 + (signal_score / 10) * 0.4

            # アンサンブルシグナル（簡易版）
            if signal_score > 3:
                action = "buy"
            elif signal_score < -3:
                action = "sell"
            else:
                action = "hold"

            # 勝率閾値チェック
            if win_rate < trading_config.TARGET_WIN_RATE:
                continue

            # ポジションがある場合
            if position is not None:
                entry_price = position['entry_price']
                entry_date = position['entry_date']

                # 利益目標または損切りに達した場合
                change_pct = (current_price - entry_price) / entry_price

                if change_pct >= profit_target or change_pct <= -stop_loss or action == "sell":
                    # ポジションをクローズ
                    profit = change_pct * position['quantity'] * entry_price
                    capital += profit

                    trade = {
                        "entry_date": entry_date,
                        "exit_date": current_date,
                        "entry_price": entry_price,
                        "exit_price": current_price,
                        "change_pct": change_pct * 100,
                        "profit": profit,
                        "capital": capital,
                    }

                    trades.append(trade)

                    if change_pct > 0:
                        win_count += 1
                    else:
                        loss_count += 1

                    position = None

            # 新規ポジションオープン
            elif action == "buy" and capital > 0:
                position_size = capital * 0.4  # 40%を投資
                quantity = position_size / current_price

                position = {
                    "symbol": df.index.name,
                    "entry_price": current_price,
                    "quantity": quantity,
                    "entry_date": current_date,
                }

                capital -= position_size

        # 最終結果
        final_capital = capital

        # 最後のポジションをクローズ（あれば）
        if position is not None:
            final_price = df['Close'].iloc[-1]
            change_pct = (final_price - position['entry_price']) / position['entry_price']
            profit = change_pct * position['quantity'] * position['entry_price']
            final_capital += profit

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
            "strategy": "default",
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

    def optimize_parameters(self, df: pd.DataFrame, param_ranges: Dict[str, List]) -> Dict[str, Any]:
        """
        パラメータ最適化（グリッドサーチ）

        Args:
            df: チャートデータ
            param_ranges: パラメータ範囲

        Returns:
            最適なパラメータと結果
        """
        logger.info("パラメータ最適化開始")

        best_result = None
        best_params = None

        # グリッドサーチ
        import itertools

        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())

        count = 0
        total = len(param_names) * len(param_values[0]) if param_values else 0

        for profit_target in param_ranges.get("profit_target", [0.02]):
            for stop_loss in param_ranges.get("stop_loss", [0.01]):
                params = {"profit_target": profit_target, "stop_loss": stop_loss}

                # バックテスト実行
                result = self.run_backtest(df, "optimization", params)

                # 最良結果を記録
                if best_result is None or result['annual_return'] > best_result['annual_return']:
                    best_result = result
                    best_params = params

                count += 1
                logger.info(f"最適化進捗: {count}/{total} - 年利{result['annual_return']*100:.2f}%")

        logger.info(f"パラメータ最適化完了")
        logger.info(f"最適パラメータ: {best_params}")
        logger.info(f"最適年利: {best_result['annual_return']*100:.2f}%")

        return {
            "best_params": best_params,
            "best_result": best_result,
        }


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
    logger.info("チャート分析専用バックテスト開始")
    logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    backtester = ChartBacktester()

    # ===== ステップ1: データ取得 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ1: 過去5年間のデータを取得")
    logger.info("=" * 80)

    data = backtester.fetch_historical_data(period="5y")

    if not data:
        logger.error("データが取得できませんでした")
        return

    # ===== ステップ2: デフォルトパラメータでバックテスト =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ2: デフォルトパラメータでバックテスト")
    logger.info("=" * 80)

    all_results = {}

    for symbol, df in data.items():
        logger.info(f"\n--- {symbol} バックテスト開始 ---")

        # デフォルトパラメータ
        result = backtester.run_backtest(df, "default")

        all_results[f"{symbol}_default"] = result

        logger.info(f"年利: {result['annual_return']*100:.2f}%")
        logger.info(f"勝率: {result['win_rate']*100:.1f}%")
        logger.info(f"取引数: {result['total_trades']}")
        logger.info(f"最終資金: ¥{result['final_capital']:,.0f}")

    # ===== ステップ3: パラメータ最適化 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ3: パラメータ最適化")
    logger.info("=" * 80)

    # 最も良いシンボルを選定
    if all_results:
        best_overall = max(all_results.items(), key=lambda x: x[1]['annual_return'])
        best_symbol = best_overall[1]['strategy'].split('_')[0]

        logger.info(f"最も良いシンボル: {best_symbol}")

        # パラメータ最適化
        if best_symbol in data:
            param_ranges = {
                "profit_target": [0.015, 0.02, 0.025, 0.03, 0.04],  # 1.5% ~ 4%
                "stop_loss": [0.008, 0.01, 0.012, 0.015, 0.02],  # 0.8% ~ 2%
            }

            optimization_result = backtester.optimize_parameters(data[best_symbol], param_ranges)

            all_results[f"{best_symbol}_optimized"] = optimization_result['best_result']

    # ===== ステップ4: サマリー表示 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ4: サマリー表示")
    logger.info("=" * 80)

    print(f"\n{'=' * 80}")
    print(f"チャート分析専用バックテスト結果（過去5年間ベース）")
    print(f"{'=' * 80}")

    # 年利20%以上の戦略を抽出
    profitable_strategies = {
        key: result for key, result in all_results.items()
        if result['annual_return'] >= 0.20
    }

    if profitable_strategies:
        print(f"\n年利20%以上の戦略: {len(profitful_strategies)}件")

        # 最も良い戦略を表示
        best_overall = max(profitful_strategies.items(), key=lambda x: x[1]['annual_return'])
        symbol = best_overall[0].split('_')[0]
        strategy = '_'.join(best_overall[0].split('_')[1:])

        print(f"\n最適戦略: {symbol}_{strategy}")
        print(f"  年利: {best_overall[1]['annual_return']*100:.2f}%")
        print(f"  勝率: {best_overall[1]['win_rate']*100:.1f}%")
        print(f"  取引数: {best_overall[1]['total_trades']}")
        print(f"  最終資金: ¥{best_overall[1]['final_capital']:,.0f}")
        print(f"  平均利益: ¥{best_overall[1]['avg_profit']:,.0f}")
        print(f"  最大利益: ¥{best_overall[1]['max_profit']:,.0f}")
        print(f"  最大損失: ¥{best_overall[1]['max_loss']:,.0f}")

        if best_overall[1]['params']:
            print(f"  パラメータ: {best_overall[1]['params']}")
    else:
        print(f"\n年利20%以上の戦略: 0件")
        print(f"年利が最も高い戦略を表示します")

        if all_results:
            best_overall = max(all_results.items(), key=lambda x: x[1]['annual_return'])
            symbol = best_overall[0].split('_')[0]
            strategy = '_'.join(best_overall[0].split('_')[1:])

            print(f"\n最適戦略（年利最大）: {symbol}_{strategy}")
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
        strategy = '_'.join(key.split('_')[1:])
        print(f"  {i}. {symbol}_{strategy}: 年利{result['annual_return']*100:.2f}%, 勝率{result['win_rate']*100:.1f}%, 取引数{result['total_trades']}")

    logger.info("\n" + "=" * 80)
    logger.info("バックテスト完了")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
