#!/usr/bin/env python
# coding:utf-8
from PoboAPI import *
import datetime
import time
import numpy as np
import pandas as pd
from copy import *
from datetime import timedelta


#开始时间，用于初始化一些参数
def OnStart(context) :
    g.underlying = "510050.SHSE"
    g.close_list = None
    g.myacc = None
    
    g.atm_iv_list = []

    g.last_trade_month = None
    g.trade_month = None
    g.next_month = None
    
    if context.accounts["option_backtest"].Login() :
        g.myacc = context.accounts["option_backtest"]
        print('option backtest login successfully')
        

# 每天行情初始化的
def OnMarketQuotationInitialEx(context, exchange, daynight):
    if exchange != 'SHSE':
        return
    SubscribeBar(g.underlying, BarType.Day)


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
    
    expire_day = GetExpireDate(option_code)
    now = GetCurrentTime().date()
    life_days = expire_day - now
    t = life_days.days / 365
    
    b = CreateCalcObj()
    iv = b.GetImpliedVolatility(direction, 0 , s_price, strike, 0.2, 0.04, t, o_price)
    return iv


def GetAtmIv(excute_date=None):
    if not excute_date:
        excute_date = g.trade_month
    print(g.trade_month)
    atm_call = GetAtmOptionContractByPos(g.underlying, 'now', 0, 0, excute_date)
    atm_put = GetAtmOptionContractByPos(g.underlying, 'now', 0, 1, excute_date)
    call_iv = GetOptionIv(atm_call)
    put_iv = GetOptionIv(atm_put)
    return (call_iv + put_iv) / 2
    
    
def GetOptionClose(option_code):
    bars = GetHisData2(option_code, BarType.Day, count=100)
    return bars[-1].close


def GetUnderlyingPrice(code):
    df = GetHisDataAsDF(code, bar_type = BarType.Day)
    close_list = df.close.values
    g.close_list = close_list
    print(('today close price:', close_list[-1]))

    
def CheckMonthMove(code):
    now = GetCurrentTime().date()
    g.last_trade_month = g.trade_month
    cur_mon, next_mon, _ns, _nns = GetOptionsLastDates(code)
    if cur_mon - now < timedelta(days=7):
        g.trade_month = next_mon
        g.next_month = None
    else:
        g.trade_month = cur_mon
        g.next_month = next_mon
        
        
def OnBar(context, code, bartype):
    # 更新标的价格序列
    GetUnderlyingPrice(code)
    
    # 更新月份
    CheckMonthMove(code)
    
    # 输出波动率序列，仅用于验证
    now = GetCurrentTime().date()
    cur_atm_iv = GetAtmIv()
    print(('cur iv', cur_atm_iv))
    
    d = dict()
    d["date"] = now.strftime('%Y%m%d')
    d["atm_iv"] = cur_atm_iv
    g.atm_iv_list.append(d)
    
    if now == datetime.datetime(2020, 8, 25).date():
        print(g.atm_iv_list)
    
    
    
