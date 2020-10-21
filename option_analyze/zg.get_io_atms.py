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
    g.underlying = "000300.SHSE"
    g.close_list = None
    g.myacc = None
    
    g.atm_op_list = []
    
    if context.accounts["option_backtest"].Login() :
        g.myacc = context.accounts["option_backtest"]
        print('option backtest login successfully')
        

# 每天行情初始化的
def OnMarketQuotationInitialEx(context, exchange, daynight):
    if exchange != 'SHSE':
        return
    SubscribeBar(g.underlying, BarType.Day)
  
        
def OnBar(context, code, bartype):
    # 更新标的价格序列
    underlying_open = GetQuote(g.underlying).open
    m_atm_call = GetAtmOptionContract(g.underlying, 0, underlying_open, 0)
    m_atm_put = GetAtmOptionContract(g.underlying, 0, underlying_open, 1)
    now = GetCurrentTime().date()

    d = dict()
    d["date"] = now.strftime('%Y%m%d')
    d["underlying_open"] = underlying_open
    d["m_atm_call"] = m_atm_call
    d["m_atm_put"] = m_atm_put
    g.atm_op_list.append(d)

    if now == datetime.datetime(2020, 10, 16).date():
        print(g.atm_op_list)
