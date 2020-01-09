import pandas as pd
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from datetime import time as dt_time
from collections import defaultdict
from pathlib import Path

from vnpy.trader.object import BarData, TradeData
from vnpy.trader.constant import Interval, Offset
from vnpy.trader.database import database_manager
from vnpy.trader.utility import extract_vt_symbol
from vnpy.app.cta_strategy.backtesting import BacktestingEngine

from boll_channel_strategy import BollChannelStrategy
from turtle_signal_strategy import TurtleSignalStrategy

strategy_dict = {
    'boll': BollChannelStrategy,
    'turtle': TurtleSignalStrategy
}

zh_to_en = {
    '多': 'long',
    '空': 'short',
    '开': 'open',
    '平': 'close'
}

dominant_data = pd.read_csv('dominant_data.csv', parse_dates=[1, 2])
exchange_map = dominant_data.copy().drop_duplicates('underlying').set_index('underlying')['exchange']

def trade_zh_to_en(trade_df: pd.DataFrame) -> pd.DataFrame:
    trade_df['direction'] = trade_df['direction'].map(zh_to_en)
    trade_df['offset'] = trade_df['offset'].map(zh_to_en)
    return trade_df


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
        data['vt_tradeid'].append(trade.vt_tradeid)
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
    sel.reset_index(inplace=True, drop=True)
    passed = sel[sel['start'] < backtest_start]
    after = sel[sel['start'] > backtest_end]
    passed_closest_idx = passed.index.values[-1]
    after_first_idx = after.index.values[0] if not after.empty else len(sel)

    # 选出的合约如果变非主力的日期和回测开始日期相比，只剩几天（不够初始化历史数据）应该排除。
    # 过滤天数：30天计算指标的历史数据 + 最少可交易7天（相当于1周交易天数）
    if passed.iloc[-1]['end'] - backtest_start < timedelta(days=37):
        passed_closest_idx += 1

    res_df = sel[passed_closest_idx: after_first_idx].copy()
    res_df.reset_index(inplace=True, drop=True)
    return res_df


def clear_open_trade_after_deadline(trades: List[TradeData], deadline: datetime) -> List[str]:
    to_pop_list = []
    ready = False
    for trade in trades:
        if trade.datetime > deadline:
            if not ready and trade.offset == Offset.OPEN:
                ready = True
            if ready:
                to_pop_list.append(trade.vt_orderid)
    return to_pop_list


def single_backtest(
    vt_symbol: str,
    start_date: datetime,
    end_date: datetime,
    strategy_class: type,
    is_last: bool = False
) -> Tuple[pd.DataFrame, pd.DataFrame, datetime]:
    """
    """
    real_end_date = end_date if is_last else end_date + timedelta(days=40)

    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval="1h",
        start=start_date,
        end=real_end_date,
        rate=0,
        slippage=0,
        size=10,
        pricetick=1,
        capital=100000,
    )
    engine.add_strategy(strategy_class, {})

    print(engine.vt_symbol, engine.start, engine.end, type(engine.start), type(engine.end))
    engine.load_data()
    engine.run_backtesting()

    # before calculate daily pnl, clear open trade after end date
    to_pop_list = clear_open_trade_after_deadline(engine.get_all_trades(), end_date)
    if to_pop_list:
        [engine.trades.pop(trade_id) for trade_id in to_pop_list]

    last_trade_dt = engine.get_all_trades()[-1].datetime
    print('last trade:', last_trade_dt)
    trade_df = vt_trade_to_df(engine.get_all_trades())

    # calculate daily pnl
    pnl_df = engine.calculate_result()

    # remove daily pnl after last trade if last trade happend after end date
    end_dt = last_trade_dt if last_trade_dt > end_date else end_date
    pnl_df = pnl_df[:end_dt.date()].copy()

    return pnl_df, trade_df, end_dt


def get_trading_date() -> pd.Series:
    df = pd.read_csv('trading_date.csv', usecols=[1], parse_dates=[0])
    return df['trading_day']


def get_pre_trading_date(dt: datetime, n: int) -> datetime:
    s = get_trading_date()
    return s[s <= dt].iloc[-n]

def get_output_path(filename: str, folder_name: Optional[str, None] = None):
    curr_dir = Path.cwd()
    folder = curr_dir.joinpath('result') if not folder_name else curr_dir.joinpath('result', folder_name)
    if not folder.exists():
        folder.mkdir()
    return curr_dir.joinpath(folder, filename)


def comodity_to_vt_symbol(commodity: str, data_mode: str) -> str:
    exchange = exchange_map[commodity.upper()]
    digit = '888' if data_mode == 'main' else '99'
    return f"{commodity.upper()}{digit}.{exchange}"


def continuous_backtest(
    commodity: str,
    data_mode: str,
    interval: str,
    strategy_name: str,
    strategy_params: dict,
    start: datetime,
    end: datetime,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """"""
    vt_symbol = comodity_to_vt_symbol(commodity, data_mode)
    f = lambda x: x.strftime("%Y%m%d")
    params_id = ''.join(list(map(str, strategy_params.values())))
    folder_name = f"{vt_symbol}_{interval}_{f(start)}{f(end)}_{strategy_name}_{params_id}"
    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=0,
        slippage=0,
        size=10,
        pricetick=1,
    )
    engine.add_strategy(strategy_dict[strategy_name], strategy_params)

    engine.load_data()
    engine.run_backtesting()

    # trade
    fname = f'{engine.vt_symbol}_trade_continuous.csv'
    trades = engine.get_all_trades()
    trade_df = vt_trade_to_df(trades)
    trade_df = trade_zh_to_en(trade_df)
    trade_df.to_csv(get_output_path(fname, folder_name))

    # pnl
    fname = f'{engine.vt_symbol}_pnl_continuous.csv'
    pnl_df = engine.calculate_result()
    pnl_df.to_csv(get_output_path(fname, folder_name))

    # result
    res_dict = engine.calculate_statistics()
    result_df = engine.daily_df
    return trade_df, pnl_df, result_df, res_dict