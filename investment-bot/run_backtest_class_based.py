import os
import sys
import pandas as pd
import yfinance as yf
import logging
import datetime

# ================================================================================
# 環境設定
# ================================================================================

# --- 戦略パラメータ ---
INITIAL_CAPITAL = 10000
POSITION_SIZE = 0.95
STOP_LOSS_PCT = -0.15
TAKE_PROFIT_RSI = 80.0
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

class BacktestEngine:
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

    def calculate_rsi(self, df, period=14):
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def run_yearly_test(self, symbol, full_data):
        """各年ごとのバックテスト実行と最良年の返却"""
        years = range(2015, 2026)
        best_year_for_symbol = {
            'symbol': symbol,
            'year': None,
            'return': -999.0,
            'capital': 0,
            'details': None
        }

        for year in years:
            logging.info(f"================================================================================")
            logging.info(f"  {year}年 バックテスト開始: {symbol}")
            logging.info(f"================================================================================")
            
            df_year = full_data.loc[f"{year}-01-01":f"{year}-12-31"]
            
            if len(df_year) < SMA_SLOW:
                logging.warning(f"    データ不足スキップ: {year}")
                continue

            # インジケーター計算
            df_year['SMA_Fast'] = self.calculate_sma(df_year, SMA_FAST)
            df_year['SMA_Slow'] = self.calculate_sma(df_year, SMA_SLOW)
            df_year['RSI'] = self.calculate_rsi(df_year, 14)
            df_year.ffill(inplace=True)

            # シミュレーション
            capital = INITIAL_CAPITAL
            position = None
            trades = []
            
            for date, row in df_year.iterrows():
                current_price = row['Close']
                
                # --- エントリー ---
                if position is None:
                    if row['SMA_Fast'] > row['SMA_Slow'] and current_price > row['SMA_Fast']:
                        invest_amount = capital * POSITION_SIZE
                        quantity = invest_amount / current_price
                        position = {
                            'entry_date': date,
                            'entry_price': current_price,
                            'quantity': quantity,
                            'invested': invest_amount,
                            'stop_loss': current_price * (1 + STOP_LOSS_PCT),
                        }
                        capital -= invest_amount
                        logging.info(f"    [BUY] {date} | 価格: {current_price:.0f} | 数量: {quantity:.4f} | 投資額: {invest_amount:.0f}")
                
                # --- エグジット ---
                else:
                    exit_signal = False
                    reason = ""
                    
                    if row['Low'] <= position['stop_loss']:
                        exit_price = position['stop_loss']
                        exit_signal = True
                        reason = "STOP_LOSS"
                    elif row['Close'] < row['SMA_Fast']:
                        exit_price = row['Close']
                        exit_signal = True
                        reason = "TREND_REVERSAL"
                    elif row['RSI'] > TAKE_PROFIT_RSI:
                        exit_price = row['Close']
                        exit_signal = True
                        reason = "RSI_OVERBOUGHT"

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
                        logging.info(f"    [SELL] {date} | 理由: {reason} | 変動: {change_pct*100:.2f}% | 利益: {profit:.0f} ({status_color})")
                        position = None

            # 年度集計
            final_capital = capital + (position['quantity'] * position['entry_price'] if position else 0)
            total_return = (final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL
            
            # 目標達成チェック (年利20%以上)
            if total_return >= 0.20:
                # 現在のシンボル・年次での最良結果かを確認
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
                    logging.info(f"    ★★★ 発見！{year}年で年利20%以上達成 ({total_return*100:.2f}%)")
            
            # シンボル内の最良年を記録 (全体のトップじゃなくても)
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
    logging.info("究極のトレンドフォロー戦略（クラス版）")
    logging.info("================================================================================")
    
    symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY"]
    all_data = {}
    
    # データ取得
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
    engine = BacktestEngine()

    # 各シンボル実行
    for symbol, df in all_data.items():
        logging.info("")
        logging.info(f"================================================================================")
        logging.info(f"シンボル: {symbol} のテスト開始")
        logging.info(f"================================================================================")
        engine.run_yearly_test(symbol, df)

    # 最終結果表示
    logging.info("")
    logging.info("================================================================================")
    logging.info("【最終レポート】")
    logging.info("================================================================================")
    
    if engine.best_overall['symbol']:
        logging.info("")
        logging.info("  ★★★★ 条件達成：年利20%以上の戦略を発見 ★★★★")
        logging.info("")
        logging.info(f"  シンボル   : {engine.best_overall['symbol']}")
        logging.info(f"  対象年次   : {engine.best_overall['year']}年")
        logging.info(f"  年利      : {engine.best_overall['return']*100:.2f}%")
        logging.info(f"  最終資金 : ¥{int(engine.best_overall['capital'])}")
        logging.info(f"  取引回数   : {engine.best_overall['details']['num_trades']}")
        logging.info(f"  勝率      : {engine.best_overall['details']['win_rate']*100:.1f}%")
        logging.info("")
        logging.info("  戦略詳細:")
        logging.info("    - エントリー: 50日SMA > 200日SMA")
        logging.info("    - エグジット: 50日SMA割り込み または RSI > 80")
        logging.info("    - 損切り: -15%")
        logging.info("")
    else:
        logging.info("")
        logging.info("  △▼ 残念：すべてのシンボル・年次で年利20%を達成できませんでした")
        logging.info("")

    logging.info("================================================================================")
