import pandas as pd
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from datetime import time as dt_time
from collections import defaultdict
from pathlib import Path, PurePath

from vnpy.trader.object import BarData, TradeData
from vnpy.trader.constant import Interval, Offset
from vnpy.trader.database import database_manager
from vnpy.trader.utility import extract_vt_symbol

from strategy.boll_channel_strategy import BollChannelStrategy
from strategy.turtle_signal_strategy import TurtleSignalStrategy
from backtesting import SegBacktestingEngine
from basic_data import future_basic_data, future_hot_start, dominant_data

DAY_START = dt_time(8)
DAY_END = dt_time(16)

NIGHT_A_START = dt_time(20)
NIGHT_A_END = dt_time(23, 59, 59)

NIGHT_B_START = dt_time(0)
NIGHT_B_END = dt_time(5)


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

compare_items = [
    'total_days',
    'profit_days',
    'max_ddpercent',
    'max_drawdown_duration',
    'total_return',
    'return_std',
    'daily_return',
    'sharpe_ratio',
    'return_drawdown_ratio'
]

# dominant_data = pd.read_csv('dominant_data.csv', parse_dates=[1, 2])
# future_basic_data = pd.read_csv('future_basic_data.csv', index_col=0)

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
    seg = dominant_data

    sel = seg[seg['underlying'] == underlying].copy()
    sel.reset_index(inplace=True, drop=True)
    passed = sel[sel['start'] < backtest_start]
    after = sel[sel['start'] > backtest_end]

    # 选出的合约如果变非主力的日期和回测开始日期相比，只剩几天（不够初始化历史数据）应该排除。
    # 过滤天数：20天计算指标的历史数据 + 最少可交易7天（相当于1周交易天数）
    after_first_idx = after.index.values[0] if not after.empty else len(sel)
    if not passed.empty:
        passed_closest_idx = passed.index.values[-1]
        if passed.iloc[-1]['end'] - backtest_start < timedelta(days=27):
            passed_closest_idx += 1
    else:
        passed_closest_idx = 0

    res_df = sel[passed_closest_idx: after_first_idx].copy()
    res_df.reset_index(inplace=True, drop=True)
    return res_df


def clear_open_trade_after_deadline(trades: List[TradeData], deadline: datetime) -> List[str]:
    over_deadline = False
    last_trade = None
    rm_start_idx = 0
    pop_list = []
    # print('new seg deadline', deadline)

    for idx, trade in enumerate(trades):
        # print(trade.datetime, trade.direction, trade.vt_symbol, trade.offset, trade.price, trade.volume)
        if trade.datetime > deadline:
            if not over_deadline:
                # if first trade after deadline is open. exit directly.
                if trade.offset == Offset.OPEN:
                    rm_start_idx = idx
                    break
                over_deadline = True
                last_trade = trade
            else:
                # next open trade and pre close is not in the same trading time
                if not is_same_trading_period(trade.datetime, last_trade.datetime) and trade.offset == Offset.OPEN:
                    rm_start_idx = idx
                    break
                else:
                    last_trade = trade
    if rm_start_idx:
        pop_list = [trade.vt_tradeid for trade in trades[rm_start_idx:]]
    return pop_list


def is_same_trading_period(new_time: datetime, old_time: datetime) -> bool:
    if DAY_START < old_time.time() < DAY_END:
        return new_time.date() == old_time.date() and new_time.time() < DAY_END
    elif NIGHT_A_START < old_time.time() < NIGHT_A_END:
        old_time_next_day = old_time + timedelta(1)
        same_a = new_time.date() == old_time.date() and NIGHT_A_START < new_time.time() <= NIGHT_A_END
        same_b = new_time.date() == old_time_next_day.date() and NIGHT_B_START <= new_time.time() < NIGHT_B_END
        return same_a or same_b
    else:
        return new_time.date() == old_time.date() and new_time.time() <= NIGHT_B_END


def process_last_trade_dt(trade_dt: datetime) -> datetime:
    if DAY_START < trade_dt.time() < DAY_END:
        trade_dt = trade_dt.replace(hour=16)
    elif NIGHT_B_START <= trade_dt.time() < NIGHT_B_END:
        trade_dt = trade_dt.replace(hour=8)
    else:
        trade_dt += timedelta(days=1)
        trade_dt = trade_dt.replace(hour=8)
    return trade_dt


def single_backtest(
    vt_symbol: str,
    interval: str,
    capital: int,
    start_date: datetime,
    end_date: datetime,
    real_start: datetime,
    strategy_class: type,
    strategy_params: dict,
    is_last: bool = False
) -> Tuple[pd.DataFrame, pd.DataFrame, datetime]:
    """"""
    commodity = strip_digt(vt_symbol)
    size = future_basic_data.loc[commodity]['size']
    pricetick = future_basic_data.loc[commodity]['pricetick']

    end_date = end_date.replace(hour=16)
    real_end_date = end_date if is_last else datetime.now()

    engine = SegBacktestingEngine()
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start_date,
        end=real_end_date,
        rate=0,
        slippage=0,
        size=size,
        pricetick=pricetick,
        capital=capital,
    )
    engine.add_strategy(strategy_class, strategy_params)

    # print(engine.vt_symbol, engine.start, engine.end, type(engine.start), type(engine.end))
    engine.load_data()
    engine.run_backtesting(real_start)

    # from copy import copy
    # copy_trades = copy(engine.get_all_trades())

    # before calculate daily pnl, clear open trade after end date
    pop_list = clear_open_trade_after_deadline(engine.get_all_trades(), end_date)
    if pop_list:
        [engine.trades.pop(trade_id) for trade_id in pop_list]

    # check trade result after pop upkeep trade
    if not engine.get_all_trades():
        print("单段回测没有成交结果！")
        # print(copy_trades)
        return

    last_trade_dt = engine.get_all_trades()[-1].datetime
    trade_df = vt_trade_to_df(engine.get_all_trades())

    # check the last trade closed excpet for the last seg contract
    if not is_last and trade_df.iloc[-1].offset != '平':
        print("单端回测合约到期前交易无法闭合")
        # print('None closed:', last_trade_dt, vt_symbol)
        # for trade in copy_trades:
        #     print(trade.datetime, trade.direction, trade.vt_symbol, trade.offset, trade.price, trade.volume)
        return

    # calculate daily pnl
    pnl_df = engine.calculate_result()

    # remove daily pnl after last trade if last trade happend after end date
    # print('last trade:', last_trade_dt, 'end_date:', end_date)
    # print('processed last trade:', process_last_trade_dt(last_trade_dt))
    end_dt = process_last_trade_dt(last_trade_dt) if last_trade_dt > end_date else end_date
    # print('new start:', end_dt)
    pnl_df = pnl_df[:end_dt.date()].copy()

    return pnl_df, trade_df, end_dt


def get_trading_date() -> pd.Series:
    df = pd.read_csv('source_data/trading_date.csv', usecols=[1], parse_dates=[0])
    return df['trading_day']


def get_pre_trading_date(dt: datetime, n: int) -> datetime:
    s = get_trading_date()
    return s[s <= dt].iloc[-n]


def get_output_path(filename: str, *folder_args, root_default='result') -> PurePath:
    folder = Path.cwd().joinpath(root_default, *folder_args)
    if not folder.exists():
        folder.mkdir(parents=True)
    return folder.joinpath(folder, filename)


def get_output_folder(*args, root_default='result') -> PurePath:
    folder = Path.cwd().joinpath(root_default, *args)
    if not folder.exists():
        folder.mkdir(parents=True)
    return folder


def comodity_to_vt_symbol(commodity: str, data_mode: str) -> str:
    exchange = future_basic_data.loc[commodity]['exchange']
    if exchange == 'SSE':
        return f"{commodity}.{exchange}"
    else:
        digit = '888' if data_mode == 'main' else '99'
        return f"{commodity.upper()}{digit}.{exchange}"


def merge_duplicate_date(df):
    """Groud process function"""
    if len(df) == 1:
        return df.iloc[-1:].copy()
    else:
        add_items = ['trade_count', 'turnover', 'commission', 'slippage', 'trading_pnl', 'holding_pnl', 'total_pnl', 'net_pnl']
        df2 = df.iloc[-1:].copy()
        last_index = df2.iloc[0].name
        df2.loc[last_index, 'start_pos'] = df.iloc[0]['start_pos']
        for item in add_items:
            df2.loc[last_index, item] = df[item].sum()
        return df2


def continuous_backtest(
    commodity: str,
    data_mode: str,
    interval: str,
    strategy_name: str,
    strategy_params: dict,
    capital: int,
    start: datetime,
    end: datetime,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """"""
    vt_symbol = comodity_to_vt_symbol(commodity, data_mode)
    # f = lambda x: x.strftime("%Y%m%d")
    # params_id = ''.join(list(map(str, strategy_params.values()))) if strategy_params else 'default'
    # folder_name = f"{commodity}_{interval}_{f(start)}{f(end)}_{strategy_name}_{params_id}"
    params_str = '.'.join([f"{k}_{v}" for k, v in strategy_params.items()]) if strategy_params else 'default'
    folder_name = f"{commodity}_{strategy_name}_{params_str}"

    size = future_basic_data.loc[commodity]['size']
    pricetick = future_basic_data.loc[commodity]['pricetick']

    engine = SegBacktestingEngine()
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=0,
        slippage=0,
        size=size,
        pricetick=pricetick,
        capital=capital
    )
    engine.add_strategy(strategy_dict[strategy_name], strategy_params)

    # run backtest
    engine.load_data()
    engine.run_backtesting()

    # save trade
    trades = engine.get_all_trades()
    trade_df = vt_trade_to_df(trades)
    trade_df = trade_zh_to_en(trade_df)
    trade_df.to_csv(get_output_path('trade_continuous.csv', folder_name))

    # save pnl
    pnl_df = engine.calculate_result()
    pnl_df.to_csv(get_output_path('pnl_continuous.csv', folder_name))

    # result
    res_dict = engine.calculate_statistics()
    res_df = engine.daily_df
    res_df.to_csv(get_output_path('source_res_continuous.csv', folder_name))
    pd.DataFrame([res_dict]).to_csv(get_output_path('result_continuous.csv', folder_name))
    return trade_df, pnl_df, res_df, res_dict


def segment_backtest(
    commodity: str,
    interval: str,
    strategy_name: str,
    strategy_params: dict,
    capital: int,
    backtest_start: datetime,
    backtest_end: datetime,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """"""
    f = lambda x: x.strftime("%Y%m%d")
    # params_id = ''.join(list(map(str, strategy_params.values()))) if strategy_params else 'default'
    # folder_name = f"{commodity}_{interval}_{f(backtest_start)}{f(backtest_end)}_{strategy_name}_{params_id}"
    params_str = '.'.join([f"{k}_{v}" for k, v in strategy_params.items()]) if strategy_name else 'default'
    folder_name = f"{commodity}_{strategy_name}_{params_str}"

    dom_df = get_dominant_in_periods(commodity, backtest_start, backtest_end)
    # print(dom_df)
    start = backtest_start
    real_next_start = None
    pnl_dfs = []
    trade_dfs = []
    for (idx, row) in dom_df.iterrows():
        # even become sub-main, but if open trade exists, it must continute until no position.
        is_last = False
        end = row['end'].to_pydatetime()
        vt_symbol = row['vt_symbol']
        
        if idx == len(dom_df) - 1:
            end = backtest_end
            is_last = True
            
        # run backtest function
        # the open trade after sub-main day must be deleted.
        res_tuple = single_backtest(vt_symbol, interval, capital, start, end, real_next_start, strategy_dict[strategy_name], strategy_params, is_last)
        if res_tuple:
            df_pnl, df_trade, prev_end_dt = res_tuple
            pnl_dfs.append(df_pnl)
            trade_dfs.append(df_trade)

            # backward n trading days to init history data
            start = get_pre_trading_date(prev_end_dt, 20).to_pydatetime()
            real_next_start = prev_end_dt
            
            # save seg backtest result to verify
            fname = f"pnl_{vt_symbol}-{f(start)}-{f(end)}.csv"
            df_pnl.to_csv(get_output_path(fname, folder_name, 'sub_result'))
        else:
            print(f"策略：{folder_name}无法进行分段回测！")
            return
        
    all_pnl_df = pd.concat(pnl_dfs)
    all_pnl_df = all_pnl_df.groupby(all_pnl_df.index, group_keys=False).apply(merge_duplicate_date)

    all_trade_df = pd.concat(trade_dfs)
    all_trade_df = trade_zh_to_en(all_trade_df)

    all_pnl_df.to_csv(get_output_path('pnl_seg.csv', folder_name))
    all_trade_df.to_csv(get_output_path('trade_seg.csv', folder_name))

    engine = SegBacktestingEngine()
    engine.capital = capital
    res_df = all_pnl_df.copy()
    res_dict = engine.calculate_statistics(df=res_df)
    res_df.to_csv(get_output_path('source_res_seg.csv', folder_name))
    pd.DataFrame([res_dict]).to_csv(get_output_path('result_seg.csv', folder_name))

    return all_trade_df, all_pnl_df, res_df, res_dict


def compare(folder: PurePath) -> dict:
    """"""
    trade_kwargs = {'index_col': 0, 'parse_dates': True}
    pnl_kwargs = {'index_col': 0, 'parse_dates': True, 'usecols': [0, 1, 2, 4, 5, 6, 10, 11, 12, 13]}
    result_kwargs = {'index_col': 0}

    trade_cont = pd.read_csv(folder.joinpath('trade_continuous.csv'), **trade_kwargs)
    trade_seg = pd.read_csv(folder.joinpath('trade_seg.csv'), **trade_kwargs)
    pnl_cont = pd.read_csv(folder.joinpath('pnl_continuous.csv'), **pnl_kwargs)
    pnl_seg = pd.read_csv(folder.joinpath('pnl_seg.csv'), **pnl_kwargs)

    res_cont = pd.read_csv(folder.joinpath('result_continuous.csv'), **result_kwargs)
    res_seg = pd.read_csv(folder.joinpath('result_seg.csv'), **result_kwargs)
    res_cont = res_cont[compare_items]
    res_seg = res_seg[compare_items]

    trade_comp = trade_cont.merge(trade_seg, left_index=True, right_index=True, how='outer', suffixes=('_cont','_seg'))
    pnl_comp = pnl_cont.merge(pnl_seg, left_index=True, right_index=True, how='outer', suffixes=('_cont','_seg'))
    res_comp = res_cont.merge(res_seg, left_index=True, right_index=True, how='outer', suffixes=('_cont','_seg'))

    # trade differences
    df = trade_comp[trade_comp.isnull().T.any()]
    trade_diff_percent = len(df[df['direction_cont'].notnull()]) / len(trade_seg)

    # pnl differences
    df = pnl_comp[pnl_comp['net_pnl_cont'] != pnl_comp['net_pnl_seg']]
    pnl_diff_percent = len(df) / len(pnl_seg)

    res_dict = res_comp.iloc[0].to_dict()
    res_dict['trade_diff_percent'] = trade_diff_percent
    res_dict['pnl_diff_percent'] = pnl_diff_percent

    return res_dict


def merge_result(
    commodity: str,
    interval: str,
    strategy_name: str,
    strategy_params: dict,
    start: datetime,
    end: datetime,
    capital: Optional[int]=None,
    data_mode: str = 'main'
):
    if capital is None:
        capital = future_basic_data.loc[commodity]['backtest_capital']
    params_str = '.'.join([f"{k}_{v}" for k, v in strategy_params.items()]) if strategy_name else 'default'
    name = f"{commodity}.{strategy_name}.{params_str}"
    res_cont_tuple = continuous_backtest(commodity, data_mode, interval, strategy_name, strategy_params, capital, start, end)
    res_seg_tuple = segment_backtest(commodity, interval, strategy_name, strategy_params, capital, start, end)
    if not res_seg_tuple:
        return
    
    res_cont = res_cont_tuple[3]
    res_seg = res_seg_tuple[3]
    # print(res_seg)
    cont_new = {key + '_cnt': value for key, value in res_cont.items()}
    seg_new = {key + '_seg': value for key, value in res_seg.items()}
    cont_new.update(seg_new)
    cont_new['name'] = name
    print(f"Name:{name} Parms:{strategy_params}finised")
    return cont_new