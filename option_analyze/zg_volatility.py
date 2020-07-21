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
    context.myacc = None
    
    g.iv = []
    
    g.sell_call = False
    g.sell_put = False
    g.close_call = False
    g.close_put = False
    
    g.last_trade_month = None
    g.trade_month = None
    g.next_month = None
    
    g.call_otm = None
    g.put_otm = None
    g.next_call_otm = None
    g.next_put_otm = None
    
    
    g.option_pos = dict()
    
    g.holidays = GetHolidayPreDays()

    
    if context.accounts["option_backtest"].Login() :
        context.myacc = context.accounts["option_backtest"]
        print('option backtest login successfully')
        
        
def GetPosByIv(iv):
    pos = 0
    if 10 <= iv < 15:
        pos = 15
    elif 15 <= iv < 25:
        pos = 30
    elif 25 <= iv < 35:
        pos = 45
    elif 35 <= iv < 45:
        pos = 60
    elif 45 <= iv < 55:
        pos = 75
    elif 55 <= iv:
        pos = 90
    return -pos


def GetCallOtm():
    g.call_otm = GetAtmOptionContractByPos(g.underlying_symbol, 'now', -2, 0, g.trade_month)
    if g.next_month:
        g.next_call_otm = GetAtmOptionContractByPos(g.underlying_symbol, 'now', -2, 0, g.next_month)
        
        
def GetPutOtm():
    g.put_otm = GetAtmOptionContractByPos(g.underlying_symbol, 'now', -2, 1, g.trade_month)
    if g.next_month:
        g.next_put_otm = GetAtmOptionContractByPos(g.underlying_symbol, 'now', -2, 1, g.next_month)    
    

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
#     print(('trade month:', g.trade_month, 'next month:', g.next_month))
    
    
def RefreshOtm():
    call_otm_pos = g.option_pos.get('call_otm', None)
    put_otm_pos = g.option_pos.get('put_otm', None)
    
    if not call_otm_pos:
        GetCallOtm()
    else:
        call_op_code = call_otm_pos['op_code']
        call_strike = GetStrikePrice(call_op_code)
        close = g.close_list[-1]
        strike_space = call_strike / close - 1
        if close >= call_strike or strike_space <= 0.02 or strike_space >= 0.05:
            print('购空间不足或过大')
            print((call_strike, close, strike_space))
            GetCallOtm()

    if not put_otm_pos:
        print('no put otm2')
        GetPutOtm()
    else:
        put_op_code = put_otm_pos['op_code']
        put_strike = GetStrikePrice(put_op_code)
        close = g.close_list[-1]
        strike_space = put_strike / close - 1
        if close <= put_strike or abs(strike_space) <= 0.02 or abs(strike_space) >= 0.05:
            print('沽空间不足或过大')
            print((put_strike, close, strike_space))
            GetPutOtm()
    
    # 上述条件可能都不触发，所以换月日必须强制刷新otm合约
    if g.last_trade_month != g.trade_month:
        GetCallOtm()
        GetPutOtm()
    

# 获取长节假日前一天
def GetHolidayPreDays():
    trading_days = GetTradingDates("SHSE", 20150209, 20200716)
#     print(trading_days)

    df = pd.DataFrame(trading_days, columns=['cur'])
    df['next'] = df['cur'].shift(-1)
    df['holidays'] = df['next'] - df['cur']
#     print(df.head())
    return df


# 判断是否大于等于5天节假日的平仓日
def IsNext2Holiday5():
    next_trade = GetNextTradingDate("SHSE", GetCurrentTradingDate("SHSE"))
    
    df = g.holidays
    df2 = df[(df['holidays'] >= timedelta(days=5)) & (df['holidays'] < timedelta(days=7))]
    return next_trade in df2['cur'].values


# 判断是否大于等于7天节假日的平仓日
def IsNext3Holiday7():
    next_trade = GetNextTradingDate("SHSE", GetCurrentTradingDate("SHSE"))
    after_next_trade = GetNextTradingDate("SHSE", next_trade)
    
    df = g.holidays
    df2 = df[(df['holidays'] >= timedelta(days=7))]
    return after_next_trade in df2['cur'].values
        

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

    
def MoveContract(context, option_type):
    pass


def call_set_target_pos(target_pos):
    call_otm_pos = g.option_pos.get('call_otm', None)
    if not call_otm_pos:
        cur_pos = 0
    else:
        cur_pos = call_otm_pos["pos"]
        
    volume = target_pos - cur_pos
    if not volume:
        return
    offset = "open" if volume > 0 else "close"
    
    if GetOptionClose(g.call_otm) < 0.006 and g.next_call_otm:
        print("当月认购权利金太低，换开下月")
        call_code = g.next_call_otm
    else:
        call_code = g.call_otm
    QuickInsertOrder(context.myacc, call_code, 'sell', offset, PriceType(PbPriceType.Limit, 16), volume)


def put_set_target_pos(target_pos):
    put_otm_pos = g.option_pos.get('put_otm', None)
    if not put_otm_pos:
        cur_pos = 0
    else:
        cur_pos = put_otm_pos["pos"]
        
    volume = target_pos - cur_pos
    if not volume:
        return
    offset = "open" if volume > 0 else "close"
    
    if GetOptionClose(g.put_otm) < 0.006 and g.next_put_otm:
        print("当月认沽权利金太低，换开下月")
        call_code = g.next_put_otm
    else:
        call_code = g.put_otm
    QuickInsertOrder(context.myacc, call_code, 'sell', offset, PriceType(PbPriceType.Limit, 16), volume)
    
    
        
def OnBar(context, code, bartype):
#     print(GetCurrentTradingDate('SHSE'))
#     pre_trade = GetNextTradingDate("SHSE", GetCurrentTradingDate("SHSE"))
#     print(pre_trade)
    
#     print(('is next day 5 holiday pre day:', IsNext2Holiday5()))
#     print(('is after next day 7 holiday pre day:', IsNext3Holiday7()))
    
    # 更新标的价格序列
    GetUnderlyingPrice(code)
    
    # 更新交易月份
    CheckMonthMove(code)
    
    # 计算平值沽购隐波均值
    cur_atm_iv = GetAtmIv()
    
    
    # 计算目标仓位并根据现有持仓调整仓位
    target_pos = GetPosByIv(cur_atm_iv)
    call_set_target_pos(target_pos)
    put_set_target_pos(target_pos)
    
    
    # 输出波动率序列，仅用于验证
#     now = GetCurrentTime().date()
#     print(('cur iv', cur_atm_iv))
#     d = dict()
#     d['date'] = now.strftime('%Y%m%d')
#     d['atm_iv'] = cur_atm_iv
#     g.iv.append(d)
#     print(g.iv)
    
    
    
