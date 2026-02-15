"""
改善版バックテストモジュール
より高度な戦略とリスク管理を導入して、年利20%達成を目指す
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

logger = logging.getLogger(__name__)


class ImprovedBacktester:
    """改善版バックテストクラス"""

    def __init__(self):
        self.symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY", "BCH-JPY", "LTC-JPY"]

    def fetch_historical_data(self, period: str = "5y") -> Dict[str, pd.DataFrame]:
        """過去のデータを取得"""
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

    def calculate_advanced_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """高度なテクニカル指標を計算"""
        df = df.copy()

        # 基本的な指標
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA10'] = df['Close'].rolling(window=10).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()

        # RSI
        df['RSI'] = self._calculate_rsi(df, period=14)

        # MACD
        df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = self._calculate_macd(df)

        # ボリンジャーバンド
        df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = self._calculate_bollinger_bands(df)

        # ATR（Average True Range）- ボラティリティ指標
        df['ATR'] = self._calculate_atr(df, period=14)

        # ボラティリティ調整
        df['Volatility'] = df['Close'].pct_change().rolling(window=20).std()

        # トレンド検出
        df['Trend'] = np.where(df['MA20'] > df['MA50'], 1, -1)

        # サポート/レジスタンス
        df['Support'] = df['Close'].rolling(window=20).min()
        df['Resistance'] = df['Close'].rolling(window=20).max()

        return df

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """RSIを計算"""
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACDを計算"""
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = macd_line - signal_line
        return macd_line, signal_line, macd_histogram

    def _calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """ボリンジャーバンドを計算"""
        middle = df['Close'].rolling(window=period).mean()
        std = df['Close'].rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """ATRを計算"""
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    def test_improved_strategy(self, df: pd.DataFrame, strategy: str, **params) -> Dict[str, Any]:
        """改善戦略をテスト"""
        logger.info(f"改善戦略テスト: {strategy} ({params})")

        df = df.copy()

        # 戦略に基づいてシグナルを生成
        if strategy == "trend_following":
            signals = self._trend_following_strategy(df, **params)
        elif strategy == "mean_reversion":
            signals = self._mean_reversion_strategy(df, **params)
        elif strategy == "momentum":
            signals = self._momentum_strategy(df, **params)
        elif strategy == "volatility_breakout":
            signals = self._volatility_breakout_strategy(df, **params)
        elif strategy == "adaptive":
            signals = self._adaptive_strategy(df, **params)
        else:
            raise ValueError(f"未知の戦略: {strategy}")

        # 取引結果を計算（高度なリスク管理付き）
        results = self._calculate_advanced_trading_results(df, signals, **params)

        logger.info(f"改善戦略テスト完了: {strategy}")
        return results

    def _trend_following_strategy(self, df: pd.DataFrame) -> pd.Series:
        """トレンドフォロー戦略"""
        signals = pd.Series(0, index=df.index)

        # 上昇トレンド + MACDクロスオーバー
        buy_condition = (df['Trend'] == 1) & (df['MACD_HIST'] > 0) & (df['MACD_HIST'].shift(1) <= 0)
        signals[buy_condition] = 1

        # 下降トレンド + MACDクロスアンダー
        sell_condition = (df['Trend'] == -1) & (df['MACD_HIST'] < 0) & (df['MACD_HIST'].shift(1) >= 0)
        signals[sell_condition] = -1

        return signals

    def _mean_reversion_strategy(self, df: pd.DataFrame) -> pd.Series:
        """平均回帰戦略"""
        signals = pd.Series(0, index=df.index)

        # 価格がサポートに近い + RSI売られすぎ
        buy_condition = (df['Close'] < df['Support'] * 1.02) & (df['RSI'] < 30)
        signals[buy_condition] = 1

        # 価格がレジスタンスに近い + RSI買われすぎ
        sell_condition = (df['Close'] > df['Resistance'] * 0.98) & (df['RSI'] > 70)
        signals[sell_condition] = -1

        return signals

    def _momentum_strategy(self, df: pd.DataFrame) -> pd.Series:
        """モメンタム戦略"""
        signals = pd.Series(0, index=df.index)

        # 5日間で+5%以上上昇 + RSI < 70
        buy_condition = (df['Close'] / df['Close'].shift(5) - 1 > 0.05) & (df['RSI'] < 70)
        signals[buy_condition] = 1

        # 5日間で-5%以上下落 + RSI > 30
        sell_condition = (df['Close'] / df['Close'].shift(5) - 1 < -0.05) & (df['RSI'] > 30)
        signals[sell_condition] = -1

        return signals

    def _volatility_breakout_strategy(self, df: pd.DataFrame) -> pd.Series:
        """ボラティリティブレイクアウト戦略"""
        signals = pd.Series(0, index=df.index)

        # ボリンジャーバンドブレイクアウト（上方）
        buy_condition = (df['Close'] > df['BB_UPPER']) & (df['Volume'] > df['Volume'].rolling(20).mean())
        signals[buy_condition] = 1

        # ボリンジャーバンドブレイクアウト（下方）
        sell_condition = (df['Close'] < df['BB_LOWER']) & (df['Volume'] > df['Volume'].rolling(20).mean())
        signals[sell_condition] = -1

        return signals

    def _adaptive_strategy(self, df: pd.DataFrame) -> pd.Series:
        """アダプティブ戦略（市場状況に応じて戦略を変更）"""
        signals = pd.Series(0, index=df.index)

        # 高ボラティリティ時: モメンタム戦略
        high_vol = df['Volatility'] > df['Volatility'].quantile(0.75)
        momentum_buy = (df['Close'] / df['Close'].shift(5) - 1 > 0.05)
        signals[high_vol & momentum_buy] = 1

        momentum_sell = (df['Close'] / df['Close'].shift(5) - 1 < -0.05)
        signals[high_vol & momentum_sell] = -1

        # 低ボラティリティ時: 平均回帰戦略
        low_vol = df['Volatility'] < df['Volatility'].quantile(0.25)
        mean_reversion_buy = (df['Close'] < df['Support'] * 1.02) & (df['RSI'] < 30)
        signals[low_vol & mean_reversion_buy] = 1

        mean_reversion_sell = (df['Close'] > df['Resistance'] * 0.98) & (df['RSI'] > 70)
        signals[low_vol & mean_reversion_sell] = -1

        return signals

    def _calculate_advanced_trading_results(self, df: pd.DataFrame, signals: pd.Series,
                                        profit_target: float = 0.025,
                                        stop_loss: float = 0.012,
                                        max_daily_loss: float = 0.05,
                                        max_consecutive_losses: int = 3,
                                        initial_capital: float = 10000) -> Dict[str, Any]:
        """高度な取引結果を計算（リスク管理付き）"""
        capital = initial_capital
        position = None
        trades = []
        win_count = 0
        loss_count = 0
        consecutive_losses = 0

        for i in range(1, len(df)):
            current_date = df.index[i]
            current_price = df['Close'].iloc[i]
            signal = signals.iloc[i]

            # ポジションがある場合
            if position is not None:
                entry_price = position['entry_price']
                entry_date = position['entry_date']

                # 利益目標または損切りに達した場合
                change_pct = (current_price - entry_price) / entry_price

                # 利益目標、損切り、売りシグナルのいずれかでクローズ
                if change_pct >= profit_target or change_pct <= -stop_loss or signal == -1:
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
                        consecutive_losses = 0
                    else:
                        loss_count += 1
                        consecutive_losses += 1

                    position = None

                    # 連続損失が一定数を超えた場合、その日の取引を停止
                    if consecutive_losses >= max_consecutive_losses:
                        # 次の日まで取引をスキップ
                        for j in range(i + 1, min(i + 24, len(df))):
                            if df.index[j].date() != current_date.date():
                                i = j
                                break

            # 新規ポジションオープン
            elif signal == 1 and capital > 0:
                # 連続損失が一定数を超えている場合はスキップ
                if consecutive_losses >= max_consecutive_losses:
                    continue

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

        results = {
            "strategy": signals.name if hasattr(signals, 'name') else "unknown",
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
        }

        return results


if __name__ == "__main__":
    # テスト実行
    import logging
    logging.basicConfig(level=logging.INFO)

    backtester = ImprovedBacktester()

    # データ取得
    data = backtester.fetch_historical_data(period="5y")

    # テスト実行
    for symbol, df in data.items():
        print(f"\n=== {symbol} 改善戦略バックテスト ===")

        # 指標計算
        df = backtester.calculate_advanced_indicators(df)

        # 各戦略をテスト
        strategies = ["trend_following", "mean_reversion", "momentum", "volatility_breakout", "adaptive"]

        for strategy in strategies:
            result = backtester.test_improved_strategy(df, strategy)
            print(f"\n{strategy}:")
            print(f"  年利: {result['annual_return']*100:.2f}%")
            print(f"  勝率: {result['win_rate']*100:.1f}%")
            print(f"  取引数: {result['total_trades']}")
            print(f"  総利益: ¥{result['final_capital']:,.0f}")
