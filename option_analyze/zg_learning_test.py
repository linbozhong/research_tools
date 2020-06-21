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
    bar = df.iloc[-1]
    print((bar.tradedate, bar.open, bar.high, bar.low, bar.close))
    
    g.call_otm_2 = GetAtmOptionContractByPos(code, 'open', -2, 0, g.trade_month)
    g.put_otm_2 = GetAtmOptionContractByPos(code, 'open', -2, 1, g.trade_month)
    call_op = GetContractInfo(g.call_otm_2)
    put_op = GetContractInfo((g.put_otm_2))
    print(call_op)
    print(put_op)
    
    ma_dict = GetIndicator("MA", code, bar_type = BarType.Day, count=100)
    print(ma_dict)
    ma5 = ma_dict["MA(5)"]
    ma10 = ma_dict["MA(10)"]
    
    
    positions = context.myacc.GetPositions()
    print(positions)
    
    posi = context.myacc.GetPositions() #获取所有持仓
    if len(posi) == 0:
        print("卖开")
        #下单卖开,2表示最新价
        QuickInsertOrder(context.myacc,g.atmopc,'sell','open',PriceType(PbPriceType.Limit,2),10)
    elif len(posi) >0:
        opcode = posi[0].contract
        print("买平")
        #下单买平,16表示对手价,平掉现有仓位的所有手数
        QuickInsertOrder(context.myacc,opcode,'buy','close',PriceType(PbPriceType.Limit,16),posi[0].volume)
    UnsubscribeBar(g.atmopc,BarType.Day)
