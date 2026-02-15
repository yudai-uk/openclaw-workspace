"""
戦略最適化スクリプト
過去5年間のデータを使って、最適な投資戦略を確立する
"""

import logging
import json
from datetime import datetime
from pathlib import Path

from src.backtester import Backtester

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger.info("=" * 80)
    logger.info("戦略最適化開始")
    logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    backtester = Backtester()

    # ===== ステップ1: データ取得 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ1: 過去5年間のデータを取得")
    logger.info("=" * 80)

    data = backtester.fetch_historical_data(period="5y")

    if not data:
        logger.error("データが取得できませんでした")
        return

    # ===== ステップ2: 全戦略テスト =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ2: 全戦略をテスト")
    logger.info("=" * 80)

    all_results = {}

    for symbol, df in data.items():
        logger.info(f"\n--- {symbol} テスト開始 ---")

        # 指標計算
        df = backtester.calculate_indicators(df)

        # 各戦略をテスト
        strategies = {
            "rsi": {},
            "macd": {},
            "ma_crossover": {},
            "bollinger": {},
            "multi": {},
        }

        for strategy, params in strategies.items():
            result = backtester.test_strategy(df, strategy, **params)

            all_results[f"{symbol}_{strategy}"] = {
                "symbol": symbol,
                "strategy": strategy,
                "annual_return": result['annual_return'],
                "win_rate": result['win_rate'],
                "total_trades": result['total_trades'],
                "final_capital": result['final_capital'],
                "max_profit": result['max_profit'],
                "max_loss": result['max_loss'],
            }

            logger.info(f"{strategy}: 年利{result['annual_return']*100:.2f}%, 勝率{result['win_rate']*100:.1f}%")

    # ===== ステップ3: 最適戦略のパラメータ最適化 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ3: 最適戦略のパラメータ最適化")
    logger.info("=" * 80)

    best_overall_strategy = None
    best_overall_result = None
    best_overall_symbol = None

    # 年利20%以上の戦略を抽出
    profitable_strategies = {
        key: result for key, result in all_results.items()
        if result['annual_return'] >= 0.20  # 年利20%以上
    }

    logger.info(f"\n年利20%以上の戦略: {len(profitable_strategies)}件")

    if profitable_strategies:
        # 最適な戦略を選定
        best_overall = max(profitful_strategies.items(), key=lambda x: x[1]['annual_return'])
        best_overall_symbol = best_overall[1]['symbol']
        best_overall_strategy = best_overall[1]['strategy']
        best_overall_result = best_overall[1]

        logger.info(f"\n最適戦略: {best_overall_symbol}_{best_overall_strategy}")
        logger.info(f"  年利: {best_overall_result['annual_return']*100:.2f}%")
        logger.info(f"  勝率: {best_overall_result['win_rate']*100:.1f}%")
        logger.info(f"  取引数: {best_overall_result['total_trades']}")
        logger.info(f"  最終資金: ¥{best_overall_result['final_capital']:,.0f}")

        # パラメータ最適化
        if best_overall_strategy == "rsi":
            param_ranges = {
                "rsi_buy": [20, 25, 30, 35],
                "rsi_sell": [65, 70, 75, 80],
                "profit_target": [0.02, 0.025, 0.03],
                "stop_loss": [0.008, 0.01, 0.012, 0.015],
            }
        elif best_overall_strategy == "ma_crossover":
            param_ranges = {
                "ma_short": [5, 10, 15],
                "ma_long": [25, 30, 50],
                "profit_target": [0.02, 0.025, 0.03],
                "stop_loss": [0.008, 0.01, 0.012, 0.015],
            }
        else:
            param_ranges = {}

        if param_ranges:
            logger.info(f"\nパラメータ最適化開始...")

            optimization_result = backtester.optimize_strategy(
                data[best_overall_symbol],
                best_overall_strategy,
                param_ranges
            )

            best_overall_result['optimized_params'] = optimization_result['best_params']
            best_overall_result['optimized_result'] = optimization_result['best_result']

            logger.info(f"\n最適パラメータ: {optimization_result['best_params']}")
            logger.info(f"最適化後の年利: {optimization_result['best_result']['annual_return']*100:.2f}%")

    # ===== ステップ4: 全結果を保存 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ4: 全結果を保存")
    logger.info("=" * 80)

    output_dir = Path(__file__).parent / "data" / "backtest_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 全結果を保存
    output_file = output_dir / f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    logger.info(f"全結果を保存: {output_file}")

    # 最適戦略を保存
    if best_overall_strategy:
        best_file = output_dir / "best_strategy.json"

        with open(best_file, 'w') as f:
            json.dump({
                "symbol": best_overall_symbol,
                "strategy": best_overall_strategy,
                "result": best_overall_result,
                "optimized_params": best_overall_result.get('optimized_params', {}),
            }, f, indent=2, default=str)

        logger.info(f"最適戦略を保存: {best_file}")

    # ===== ステップ5: サマリー表示 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ5: サマリー表示")
    logger.info("=" * 80)

    if best_overall_strategy:
        print(f"""
{'=' * 80}
最適な投資戦略（過去5年間ベース）
{'=' * 80}

通貨: {best_overall_symbol}
戦略: {best_overall_strategy}

パフォーマンス:
  年利: {best_overall_result['annual_return']*100:.2f}%
  勝率: {best_overall_result['win_rate']*100:.1f}%
  取引数: {best_overall_result['total_trades']}
  最終資金: ¥{best_overall_result['final_capital']:,.0f}
  平均利益: ¥{best_overall_result['avg_profit']:,.0f}
  最大利益: ¥{best_overall_result['max_profit']:,.0f}
  最大損失: ¥{best_overall_result['max_loss']:,.0f}
""")

        if best_overall_result.get('optimized_params'):
            print(f"""
最適パラメータ:
""")
            for param, value in best_overall_result['optimized_params'].items():
                print(f"  {param}: {value}")

    print(f"""
年利20%以上の戦略: {len(profitful_strategies)}件
テストした戦略総数: {len(all_results)}件
""")

    logger.info("\n" + "=" * 80)
    logger.info("戦略最適化完了")
    logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
