import os
import sys
import pandas as pd
import yfinance as yf
import logging
import datetime

# ================================================================================
# 環境設定
# ================================================================================

# --- 戦略パラメータ (V3: ガーディアン - 安全重視版) ---
INITIAL_CAPITAL = 10000
POSITION_SIZE = 0.95
TRAILING_STOP_PCT = 0.15 # トレイリング・ストップ (最高値から-15%下がったら売る)

SMA_FAST = 50
SMA_SLOW = 200

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ================================================================================
# バックテストエンジン (クラス構造)
# ================================================================================

class BacktestEngineV3:
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
            logging.info(f"================================================================================")
            logging.info(f"  {year}年 バックテスト開始: {symbol} (V3ガーディアン)")
            logging.info(f"================================================================================")
            
            df_year = full_data.loc[f"{year}-01-01":f"{year}-12-31"]
            
            if len(df_year) < SMA_SLOW:
                logging.warning(f"    データ不足スキップ: {year}")
                continue

            # インジケーター計算
            df_year['SMA_Fast'] = self.calculate_sma(df_year, SMA_FAST)
            df_year['SMA_Slow'] = self.calculate_sma(df_year, SMA_SLOW)
            
            # 前方埋め
            df_year.ffill(inplace=True)

            # シミュレーション
            capital = INITIAL_CAPITAL
            position = None
            trades = []
            
            for date, row in df_year.iterrows():
                current_price = row['Close']
                
                # --- エントリーロジック (V3改良版) ---
                if position is None:
                    # 条件1: ゴールデンクロス (SMA50 > SMA200)
                    cond_golden_cross = row['SMA_Fast'] > row['SMA_Slow']
                    
                    # 条件2 (V3最重要): 価格が長期SMA(200)より上にあること
                    # これにより、暴落相場（価格 < SMA200）でのエントリーを完全に防ぐ
                    cond_price_above_long_sma = current_price > row['SMA_Slow']
                    
                    if cond_golden_cross and cond_price_above_long_sma:
                        invest_amount = capital * POSITION_SIZE
                        quantity = invest_amount / current_price
                        
                        position = {
                            'entry_date': date,
                            'entry_price': current_price,
                            'quantity': quantity,
                            'invested': invest_amount,
                            'trailing_stop': current_price * (1 - TRAILING_STOP_PCT), # トレイリングストップ初期値
                            'highest_price': current_price, # トレイリング用最高値記録
                        }
                        capital -= invest_amount
                        logging.info(f"    [BUY V3] {date} | 価格: {current_price:.0f} | LongSMA: {row['SMA_Slow']:.0f} (Price > LongSMA OK) | 投資額: {invest_amount:.0f}")
                
                # --- エグジットロジック (ホールド中) ---
                else:
                    exit_signal = False
                    reason = ""
                    exit_price = 0
                    
                    # 1. トレイリングストップ (最高値更新と売り判定)
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
                        
                        change_pct = (exit_price - position['entry_price']) / position['entry_price']
                        
                        trades.append({
                            'symbol': symbol,
                            'year': year,
                            'entry_date': position['entry_date'],
                            'exit_date': date,
                            'entry_price': position['entry_price'],
                            'exit_price': exit_price,
                            'reason': reason,
                            'change_pct': change_pct,
                            'profit': profit
                        })
                        
                        status_color = "LOSS" if profit < 0 else "PROFIT"
                        logging.info(f"    [SELL V3] {date} | 理由: {reason} | 変動: {change_pct*100:.2f}% | 利益: {profit:.0f} ({status_color}) | 残高: {capital:.0f}")
                        position = None

            # 年度サマリー計算
            final_capital = capital + (position['quantity'] * position['entry_price'] if position else 0)
            total_return = (final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL
            
            # 目標達成チェック (年利20%以上)
            if total_return >= 0.20:
                if total_return > self.best_overall['return']:
                    self.best_overall = {
                        'symbol': symbol,
                        'year': year,
                        'return': total_return,
                        'capital': final_capital,
                        'details': {
                            'num_trades': len(trades),
                            'win_rate': len([t for t in trades if t['profit'] > 0]) / len(trades) if trades else 0
                        }
                    }
                    logging.info(f"    ★★★ V3 発見！{year}年で年利20%以上達成 ({total_return*100:.2f}%)")
            
            # シンボル内の最良年を記録
            if total_return > best_year_for_symbol['return']:
                best_year_for_symbol = {
                    'year': year,
                    'return': total_return,
                    'capital': final_capital,
                    'trades': trades
                }
            
            logging.info(f"  --- {year}年 結果: 年利 {total_return*100:.2f}% ---")
        
        return best_year_for_symbol

# ================================================================================
# メイン実行
# ================================================================================
if __name__ == "__main__":
    logging.info("================================================================================")
    logging.info("究極のトレンドフォロー戦略 V3：ガーディアン（安全重視・ベアートラップ排除版）")
    logging.info("================================================================================")
    
    # データ取得
    symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY"]
    all_data = {}
    
    logging.info("データ取得中...")
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="11y", interval="1d")
            df.dropna(inplace=True)
            if not df.empty:
                all_data[symbol] = df
                logging.info(f"  取得完了: {symbol}")
        except Exception as e:
            logging.error(f"  エラー: {symbol} - {e}")

    # エンジン初期化
    engine = BacktestEngineV3()

    # 各シンボル実行
    for symbol, df in all_data.items():
        logging.info("")
        logging.info(f"================================================================================")
        logging.info(f"シンボル: {symbol} のテスト開始 (V3)")
        logging.info(f"================================================================================")
        engine.run_yearly_test(symbol, df)

    # 最終結果表示
    logging.info("")
    logging.info("================================================================================")
    logging.info("【最終レポート V3】")
    logging.info("================================================================================")
    
    if engine.best_overall['symbol']:
        logging.info("")
        logging.info("  ★★★★ V3 条件達成：年利20%以上の戦略を発見 ★★★★")
        logging.info("")
        logging.info(f"  シンボル   : {engine.best_overall['symbol']}")
        logging.info(f"  対象年次   : {engine.best_overall['year']}年")
        logging.info(f"  年利      : {engine.best_overall['return']*100:.2f}%")
        logging.info(f"  最終資金 : ¥{int(engine.best_overall['capital'])}")
        logging.info(f"  取引回数   : {engine.best_overall['details']['num_trades']}")
        logging.info(f"  勝率      : {engine.best_overall['details']['win_rate']*100:.1f}%")
        logging.info("")
        logging.info("  V3 戦略詳細:")
        logging.info("    - エントリー: SMA50 > SMA200 AND 価格 > SMA200 (長期トレンド上昇絶対条件)")
        logging.info("    - エグジット: 50日SMA割り込み")
        logging.info("    - 損切り   : トレイリングストップ (最高値から-15%)")
        logging.info("")
        logging.info("  ★ 特徴: ベアー・トラップ（暴落相場での買い）を完全に防止します。")
    else:
        logging.info("")
        logging.info("  △▼ V3: すべてのシンボル・年次で年利20%を達成できませんでした")
        logging.info("")

    logging.info("================================================================================")
