import os
import sys
import pandas as pd
import yfinance as yf
import logging
import datetime

# ================================================================================
# 環境設定
# ================================================================================

# --- 戦略パラメータ (V4 Final: Guardian + ATR Filter) ---
INITIAL_CAPITAL = 10000
POSITION_SIZE = 0.95
TRAILING_STOP_PCT = 0.15
SMA_FAST = 50
SMA_SLOW = 200
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5 # ATRが平均の1.5倍を超えた時のみエントリー（ボラティリティ拡大検知）

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ================================================================================
# バックテストエンジン (クラス構造)
# ================================================================================

class BacktestEngineV4Final:
    def __init__(self):
        pass

    def calculate_sma(self, df, period):
        return df['Close'].rolling(window=period).mean()

    def calculate_atr(self, df, period):
        """ATR (Average True Range) 計算"""
        high = df['High']
        low = df['Low']
        tr = high - low
        return tr.rolling(window=period).mean()

    def run_simulation(self, symbol, full_data):
        """2015年〜2025年の完全シミュレーション"""
        years = range(2015, 2026) # 2015年から2025年まで
        results = []
        
        for year in years:
            df_year = full_data.loc[f"{year}-01-01":f"{year}-12-31"]
            
            # データ不足の場合はスキップ (0%と記録)
            if len(df_year) < SMA_SLOW:
                results.append({
                    'year': year,
                    'return_pct': 0.0,
                    'final_capital': INITIAL_CAPITAL,
                    'status': 'NO_DATA'
                })
                continue

            # インジケーター計算
            df_year['SMA_Fast'] = self.calculate_sma(df_year, SMA_FAST)
            df_year['SMA_Slow'] = self.calculate_sma(df_year, SMA_SLOW)
            df_year['ATR'] = self.calculate_atr(df_year, ATR_PERIOD)
            df_year['ATR_Mean'] = df_year['ATR'].rolling(window=20).mean()
            
            # 欠損値処理
            df_year.ffill(inplace=True)

            # シミュレーション (年単位でリセット、前年キャピタルを10000として再検証)
            # ※ 注: 実運用は複利ですが、戦略の年次ごとのパフォーマンス比較のため、
            #    各年の初期資金を10000としてリセットして計算します。
            capital = INITIAL_CAPITAL
            position = None
            
            for date, row in df_year.iterrows():
                current_price = row['Close']
                
                # --- エントリーロジック (V4: Guardian + ATR Filter) ---
                if position is None:
                    # 基本条件 (Guardian)
                    cond_golden_cross = row['SMA_Fast'] > row['SMA_Slow']
                    cond_price_above_long_sma = current_price > row['SMA_Slow']
                    
                    # 追加条件 (V4 ATR Filter): ボラティリティ拡大確認
                    # → レンジ相場（低ボラティリティ）でのだましエントリーを防止
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
            status = 'WIN' if total_return >= 0 else 'LOSS'
            
            results.append({
                'year': year,
                'return_pct': total_return,
                'final_capital': final_capital,
                'status': status
            })
        
        return results

# ================================================================================
# メイン実行
# ================================================================================
if __name__ == "__main__":
    logging.info("================================================================================")
    logging.info("V4 Final Simulation: BTC, ETH, XRP (2015-2025)")
    logging.info("================================================================================")
    
    symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY"]
    all_results = {}
    
    logging.info("データ取得中...")
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="12y", interval="1d")
            df.dropna(inplace=True)
            if not df.empty:
                all_results[symbol] = df
                logging.info(f"  取得完了: {symbol}")
        except Exception as e:
            logging.error(f"  エラー: {symbol} - {e}")

    engine = BacktestEngineV4Final()

    for symbol, df in all_results.items():
        logging.info(f"--------------------------------------------------------------------------------")
        logging.info(f"シンボル: {symbol} のシミュレーション開始 (V4)")
        logging.info(f"--------------------------------------------------------------------------------")
        
        sim_results = engine.run_simulation(symbol, df)
        
        logging.info(f"{'年次':<6} | {'成績':<8} | {'収益率':<10} | {'最終資金':<12}")
        logging.info("--------+----------+------------+--------------")
        
        win_count = 0
        loss_count = 0
        
        for r in sim_results:
            if r['status'] == 'NO_DATA':
                status_marker = " DATAなし "
            else:
                status_marker = " WIN " if r['status'] == 'WIN' else " LOSS "
                if r['status'] == 'WIN': win_count += 1
                if r['status'] == 'LOSS': loss_count += 1
            
            logging.info(f"{r['year']} | {status_marker:<10} | {r['return_pct']*100:>7.2f}% | ¥{int(r['final_capital']):>10,}")
        
        # シンボルサマリー
        logging.info("--------+----------+------------+--------------")
        total_years = len(sim_results)
        if total_years > 0:
            win_rate = (win_count / total_years) * 100
            logging.info(f"[シンボルサマリー] 勝率: {win_rate:.1f}% ({win_count}/{total_years})")
            if win_rate >= 70:
                logging.info(f"                 -> 優れた戦略です。")
            elif win_rate >= 50:
                logging.info(f"                 -> 良好な戦略です。")
            else:
                logging.info(f"                 -> 改善の余地があります。")
        else:
            logging.info(f"[シンボルサマリー] データなし")

    logging.info("")
    logging.info("================================================================================")
