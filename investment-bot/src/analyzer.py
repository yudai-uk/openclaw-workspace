import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import talib

from config import trading_config

logger = logging.getLogger(__name__)

class AdvancedTechnicalAnalyzer:
    def __init__(self):
        pass

    def analyze(self, market_data):
        """
        チャート分析APIと互換性のあるインターフェース
        
        Args:
            market_data (dict): 市場データ
        """
        # データフレームを作成
        df = pd.DataFrame(market_data['data'])
        
        # 日付インデックスを設定
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
        else:
            df.index = pd.to_datetime(df.index)
            df.sort_index(inplace=True)
            
        # 必要なカラムの確認と型変換
        df['Close'] = df['Close'].astype(float)
        df['High'] = df['High'].astype(float)
        df['Low'] = df['Low'].astype(float)
        df['Open'] = df['Open'].astype(float)
        
        # テクニカル指標の計算
        df = self.calculate_indicators(df)
        
        # 高度な分析（新戦略：ボラティリティ・ブレイクアウト）
        # 最新のシグナルスコアを取得
        if len(df) >= 50:
            action = self.breakout_strategy(df)
            signal_score = self._calculate_signal_score(df, action)
        else:
            action = "neutral"
            signal_score = 0
            
        # 勝率推定
        base_win_rate = 0.45
        win_rate = base_win_rate + (signal_score / 10.0) * 0.3
        win_rate = max(0.1, min(0.9, win_rate))
        
        return {
            "signal_score": signal_score,
            "win_rate": win_rate,
            "ensemble_signal": action,
            "indicators": {
                "rsi": df['rsi'].iloc[-1] if 'rsi' in df and len(df) > 0 else None,
                "macd": df['macd'].iloc[-1] if 'macd' in df and len(df) > 0 else None,
                "signal": df['macdsignal'].iloc[-1] if 'macdsignal' in df and len(df) > 0 else None,
            }
        }
    
    def _calculate_signal_score(self, df, action):
        """シグナルスコア計算（簡易版）"""
        score = 0
        if action == "buy":
            score = 8.0 # 強い買いシグナル
        elif action == "sell":
            score = -8.0 # 強い売りシグナル
        else:
            score = 0
        return score

    def calculate_indicators(self, df):
        """基本的なテクニカル指標を計算"""
        # 終値
        df['close'] = df['Close']
        df['high'] = df['High']
        df['low'] = df['Low']
        
        # SMA (Simple Moving Average) - 50日線を主に使用
        df['sma_50'] = df['close'].rolling(window=50).mean()
        
        # 期間最高値 (50日間) - ブレイクアウト戦略用
        df['high_50'] = df['high'].rolling(window=50).max()
        
        # RSI (Relative Strength Index) - 参考用
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)

        # MACD (参考用)
        macd, macdsignal, macdhist = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['macd'] = macd
        df['macdsignal'] = macdsignal
        df['macdhist'] = macdhist

        return df

    def breakout_strategy(self, df, row_idx=None):
        """
        ボラティリティ・ブレイクアウト戦略（Volatility Breakout）
        
        ルール:
        1. 買い: 価格が過去50日間の最高値を更新した時 (High > High_50)
        2. 売り: 価格がSMA50を下回った時
        """
        if len(df) < 50:
            return "neutral"
        
        if row_idx is None:
            current_data = df.iloc[-1]
        else:
            current_data = df.iloc[row_idx]
            
        current_price = current_data['close']
        current_high = current_data['high']
        
        sma_50 = current_data['sma_50']
        high_50 = current_data['high_50']
        
        # 1. 買いシグナル: 新高更新
        is_buy = current_high > high_50
        
        # 2. 売りシグナル: トレンド崩壊
        is_sell = current_price < sma_50
        
        # 判定
        if is_buy:
            return "buy"
        elif is_sell:
            return "sell"
        else:
            return "hold"

    # 以前のadvanced_technical_analysisは破棄し、breakout_strategyを使用します。
    def advanced_technical_analysis(self, df, row_idx=None):
        # 互換性維持のためラッパー
        return self.breakout_strategy(df, row_idx)
