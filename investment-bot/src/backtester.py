"""
バックテストモジュール
過去のデータで戦略をテストし、最適な投資手法を確立する
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


class Backtester:
    """バックテストクラス"""

    def __init__(self):
        self.symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY", "BCH-JPY", "LTC-JPY"]

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

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        テクニカル指標を計算

        Args:
            df: OHLCVデータ

        Returns:
            指標付きデータフレーム
        """
        df = df.copy()

        # 移動平均線
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA10'] = df['Close'].rolling(window=10).mean()
        df['MA25'] = df['Close'].rolling(window=25).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()

        # RSI
        df['RSI'] = self._calculate_rsi(df, period=14)

        # MACD
        df['MACD'], df['MACD_SIGNAL'], df['MACD_HIST'] = self._calculate_macd(df)

        # ボリンジャーバンド
        df['BB_UPPER'], df['BB_MIDDLE'], df['BB_LOWER'] = self._calculate_bollinger_bands(df)

        # 価格変動率
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=20).std()

        return df

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        RSIを計算

        Args:
            df: データフレーム
            period: 期間

        Returns:
            RSIシリーズ
        """
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _calculate_macd(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        MACDを計算

        Args:
            df: データフレーム

        Returns:
            (MACDライン, シグナルライン, ヒストグラム)
        """
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()

        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = macd_line - signal_line

        return macd_line, signal_line, macd_histogram

    def _calculate_bollinger_bands(self, df: pd.DataFrame, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        ボリンジャーバンドを計算

        Args:
            df: データフレーム
            period: 期間
            std_dev: 標準偏差の倍数

        Returns:
            (上限, 中間, 下限)
        """
        middle = df['Close'].rolling(window=period).mean()
        std = df['Close'].rolling(window=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)

        return upper, middle, lower

    def test_strategy(self, df: pd.DataFrame, strategy: str, **params) -> Dict[str, Any]:
        """
        戦略をテスト

        Args:
            df: データフレーム
            strategy: 戦略名
            **params: 戦略パラメータ

        Returns:
            テスト結果
        """
        logger.info(f"戦略テスト: {strategy} ({params})")

        df = df.copy()

        # 戦略に基づいてシグナルを生成
        if strategy == "rsi":
            signals = self._rsi_strategy(df, **params)
        elif strategy == "macd":
            signals = self._macd_strategy(df, **params)
        elif strategy == "ma_crossover":
            signals = self._ma_crossover_strategy(df, **params)
        elif strategy == "bollinger":
            signals = self._bollinger_strategy(df, **params)
        elif strategy == "multi":
            signals = self._multi_strategy(df, **params)
        else:
            raise ValueError(f"未知の戦略: {strategy}")

        # 取引結果を計算
        results = self._calculate_trading_results(df, signals, **params)

        logger.info(f"戦略テスト完了: {strategy}")
        return results

    def _rsi_strategy(self, df: pd.DataFrame, rsi_buy: float = 30, rsi_sell: float = 70) -> pd.Series:
        """
        RSI戦略

        Args:
            df: データフレーム
            rsi_buy: 買いRSI閾値
            rsi_sell: 売りRSI閾値

        Returns:
            シグナルシリーズ (1=買い, -1=売り, 0=ホールド)
        """
        signals = pd.Series(0, index=df.index)

        # 買いシグナル: RSI < rsi_buy
        signals[df['RSI'] < rsi_buy] = 1

        # 売りシグナル: RSI > rsi_sell
        signals[df['RSI'] > rsi_sell] = -1

        return signals

    def _macd_strategy(self, df: pd.DataFrame) -> pd.Series:
        """
        MACD戦略

        Args:
            df: データフレーム

        Returns:
            シグナルシリーズ
        """
        signals = pd.Series(0, index=df.index)

        # 買いシグナル: MACDラインがシグナルラインを上回る
        signals[(df['MACD'] > df['MACD_SIGNAL']) & (df['MACD'].shift(1) <= df['MACD_SIGNAL'].shift(1))] = 1

        # 売りシグナル: MACDラインがシグナルラインを下回る
        signals[(df['MACD'] < df['MACD_SIGNAL']) & (df['MACD'].shift(1) >= df['MACD_SIGNAL'].shift(1))] = -1

        return signals

    def _ma_crossover_strategy(self, df: pd.DataFrame, ma_short: int = 5, ma_long: int = 25) -> pd.Series:
        """
        移動平均線クロスオーバー戦略

        Args:
            df: データフレーム
            ma_short: 短期移動平均
            ma_long: 長期移動平均

        Returns:
            シグナルシリーズ
        """
        signals = pd.Series(0, index=df.index)

        # 短期・長期移動平均を計算
        df['MA_SHORT'] = df['Close'].rolling(window=ma_short).mean()
        df['MA_LONG'] = df['Close'].rolling(window=ma_long).mean()

        # ゴールデンクロス（買いシグナル）
        signals[(df['MA_SHORT'] > df['MA_LONG']) & (df['MA_SHORT'].shift(1) <= df['MA_LONG'].shift(1))] = 1

        # デッドクロス（売りシグナル）
        signals[(df['MA_SHORT'] < df['MA_LONG']) & (df['MA_SHORT'].shift(1) >= df['MA_LONG'].shift(1))] = -1

        return signals

    def _bollinger_strategy(self, df: pd.DataFrame) -> pd.Series:
        """
        ボリンジャーバンド戦略

        Args:
            df: データフレーム

        Returns:
            シグナルシリーズ
        """
        signals = pd.Series(0, index=df.index)

        # 買いシグナル: 価格が下限を下回る
        signals[df['Close'] < df['BB_LOWER']] = 1

        # 売りシグナル: 価格が上限を上回る
        signals[df['Close'] > df['BB_UPPER']] = -1

        return signals

    def _multi_strategy(self, df: pd.DataFrame) -> pd.Series:
        """
        複合戦略（複数の戦略を組み合わせる）

        Args:
            df: データフレーム

        Returns:
            シグナルシリーズ
        """
        signals = pd.Series(0, index=df.index)

        # RSIシグナル
        rsi_buy = df['RSI'] < 30
        rsi_sell = df['RSI'] > 70

        # MACDシグナル
        macd_buy = df['MACD_HIST'] > 0
        macd_sell = df['MACD_HIST'] < 0

        # 移動平均線シグナル
        ma_buy = df['Close'] > df['MA50']
        ma_sell = df['Close'] < df['MA50']

        # 複合買いシグナル（3つの条件すべて満たす）
        signals[rsi_buy & macd_buy & ma_buy] = 1

        # 複合売りシグナル（3つの条件すべて満たす）
        signals[rsi_sell & macd_sell & ma_sell] = -1

        return signals

    def _calculate_trading_results(self, df: pd.DataFrame, signals: pd.Series,
                                 profit_target: float = 0.025,
                                 stop_loss: float = 0.012,
                                 initial_capital: float = 10000) -> Dict[str, Any]:
        """
        取引結果を計算

        Args:
            df: データフレーム
            signals: シグナルシリーズ
            profit_target: 利益目標（割合）
            stop_loss: 損切り（割合）
            initial_capital: 初期資金

        Returns:
            取引結果
        """
        capital = initial_capital
        position = None  # {"symbol": str, "entry_price": float, "quantity": float, "entry_date": datetime}

        trades = []
        win_count = 0
        loss_count = 0

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

                if change_pct >= profit_target or change_pct <= -stop_loss or signal == -1:
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
            elif signal == 1 and capital > 0:
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

    def optimize_strategy(self, df: pd.DataFrame, strategy: str, param_ranges: Dict[str, List]) -> Dict[str, Any]:
        """
        戦略を最適化（グリッドサーチ）

        Args:
            df: データフレーム
            strategy: 戦略名
            param_ranges: パラメータ範囲

        Returns:
            最適なパラメータと結果
        """
        logger.info(f"戦略最適化開始: {strategy}")

        best_result = None
        best_params = None

        # グリッドサーチ
        import itertools

        param_names = list(param_ranges.keys())
        param_values = list(param_ranges.values())

        for params in itertools.product(*param_values):
            param_dict = dict(zip(param_names, params))

            # 戦略をテスト
            result = self.test_strategy(df, strategy, **param_dict)

            # 最良結果を記録
            if best_result is None or result['annual_return'] > best_result['annual_return']:
                best_result = result
                best_params = param_dict

        logger.info(f"戦略最適化完了: {strategy}")
        logger.info(f"最適パラメータ: {best_params}")
        logger.info(f"最適結果: 年利{best_result['annual_return']*100:.2f}%")

        return {
            "best_params": best_params,
            "best_result": best_result,
            "strategy": strategy,
        }


if __name__ == "__main__":
    # テスト実行
    import logging
    logging.basicConfig(level=logging.INFO)

    backtester = Backtester()

    # データ取得
    data = backtester.fetch_historical_data(period="5y")

    # テスト実行
    for symbol, df in data.items():
        print(f"\n=== {symbol} バックテスト ===")

        # 指標計算
        df = backtester.calculate_indicators(df)

        # 各戦略をテスト
        strategies = ["rsi", "macd", "ma_crossover", "bollinger", "multi"]

        for strategy in strategies:
            result = backtester.test_strategy(df, strategy)
            print(f"\n{strategy}:")
            print(f"  年利: {result['annual_return']*100:.2f}%")
            print(f"  勝率: {result['win_rate']*100:.1f}%")
            print(f"  取引数: {result['total_trades']}")
            print(f"  総利益: ¥{result['final_capital']:,.0f}")
