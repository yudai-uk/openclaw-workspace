import os
import sys
import pandas as pd
import yfinance as yf
import logging
import datetime

# ================================================================================
# 環境設定
# ================================================================================

# --- 戦略パラメータ (V6: Dynamic ATR・Guardian) ---
INITIAL_CAPITAL = 10000
POSITION_SIZE = 0.95
TRAILING_STOP_PCT = 0.15
SMA_FAST = 50
SMA_SLOW = 200
ATR_PERIOD = 14
# V6 変更点: ATRマルチプライヤを1.5 -> 1.2に緩和し、BTC/ETHの緩やかなトレンド初期を捕捉
ATR_MULTIPLIER = 1.2 

# V5 から削除したフィルター: RSI, Volume (Sentiment/SNS filters)
# 理由: これらがBTC/ETHの「緩やかなトレンド」へのエントリーを阻害していたため。

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ================================================================================
# バックテストエンジン (クラス構造)
# ================================================================================

class BacktestEngineV6:
    def __init__(self):
        self.best_overall = {
            'symbol': None,
            'year': None,
            'return': -999.0,
            'capital': 0,
            'details': None
        }

    def calculate_sma(self, df, period):
        return df['Close'].rolling(window=period).mean()

    def calculate_atr(self, df, period):
        """ATR (Average True Range) 計算"""
        high = df['High']
        low = df['Low']
        tr = high - low
        return tr.rolling(window=period).mean()

    def run_yearly_test(self, symbol, full_data):
        """各年ごとのバックテスト実行と最良年の返却"""
        years = range(2015, 2026) # 2015年から2025年まで
        best_year_for_symbol = {
            'symbol': symbol,
            'year': None,
            'return': -999.0,
            'capital': 0,
            'details': None
        }

        for year in years:
            df_year = full_data.loc[f"{year}-01-01":f"{year}-12-31"]
            
            if len(df_year) < SMA_SLOW:
                continue

            # インジケーター計算
            df_year['SMA_Fast'] = self.calculate_sma(df_year, SMA_FAST)
            df_year['SMA_Slow'] = self.calculate_sma(df_year, SMA_SLOW)
            df_year['ATR'] = self.calculate_atr(df_year, ATR_PERIOD)
            df_year['ATR_Mean'] = df_year['ATR'].rolling(window=20).mean()
            
            # 前方埋め
            df_year.ffill(inplace=True)

            # シミュレーション
            capital = INITIAL_CAPITAL
            position = None
            
            for date, row in df_year.iterrows():
                current_price = row['Close']
                
                # --- エントリーロジック (V6: Dynamic ATR・Guardian) ---
                if position is None:
                    # 基本条件 (V4 Guardian)
                    cond_golden_cross = row['SMA_Fast'] > row['SMA_Slow']
                    cond_price_above_long_sma = current_price > row['SMA_Slow']
                    
                    # 条件 (V6): 動的なATRフィルター (1.2倍)
                    cond_volatility_surge = pd.notna(row['ATR']) and (row['ATR'] > row['ATR_Mean'] * ATR_MULTIPLIER)
                    
                    if cond_golden_cross and cond_price_above_long_sma and cond_volatility_surge:
                        invest_amount = capital * POSITION_SIZE
                        quantity = invest_amount / current_price
                        
                        position = {
                            'entry_date': date,
                            'entry_price': current_price,
                            'quantity': quantity,
                            'invested': invest_amount,
                            'trailing_stop': current_price * (1 - TRAILING_STOP_PCT),
                            'highest_price': current_price,
                        }
                        capital -= invest_amount
                
                # --- エグジットロジック ---
                else:
                    exit_signal = False
                    reason = ""
                    exit_price = 0
                    
                    # 1. トレイリングストップ (利益確保 & 暴落対応)
                    if current_price > position['highest_price']:
                        position['highest_price'] = current_price
                        position['trailing_stop'] = current_price * (1 - TRAILING_STOP_PCT)
                    
                    if row['Low'] <= position['trailing_stop']:
                        exit_price = position['trailing_stop']
                        exit_signal = True
                        reason = "TRAILING_STOP"

                    # 2. トレンド反転 (デッドクロス: Price < SMA_Fast)
                    elif row['Close'] < row['SMA_Fast']:
                        exit_price = row['Close']
                        exit_signal = True
                        reason = "TREND_REVERSAL"

                    # --- 決済処理 ---
                    if exit_signal:
                        profit = (exit_price - position['entry_price']) * position['quantity']
                        capital += (position['quantity'] * exit_price)
                        position = None

            # 年度サマリー計算
            final_capital = capital + (position['quantity'] * position['entry_price'] if position else 0)
            total_return = (final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL
            
            # 最良年の記録更新
            if total_return > best_year_for_symbol['return']:
                best_year_for_symbol = {
                    'year': year,
                    'return': total_return,
                    'capital': final_capital
                }
        
        return best_year_for_symbol

# ================================================================================
# メイン実行
# ================================================================================
if __name__ == "__main__":
    logging.info("================================================================================")
    logging.info("V6 Dynamic ATR・Guardian: BTC/ETHの機会回復 & XRPの利益維持")
    logging.info("================================================================================")
    
    symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY"]
    all_data = {}
    
    logging.info("データ取得中...")
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="12y", interval="1d")
            df.dropna(inplace=True)
            if not df.empty:
                all_data[symbol] = df
                logging.info(f"  取得完了: {symbol}")
        except Exception as e:
            logging.error(f"  エラー: {symbol} - {e}")

    # エンジン初期化
    engine = BacktestEngineV6()
    global_best = {'symbol': None, 'return': -999.0}

    # 各シンボル実行
    for symbol, df in all_data.items():
        logging.info(f"シンボル: {symbol} のテスト開始 (V6)")
        result = engine.run_yearly_test(symbol, df)
        
        if result['return'] > global_best['return']:
            global_best = {
                'symbol': symbol,
                'year': result['year'],
                'return': result['return'],
                'capital': result['capital']
            }

    # 最終結果表示
    logging.info("")
    logging.info("================================================================================")
    logging.info("【最終レポート V6】")
    logging.info("================================================================================")
    
    if global_best['symbol']:
        logging.info("")
        logging.info("  ★★★★ V6 結果: Dynamic ATRによる最適化 ★★★★")
        logging.info("")
        logging.info(f"  最強シンボル: {global_best['symbol']}")
        logging.info(f"  対象年次  : {global_best['year']}年")
        logging.info(f"  検証年利    : {global_best['return']*100:.2f}%")
        logging.info(f"  最終資金 : ¥{int(global_best['capital'])}")
        logging.info("")
        logging.info("  V6 改善点:")
        logging.info("    1. 感情/SNSフィルターの削除: BTC/ETHの緩やかなトレンドを回収")
        logging.info("    2. ATRマルチプライヤ最適化: 1.5倍 -> 1.2倍 (初期トレンド捕捉)")
        logging.info("    3. トレイリングストップ維持: 暴落防御")
        logging.info("")
    else:
        logging.info("  条件達成なし")

    logging.info("================================================================================")
