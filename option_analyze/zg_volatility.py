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
    g.underlying_symbol = "510050.SHSE"
    g.close_list = None
    context.myacc = None
    
    g.sell_call = False
    g.sell_put = False
    g.close_call = False
    g.close_put = False
    
    g.last_trade_month = None
    g.trade_month = None
    g.next_month = None
    
    g.call_otm_2 = None
    g.put_otm_2 = None
    g.next_call_otm_2 = None
    g.next_put_otm_2 = None
    
    g.fixed_pos = 30
    
    g.option_pos = dict()
    
    if context.accounts["option_backtest"].Login() :
        context.myacc = context.accounts["option_backtest"]
        print('option backtest login successfully')
        

# 每天行情初始化的
def OnMarketQuotationInitialEx(context, exchange, daynight):
    if exchange != 'SHSE':
        return
    SubscribeBar(g.underlying_symbol, BarType.Day)


def GetStrikePrice(option_code):
    option = GetContractInfo(option_code)
    return option["行权价格"]

def GetExpireDate(option_code):
    option = GetContractInfo(option_code)
    return option["最后交易日"]

def GetOptionType(option_code):
    option = GetContractInfo(option_code)
    return option["期权种类"]

def GetOptionIv(option_code):
    o_price = GetOptionClose(option_code)
    s_price = g.close_list[-1]
    direction = GetOptionType(option_code)
    strike = GetStrikePrice(option_code)
    
    exprie_day = GetExpireDate(option_code)
    now = GetCurrentTime().date()
    life_days = expire_day - now
    t = life_days.date() / 365
    
    b = CreateCalcObj()
    iv = b.GetImpliedVolatility(direction, 0 , s_price, strike, 0.2, 0.04, t, o_price)
    return iv

def GetIv():
    pass
    

def GetOptionClose(option_code):
    bars = GetHisData2(option_code, BarType.Day, count=100)
    return bars[-1].close


def MoveContract(context, option_type):
    pass
              
            
def GetCallOtm():
    pass
        
        
def GetPutOtm():
    pass
                
            
def RefreshOtm():
    pass
        
def OnBar(context, code, bartype):
    pass
    
