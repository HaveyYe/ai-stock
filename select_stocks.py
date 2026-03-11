import akshare as ak
import pandas as pd
import time
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import DINGTALK_WEBHOOK

def get_last_trade_date():
    today = datetime.now()
    trade_date = today
    
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

def format_number(num):
    if pd.isna(num) or num == 0 or num is None:
        return "0"
    try:
        num = float(num)
        if num >= 1e8:
            return f"{num/1e8:.2f}亿"
        elif num >= 1e4:
            return f"{num/1e4:.2f}万"
        else:
            return f"{num:.2f}"
    except:
        return str(num)

def format_price(price):
    try:
        if pd.isna(price) or price is None:
            return "0.00"
        return f"{float(price):.2f}"
    except:
        return str(price)

def format_change(change):
    try:
        if pd.isna(change) or change is None:
            return "0.00%"
        return f"{float(change):.2f}%"
    except:
        return str(change)

def parse_time_to_minutes(time_str):
    try:
        time_str = str(time_str).zfill(6)
        hour = int(time_str[:2])
        minute = int(time_str[2:4])
        return hour * 60 + minute
    except:
        return 9999

def is_within_30_minutes_of_open(time_str):
    try:
        open_time = 9 * 60 + 25
        limit_time = parse_time_to_minutes(time_str)
        return open_time <= limit_time <= open_time + 30
    except:
        return False

def get_limit_up_stocks_yesterday():
    try:
        trade_date = get_last_trade_date()
        
        stock_zt_pool_em_df = ak.stock_zt_pool_em(date=trade_date)
        
        stocks = []
        for _, row in stock_zt_pool_em_df.iterrows():
            code = row['代码']
            name = row['名称']
            
            if pd.isna(code) or pd.isna(name):
                continue
            
            code_str = str(code).zfill(6)
            name_str = str(name)
            
            if 'ST' in name_str:
                continue
            
            if code_str.startswith('68') or code_str.startswith('30') or code_str.startswith('4') or code_str.startswith('8'):
                continue
            
            try:
                amount = float(str(row['成交额']).replace(',', ''))
            except:
                amount = 0
            
            try:
                first_limit_up_time = str(row['首次封板时间']).zfill(6)
            except:
                first_limit_up_time = '092500'
            
            try:
                limit_up_count = int(row['连板数']) if not pd.isna(row['连板数']) else 0
            except:
                limit_up_count = 0
            
            try:
                炸板次数 = int(row['炸板次数']) if not pd.isna(row['炸板次数']) else 0
            except:
                炸板次数 = 0
            
            stocks.append({
                'code': code_str,
                'name': name_str,
                'price': row['最新价'],
                'change': row['涨跌幅'],
                'amount': amount,
                'first_limit_up_time': first_limit_up_time,
                'limit_up_count': limit_up_count,
                '炸板次数': 炸板次数
            })
        
        return stocks
    except Exception as e:
        print(f"获取昨日涨停股票失败: {e}")
        return []

def get_real_time_data_single(stock_code):
    try:
        stock_zh_a_spot_em_df = ak.stock_zh_a_spot_em()
        stock_row = stock_zh_a_spot_em_df[stock_zh_a_spot_em_df['代码'] == stock_code]
        if not stock_row.empty:
            price = stock_row.iloc[0]['最新价']
            change = stock_row.iloc[0]['涨跌幅']
            amount = stock_row.iloc[0]['成交额']
            
            try:
                amount_value = float(str(amount).replace(',', ''))
            except:
                amount_value = 0
            
            return {
                'code': stock_code,
                'price': price,
                'change': change,
                'amount': amount_value,
                'success': True
            }
        return {'code': stock_code, 'success': False}
    except Exception as e:
        return {'code': stock_code, 'success': False}

def get_real_time_data_batch(stock_codes):
    stock_data_dict = {}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_real_time_data_single, code): code for code in stock_codes}
        
        for future in as_completed(futures):
            result = future.result()
            if result['success']:
                stock_data_dict[result['code']] = {
                    'price': result['price'],
                    'change': result['change'],
                    'amount': result['amount']
                }
    
    return stock_data_dict

def send_dingtalk_message(stocks):
    if not stocks:
        message = "今日无符合条件的股票"
    else:
        message = "【昨日开盘30分钟内首版涨停股票推荐】\n\n"
        for i, stock in enumerate(stocks, 1):
            price_str = format_price(stock['price'])
            change_str = format_change(stock['change'])
            amount_str = format_number(stock['amount'])
            
            message += f"{i}. {stock['name']}({stock['code']}) - 价格: {price_str} - 涨幅: {change_str} - 成交额: {amount_str}\n"
    
    data = {
        "msgtype": "text",
        "text": {
            "content": message
        }
    }
    
    try:
        response = requests.post(DINGTALK_WEBHOOK, json=data, timeout=10)
        if response.status_code == 200:
            print("消息发送成功")
        else:
            print(f"消息发送失败: {response.text}")
    except Exception as e:
        print(f"发送消息失败: {e}")

def send_real_time_update(stock):
    price_str = format_price(stock['price'])
    change_str = format_change(stock['change'])
    amount_str = format_number(stock['amount'])
    
    message = f"【实时监控更新】\n\n{stock['name']}({stock['code']})\n价格: {price_str} - 涨幅: {change_str} - 成交额: {amount_str}"
    
    data = {
        "msgtype": "text",
        "text": {
            "content": message
        }
    }
    
    try:
        response = requests.post(DINGTALK_WEBHOOK, json=data, timeout=10)
        if response.status_code == 200:
            print(f"实时更新发送成功: {stock['name']}")
        else:
            print(f"实时更新发送失败: {response.text}")
    except Exception as e:
        print(f"发送实时更新失败: {e}")

def monitor_real_time(stocks, stock_data_dict, duration_minutes=30, interval_seconds=60):
    print(f"开始实时监控 {duration_minutes} 分钟...")
    start_time = time.time()
    duration_seconds = duration_minutes * 60
    
    while time.time() - start_time < duration_seconds:
        for stock in stocks:
            if stock['code'] in stock_data_dict:
                stock['price'] = stock_data_dict[stock['code']]['price']
                stock['change'] = stock_data_dict[stock['code']]['change']
                stock['amount'] = stock_data_dict[stock['code']]['amount']
                send_real_time_update(stock)
        
        time.sleep(interval_seconds)

def main():
    print("开始执行股票筛选...")
    
    limit_up_stocks = get_limit_up_stocks_yesterday()
    print(f"获取到 {len(limit_up_stocks)} 只昨日涨停股票")
    
    filtered_stocks = []
    for stock in limit_up_stocks:
        if not is_within_30_minutes_of_open(stock['first_limit_up_time']):
            continue
        
        if stock['limit_up_count'] > 1:
            continue
        
        filtered_stocks.append(stock)
    
    print(f"筛选后剩余 {len(filtered_stocks)} 只股票")
    
    sorted_stocks = sorted(filtered_stocks, key=lambda x: x['amount'], reverse=True)
    
    selected_stocks = sorted_stocks[:5]
    
    print("正在获取实时数据...")
    stock_codes = [stock['code'] for stock in selected_stocks]
    stock_data_dict = get_real_time_data_batch(stock_codes)
    
    for stock in selected_stocks:
        if stock['code'] in stock_data_dict:
            stock['price'] = stock_data_dict[stock['code']]['price']
            stock['change'] = stock_data_dict[stock['code']]['change']
            stock['amount'] = stock_data_dict[stock['code']]['amount']
            print(f"成功获取 {stock['name']} 实时数据")
        else:
            print(f"未找到 {stock['name']} 实时数据，使用昨日数据")
    
    send_dingtalk_message(selected_stocks)
    
    monitor_real_time(selected_stocks, stock_data_dict, duration_minutes=30, interval_seconds=60)
    
    print("股票筛选完成")

if __name__ == "__main__":
    main()