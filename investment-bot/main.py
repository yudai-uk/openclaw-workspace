"""
改善版投資ボット - メイン実行ファイル（チャート分析専用版・修正済）
感情分析なし、テクニカル分析のみで完璧にする
"""

import logging
import argparse
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    trading_config,
    api_config,
    analysis_config,
)
from src.collector import CollectorManager
from src.analyzer import AdvancedTechnicalAnalyzer
from src.trader import TradeManager
from src.monitor import DiscordNotifier, TradeMonitor


def setup_logging():
    """ログ設定"""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"bot_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(),
        ]
    )

    return logging.getLogger(__name__)


def main(dry_run: bool = True, send_notification: bool = False, trading_mode: str = "swing"):
    """
    メイン処理（改善版チャート分析専用）

    Args:
        dry_run: ドライランモード（実際には注文しない）
        send_notification: Discord通知を送るか
        trading_mode: 取引モード ("swing" または "day"）
    """
    logger = setup_logging()

    logger.info("=" * 80)
    logger.info("改善版投資ボット開始（チャート分析専用）")
    logger.info(f"実行モード: {'ドライラン' if dry_run else '本番'}")
    logger.info(f"取引モード: {trading_mode} ({'スイングトレード' if trading_mode == 'swing' else 'デイトレード'})")
    logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    # 通知初期化（例外処理の前に行う）
    notifier = DiscordNotifier(webhook_url=api_config.DISCORD_WEBHOOK_URL) if (send_notification and api_config.DISCORD_WEBHOOK_URL) else None

    try:
        # コンポーネント初期化
        logger.info("コンポーネント初期化...")

        # 情報収集マネージャー（チャートデータのみ）
        collector = CollectorManager(twitter_bearer_token="")  # Twitterは無効化

        # 高度なテクニカル分析器
        technical_analyzer = AdvancedTechnicalAnalyzer()

        # 取引マネージャー（短期取引対応）
        trader = TradeManager(
            api_key=api_config.BITFLYER_API_KEY,
            api_secret=api_config.BITFLYER_API_SECRET,
            dry_run=dry_run,
            trading_mode=trading_mode,
        )

        # 監視モジュール
        monitor = TradeMonitor()

        logger.info("コンポーネント初期化完了")

        # ===== ステップ1: モデル学習（今回はスキップ） =====
        logger.info("\n" + "=" * 80)
        logger.info("ステップ1: モデル学習（チャート分析専用なのでスキップ）")
        logger.info("=" * 80)

        # ===== ステップ2: チャートデータ収集 =====
        logger.info("\n" + "=" * 80)
        logger.info("ステップ2: チャートデータ収集")
        logger.info("=" * 80)

        # チャートデータのみ収集
        chart_data = collector.collect_all(symbols=trading_config.cryptos)

        logger.info(f"チャートデータ収集完了: {len(chart_data['chart_data'])}通貨")

        # ===== ステップ3: 高度なテクニカル分析 =====
        logger.info("\n" + "=" * 80)
        logger.info("ステップ3: 高度なテクニカル分析")
        logger.info("=" * 80)

        signals = {}

        for symbol, data in chart_data['chart_data'].items():
            # 高度なテクニカル分析
            technical = technical_analyzer.analyze(data)

            # シグナルを保存
            signals[symbol] = technical

            logger.info(f"\n{symbol}:")
            logger.info(f"  テクニカルシグナル: {technical.get('ensemble_signal', 'neutral')}")
            logger.info(f"  シグナルスコア: {technical.get('signal_score', 0):.2f}")
            logger.info(f"  予測勝率: {technical.get('win_rate', 0):.1%}")
            logger.info(f"  取引アクション: {technical.get('action')}")

        # ===== ステップ4: 取引実行 =====
        logger.info("\n" + "=" * 80)
        logger.info("ステップ4: 取引実行")
        logger.info("=" * 80)

        trades = trader.execute_trades(signals)

        logger.info(f"実行された取引: {len(trades)}件")

        # ===== ステップ5: 通知 =====
        if notifier:
            logger.info("\n" + "=" * 80)
            logger.info("ステップ5: 通知送信")
            logger.info("=" * 80)

            # サマリー通知
            notifier.send_technical_summary_notification(signals, trades)

            # 取引通知
            for trade in trades:
                signal = signals.get(trade['symbol'])
                if signal:
                    notifier.send_trade_notification(trade, signal)

        # ===== ステップ6: パフォーマンスレポート =====
        logger.info("\n" + "=" * 80)
        logger.info("ステップ6: パフォーマンスレポート")
        logger.info("=" * 80)

        summary = monitor.get_technical_performance_summary()
        logger.info(summary)

        if notifier:
            # 日次レポートを送信（1日1回、例えば朝9時に）
            current_hour = datetime.now().hour
            if current_hour == 9:
                notifier.send_notification(summary)

        logger.info("\n" + "=" * 80)
        logger.info("改善版投資ボット完了（チャート分析専用）")
        logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"エラー発生: {e}", exc_info=True)

        if notifier:
            notifier.send_error_notification(str(e))

        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="改善版投資ボット（チャート分析専用）")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="ドライランモード（実際には注文しない）",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="本番モード（実際に注文する）",
    )
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Discord通知を送る",
    )
    parser.add_argument(
        "--mode",
        choices=["swing", "day"],
        default="swing",
        help="取引モード（swing=スイングトレード, day=デイトレード）",
    )

    args = parser.parse_args()

    # ドライラン/本番モード決定
    dry_run = not args.live

    # 実行
    main(dry_run=dry_run, send_notification=args.notify, trading_mode=args.mode)
