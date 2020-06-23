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
#     g.move_pos = True
    
#     g.cur_month = None
    g.last_trade_month = None
    g.trade_month = None
    g.next_month = None

    
    g.call_otm_2 = None
    g.put_otm_2 = None
    
#     g.cur_call_otm_2 = None
#     g.cur_put_otm_2 = None
    g.next_call_otm_2 = None
    g.next_put_otm_2 = None
    
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
    
    
    # 权利金太低开到下个月
    
    
    print("{code}-onBar event running".format(code=code))
    
    now = GetCurrentTime().date()
#     print(('now', now))

    
    # 选择新的操作月份，并设定移仓换月的标记
    g.last_trade_month = g.trade_month
    cur_mon, next_mon, _ns, _nns = GetOptionsLastDates(code)
    if cur_mon - now < timedelta(days=5):
        g.trade_month = next_mon
        g.next_month = None
#         g.move_pos = True
    else:
        g.trade_month = cur_mon
        g.next_month = next_mon
    print(('trade month last day', g.trade_month))
    
    
    # 选出当月和下月虚2档沽购合约
    g.call_otm_2 = GetAtmOptionContractByPos(code, 'open', -2, 0, g.trade_month)
    g.put_otm_2 = GetAtmOptionContractByPos(code, 'open', -2, 1, g.trade_month)
    if g.next_month:
        g.next_call_otm_2 = GetAtmOptionContractByPos(code, 'open', -2, 0, g.next_month)
        g.next_put_otm_2 = GetAtmOptionContractByPos(code, 'open', -2, 1, g.next_month)
    
    call_df = GetHisDataAsDF(g.call_otm_2, bar_type=BarType.Day)
    put_df = GetHisDataAsDF(g.put_otm_2, bar_type=BarType.Day)

    df = GetHisDataAsDF(code, bar_type = BarType.Day)
    close_list = df.close.values
    print(close_list)
    
    bar = df.iloc[-1]
    print((bar.tradedate, bar.open, bar.high, bar.low, bar.close))
  
        
    call_op = GetContractInfo(g.call_otm_2)
    put_op = GetContractInfo((g.put_otm_2))
    print((g.call_otm_2, call_op))
    print((g.put_otm_2, put_op))
    
    
    # 计算指标和交易信号
    ma_dict = GetIndicator("MA", code, bar_type = BarType.Day, count=100)
    ma5 = ma_dict["MA(5)"]
    ma10 = ma_dict["MA(10)"]
    ma20 = ma_dict["MA(20)"]
    
#     print(ma20[0] == 1.7976931348623157e+308)

    if close_list[-2] < ma20[-2] and close_list[-1] > ma20[-1]:
        print('signal')
        print(('long day', bar.tradedate, close_list[-1], ma20[-1]))
        g.long_signal = True
    
    if close_list[-2] > ma20[-2] and close_list[-1] < ma20[-1]:
        print('signal')
        print(('short day', bar.tradedate, close_list[-1], ma20[-1]))
        g.short_signal = True
    

    # 获取持仓信息
    call_otm2_pos = g.option_pos.get('call_otm_2', None)
    put_otm2_pos = g.option_pos.get('put_otm_2', None)
    
    
    # 先检查是否有交易信号，如有平仓操作，则取消移仓换月操作
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
            
            if put_df.iloc[-1].close < 0.006 and g.next_put_otm_2:
                print("卖沽权利金太低，换开下月")
                put_code = g.next_put_otm_2
            else:
                put_code = g.put_otm_2
            QuickInsertOrder(context.myacc, put_code, 'sell', 'open', PriceType(PbPriceType.Limit, 16), g.fixed_pos)
            
            d = {}
            d['op_code'] = put_code
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
            
            if call_df.iloc[-1].close < 0.006 and g.next_call_otm_2:
                print("卖购权利金太低，换开下月")
                call_code = g.next_call_otm_2
            else:
                call_code = g.call_otm_2
            QuickInsertOrder(context.myacc, call_code, 'sell', 'open', PriceType(PbPriceType.Limit, 16), g.fixed_pos)
            
            d = {}
            d['op_code'] = call_code
            d['pos'] = -g.fixed_pos
            g.option_pos['call_otm_2'] = d
            g.short_signal = False
            
            
    # 移仓换月
    if g.last_trade_month and g.last_trade_month != g.trade_month:
        print("compare month")
        print((g.last_trade_month, g.trade_month))
        if call_otm2_pos:
            print("移仓卖购")
            
            op_code = call_otm2_pos['op_code']
            call_op = GetContractInfo(op_code)
            if call_op['最后交易日'] == g.trade_month:
                print("卖购已是下月合约")
                pass
            else:
                pos = call_otm2_pos['pos']
                QuickInsertOrder(context.myacc, op_code, 'buy', 'close',PriceType(PbPriceType.Limit, 16), abs(pos))
                QuickInsertOrder(context.myacc, g.call_otm_2, 'sell', 'open', PriceType(PbPriceType.Limit, 16), abs(pos))

                call_otm2_pos['op_code'] = g.call_otm_2
                call_otm2_pos['pos'] = -pos
            
            
        if put_otm2_pos:
            print("移仓卖沽")
            
            op_code = put_otm2_pos['op_code']
            put_op = GetContractInfo(op_code)
            if put_op['最后交易日'] == g.trade_month:
                print("卖沽已是下月合约")
                pass
            else:
                pos = put_otm2_pos['pos']
                QuickInsertOrder(context.myacc, op_code, 'buy', 'close',PriceType(PbPriceType.Limit, 16), abs(pos))
                QuickInsertOrder(context.myacc, g.put_otm_2, 'sell', 'open', PriceType(PbPriceType.Limit, 16), abs(pos))

                put_otm2_pos['op_code'] = g.put_otm_2
                put_otm2_pos['pos'] = -pos

        

        
        