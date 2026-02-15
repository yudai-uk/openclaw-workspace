"""
改善版戦略最適化スクリプト
過去5年間のデータを使って、最適な投資戦略を確立する（改善版）
"""

import logging
import json
from datetime import datetime
from pathlib import Path

from src.improved_backtester import ImprovedBacktester

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger.info("=" * 80)
    logger.info("改善版戦略最適化開始")
    logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    backtester = ImprovedBacktester()

    # ===== ステップ1: データ取得 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ1: 過去5年間のデータを取得")
    logger.info("=" * 80)

    data = backtester.fetch_historical_data(period="5y")

    if not data:
        logger.error("データが取得できませんでした")
        return

    # ===== ステップ2: 全改善戦略テスト =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ2: 全改善戦略をテスト")
    logger.info("=" * 80)

    all_results = {}

    for symbol, df in data.items():
        logger.info(f"\n--- {symbol} テスト開始 ---")

        # 高度な指標計算
        df = backtester.calculate_advanced_indicators(df)

        # 各改善戦略をテスト
        strategies = ["trend_following", "mean_reversion", "momentum", "volatility_breakout", "adaptive"]

        for strategy in strategies:
            result = backtester.test_improved_strategy(df, strategy)

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

    # ===== ステップ3: 年利20%以上の戦略を抽出 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ3: 年利20%以上の戦略を抽出")
    logger.info("=" * 80)

    profitable_strategies = {
        key: result for key, result in all_results.items()
        if result['annual_return'] >= 0.20  # 年利20%以上
    }

    logger.info(f"年利20%以上の戦略: {len(profitable_strategies)}件")

    # 年利20%以上の戦略を表示
    for key, result in profitable_strategies.items():
        logger.info(f"  {key}: 年利{result['annual_return']*100:.2f}%, 勝率{result['win_rate']*100:.1f}%")

    # ===== ステップ4: 最適戦略の選定 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ4: 最適戦略の選定")
    logger.info("=" * 80)

    if profitable_strategies:
        best_overall = max(profitful_strategies.items(), key=lambda x: x[1]['annual_return'])
        best_overall_symbol = best_overall[1]['symbol']
        best_overall_strategy = best_overall[1]['strategy']
        best_overall_result = best_overall[1]

        logger.info(f"\n最適戦略: {best_overall_symbol}_{best_overall_strategy}")
        logger.info(f"  年利: {best_overall_result['annual_return']*100:.2f}%")
        logger.info(f"  勝率: {best_overall_result['win_rate']*100:.1f}%")
        logger.info(f"  取引数: {best_overall_result['total_trades']}")
        logger.info(f"  最終資金: ¥{best_overall_result['final_capital']:,.0f}")
    else:
        logger.info("\n年利20%以上の戦略が見つかりませんでした")
        logger.info("年利が最も高い戦略を表示します")

        # 年利が最も高い戦略を表示
        if all_results:
            best_overall = max(all_results.items(), key=lambda x: x[1]['annual_return'])
            best_overall_symbol = best_overall[1]['symbol']
            best_overall_strategy = best_overall[1]['strategy']
            best_overall_result = best_overall[1]

            logger.info(f"\n最適戦略（年利最大）: {best_overall_symbol}_{best_overall_strategy}")
            logger.info(f"  年利: {best_overall_result['annual_return']*100:.2f}%")
            logger.info(f"  勝率: {best_overall_result['win_rate']*100:.1f}%")
            logger.info(f"  取引数: {best_overall_result['total_trades']}")
            logger.info(f"  最終資金: ¥{best_overall_result['final_capital']:,.0f}")
        else:
            logger.info("戦略が見つかりませんでした")
            return

    # ===== ステップ5: 全結果を保存 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ5: 全結果を保存")
    logger.info("=" * 80)

    output_dir = Path(__file__).parent / "data" / "backtest_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 全結果を保存
    output_file = output_dir / f"improved_backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    logger.info(f"全結果を保存: {output_file}")

    # 最適戦略を保存
    if profitable_strategies:
        best_file = output_dir / "best_improved_strategy.json"

        with open(best_file, 'w') as f:
            json.dump({
                "symbol": best_overall_symbol,
                "strategy": best_overall_strategy,
                "result": best_overall_result,
            }, f, indent=2, default=str)

        logger.info(f"最適戦略を保存: {best_file}")

    # ===== ステップ6: サマリー表示 =====
    logger.info("\n" + "=" * 80)
    logger.info("ステップ6: サマリー表示")
    logger.info("=" * 80)

    if profitable_strategies:
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

    print(f"""
年利20%以上の戦略: {len(profitable_strategies)}件
テストした戦略総数: {len(all_results)}件
""")

    # 年利が最も高い戦略をランキング表示
    print(f"年利ランキング（上位5位）:")
    sorted_results = sorted(all_results.items(), key=lambda x: x[1]['annual_return'], reverse=True)[:5]
    for i, (key, result) in enumerate(sorted_results, 1):
        print(f"  {i}. {key}: 年利{result['annual_return']*100:.2f}%, 勝率{result['win_rate']*100:.1f}%")

    logger.info("\n" + "=" * 80)
    logger.info("改善版戦略最適化完了")
    logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
