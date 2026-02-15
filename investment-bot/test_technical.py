"""
簡易なテスト実行スクリプト（チャート分析専用版）
感情分析なし、テクニカル分析のみ
"""

import logging
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

from config import trading_config
from src.collector import CollectorManager
from src.analyzer import AdvancedTechnicalAnalyzer


def setup_logging():
    """ログ設定"""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(),
        ]
    )

    return logging.getLogger(__name__)


def main():
    """メイン処理"""
    logger = setup_logging()

    logger.info("=" * 80)
    logger.info("チャート分析専用版テスト実行開始")
    logger.info(f"日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    try:
        # ===== コンポーネント初期化 =====
        logger.info("コンポーネント初期化...")

        # 情報収集マネージャー（チャートデータのみ）
        collector = CollectorManager(twitter_bearer_token="")

        # 高度なテクニカル分析器
        technical_analyzer = AdvancedTechnicalAnalyzer()

        logger.info("コンポーネント初期化完了")

        # ===== チャートデータ収集 =====
        logger.info("\n" + "=" * 80)
        logger.info("ステップ1: チャートデータ収集")
        logger.info("=" * 80)

        chart_data = collector.collect_all(symbols=trading_config.cryptos)

        logger.info(f"チャートデータ収集完了: {len(chart_data['chart_data'])}通貨")

        # ===== 高度なテクニカル分析 =====
        logger.info("\n" + "=" * 80)
        logger.info("ステップ2: 高度なテクニカル分析")
        logger.info("=" * 80)

        for symbol, data in chart_data['chart_data'].items():
            # 高度なテクニカル分析
            technical = technical_analyzer.analyze(data)

            logger.info(f"\n{symbol}:")
            logger.info(f"  テクニカルシグナル: {technical.get('ensemble_signal', 'neutral')}")
            logger.info(f"  シグナルスコア: {technical.get('signal_score', 0):.2f}")
            logger.info(f"  予測勝率: {technical.get('win_rate', 0):.1%}")
            logger.info(f"  取引アクション: {technical.get('action')}")

        logger.info("\n" + "=" * 80)
        logger.info("テスト実行完了")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"エラー発生: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
