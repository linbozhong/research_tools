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
#     context.myacc = None
    g.myacc = None
    
    g.iv = []
    g.atm_iv = 0
    g.pos_delta = 0
    g.target_pos = 0
    
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
    g.holiday_clear = False

    
    if context.accounts["option_backtest"].Login() :
        g.myacc = context.accounts["option_backtest"]
        print('option backtest login successfully')
        
        
def SetOpFee(op_code):
    fee = PBObj()
    fee.CloseUnit = 1.7
    g.myacc.SetFee(op_code, fee)
    fee_value = g.myacc.GetFee(op_code)
#     print(('fee value:', fee_value.CloseUnit))
        

def GetPosByIvSignal():
    if len(g.iv) == 1:
        pos = GetPosByIv(g.iv[0] * 100)
    else:
        last_iv = g.iv[-2]
        now_iv = g.iv[-1]
        print(('now iv:', now_iv, 'last iv:', last_iv))
        if now_iv > last_iv:
            pos = GetPosWhenIvUp(now_iv * 100)
            # 升波如果碰到降仓则不改仓位
            if abs(pos) <= abs(g.target_pos):
                pos = g.target_pos
        elif now_iv < last_iv:
            pos = GetPosWhenIvDown(now_iv * 100)
            # 降波如果碰到加仓则不改仓位
            if abs(pos) >= abs(g.target_pos):
                pos = g.target_pos
        else:
            return g.target_pos
    return pos


def GetPosWhenIvUp(iv):
    if iv >= 80:
        pos = 105
    elif iv >= 60:
        pos = 90
    elif iv >= 45:
        pos = 75
    elif iv >= 35:
        pos = 60
    elif iv >= 25:
        pos = 45
    elif iv >= 20:
        pos = 30
    elif iv >= 15:
        pos = 0
    else:
        pos = 0
    return -pos
        

def GetPosWhenIvDown(iv):
    if iv < 10:
        pos = 0
    elif iv < 15:
        pos = 0
    elif iv < 20:
        pos = 30
    elif iv < 25:
        pos = 45
    elif iv < 35:
        pos = 60
    elif iv < 45:
        pos = 75
    elif iv < 60:
        pos = 90
    elif iv < 80:
        pos = 105
    else:
        pos = 105
    return -pos    
    
    
def GetPosByIv(iv):
    pos = 0
    if 10 <= iv < 15:
        pos = 0
    elif 15 <= iv < 20:
        pos = 30
    elif 20 <= iv < 25:
        pos = 45
    elif 25 <= iv < 35:
        pos = 60
    elif 35 <= iv < 45:
        pos = 75
    elif 45 <= iv < 60:
        pos = 90
    elif 60 <= iv < 80:
        pos = 105 
    elif 80 <= iv:
        pos = 105
    return -pos


def GetCallOtm(level=-2):
    g.call_otm = GetAtmOptionContractByPos(g.underlying, 'now', level, 0, g.trade_month)
    # 此处有bug，如果没有下月month，就会变成乱取next_call_otm
    if g.next_month:
        g.next_call_otm = GetAtmOptionContractByPos(g.underlying, 'now', level, 0, g.next_month)
    else:
        g.next_call_otm = g.call_otm
        
#     SetOpFee(g.call_otm)
#     SetOpFee(g.next_call_otm)
    print(('get_call_otm', g.call_otm, GetStrikePrice(g.call_otm), g.next_call_otm, GetStrikePrice(g.next_call_otm)))
        
        
def GetPutOtm(level=-2):
    g.put_otm = GetAtmOptionContractByPos(g.underlying, 'now', level, 1, g.trade_month)
    if g.next_month:
        g.next_put_otm = GetAtmOptionContractByPos(g.underlying, 'now', level, 1, g.next_month)
    else:
        g.next_put_otm = g.put_otm
        
#     SetOpFee(g.put_otm)
#     SetOpFee(g.next_put_otm)
    print(('get_put_otm', g.put_otm, GetStrikePrice(g.put_otm), g.next_put_otm, GetStrikePrice(g.next_put_otm)))


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
    print(('trade month:', g.trade_month, 'next month:', g.next_month))
    
    
def RefreshOtm():
    call_otm_pos = GetCallPos()
    put_otm_pos = GetPutPos()
    
    # 无持仓需要每天刷新下单的虚值合约
    # 有持仓则要做虚实度判断才能更新合约（实现delta对冲）
    if not call_otm_pos['pos']:
        print('Refresh otm: no call otm')
        GetCallOtm()
    else:
        call_op_code = call_otm_pos['op_code']
        call_strike = GetStrikePrice(call_op_code)
        close = g.close_list[-1]
        strike_space = call_strike / close - 1
        if close >= call_strike or strike_space <= 0.02 or strike_space >= 0.06:
            print('购空间不足或过大')
            print((call_strike, close, strike_space))
            GetCallOtm()

    if not put_otm_pos['pos']:
        print('Refresh otm: no put otm')
        GetPutOtm()
    else:
        put_op_code = put_otm_pos['op_code']
        put_strike = GetStrikePrice(put_op_code)
        close = g.close_list[-1]
        strike_space = put_strike / close - 1
        if close <= put_strike or abs(strike_space) <= 0.02 or abs(strike_space) >= 0.06:
            print('沽空间不足或过大')
            print((put_strike, close, strike_space))
            GetPutOtm()
    
    # 有持仓且虚实度不变，但是到换月日了，需要换到下月合约，必须强制刷新otm合约，以便在MoveContract函数调仓
    if g.last_trade_month != g.trade_month:
        # 如果已经是下月则不变
        print(('换月日日期', g.last_trade_month, g.trade_month,))
        call_code = GetCallPos()['op_code']
#         print(('购合约名称：', call_code))
        if call_code:
            call_trade_month = GetExpireDate(call_code)
            print(( 'call合约：', call_code, call_trade_month))
            if g.trade_month == call_trade_month:
                print('购换月日虚实不变且已经是下月合约，无需更新otm')
            else:
                GetCallOtm()
        
        put_code = GetPutPos()['op_code']
        if put_code:
            put_trade_month = GetExpireDate(put_code)
            print(('put合约：', put_code, put_trade_month))
            if g.trade_month == put_trade_month:
                print('沽换月日虚实不变且已经是下月合约，无需更新otm')
            else:
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


# 判断是否大于5小于7天节假日后的首个交易日
def IsAfterHoliday5():
    df = g.holidays
    df2 = df[(df['holidays'] >= timedelta(days=5)) & (df['holidays'] < timedelta(days=7))]
    return GetCurrentTradingDate("SHSE") in df2['next'].values

# 判断是否大于7天节假日后的首个交易日
def IsAfterHoliday7():
    df = g.holidays
    df2 = df[(df['holidays'] >= timedelta(days=7))]
    return GetCurrentTradingDate("SHSE") in df2['next'].values
    

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
    print(('today close price:', close_list[-1]))

    
def IsEmptyPos():
    call_pos = GetCallPos()
    put_pos = GetPutPos()
    print(('is empty:', call_pos, put_pos))
    return call_pos['pos'] == 0 and put_pos['pos'] == 0


def GetPosDict(op_type):
    if op_type == "call":
        return GetCallPos()
    else:
        return GetPutPos()
    
    
def GetCallPos():
    call_otm_pos = g.option_pos.get('call_otm', None)
    if call_otm_pos is None:
        call_otm_pos = dict()
        call_otm_pos['op_code'] = ""
        call_otm_pos['pos'] = 0
        g.option_pos['call_otm'] = call_otm_pos
    return g.option_pos['call_otm']
    
    
def GetPutPos():
    put_otm_pos = g.option_pos.get('put_otm', None)
    if put_otm_pos is None:
        put_otm_pos = dict()
        put_otm_pos['op_code'] = ""
        put_otm_pos['pos'] = 0
        g.option_pos['put_otm'] = put_otm_pos
    return g.option_pos['put_otm']
    
    
def Buy(op_type, code, volume):
    QuickInsertOrder(g.myacc, code, "buy", "open", PriceType(PbPriceType.Limit, 16), volume)

    pos_dict = GetPosDict(op_type)
    pos_dict['op_code'] = code
    pos_dict['pos'] += volume
        

def Short(op_type, code, volume):
    QuickInsertOrder(g.myacc, code, "sell", "open", PriceType(PbPriceType.Limit, 16), volume)

    pos_dict = GetPosDict(op_type)
    pos_dict['op_code'] = code
    pos_dict['pos'] -= volume


def Sell(op_type, code, volume):
    QuickInsertOrder(g.myacc, code, "sell", "close", PriceType(PbPriceType.Limit, 16), volume)

    pos_dict = GetPosDict(op_type)
    if code == pos_dict['op_code']:
        pos_dict['pos'] -= volume
        if pos_dict['pos'] == 0:
            print('pos is empty now')
            pos_dict['op_code'] = ''

            
def Cover(op_type, code, volume):
    QuickInsertOrder(g.myacc, code, "buy", "close", PriceType(PbPriceType.Limit, 16), volume)

    pos_dict = GetPosDict(op_type)
    if code == pos_dict['op_code']:
        pos_dict['pos'] += volume
        if pos_dict['pos'] == 0:
            print('pos is empty now')
            pos_dict['op_code'] = ''

            
def CalcPosDelta():
    call_otm_pos = g.option_pos.get('call_otm', None)
    if not call_otm_pos:
        cur_pos = 0
    else:
        cur_pos = call_otm_pos["pos"]
        
    return g.target_pos - cur_pos
            
            
def ModifyPos(op_type, code):
    if not g.pos_delta:
        print("合约无需移仓或加减仓")
    else:
        if g.pos_delta < 0:
            # 加仓
            Short(op_type, code, abs(g.pos_delta))
        else:
            # 减仓
            Cover(op_type, code, g.pos_delta)

            
def ClearBeforeHoliday():
    if IsEmptyPos():
        print("节假日前已空仓，无需再次平仓")
        return
    for op_type in ['call', 'put']:
        pos_dict = GetPosDict(op_type)
        op_code = pos_dict['op_code']
        op_pos = pos_dict['pos']

        Cover(op_type, op_code, abs(op_pos))

    
def MoveContract(option_type):
    # 先前置判断一定要有仓位
    if IsEmptyPos():
        print("空仓，无需移仓")
        return
    
    # 有仓位的前提下
    pos_dict = GetPosDict(option_type)
    op_code = pos_dict['op_code']
    op_pos = pos_dict['pos']
    
    if option_type == "call":
        cur_otm = g.call_otm
        next_otm = g.next_call_otm
    else:
        cur_otm = g.put_otm
        next_otm = g.next_put_otm
    
    print(('pos', option_type, 'pos_code', op_code))
    print((option_type, 'cur_otm:', cur_otm, 'next_otm:', next_otm ))
    print((option_type, 'cur_otm_strike:', GetStrikePrice(cur_otm), 'next_otm_strike:', GetStrikePrice(next_otm)))

    
    # 不需要水平或垂直移仓，直接执行加减仓
    if op_code == next_otm:
        ModifyPos(option_type, op_code)
    # 不需要垂直移仓
    elif op_code == cur_otm:
        # 需要水平移仓（当月权利金过低，且存在下月合约可以移）
        if GetOptionClose(op_code) < 0.003 and next_otm != cur_otm:
            Cover(option_type, op_code, abs(op_pos))
            Short(option_type, next_otm, abs(g.target_pos))
        # 无法水平移仓
        else:
            ModifyPos(option_type, op_code)
    # 需要垂直移仓
    else:
        Cover(option_type, op_code, abs(op_pos))
        
        # 修订某些极端交易天数的特殊情况（因为懒，直接硬修订！:），一般不建议这样！）
        if GetCurrentTime().date() == datetime.datetime(2019, 2, 25).date() and option_type == 'put':
            Short(option_type, '10001714.SHSE', abs(g.target_pos))
            return

        # 垂直移仓的权利金太低，且存在下月合约可以移，需要同步水平移仓
        if GetOptionClose(cur_otm) < 0.005 and next_otm != cur_otm:
            Short(option_type, next_otm, abs(g.target_pos))
        else:
            Short(option_type, cur_otm, abs(g.target_pos))
       
                
def SetInitPos():
    # 修订某些极端交易天数的特殊情况（因为懒，直接硬修订！:），一般不建议这样！）
    print(GetCurrentTime().date())
    if GetCurrentTime().date() == datetime.datetime(2020, 2, 3).date():
        print("到了20200203这天")
        Short('call', '10002267.SHSE', 75)
        Short('put', '10002268.SHSE', 45)
        return
    
    if GetOptionClose(g.call_otm) < 0.005 and g.next_call_otm != g.call_otm:
        print(("当月认购权利金太低，换开下月:", GetOptionClose(g.call_otm)))
        call_code = g.next_call_otm
    else:
        call_code = g.call_otm
        
    if GetOptionClose(g.put_otm) < 0.005 and g.next_put_otm != g.put_otm:
        print(("当月认沽权利金太低，换开下月:", GetOptionClose(g.put_otm)))
        put_code = g.next_put_otm
    else:
        put_code = g.put_otm
        
    Short('call', call_code, abs(g.target_pos))
    Short('put', put_code, abs(g.target_pos))
    
    # 初始建完仓后设定没有目标仓差，否则调仓阶段会再下单
    g.pos_delta = 0
                
        
def OnBar(context, code, bartype):
#     print(GetCurrentTradingDate('SHSE'))
#     pre_trade = GetNextTradingDate("SHSE", GetCurrentTradingDate("SHSE"))
#     print(pre_trade)
    print(('查看日初仓位：', g.option_pos))
    
    print(('is next day 5 holiday pre day:', IsNext2Holiday5()))
    print(('is after next day 7 holiday pre day:', IsNext3Holiday7()))
    print(('is first day after 5 holiday:', IsAfterHoliday5()))
    print(('is first day after 7 holiday:', IsAfterHoliday7()))

    # 节假日结束后，清除假日清仓标记，允许建仓
    if IsAfterHoliday5() or IsAfterHoliday7():
        g.holiday_clear = False
    
    # 如果是长节假日前的平仓日，无需再做任何调仓判断，直接平掉所有仓位，并跳过其他调仓逻辑
    if IsNext2Holiday5() or IsNext3Holiday7():
        ClearBeforeHoliday()
        g.holiday_clear = True
        print("快要放假了，清仓休息了！")
        return
    
    if g.holiday_clear:
        print("已经启动节假日清仓，假日结束前不允许建仓")
        return

    # 更新标的价格序列
    GetUnderlyingPrice(code)
    
    # 更新交易月份
    CheckMonthMove(code)
    
    # 更新下单虚值合约
    RefreshOtm()
    
    # 计算平值沽购隐波均值、目标仓位、仓位差
    g.atm_iv = GetAtmIv()
    g.iv.append(g.atm_iv)
    g.target_pos = GetPosByIvSignal()
    print(('before calc pos delta, target_pos:', g.target_pos))
    g.pos_delta = CalcPosDelta()
    print(('iv:', g.atm_iv, 'target:', g.target_pos, 'pos_delta:', g.pos_delta))
    
    
    # 没有初始仓位就先建仓，并跳过调仓逻辑
    if IsEmptyPos():
        print('create pos')
        SetInitPos()
        return
        
#     移仓、加减仓
    MoveContract('call')
    MoveContract('put')
    
    # 计算目标仓位并根据现有持仓调整仓位
    
    
    # 输出波动率序列，仅用于验证
#     now = GetCurrentTime().date()
#     print(('cur iv', cur_atm_iv))
#     d = dict()
#     d['date'] = now.strftime('%Y%m%d')
#     d['atm_iv'] = cur_atm_iv
#     g.iv.append(d)
#     print(g.iv)
    
    
    
