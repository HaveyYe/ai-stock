# -*- coding: utf-8 -*-
import akshare as ak
import pandas as pd
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def get_all_stock_codes():
    print('正在获取所有A股股票代码...')
    stock_info = ak.stock_info_a_code_name()
    codes = []
    for _, row in stock_info.iterrows():
        code = row['code']
        name = row['name']
        if pd.isna(code) or pd.isna(name):
            continue
        code_str = str(code).zfill(6)
        codes.append({'code': code_str, 'name': name})
    print(f'共获取 {len(codes)} 只股票')
    return codes

def is_mainboard_stock(code):
    code_str = str(code).zfill(6)
    if 'ST' in str(code) or 'S' in str(code):
        return False
    if code_str.startswith('68') or code_str.startswith('30') or code_str.startswith('4') or code_str.startswith('8'):
        return False
    return True

def download_stock_data(code, name, start_date, end_date, data_dir):
    try:
        code_str = str(code).zfill(6)
        filename = f"{code_str}_{name}.csv"
        filepath = os.path.join(data_dir, filename)
        
        if os.path.exists(filepath):
            return {'code': code_str, 'name': name, 'status': 'exists', 'filename': filename}
        
        df = ak.stock_zh_a_hist(symbol=code_str, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
        
        if df.empty:
            return {'code': code_str, 'name': name, 'status': 'empty', 'filename': filename}
        
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        return {'code': code_str, 'name': name, 'status': 'success', 'filename': filename}
    
    except Exception as e:
        return {'code': code_str, 'name': name, 'status': 'error', 'error': str(e)}

def download_all_stock_data():
    start_date = '20250101'
    end_date = datetime.now().strftime('%Y%m%d')
    data_dir = 'stock_data'
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    all_stocks = get_all_stock_codes()
    mainboard_stocks = [s for s in all_stocks if is_mainboard_stock(s['code'])]
    
    print(f'\n主板股票数量: {len(mainboard_stocks)}')
    print(f'开始下载数据...')
    
    success_count = 0
    error_count = 0
    exists_count = 0
    
    lock = threading.Lock()
    
    def process_stock(stock):
        result = download_stock_data(stock['code'], stock['name'], start_date, end_date, data_dir)
        
        with lock:
            if result['status'] == 'success':
                nonlocal success_count, error_count, exists_count
                success_count += 1
                print(f'[{success_count + error_count + exists_count}/{len(mainboard_stocks)}] 成功: {result["name"]}({result["code"]})')
            elif result['status'] == 'exists':
                exists_count += 1
            elif result['status'] == 'error':
                error_count += 1
                print(f'[{success_count + error_count + exists_count}/{len(mainboard_stocks)}] 错误: {result["name"]}({result["code"]}) - {result.get("error", "未知错误")}')
        
        return result
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(process_stock, stock): stock for stock in mainboard_stocks}
        
        for future in as_completed(futures):
            pass
    
    print(f'\n下载完成!')
    print(f'成功: {success_count}')
    print(f'已存在: {exists_count}')
    print(f'错误: {error_count}')
    
    return data_dir

if __name__ == '__main__':
    print('开始下载股票数据...')
    data_dir = download_all_stock_data()
    print(f'数据已保存到 {data_dir}/ 目录')
