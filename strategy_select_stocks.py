import datetime

def get_last_trade_date():
    today = datetime.datetime.now()
    for i in range(1, 10):
        trade_date = today - datetime.timedelta(days=i)
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

def init(context):
    set_benchmark('000300.SH')
    log.info('选股策略开始运行')
    set_commission(PerShare(type='stock', cost=0.0002))
    set_slippage(PriceSlippage(0.005))
    set_volume_limit(0.25, 0.5)
    context.selected_stocks = []
    context.hold_stocks = {}
    context.max_hold_days = 1

def before_trading(context):
    date = get_datetime().strftime('%Y-%m-%d %H:%M:%S')
    log.info('{} 盘前运行'.format(date))
    
    trade_date = get_last_trade_date()
    
    try:
        stock_zt_pool_df = ak.stock_zt_pool_em(date=trade_date)
    except Exception as e:
        log.info(f'获取昨日涨停股票失败: {e}')
        return
    
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
    
    context.selected_stocks = filtered_stocks[:5]
    
    log.info(f'筛选出 {len(context.selected_stocks)} 只股票')
    for stock in context.selected_stocks:
        log.info(f"{stock['name']}({stock['code']}) - 集合竞价/市值比: {stock['amount_to_mv_ratio']:.4f}")

def handle_bar(context, bar_dict):
    time = get_datetime().strftime('%Y-%m-%d %H:%M:%S')
    log.info('{} 盘中运行'.format(time))
    
    if len(context.selected_stocks) == 0:
        return
    
    for stock in context.selected_stocks:
        code = stock['code']
        
        if code in context.portfolio.stock_account.positions:
            continue
        
        current_price = bar_dict[code].close
        
        order_target_percent(code, 0.2)
        
        context.hold_stocks[code] = {
            'cost_basis': current_price,
            'buy_time': get_datetime(),
            'target_price': current_price * 1.1,
            'stop_loss_price': current_price * 0.9
        }
    
    positions = list(context.portfolio.stock_account.positions)
    
    for code in positions:
        if code not in context.hold_stocks:
            continue
        
        hold_info = context.hold_stocks[code]
        current_price = bar_dict[code].close
        
        if current_price >= hold_info['target_price']:
            log.info(f'{code} 达到止盈价 {hold_info["target_price"]:.2f}，清仓')
            order_target(code, 0)
            del context.hold_stocks[code]
        elif current_price <= hold_info['stop_loss_price']:
            log.info(f'{code} 达到止损价 {hold_info["stop_loss_price"]:.2f}，清仓')
            order_target(code, 0)
            del context.hold_stocks[code]

def after_trading(context):
    time = get_datetime().strftime('%Y-%m-%d %H:%M:%S')
    log.info('{} 盘后运行'.format(time))
    
    positions = list(context.portfolio.stock_account.positions)
    
    for code in positions:
        if code in context.hold_stocks:
            continue
        
        order_target(code, 0)
    
    context.selected_stocks = []
    
    log.info('一天结束')
