import pandas as pd
from typing import List
from datetime import datetime， timedelta
from collections import defaultdict

from vnpy.trader.object import BarData, TradeData
from vnpy.trader.constant import Interval
from vnpy.trader.database import database_manager
from vnpy.trader.utility import extract_vt_symbol


def vt_bar_to_df(bars: List[BarData]) -> pd.DataFrame:
    data = defaultdict(list)
    for bar in bars:
        data['datetime'].append(bar.datetime)
        data['open'].append(bar.open_price)
        data['high'].append(bar.high_price)
        data['low'].append(bar.low_price)
        data['close'].append(bar.close_price)
        data['volume'].append(bar.volume)
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df


def vt_trade_to_df(trades: List[TradeData]) -> pd.DataFrame:
    data = defaultdict(list)
    for trade in trades:
        data['datetime'].append(trade.datetime)
        data['vt_symbol'].append(trade.vt_symbol)
        data['direction'].append(trade.direction.value)
        data['offset'].append(trade.offset.value)
        data['price'].append(trade.price)
        data['volume'].append(trade.volume)
    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df


def load_data(vt_symbol: str, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
    symbol, exchange = extract_vt_symbol(vt_symbol)
    data = database_manager.load_bar_data(
        symbol,
        exchange,
        Interval(interval),
        start=start,
        end=end,
    )
    return vt_bar_to_df(data)


def strip_digt(symbol: str) -> str:
    res = ""
    for char in symbol:
        if not char.isdigit():
            res += char
        else:
            break
    return res


def to_vt_symbol(rq_symbol: str) -> str:
    """input symbol like RB1905.SHFE"""
    symbol, exchange = rq_symbol.split('.')
    if exchange in ['SHFE', 'DCE', 'INE']:
        return '.'.join([symbol.lower(), exchange])
    elif exchange in ['CZCE']:
        for idx, char in enumerate(symbol):
            if char.isdigit():
                break
        new_symbol = symbol[:idx] + symbol[idx+1:]
        return '.'.join([new_symbol, exchange])
    else:
        return rq_symbol


def get_dominant_in_periods(underlying: str, backtest_start: datetime, backtest_end: datetime) -> pd.DataFrame:
    """
    获取某个日期区间的主力合约数据
    """
    underlying = underlying.upper()
    seg = pd.read_csv('dominant_data.csv', parse_dates=[1, 2])
    
    sel = seg[seg['underlying'] == underlying].copy()
    sel.reset_index(inplace=True)
    passed = sel[sel['start'] < backtest_start]
    after = sel[sel['start'] > backtest_end]
    passed_closest_idx = passed.index.values[-1]
    after_first_idx = after.index.values[0] if not after.empty else len(sel)
    
    if passed.iloc[-1]['end'] - backtest_start < timedelta(days=37):
        passed_closest_idx += 1
    return sel[passed_closest_idx: after_first_idx].copy()