import pandas as pd
from typing import List
from datetime import datetime
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