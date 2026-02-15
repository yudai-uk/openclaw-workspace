import os
import sys
import pandas as pd
import yfinance as yf
import logging
import datetime

# ================================================================================
# 環境設定
# ================================================================================

# --- 戦略パラメータ (V2: 改良版) ---
INITIAL_CAPITAL = 10000
POSITION_SIZE = 0.95
# 注: Trailing Stop は動的に計算されるため、ここでは初期値のみ定義
TRAILING_STOP_PCT = 0.15 # 最高値から15%下がったら売る (ボラティリティに対応)

# インジケーター設定
SMA_FAST = 50
SMA_SLOW = 200
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
BB_PERIOD = 20
BB_STD = 2.0

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ================================================================================
# バックテストエンジン (クラス構造)
# ================================================================================

class BacktestEngineV2:
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

    def calculate_macd(self, df):
        """MACDを計算"""
        ema_fast = df['Close'].ewm(span=MACD_FAST, adjust=False).mean()
        ema_slow = df['Close'].ewm(span=MACD_SLOW, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=9, adjust=False).mean()
        return macd, signal

    def calculate_bb_width(self, df):
        """ボリンジャーバンドの幅を計算（ボラティリティ指標）"""
        middle = df['Close'].rolling(window=BB_PERIOD).mean()
        std = df['Close'].rolling(window=BB_PERIOD).std()
        upper = middle + (std * BB_STD)
        lower = middle - (std * BB_STD)
        # 幅 = (上限 - 下限) / 中心
        width = (upper - lower) / middle
        return width

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
            logging.info(f"  {year}年 バックテスト開始: {symbol} (V2改良版)")
            logging.info(f"================================================================================")
            
            df_year = full_data.loc[f"{year}-01-01":f"{year}-12-31"]
            
            if len(df_year) < SMA_SLOW:
                logging.warning(f"    データ不足スキップ: {year}")
                continue

            # インジケーター計算
            df_year['SMA_Fast'] = self.calculate_sma(df_year, SMA_FAST)
            df_year['SMA_Slow'] = self.calculate_sma(df_year, SMA_SLOW)
            df_year['RSI'] = self.calculate_rsi(df_year, 14)
            
            # V2: 追加インジケーター
            macd, signal = self.calculate_macd(df_year)
            df_year['MACD'] = macd
            df_year['MACD_Signal'] = signal
            df_year['BB_Width'] = self.calculate_bb_width(df_year)
            
            # 前方埋め
            df_year.ffill(inplace=True)

            # シミュレーション
            capital = INITIAL_CAPITAL
            position = None
            trades = []
            
            for date, row in df_year.iterrows():
                current_price = row['Close']
                
                # --- エントリーロジック (V2改良版) ---
                if position is None:
                    # 条件1: ゴールデンクロス (SMA50 > SMA200)
                    cond_golden_cross = row['SMA_Fast'] > row['SMA_Slow']
                    
                    # 条件2: 価格がSMAの上にいる（トレンド維持確認）
                    cond_price_above_sma = current_price > row['SMA_Fast']
                    
                    # 条件3 (V2): MACDがプラス（上昇モメンタム確認）
                    cond_macd_pos = row['MACD'] > row['MACD_Signal'] if pd.notna(row['MACD']) else False
                    
                    # 条件4 (V2): ボラティリティ拡大 (BB_Widthが直近平均より大きい)
                    # 簡易的に BB_Width > 0.02 (2%以上) を採用
                    cond_volatility = row['BB_Width'] > 0.02

                    # 総合判断
                    if cond_golden_cross and cond_price_above_sma and cond_macd_pos and cond_volatility:
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
                        logging.info(f"    [BUY V2] {date} | 価格: {current_price:.0f} | BB_Width: {row['BB_Width']:.3f} | 投資額: {invest_amount:.0f}")
                
                # --- エグジットロジック (ホールド中) ---
                else:
                    exit_signal = False
                    reason = ""
                    exit_price = 0
                    
                    # 1. トレイリングストップ (最高値更新と売り判定)
                    if current_price > position['highest_price']:
                        position['highest_price'] = current_price
                        # 最高値更新に伴い、ストップラインも引き上げる
                        position['trailing_stop'] = current_price * (1 - TRAILING_STOP_PCT)
                    
                    if row['Low'] <= position['trailing_stop']:
                        exit_price = position['trailing_stop']
                        exit_signal = True
                        reason = "TRAILING_STOP"

                    # 2. トレンド反転 (デッドクロス: Price < SMA_Fast)
                    # V2: RSI Overbought の条件を削除（売り惜しみ防止解除）
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
                        logging.info(f"    [SELL V2] {date} | 理由: {reason} | 変動: {change_pct*100:.2f}% | 利益: {profit:.0f} ({status_color}) | 残高: {capital:.0f}")
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
                    logging.info(f"    ★★★ V2 発見！{year}年で年利20%以上達成 ({total_return*100:.2f}%)")
            
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
    logging.info("究極のトレンドフォロー戦略 V2：マイナス転落防止・安定性向上版")
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
    engine = BacktestEngineV2()

    # 各シンボル実行
    for symbol, df in all_data.items():
        logging.info("")
        logging.info(f"================================================================================")
        logging.info(f"シンボル: {symbol} のテスト開始 (V2)")
        logging.info(f"================================================================================")
        engine.run_yearly_test(symbol, df)

    # 最終結果表示
    logging.info("")
    logging.info("================================================================================")
    logging.info("【最終レポート V2】")
    logging.info("================================================================================")
    
    if engine.best_overall['symbol']:
        logging.info("")
        logging.info("  ★★★★ V2 条件達成：年利20%以上の戦略を発見 ★★★★")
        logging.info("")
        logging.info(f"  シンボル   : {engine.best_overall['symbol']}")
        logging.info(f"  対象年次   : {engine.best_overall['year']}年")
        logging.info(f"  年利      : {engine.best_overall['return']*100:.2f}%")
        logging.info(f"  最終資金 : ¥{int(engine.best_overall['capital'])}")
        logging.info(f"  取引回数   : {engine.best_overall['details']['num_trades']}")
        logging.info(f"  勝率      : {engine.best_overall['details']['win_rate']*100:.1f}%")
        logging.info("")
        logging.info("  V2 戦略詳細:")
        logging.info("    - エントリー: SMA50 > SMA200 AND MACD > Signal AND ボラティリティ拡大")
        logging.info("    - エグジット: 50日SMA割り込み (RSI売り削除)")
        logging.info("    - 損切り   : トレイリングストップ (最高値から-15%)")
        logging.info("")
    else:
        logging.info("")
        logging.info("  △▼ V2: すべてのシンボル・年次で年利20%を達成できませんでした")
        logging.info("")

    logging.info("================================================================================")
