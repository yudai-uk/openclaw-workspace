"""
情報収集モジュール（仮想通貨版）
ニュース、SNS、チャートデータを収集する
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import feedparser
import requests
import yfinance as yf
from bs4 import BeautifulSoup

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import analysis_config

logger = logging.getLogger(__name__)


class NewsCollector:
    """ニュース収集クラス"""

    def __init__(self):
        self.sources = analysis_config.NEWS_SOURCES

    def collect_news(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        ニュースを収集

        Args:
            hours: 過去何時間分のニュースを収集するか

        Returns:
            ニュース記事のリスト
        """
        logger.info(f"ニュース収集開始（過去{hours}時間分）")
        news_list = []

        cutoff_time = datetime.now() - timedelta(hours=hours)

        for url in self.sources:
            try:
                logger.info(f"ニュースソース: {url}")
                feed = feedparser.parse(url)

                for entry in feed.entries:
                    published = self._parse_date(entry)

                    if published < cutoff_time:
                        continue

                    news_list.append({
                        "title": entry.get("title", ""),
                        "content": self._clean_content(entry.get("description", entry.get("summary", ""))),
                        "url": entry.get("link", ""),
                        "published": published.isoformat(),
                        "source": url,
                    })

                logger.info(f"  → {len(news_list)}件のニュースを取得")

            except Exception as e:
                logger.error(f"ニュース収集エラー ({url}): {e}")

        logger.info(f"ニュース収集完了: {len(news_list)}件")
        return news_list

    def _parse_date(self, entry: Any) -> datetime:
        """日付をパース"""
        try:
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6])
            else:
                return datetime.now() - timedelta(hours=1)
        except:
            return datetime.now() - timedelta(hours=1)

    def _clean_content(self, content: str) -> str:
        """HTMLタグを削除"""
        if not content:
            return ""
        soup = BeautifulSoup(content, "html.parser")
        return soup.get_text(strip=True)


class TwitterCollector:
    """Twitter (X) 収集クラス"""

    def __init__(self, bearer_token: str = None):
        self.bearer_token = bearer_token
        self.keywords = analysis_config.TWITTER_KEYWORDS

    def collect_tweets(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        ツイートを収集

        Args:
            hours: 過去何時間分のツイートを収集するか

        Returns:
            ツイートのリスト
        """
        if not self.bearer_token:
            logger.warning("Twitter APIキーが設定されていません")
            return []

        logger.info(f"ツイート収集開始（過去{hours}時間分）")
        tweets = []

        try:
            import tweepy

            client = tweepy.Client(bearer_token=self.bearer_token)

            for keyword in self.keywords:
                try:
                    logger.info(f"キーワード: {keyword}")

                    query = f"{keyword} -is:retweet lang:ja"
                    response = client.search_recent_tweets(
                        query=query,
                        max_results=100,
                        tweet_fields=["created_at", "author_id", "public_metrics"],
                    )

                    if response.data:
                        for tweet in response.data:
                            tweets.append({
                                "text": tweet.text,
                                "created_at": tweet.created_at.isoformat(),
                                "author_id": tweet.author_id,
                                "metrics": tweet.public_metrics,
                                "keyword": keyword,
                            })

                    logger.info(f"  → {len(tweets)}件のツイートを取得")

                except Exception as e:
                    logger.error(f"ツイート収集エラー ({keyword}): {e}")

        except ImportError:
            logger.error("tweepyがインストールされていません")
        except Exception as e:
            logger.error(f"Twitter APIエラー: {e}")

        logger.info(f"ツイート収集完了: {len(tweets)}件")
        return tweets


class ChartDataCollector:
    """チャートデータ収集クラス（仮想通貨）"""

    def __init__(self):
        pass

    def collect_chart_data(self, symbols: List[str], period: str = "1mo") -> Dict[str, Any]:
        """
        チャートデータを収集

        Args:
            symbols: 通貨ペアのリスト（例: ["BTC_JPY", "ETH_JPY"]）
            period: データ期間 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

        Returns:
            チャートデータの辞書 {symbol: data}
        """
        logger.info(f"チャートデータ収集開始: {len(symbols)}通貨")

        chart_data = {}

        for symbol in symbols:
            try:
                logger.info(f"通貨: {symbol}")

                # Yahoo Financeシンボルに変換
                yf_symbol = self._to_yahoo_finance_symbol(symbol)

                if not yf_symbol:
                    logger.warning(f"  Yahoo Financeシンボルが見つかりません: {symbol}")
                    continue

                ticker = yf.Ticker(yf_symbol)
                hist = ticker.history(period=period, interval="1h")

                if hist.empty:
                    logger.warning(f"  データなし: {symbol}")
                    continue

                # 直近の価格
                latest_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2] if len(hist) > 1 else hist['Close'].iloc[0]
                change_pct = ((latest_price - prev_price) / prev_price) * 100

                chart_data[symbol] = {
                    "symbol": symbol,
                    "current_price": latest_price,
                    "previous_price": prev_price,
                    "change_pct": change_pct,
                    "data": hist.to_dict('records'),
                    "period": period,
                }

                logger.info(f"  現在価格: {latest_price:,.2f}円 ({change_pct:+.2f}%)")

            except Exception as e:
                logger.error(f"チャートデータ収集エラー ({symbol}): {e}")

        logger.info(f"チャートデータ収集完了: {len(chart_data)}通貨")
        return chart_data

    def _to_yahoo_finance_symbol(self, bitflyer_symbol: str) -> str:
        """
        bitFlyerシンボルをYahoo Financeシンボルに変換

        Args:
            bitflyer_symbol: bitFlyerシンボル（例: BTC_JPY）

        Returns:
            Yahoo Financeシンボル（例: BTC-JPY）
        """
        # Yahoo Financeのシンボルマッピング
        mapping = {
            "BTC_JPY": "BTC-JPY",
            "ETH_JPY": "ETH-JPY",
            "XRP_JPY": "XRP-JPY",
            "BCH_JPY": "BCH-JPY",
            "LTC_JPY": "LTC-JPY",
        }

        return mapping.get(bitflyer_symbol, None)


class CollectorManager:
    """情報収集マネージャー（チャートデータのみ、感情分析なし）"""

    def __init__(self, twitter_bearer_token: str = None):
        # 感情分析は無効化
        self.chart_collector = ChartDataCollector()

    def collect_all(self, symbols: List[str], hours: int = 24) -> Dict[str, Any]:
        """
        チャートデータのみを収集（感情分析なし）

        Args:
            symbols: 通貨ペアのリスト
            hours: 過去何時間分の情報を収集するか（今回は無効）

        Returns:
            チャートデータの辞書 {symbol: data}
        """
        logger.info("=== チャートデータ収集開始（感情分析なし）===")

        data = {
            "timestamp": datetime.now().isoformat(),
            "chart_data": {},
        }

        # チャートデータ収集
        data["chart_data"] = self.chart_collector.collect_chart_data(symbols=symbols)

        logger.info(f"チャートデータ収集完了: {len(data['chart_data'])}通貨")

        return data


if __name__ == "__main__":
    # テスト実行
    import logging
    logging.basicConfig(level=logging.INFO)

    manager = CollectorManager(twitter_bearer_token="")
    data = manager.collect_all(
        symbols=["BTC_JPY", "ETH_JPY"],  # BTC, ETH
        hours=24,
    )

    print(f"\nニュース: {len(data['news'])}件")
    print(f"ツイート: {len(data['tweets'])}件")
    print(f"チャートデータ: {len(data['chart_data'])}通貨")
