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
    
    g.month = None
    g.next_month = None
    g.season = None
    g.next_season = None
    
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
    try:
        o_price = GetOptionClose(option_code)
    except IndexError:
        iv = None
    else:
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


def GetSkewIv():
    atm_call = GetAtmOptionContractByPos(g.underlying, 'now', 0, 0, g.trade_month)
    atm_put = GetAtmOptionContractByPos(g.underlying, 'now', 0, 1, g.trade_month)
    otm_call = GetAtmOptionContractByPos(g.underlying, 'now', -2, 0, g.trade_month)
    otm_put = GetAtmOptionContractByPos(g.underlying, 'now', -2, 1, g.trade_month)
    
    atm_call_iv = GetOptionIv(atm_call)
    atm_put_iv = GetOptionIv(atm_put)
    
    if atm_call == otm_call:
        otm_call_iv = None
    else:
        otm_call_iv = GetOptionIv(otm_call)
        
    if atm_put == otm_put:
        otm_put_iv = None
    else:
        otm_put_iv = GetOptionIv(otm_put)
        
    return atm_call_iv, atm_put_iv, otm_call_iv, otm_put_iv
    
def GetAtmIv(excute_date):
    atm_call = GetAtmOptionContractByPos(g.underlying, 'now', 0, 0, excute_date)
    atm_put = GetAtmOptionContractByPos(g.underlying, 'now', 0, 1, excute_date)
    
    call_iv = GetOptionIv(atm_call)
    put_iv = GetOptionIv(atm_put)
    if call_iv is None or put_iv is None:
        return None, None, None
    else:
        return (call_iv + put_iv) / 2, call_iv, put_iv
    
    
def GetOptionClose(option_code):
    bars = GetHisData2(option_code, BarType.Day, count=100)
#     print(('get option code', option_code))
#     print(bars[-1])
    return bars[-1].close


def GetUnderlyingPrice(code):
    df = GetHisDataAsDF(code, bar_type = BarType.Day)
    close_list = df.close.values
    g.close_list = close_list
    print(('today close price:', close_list[-1]))

    
def GetAllMonth(code):
    g.month, g.next_month, g.season, g.next_season = GetOptionsLastDates(code)


def CheckMonthMove(code):
    now = GetCurrentTime().date()
    g.last_trade_month = g.trade_month
    cur_mon, next_mon, _ns, _nns = GetOptionsLastDates(code)
    if cur_mon - now < timedelta(days=10):
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
    GetAllMonth(code)
    
    
    # 输出波动率序列
    now = GetCurrentTime().date()
    month_atm_iv, month_call, month_put = GetAtmIv(g.month)
    next_month_atm_iv, next_month_call, next_month_put = GetAtmIv(g.next_month)
    season_atm_iv, season_call, season_put = GetAtmIv(g.season)
    next_season_atm_iv, next_season_call, next_season_put = GetAtmIv(g.next_season)
    
    skew_atm_call, skew_atm_put, skew_otm_call, skew_otm_put = GetSkewIv()
#     print(('cur iv', cur_atm_iv))
    
    d = dict()
    d["date"] = now.strftime('%Y%m%d')
    d["expire_date"] = g.month.strftime('%Y%m%d')
    d["month"] = month_atm_iv
    d["month_call"] = month_call
    d["month_put"] = month_put
    d["next_month"] = next_month_atm_iv
    d["next_month_call"] = next_month_call
    d["next_month_put"] = next_month_put
    d["season"] = season_atm_iv
    d["season_call"] = season_call
    d["season_put"] = season_put
    d["next_season"] = next_season_atm_iv
    d["next_season_call"] = next_season_call
    d["next_season_put"] = next_season_put
    d["skew_atm_call"] = skew_atm_call
    d["skew_atm_put"] = skew_atm_put
    d["skew_otm_call"] = skew_otm_call
    d["skew_otm_put"] = skew_otm_put

#     print(d)
    g.atm_iv_list.append(d)
    
    if now == datetime.datetime(2020, 9, 18).date():
        print(g.atm_iv_list)
    
    
    
