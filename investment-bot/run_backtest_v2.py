import os
import sys
import yfinance as yf
import pandas as pd
import logging
import datetime

# ================================================================================
# 強制修正: 日足データ対応パラメータ（設定ファイル無視）
# ================================================================================
# これらの値は変更不可です。
PROFIT_TARGET = 0.30   # 利益目標: +30%
STOP_LOSS = -0.20      # 損失設定: -20% (非常に緩い、日足ノイズに耐える)
BUY_THRESHOLD = 4.0
SELL_THRESHOLD = -4.0
POSITION_SIZE = 0.4     # 40%を投資
TARGET_WIN_RATE = 0.35
INITIAL_CAPITAL = 10000

# テクニカル分析設定
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# ================================================================================
# ロギング設定
# ================================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ================================================================================
# データ取得関数
# ================================================================================
def get_historical_data(symbol, period="5y"):
    """過去5年間のデータを取得"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval="1d")
        df = df.dropna()
        logging.info(f"  データ取得: {len(df)}件")
        return df
    except Exception as e:
        logging.error(f"データ取得エラー: {e}")
        return pd.DataFrame()

# ================================================================================
# テクニカル分析関数
# ================================================================================
def calculate_indicators(df):
    """テクニカル指標を計算"""
    df['RSI'] = yf.RSI(df['Close'], window=RSI_PERIOD)
    df['Upper_Band'], df['Middle_Band'], df['Lower_Band'] = yf.BollingerBands(df['Close'], window=BOLLINGER_PERIOD, num_std=BOLLINGER_STD)
    return df

def generate_signal(df):
    """シグナルを生成"""
    latest = df.iloc[-1]
    score = 0
    
    # RSIシグナル
    if latest['RSI'] < RSI_OVERSOLD:
        score += 2
    elif latest['RSI'] > RSI_OVERBOUGHT:
        score -= 2
        
    # ボリティリティ・ブレイクアウト
    if latest['Close'] > latest['Upper_Band']:
        score += 3
    
    if score >= BUY_THRESHOLD:
        return "BUY"
    elif score <= SELL_THRESHOLD:
        return "SELL"
    return "HOLD"

# ================================================================================
# バックテスト関数
# ================================================================================
def run_backtest(symbol, df, profit_target, stop_loss_pct, initial_capital, position_size, strategy_name="default"):
    """バックテストを実行"""
    capital = initial_capital
    position = None
    trades = []
    
    for date, row in df.iterrows():
        current_price = row['Close']
        
        # まだポジションがない場合
        if position is None:
            signal = generate_signal(df.loc[:date.name + 1])
            if signal == "BUY" and capital > 0:
                # ポジションサイズを計算（資金の40%）
                invest_amount = capital * position_size
                quantity = invest_amount / current_price
                position = {
                    'entry_date': date,
                    'entry_price': current_price,
                    'quantity': quantity,
                    'invested': invest_amount,
                    'stop_loss': current_price * (1 + stop_loss_pct),
                    'take_profit': current_price * (1 + profit_target)
                }
                capital -= invest_amount
                logging.info(f"  新規エントリー: {date} | 価格: {current_price:.2f} | 数量: {quantity:.4f} | 投資額: {invest_amount:.2f} | 残高: {capital:.2f}")
        
        # ポジションを持っている場合
        else:
            # 損切りのチェック
            if row['Low'] <= position['stop_loss']:
                exit_price = position['stop_loss']
                change_pct = (exit_price - position['entry_price']) / position['entry_price']
                profit = change_pct * position['quantity'] * position['entry_price']
                
                capital += (position['quantity'] * exit_price)
                
                trades.append({
                    'symbol': symbol,
                    'entry_date': position['entry_date'],
                    'exit_date': date,
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'reason': 'stop_loss',
                    'change_pct': change_pct,
                    'profit': profit
                })
                
                logging.info(f"  取引クローズ: {date} | 理由: stop_loss | エントリー: {position['entry_price']:.2f} | エグジット: {exit_price:.2f} | 変動: {change_pct:.2%} | 利益: {profit:.2f} | 残高: {capital:.2f}")
                position = None
                
            # 利益確定のチェック
            elif row['High'] >= position['take_profit']:
                exit_price = position['take_profit']
                change_pct = (exit_price - position['entry_price']) / position['entry_price']
                profit = change_pct * position['quantity'] * position['entry_price']
                
                capital += (position['quantity'] * exit_price)
                
                trades.append({
                    'symbol': symbol,
                    'entry_date': position['entry_date'],
                    'exit_date': date,
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'reason': 'take_profit',
                    'change_pct': change_pct,
                    'profit': profit
                })
                
                logging.info(f"  取引クローズ: {date} | 理由: take_profit | エントリー: {position['entry_price']:.2f} | エグジット: {exit_price:.2f} | 変動: {change_pct:.2%} | 利益: {profit:.2f} | 残高: {capital:.2f}")
                position = None

    return trades, capital

# ================================================================================
# メイン実行部
# ================================================================================
if __name__ == "__main__":
    logging.info("================================================================================")
    logging.info("チャート分析専用バックテスト開始（5年間）")
    logging.info(f"日時: {datetime.datetime.now()}")
    logging.info("================================================================================")
    
    # ----------------------------------------------------------------
    # ステップ1: 過去5年間のデータを取得
    # ----------------------------------------------------------------
    logging.info("")
    logging.info("================================================================================")
    logging.info("ステップ1: 過去5年間のデータを取得")
    logging.info("================================================================================")
    logging.info(f"過去5y分のデータを取得開始（1d）")
    
    symbols = ["BTC-JPY", "ETH-JPY", "XRP-JPY", "BCH-JPY", "LTC-JPY"]
    data = {}
    for symbol in symbols:
        logging.info(f"シンボル: {symbol}")
        df = get_historical_data(symbol)
        if not df.empty:
            data[symbol] = df
        else:
            logging.error(f"  データが空です: {symbol}")
    
    logging.info(f"データ取得完了: {len(data)}シンボル")
    
    # ----------------------------------------------------------------
    # ステップ2: 5年間のバックテスト（強制修正パラメータ）
    # ----------------------------------------------------------------
    logging.info("")
    logging.info("================================================================================")
    logging.info("ステップ2: 5年間のバックテスト（強制修正パラメータ）")
    logging.info("================================================================================")
    logging.info(f"設定: 利益目標={PROFIT_TARGET*100:.0f}%, 損失={STOP_LOSS*100:.0f}%")
    
    all_results = []
    
    for symbol, df in data.items():
        logging.info("")
        logging.info(f"--- {symbol} バックテスト開始 ---")
        
        # インジケータ計算
        df = calculate_indicators(df)
        
        # バックテスト実行
        strategy_name = f"2025_v2_fixed" # バージョン2で区別
        logging.info(f"バックテスト開始: {strategy_name}")
        logging.info(f"ボラティリティ・ブレイクアウト戦略でバックテストを実行中... (利益目標: {PROFIT_TARGET*100:.0f}%, 損切り: {STOP_LOSS*100:.0f}%)")
        
        trades, final_capital = run_backtest(
            symbol, 
            df, 
            profit_target=PROFIT_TARGET,
            stop_loss_pct=STOP_LOSS,
            initial_capital=INITIAL_CAPITAL,
            position_size=POSITION_SIZE,
            strategy_name=strategy_name
        )
        
        # 結果の分析
        num_trades = len(trades)
        profitable_trades = [t for t in trades if t['profit'] > 0]
        win_rate = len(profitable_trades) / num_trades if num_trades > 0 else 0
        total_return = (final_capital - INITIAL_CAPITAL) / INITIAL_CAPITAL
        
        result = {
            'symbol': symbol,
            'strategy_name': strategy_name,
            'profit_target': PROFIT_TARGET,
            'stop_loss': STOP_LOSS,
            'initial_capital': INITIAL_CAPITAL,
            'final_capital': final_capital,
            'total_return': total_return,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'trades': trades
        }
        
        all_results.append(result)
        
        logging.info(f"バックテスト完了: {strategy_name}")
        logging.info(f"年利: {total_return*100:.2f}%")
        logging.info(f"勝率: {win_rate*100:.2f}%")
        logging.info(f"取引数: {num_trades}")
        logging.info(f"最終資金: ¥{int(final_capital)}")
        logging.info("")
    
    # ----------------------------------------------------------------
    # ステップ3: サマリー表示
    # ----------------------------------------------------------------
    logging.info("")
    logging.info("================================================================================")
    logging.info("ステップ3: サマリー表示")
    logging.info("================================================================================")
    logging.info("")
    
    logging.info("================================================================================")
    logging.info("5年間バックテスト完了（強制修正）")
    logging.info("================================================================================")
    logging.info("")
    
    logging.info("================================================================================")
    logging.info("チャート分析専用バックテスト結果（5年間）")
    logging.info("================================================================================")
    
    # 年利20%以上の戦略を検索
    winning_strategies = [r for r in all_results if r['total_return'] >= 0.20]
    
    if winning_strategies:
        logging.info(f"年利20%以上の戦略: {len(winning_strategies)}件")
        logging.info("年利が最も高い戦略を表示します")
        best_strategy = max(all_results, key=lambda x: x['total_return'])
        logging.info("")
        logging.info(f"最適戦略（年利最大）: {best_strategy['symbol']}_{best_strategy['strategy_name']}")
        logging.info(f"  年利: {best_strategy['total_return']*100:.2f}%")
        logging.info(f"  勝率: {best_strategy['win_rate']*100:.2f}%")
        logging.info(f"  取引数: {best_strategy['num_trades']}")
        
        # 最終資金
        logging.info(f"  最終資金: ¥{int(best_strategy['final_capital'])}")
        
        # 利益計算
        profits = [t['profit'] for t in best_strategy['trades'] if t['profit'] > 0]
        avg_profit = sum(profits) / len(profits) if profits else 0
        max_profit = max(profits) if profits else 0
        
        # 損失計算
        losses = [t['profit'] for t in best_strategy['trades'] if t['profit'] < 0]
        max_loss = min(losses) if losses else 0
        
        logging.info(f"  平均利益: ¥{int(avg_profit)}")
        logging.info(f"  最大利益: ¥{int(max_profit)}")
        logging.info(f"  最大損失: ¥{int(max_loss)}")
    else:
        logging.info("年利20%以上の戦略はありませんでした")
        
        # それでも年利最大の戦略を表示
        if all_results:
            best_strategy = max(all_results, key=lambda x: x['total_return'])
            logging.info(f"年利が最も高い戦略を表示します (全戦略中): {best_strategy['symbol']}_{best_strategy['strategy_name']}")
            logging.info("")
            logging.info(f"最適戦略（年利最大）: {best_strategy['symbol']}_{best_strategy['strategy_name']}")
            logging.info(f"  年利: {best_strategy['total_return']*100:.2f}%")
            logging.info(f"  勝率: {best_strategy['win_rate']*100:.2f}%")
            logging.info(f"  取引数: {best_strategy['num_trades']}")
            logging.info(f"  最終資金: ¥{int(best_strategy['final_capital'])}")
    
    # 年利ランキング（上位5位）を表示
    logging.info("")
    logging.info(f"年利ランキング（上位5位）:")
    sorted_results = sorted(all_results, key=lambda x: x['total_return'], reverse=True)
    for i, r in enumerate(sorted_results[:5]):
        logging.info(f"  {i+1}. {r['symbol']}_{r['strategy_name']}: 年利{r['total_return']*100:.2f}%, 勝率{r['win_rate']*100:.2f}%, 取引数{r['num_trades']}")
    
    logging.info("")
    logging.info("================================================================================")
