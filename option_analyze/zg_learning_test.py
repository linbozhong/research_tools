#!/usr/bin/env python
# coding:utf-8
from PoboAPI import *
import datetime
import time
import numpy as np
from copy import *
from datetime import timedelta


#开始时间，用于初始化一些参数
def OnStart(context) :
    print("on start is runing..")
    g.auth_name = "linbozhong"
    g.underlying_symbol = "510050.SHSE"
    context.myacc = None
    context.test_var = "hello contetx var"
    
    g.long_signal = False
    g.short_signal = False
    
    g.call_otm_2 = None
    g.put_otm_2 = None
    g.trade_month = None
    
    g.fixed_pos = 10
    
    g.option_pos = dict()
    
    if context.accounts["option_backtest"].Login() :
        context.myacc = context.accounts["option_backtest"]
        print('option backtest login successfully')
        

# 每天行情初始化的，获取当前的50etf对应的平值期权
def OnMarketQuotationInitialEx(context, exchange, daynight):
    if exchange != 'SHSE':
        return
    
    SubscribeBar(g.underlying_symbol, BarType.Day)

    
    option_list = GetOptionContracts(g.underlying_symbol, 0, 0)
#     print(option_list)
    
#     klinedata = GetHisData2(g.underlying_symbol, BarType.Day)
#     lastclose = klinedata[-1].close
    
    bar_list = GetHisData2(g.underlying_symbol, BarType.Day, count=2)
    last_bar = bar_list[-1]
    print((g.underlying_symbol, last_bar.datetime, last_bar.close))
    
    g.atmopc = GetAtmOptionContract(g.underlying_symbol, 0, last_bar.close, 0)
    contract = GetContractInfo(g.atmopc)
#     print(g.atmopc)
#     print(contract)
#     SubscribeBar(g.atmopc, BarType.Day)
    
#     print(context.myacc.AccountBalance)
#     print(g.auth_name)
#     print(context.backtest)
#     print(context.accounts)
#     print(context.param)
#     print(context.test_var)

  
def OnBar(context, code, bartype):
    # 到期前平仓逻辑
    
    
    # 权利金太低不开仓逻辑
    
    
    print("{code}-onBar event running".format(code=code))
    
    now = GetCurrentTime().date()
#     print(('now', now))
    
    cur_mon, next_mon, _ns, _nns = GetOptionsLastDates(code)
    if cur_mon - now < timedelta(days=5):
        g.trade_month = next_mon
    else:
        g.trade_month = cur_mon
    
    print(('trade month last day', g.trade_month))
    

    df = GetHisDataAsDF(code, bar_type = BarType.Day)
    close_list = df.close.values
    print(close_list)
    
    bar = df.iloc[-1]
    print((bar.tradedate, bar.open, bar.high, bar.low, bar.close))
    
    g.call_otm_2 = GetAtmOptionContractByPos(code, 'open', -2, 0, g.trade_month)
    g.put_otm_2 = GetAtmOptionContractByPos(code, 'open', -2, 1, g.trade_month)
    call_op = GetContractInfo(g.call_otm_2)
    put_op = GetContractInfo((g.put_otm_2))
    print((g.call_otm_2, call_op))
    print((g.put_otm_2, put_op))
    
    ma_dict = GetIndicator("MA", code, bar_type = BarType.Day, count=100)
#     print(ma_dict)
    ma5 = ma_dict["MA(5)"]
    ma10 = ma_dict["MA(10)"]
    ma20 = ma_dict["MA(20)"]
    
#     print(ma20[0] == 1.7976931348623157e+308)
#     print(ma20[0])

#     print(ma20)

    if close_list[-2] < ma20[-2] and close_list[-1] > ma20[-1]:
        print('signal')
        print(('long day', bar.tradedate, close_list[-1], ma20[-1]))
        g.long_signal = True
    
    if close_list[-2] > ma20[-2] and close_list[-1] < ma20[-1]:
        print('signal')
        print(('short day', bar.tradedate, close_list[-1], ma20[-1]))
        g.short_signal = True
    
#     positions = context.myacc.GetPositions()
#     print(positions)


    call_otm2_pos = g.option_pos.get('call_otm_2', None)
    put_otm2_pos = g.option_pos.get('put_otm_2', None)
    
    if g.long_signal:
        if call_otm2_pos:
            print("平虚2档购")
            op_code = call_otm2_pos['op_code']
            pos = call_otm2_pos['pos']
            QuickInsertOrder(context.myacc, op_code, 'buy', 'close',PriceType(PbPriceType.Limit, 16), abs(pos))

            g.option_pos['call_otm_2'] = None
            g.long_signal = False
           
        
        if not put_otm2_pos:
            print("卖虚2档沽")
            QuickInsertOrder(context.myacc, g.put_otm_2, 'sell', 'open', PriceType(PbPriceType.Limit, 16), g.fixed_pos)
            
            d = {}
            d['op_code'] = g.put_otm_2
            d['pos'] = -g.fixed_pos
            g.option_pos['put_otm_2'] = d
            g.long_signal = False

            
    if g.short_signal:
        if put_otm2_pos:
            print("平虚2档沽")
            op_code = put_otm2_pos['op_code']
            pos = put_otm2_pos['pos']
            QuickInsertOrder(context.myacc, op_code, 'buy', 'close',PriceType(PbPriceType.Limit, 16), abs(pos))
            
            g.option_pos['put_otm_2'] = None
            g.short_signal = False
        
        if not call_otm2_pos:
            print("卖虚2档购")
            QuickInsertOrder(context.myacc, g.call_otm_2, 'sell', 'open', PriceType(PbPriceType.Limit, 16), g.fixed_pos)
            
            d = {}
            d['op_code'] = g.call_otm_2
            d['pos'] = -g.fixed_pos
            g.option_pos['call_otm_2'] = d
            g.short_signal = False