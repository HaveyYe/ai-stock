import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import os
import glob

def get_last_trade_date():
    today = datetime.now()
    for i in range(1, 10):
        trade_date = today - timedelta(days=i)
        date_str = trade_date.strftime('%Y%m%d')
        try:
            stock_zt_pool_df = ak.stock_zt_pool_em(date=date_str)
            if not stock_zt_pool_df.empty:
                return date_str
        except:
            continue
    return trade_date.strftime('%Y%m%d')

def is_mainboard_stock(code):
    code_str = str(code).zfill(6)
    if 'ST' in str(code) or 'S' in str(code):
        return False
    if code_str.startswith('68') or code_str.startswith('30') or code_str.startswith('4') or code_str.startswith('8'):
        return False
    return True

def load_stock_data(code, data_dir='stock_data'):
    code_str = str(code).zfill(6)
    filename = f"{code_str}_*.csv"
    filepath = os.path.join(data_dir, filename)
    
    files = glob.glob(filepath)
    if not files:
        return None
    
    try:
        df = pd.read_csv(files[0])
        df['日期'] = pd.to_datetime(df['日期'])
        df = df.sort_values('日期').reset_index(drop=True)
        return df
    except:
        return None

def load_all_stock_data(data_dir='stock_data'):
    stock_files = glob.glob(os.path.join(data_dir, '*.csv'))
    stock_data = {}
    
    for filepath in stock_files:
        try:
            filename = os.path.basename(filepath)
            code = filename.split('_')[0]
            df = pd.read_csv(filepath)
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期').reset_index(drop=True)
            stock_data[code] = df
        except:
            continue
    
    return stock_data

def select_stocks_yesterday():
    trade_date = get_last_trade_date()
    
    try:
        stock_zt_pool_df = ak.stock_zt_pool_em(date=trade_date)
    except Exception as e:
        print(f'获取昨日涨停股票失败: {e}')
        return []
    
    filtered_stocks = []
    
    for _, row in stock_zt_pool_df.iterrows():
        code = row['代码']
        name = row['名称']
        
        if pd.isna(code) or pd.isna(name):
            continue
        
        code_str = str(code).zfill(6)
        
        if not is_mainboard_stock(code_str):
            continue
        
        try:
            first_limit_up_time = str(row['首次封板时间']).zfill(6)
        except:
            continue
        
        try:
            hour = int(first_limit_up_time[:2])
            minute = int(first_limit_up_time[2:4])
            open_time = 9 * 60 + 25
            limit_time = hour * 60 + minute
            if limit_time < open_time or limit_time > open_time + 30:
                continue
        except:
            continue
        
        try:
            amount = float(str(row['成交额']).replace(',', ''))
        except:
            amount = 0
        
        try:
            market_value = row['总市值']
            if pd.isna(market_value) or market_value == 0:
                continue
            market_value = float(str(market_value).replace(',', ''))
        except:
            continue
        
        if amount == 0 or market_value == 0:
            continue
        
        amount_to_mv_ratio = amount / market_value
        
        filtered_stocks.append({
            'code': code_str,
            'name': name,
            'amount': amount,
            'market_value': market_value,
            'amount_to_mv_ratio': amount_to_mv_ratio
        })
    
    filtered_stocks.sort(key=lambda x: x['amount_to_mv_ratio'], reverse=True)
    
    return filtered_stocks[:5]

def backtest_strategy(stock_data, start_date, end_date, initial_capital=100000):
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    selected_stocks = select_stocks_yesterday()
    selected_codes = [s['code'] for s in selected_stocks]
    
    print(f'\n选股结果:')
    for stock in selected_stocks:
        print(f"  {stock['name']}({stock['code']}) - 比值: {stock['amount_to_mv_ratio']:.4f}")
    
    if not selected_stocks:
        print('无符合条件的股票')
        return None
    
    trading_days = []
    for date in pd.date_range(start=start_dt, end=end_dt):
        date_str = date.strftime('%Y-%m-%d')
        for code in selected_codes:
            if code in stock_data:
                stock_df = stock_data[code]
                if date in stock_df['日期'].values:
                    trading_days.append(date)
                    break
    
    trading_days = sorted(list(set(trading_days)))
    
    capital = initial_capital
    positions = {}
    trades = []
    daily_values = []
    
    for current_date in trading_days:
        current_positions = list(positions.keys())
        
        for code in current_positions:
            if code not in stock_data:
                continue
            
            stock_df = stock_data[code]
            day_data = stock_df[stock_df['日期'] == current_date]
            
            if day_data.empty:
                continue
            
            current_price = day_data.iloc[0]['收盘']
            
            if code in positions:
                pos = positions[code]
                if current_price >= pos['target_price']:
                    sell_value = pos['shares'] * current_price
                    profit = sell_value - pos['cost']
                    capital += sell_value
                    trades.append({
                        'date': current_date,
                        'code': code,
                        'action': 'sell',
                        'price': current_price,
                        'profit': profit
                    })
                    del positions[code]
                    print(f'{current_date} 止盈卖出 {code}')
                elif current_price <= pos['stop_loss_price']:
                    sell_value = pos['shares'] * current_price
                    profit = sell_value - pos['cost']
                    capital += sell_value
                    trades.append({
                        'date': current_date,
                        'code': code,
                        'action': 'sell',
                        'price': current_price,
                        'profit': profit
                    })
                    del positions[code]
                    print(f'{current_date} 止损卖出 {code}')
        
        if current_date == trading_days[0]:
            for stock in selected_stocks:
                code = stock['code']
                
                if code not in stock_data:
                    continue
                
                stock_df = stock_data[code]
                day_data = stock_df[stock_df['日期'] == current_date]
                
                if day_data.empty:
                    continue
                
                current_price = day_data.iloc[0]['收盘']
                
                if capital >= current_price * 100:
                    shares = int(capital * 0.2 / current_price / 100) * 100
                    if shares > 0:
                        cost = shares * current_price
                        positions[code] = {
                            'shares': shares,
                            'cost': cost,
                            'target_price': current_price * 1.1,
                            'stop_loss_price': current_price * 0.9
                        }
                        capital -= cost
                        trades.append({
                            'date': current_date,
                            'code': code,
                            'action': 'buy',
                            'price': current_price,
                            'shares': shares
                        })
                        print(f'{current_date} 开盘买入 {code} {shares}股')
        
        total_value = capital
        for code, pos in positions.items():
            if code in stock_data:
                stock_df = stock_data[code]
                day_data = stock_df[stock_df['日期'] == current_date]
                if not day_data.empty:
                    current_price = day_data.iloc[0]['收盘']
                    total_value += pos['shares'] * current_price
        
        daily_values.append({
            'date': current_date,
            'capital': capital,
            'total_value': total_value
        })
    
    result_df = pd.DataFrame(daily_values)
    
    if result_df.empty:
        return None
    
    result_df['return'] = (result_df['total_value'] - initial_capital) / initial_capital * 100
    
    return {
        'trades': trades,
        'daily_values': result_df,
        'final_value': result_df.iloc[-1]['total_value'],
        'total_return': result_df.iloc[-1]['return']
    }

def print_backtest_result(result):
    if result is None:
        print('回测结果为空')
        return
    
    print(f'\n=== 回测结果 ===')
    print(f'最终市值: {result["final_value"]:.2f} 元')
    print(f'总收益率: {result["total_return"]:.2f}%')
    
    trades_df = pd.DataFrame(result['trades'])
    if not trades_df.empty:
        print(f'\n交易记录:')
        print(trades_df.to_string())
    
    print(f'\n每日净值:')
    print(result['daily_values'].to_string())

if __name__ == '__main__':
    data_dir = 'stock_data'
    
    if not os.path.exists(data_dir):
        print(f'请先运行 download_stock_data.py 下载数据到 {data_dir} 目录')
        exit(1)
    
    print('正在加载股票数据...')
    stock_data = load_all_stock_data(data_dir)
    print(f'共加载 {len(stock_data)} 只股票数据')
    
    start_date = '2025-01-01'
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    print(f'\n开始回测 ({start_date} 到 {end_date})...')
    result = backtest_strategy(stock_data, start_date, end_date, initial_capital=100000)
    
    if result:
        print_backtest_result(result)
