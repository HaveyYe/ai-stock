import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import os

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

def select_stocks():
    trade_date = get_last_trade_date()
    
    print(f'正在获取 {trade_date} 的涨停股票...')
    
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
    
    selected_stocks = filtered_stocks[:5]
    
    print(f'\n筛选出 {len(selected_stocks)} 只股票:')
    for i, stock in enumerate(selected_stocks, 1):
        print(f"{i}. {stock['name']}({stock['code']}) - 成交额: {stock['amount']/1e8:.2f}亿 - 总市值: {stock['market_value']/1e8:.2f}亿 - 比值: {stock['amount_to_mv_ratio']:.4f}")
    
    return selected_stocks

def save_stock_list(stocks, filename='selected_stocks.csv'):
    if not stocks:
        print('无股票可保存')
        return
    
    df = pd.DataFrame(stocks)
    df['code'] = df['code'].apply(lambda x: str(x).zfill(6))
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f'\n股票列表已保存到 {filename}')

if __name__ == '__main__':
    print('开始执行股票筛选...')
    selected_stocks = select_stocks()
    save_stock_list(selected_stocks)
