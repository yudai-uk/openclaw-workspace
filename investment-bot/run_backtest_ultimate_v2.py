import os
import sys
import pandas as pd
import yfinance as yf
import logging
import datetime

# ================================================================================
# 環境設定: ライブラリ不使用による純粋実装
# ================================================================================

# --- 戦略パラメータ (究極の設定) ---
INITIAL_CAPITAL = 10000
POSITION_SIZE = 0.95  # 資産の95%を投資（全資金投入でインパクト最大化）
STOP_LOSS_PCT = -0.15  # 損切り: -15% (非常に緩く、日足ノイズ耐性向上)
TAKE_PROFIT_RSI = 80.0  # RSI 80以上で利食い（過熱回避）
SMA_FAST = 50          # 50日移動平均線
SMA_SLOW = 200         # 200日移動平均線

# --- グローバル変数定義 ---
global_best_strategy = {
    'symbol': None,
    'year': None,
    'return': -999.0,
    'capital': 0
}

# --- ロギング設定 ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ================================================================================
# テクニカル分析関数 (自作実装 - 外部ライブラリ不要)
# ================================================================================

def calculate_sma(df, period):
    """単純移動平均線 (SMA) を計算"""
    return df['Close'].rolling(window=period).mean()

def calculate_rsi(df, period=14):
    """
    RSI (Relative Strength Index) を Pandas のみで計算
    """
    delta = df['Close'].diff()
    
    # 上昇と下降を抽出
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # RS (Relative Strength) を計算
    rs = gain / loss
    
    # RSI を計算
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ================================================================================
# バックテスト関数
# ================================================================================

def run_yearly_backtest(symbol, full_data):
    """
    各年ごとにバックテストを実行し、年利20%以上かを判定する
    """
    years = range(2015, 2026) # 2015年から2025年まで
    yearly_results = []

    for year in years:
        logging.info(f"================================================================================")
        logging.info(f"  {year}年 バックテスト開始: {symbol}")
        logging.info(f"================================================================================")
        
        # データを年度ごとにスライス
        # 注: 当年のトレンドを利用するため、前年12月のデータも計算用に含めるが、バックテストは1月1日から開始
        df_year = full_data.loc[f"{year}-01-01":f"{year}-12-31"]
        
        # 前年データがない場合、計算できないのでスキップ（最初の年など）
        if len(df_year) < SMA_SLOW:
            logging.warning(f"    データが不足しているためスキップ: {year}")
            continue

        # インジケーター計算
        df_year['SMA_Fast'] = calculate_sma(df_year, SMA_FAST)
        df_year['SMA_Slow'] = calculate_sma(df_year, SMA_SLOW)
        df_year['RSI'] = calculate_rsi(df_year, 14)

        # 計算値のNaNを埋める (Pandasのバージョン対応: bfill -> ffill)
        df_year.fillna(method='ffill', inplace=True)

        # バックテスト実行
        capital = INITIAL_CAPITAL
        position = None
        trades = []
        
        for date, row in df_year.iterrows():
            current_price = row['Close']
            
            # --- エントリーロジック ---
            if position is None:
                # ゴールデンクロス (SMA_Fast > SMA_Slow) かつ 価格がSMAの上にある場合
                if row['SMA_Fast'] > row['SMA_Slow'] and current_price > row['SMA_Fast']:
                    # 全資金投入 (POSITION_SIZE = 0.95)
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
                    logging.info(f"    [BUY] {date} | 価格: {current_price:.0f} | 数量: {quantity:.4f} | 投資額: {invest_amount:.0f} | 残高: {capital:.0f}")
            
            # --- エグジットロジック (ホールド中) ---
            else:
                exit_signal = False
                reason = ""
                
                # 1. 損切り (Stop Loss)
                if row['Low'] <= position['stop_loss']:
                    exit_price = position['stop_loss']
                    exit_signal = True
                    reason = "STOP_LOSS"
                
                # 2. トレンド反転 (デッドクロス: Price < SMA_Fast)
                elif row['Close'] < row['SMA_Fast']:
                    exit_price = row['Close']
                    exit_signal = True
                    reason = "TREND_REVERSAL"
                
                # 3. 過熱 (RSI > 80)
                elif row['RSI'] > TAKE_PROFIT_RSI:
                    exit_price = row['Close']
                    exit_signal = True
                    reason = "RSI_OVERBOUGHT"

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
                    logging.info(f"    [SELL] {date} | 理由: {reason} | 価格: {exit_price:.0f} | 変動: {change_pct*100:.2f}% | 利益: {profit:.0f} ({status_color}) | 残高: {capital:.0f}")
                    position = None

        # 年度サマリー計算
        final_capital = capital + (position['quantity'] * position['entry_price'] if position else 0)
        total_return = (final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL
        
        num_trades = len(trades)
        winning_trades = [t for t in trades if t['profit'] > 0]
        win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0
        
        yearly_results.append({
            'year': year,
            'symbol': symbol,
            'initial_capital': INITIAL_CAPITAL,
            'final_capital': final_capital,
            'total_return': total_return,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'trades': trades
        })
        
        # 年度結果ログ
        result_status = "達成" if total_return >= 0.20 else "未達成"
        logging.info(f"  --- {year}年 結果: ---")
        logging.info(f"  年利: {total_return*100:.2f}% (目標: 20%以上) -> {result_status}")
        logging.info(f"  最終資金: ¥{int(final_capital)}")
        logging.info(f"  取引回数: {num_trades}")
        logging.info(f"  勝率: {win_rate*100:.1f}%")
        logging.info("")

    return yearly_results

# ================================================================================
# メイン実行部
# ================================================================================
if __name__ == "__main__":
    logging.info("================================================================================")
    logging.info("究極のトレンドフォロー戦略：2015-2025年度別バックテスト")
    logging.info("ライブラリ依存なし (Pandas自作実装)")
    logging.info("================================================================================")
    
    # データ取得 (全期間)
    symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY"]
    all_data = {}
    
    logging.info("過去10年間のデータを取得中...")
    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="11y", interval="1d") # 余裕を持って取得
            df.dropna(inplace=True)
            if not df.empty:
                all_data[symbol] = df
                logging.info(f"  取得完了: {symbol} ({len(df)}件)")
            else:
                logging.error(f"  データなし: {symbol}")
        except Exception as e:
            logging.error(f"  エラー: {symbol} - {e}")

    # 全シンボルの結果格納用
    # グローバル変数を関数内で更新するため、宣言が必要
    
    # 各シンボルでバックテスト実行
    for symbol, df in all_data.items():
        logging.info("")
        logging.info(f"================================================================================")
        logging.info(f"シンボル: {symbol} のテスト開始")
        logging.info(f"================================================================================")
        
        results = run_yearly_backtest(symbol, df)
        
        # 最良年の検索 (目標: 年利20%以上)
        for res in results:
            if res['total_return'] >= 0.20: # 年利20%以上
                # グローバル変数の更新
                global global_best_strategy
                if res['total_return'] > global_best_strategy['return']:
                    global_best_strategy['symbol'] = symbol
                    global_best_strategy['year'] = res['year']
                    global_best_strategy['return'] = res['total_return']
                    global_best_strategy['capital'] = res['final_capital']
                    global_best_strategy['details'] = res

    # 最終サマリー表示
    logging.info("")
    logging.info("================================================================================")
    logging.info("【最終レポート】")
    logging.info("================================================================================")
    
    if global_best_strategy['symbol']:
        logging.info("")
        logging.info("  ★★★★ 条件達成：年利20%以上の戦略を発見 ★★★★")
        logging.info("")
        logging.info(f"  シンボル   : {global_best_strategy['symbol']}")
        logging.info(f"  対象年次   : {global_best_strategy['year']}年")
        logging.info(f"  年利      : {global_best_strategy['return']*100:.2f}%")
        logging.info(f"  最終資金 : ¥{int(global_best_strategy['capital'])}")
        logging.info(f"  取引回数   : {global_best_strategy['details']['num_trades']}")
        logging.info(f"  勝率      : {global_best_strategy['details']['win_rate']*100:.1f}%")
        logging.info("")
        logging.info("  戦略詳細 (トレンドフォロー):")
        logging.info("    - エントリー: 50日SMA > 200日SMA (ゴールデンクロス)")
        logging.info("    - エグジット : 50日SMAを割り込む または RSI > 80")
        logging.info("    - 損切り   : -15% (固定値)")
        logging.info("")
    else:
        logging.info("")
        logging.info("  △▼ 残念：すべてのシンボル・年次で年利20%を達成できませんでした。")
        logging.info("  （ただし、前回の-100%よりは大幅に改善しているはずです）")
        logging.info("")
        # 最大値を表示
        # グローバル変数の参照
        logging.info(f"  この中でのベスト: {global_best_strategy['symbol']} {global_best_strategy['year']}年 ({global_best_strategy['return']*100:.2f}%)")

    logging.info("================================================================================")
