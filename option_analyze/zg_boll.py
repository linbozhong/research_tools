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


def GetOptionClose(option_code):
    bars = GetHisData2(option_code, BarType.Day, count=100)
    return bars[-1].close


def MoveContract(context, option_type):
    call_otm2_pos = g.option_pos.get('call_otm_2', None)
    put_otm2_pos = g.option_pos.get('put_otm_2', None)
    
    # type is 'call' or 'put'
    if option_type == "call":
        if not call_otm2_pos:
            print("没有卖购合约")
        else:
            op_code = call_otm2_pos['op_code']
            if op_code != g.call_otm_2:
                # 开仓就是下月合约跳过
                if op_code == g.next_call_otm_2:
                    return
                
                # 权利金太低的合约提前移到下月
                call_otm_close = GetOptionClose(g.call_otm_2)
                if call_otm_close < 0.005 and g.next_call_otm_2:
                    call_otm = g.next_call_otm_2
                else:
                    call_otm = g.call_otm_2
                
                pos = call_otm2_pos['pos']
                QuickInsertOrder(context.myacc, op_code, 'buy', 'close',PriceType(PbPriceType.Limit, 16), abs(pos))
                QuickInsertOrder(context.myacc, call_otm, 'sell', 'open', PriceType(PbPriceType.Limit, 16), abs(pos))

                call_otm2_pos['op_code'] = call_otm
                call_otm2_pos['pos'] = -pos
                print("{old}平仓，{new}开仓".format(old=op_code, new=call_otm))
            
    if option_type == "put":
        if not put_otm2_pos:
            print("没有卖沽合约")
        else:
            op_code = put_otm2_pos['op_code']
            if op_code != g.put_otm_2:
#                 print(("沽移仓", op_code, g.put_otm_2))
                if op_code == g.next_put_otm_2:
                    return
                
                put_otm_close = GetOptionClose(g.put_otm_2)
                if put_otm_close < 0.005 and g.next_put_otm_2:
                    put_otm = g.next_put_otm_2
                else:
                    put_otm = g.put_otm_2
                
                
                pos = put_otm2_pos['pos']
                QuickInsertOrder(context.myacc, op_code, 'buy', 'close',PriceType(PbPriceType.Limit, 16), abs(pos))
                QuickInsertOrder(context.myacc, put_otm, 'sell', 'open', PriceType(PbPriceType.Limit, 16), abs(pos))

                put_otm2_pos['op_code'] = put_otm
                put_otm2_pos['pos'] = -pos
                print("{old}平仓，{new}开仓".format(old=op_code, new=put_otm))
              
            
def GetCallOtm():
    g.call_otm_2 = GetAtmOptionContractByPos(g.underlying_symbol, 'now', -2, 0, g.trade_month)
    if g.next_month:
        g.next_call_otm_2 = GetAtmOptionContractByPos(g.underlying_symbol, 'now', -2, 0, g.next_month)
        
        
def GetPutOtm():
    g.put_otm_2 = GetAtmOptionContractByPos(g.underlying_symbol, 'now', -2, 1, g.trade_month)
    if g.next_month:
        g.next_put_otm_2 = GetAtmOptionContractByPos(g.underlying_symbol, 'now', -2, 1, g.next_month)
                
            
def RefreshOtm():
    call_otm2_pos = g.option_pos.get('call_otm_2', None)
    put_otm2_pos = g.option_pos.get('put_otm_2', None)
    
    if not call_otm2_pos:
        GetCallOtm()
    else:
        call_op_code = call_otm2_pos['op_code']
        call_strike = GetStrikePrice(call_op_code)
        close = g.close_list[-1]
        strike_space = call_strike / close - 1
        if close >= call_strike or strike_space <= 0.02 or strike_space >= 0.05:
            print('购空间不足或过大')
            print((call_strike, close, strike_space))
            GetCallOtm()

    if not put_otm2_pos:
        print('no put otm2')
        GetPutOtm()
    else:
        put_op_code = put_otm2_pos['op_code']
        put_strike = GetStrikePrice(put_op_code)
        close = g.close_list[-1]
        strike_space = put_strike / close - 1
        if close <= put_strike or abs(strike_space) <= 0.02 or abs(strike_space) >= 0.05:
            print('沽空间不足或过大')
            print((put_strike, close, strike_space))
            GetPutOtm()

        
def OnBar(context, code, bartype):
    g.close_call = False
    g.close_put = False
    print(('close_call', g.close_call, 'close_put', g.close_put))
    print(('sell_call', g.sell_call, 'sell_put', g.sell_put))
    
    # 获取标的历史数据
    df = GetHisDataAsDF(code, bar_type = BarType.Day)
    close_list = df.close.values
    g.close_list = close_list
#     print(close_list)
    bar = df.iloc[-1]
    print((bar.tradedate, bar.open, bar.high, bar.low, bar.close))
    
    
    # 选择新的操作月份
    now = GetCurrentTime().date()
    g.last_trade_month = g.trade_month
    cur_mon, next_mon, _ns, _nns = GetOptionsLastDates(code)
    if cur_mon - now < timedelta(days=5):
        g.trade_month = next_mon
        g.next_month = None
    else:
        g.trade_month = cur_mon
        g.next_month = next_mon
    print(('trade month last day', g.trade_month))
    
    
    # 选出当月和下月虚2档沽购合约
    RefreshOtm()
    
    # 换月日强制刷新
    if g.last_trade_month != g.trade_month:
        GetCallOtm()
        GetPutOtm()
        
#     print(("行权价格", GetStrikePrice(g.call_otm_2)))

#     print('期权价格')
#     print(GetOptionClose(g.call_otm_2))
        
    
    # 获取当前操作月份虚2档沽购合约的历史数据
    call_df = GetHisDataAsDF(g.call_otm_2, bar_type=BarType.Day)
    put_df = GetHisDataAsDF(g.put_otm_2, bar_type=BarType.Day)

  
    # 查看期权详情，仅用于验证策略逻辑
    call_op = GetContractInfo(g.call_otm_2)
    put_op = GetContractInfo((g.put_otm_2))
    print((g.call_otm_2, call_op))
    print((g.put_otm_2, put_op))
    
    
    # 计算标的技术指标和交易信号
#     ma_dict = GetIndicator("MA", code, bar_type=BarType.Day, count=100)
#     ma5 = ma_dict["MA(5)"]
#     ma10 = ma_dict["MA(10)"]
#     ma20 = ma_dict["MA(20)"]
    
    
    boll_dict = GetIndicator("BOLL", code, params=(20, 2), bar_type=BarType.Day, count=100)
    boll_mid = boll_dict["MID"]
    boll_up = boll_dict["UPPER"]
    boll_lower = boll_dict["LOWER"]
    print((bar.tradedate, 'boll', boll_mid[-1], boll_up[-1], boll_lower[-1]))
    
    
#     print(ma20[0] == 1.7976931348623157e+308)

    if close_list[-2] < boll_mid[-2] and close_list[-1] > boll_mid[-1]:
        print('sell put signal')
        print(('long day', bar.tradedate, close_list[-1], boll_mid[-1]))
        g.sell_put = True
    
    if close_list[-2] > boll_mid[-2] and close_list[-1] < boll_mid[-1]:
        print('sell call signal')
        print(('short day', bar.tradedate, close_list[-1], boll_mid[-1]))
        g.sell_call = True
        
    if close_list[-1] > boll_up[-2]:
        print('close call signal')
        g.close_call = True
        
    if close_list[-1] < boll_lower[-2]:
        print('close put signal')
        g.close_put = True

    # 获取持仓信息
    call_otm2_pos = g.option_pos.get('call_otm_2', None)
    put_otm2_pos = g.option_pos.get('put_otm_2', None)
    
    # 先检查是否有交易信号，如有平仓操作，则取消移仓换月操作
    if g.sell_put:
        if not put_otm2_pos:
            print("卖虚2档沽")
            
            if put_df.iloc[-1].close < 0.005 and g.next_put_otm_2:
                print("卖沽权利金太低，换开下月")
                put_code = g.next_put_otm_2
            else:
                put_code = g.put_otm_2
            QuickInsertOrder(context.myacc, put_code, 'sell', 'open', PriceType(PbPriceType.Limit, 16), g.fixed_pos)
            
            d = {}
            d['op_code'] = put_code
            d['pos'] = -g.fixed_pos
            g.option_pos['put_otm_2'] = d
            g.sell_put = False
        else:
            g.sell_put = False
        
    if g.close_call:
        if call_otm2_pos:
            print("平虚2档购")
            op_code = call_otm2_pos['op_code']
            pos = call_otm2_pos['pos']
            QuickInsertOrder(context.myacc, op_code, 'buy', 'close',PriceType(PbPriceType.Limit, 16), abs(pos))

            g.option_pos['call_otm_2'] = None
            g.close_call = False
            
            
    if g.sell_call:
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
            g.sell_call = False
        else:
            g.sell_call = False
            
    if g.close_put:
        if put_otm2_pos:
            print("平虚2档沽")
            op_code = put_otm2_pos['op_code']
            pos = put_otm2_pos['pos']
            QuickInsertOrder(context.myacc, op_code, 'buy', 'close',PriceType(PbPriceType.Limit, 16), abs(pos))
            
            g.option_pos['put_otm_2'] = None
            g.close_put = False
    
    
    # 移仓换月
    MoveContract(context, "call")
    MoveContract(context, "put")
    
    
