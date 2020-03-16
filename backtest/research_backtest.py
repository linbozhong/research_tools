# 用于多进程，jupyter notebook在win环境下无法运行多进程
import sys
import os
import numpy as np
from pathlib import Path
new_version_path = Path(os.getenv('VNPY2.0.8'))
sys.path.insert(0, str(new_version_path))

import multiprocessing
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Optional, List
from itertools import product
from multiprocessing import Pool

from vnpy.app.cta_strategy.backtesting import BacktestingEngine, OptimizationSetting
from vnpy.trader.constant import Offset

from utility import comodity_to_vt_symbol, get_output_path, vt_trade_to_df, trade_zh_to_en, get_output_folder, load_data
from backtesting import ResearchBacktestingEngine
from trade_match import calculate_trades_result, generate_trade_df, exhaust_trade_result

from strategy.turtle_b_strategy import TurtleBStrategy
from strategy.turtle_c_strategy import TurtleCStrategy
from strategy.turtle_d_strategy import TurtleDStrategy
from strategy.turtle_e_strategy import TurtleEStrategy

from strategy.turtle_rsi_strategy import TurtleRsiFilterStrategy
from strategy.turtle_fluid_strategy import TurtleFluidSizeStrategy

from strategy.boll_channel_strategy import BollChannelStrategy
from strategy.boll_ma_strategy import BollMaStrategy
from strategy.boll_ma_rsi_strategy import BollMaRsiStrategy
from strategy.boll_ma_fluid_strategy import BollFluidStrategy

from strategy.double_ma_strategy import DoubleMaStrategy
from strategy.double_ma_rsi_strategy import DoubleMaRsiStrategy
from strategy.double_ma_std_strategy import DoubleMaStdStrategy
from strategy.double_ma_atr_strategy import DoubleMaAtrStrategy
from strategy.double_ma_atr_b_strategy import DoubleMaAtrBStrategy

import vnpy
print(vnpy.__version__)

future_basic_data = pd.read_csv('future_basic_data.csv', index_col=0)
future_hot_start = pd.read_csv('future_hot_start.csv', index_col=0,  header=None, names=['hot_start'])

strategy_class_map = {
    'turtle': TurtleBStrategy,
    'turtle_inverse_trade': TurtleCStrategy,
    'turtle_exit_ma': TurtleDStrategy,
    'turtle_entry_following_stop': TurtleEStrategy,
    'turtle_rsi_filter': TurtleRsiFilterStrategy,
    'turtle_fluid_size': TurtleFluidSizeStrategy,
    'boll': BollChannelStrategy,
    'boll_exit_ma': BollMaStrategy,
    'boll_ma_rsi': BollMaRsiStrategy,
    'boll_fluid': BollFluidStrategy,
    'double_ma': DoubleMaStrategy,
    'double_ma_rsi': DoubleMaRsiStrategy,
    'double_ma_std': DoubleMaStdStrategy,
    'double_ma_atr': DoubleMaAtrStrategy,
    'double_ma_atr_plus_ma': DoubleMaAtrBStrategy
}


def get_hot_start(commodity: str) -> datetime:
    start = future_hot_start.loc[commodity.upper()]['hot_start']
    start = datetime.strptime(start, '%Y-%m-%d')
    if not pd.isna(start):
        return start


def get_future_trade_date_index(start: datetime, end: datetime) -> np.ndarray:
    """
    返回用于对比所有期货品种的标准化时间序列
    各品种夜盘时间不固定（有的无夜盘），在计算每日盈亏的时候就会出现时间线不齐的情况，此处以au为标准。
    """
    df = load_data('AU888.SHFE', '1h', start, end, )
    df['date'] = df.index.map(lambda dt: dt.date())
    return df['date'].drop_duplicates().values


def params_to_str(params: dict, sep: str = '.') -> str:
    if params:
        for v in params.values():
            if isinstance(v, float):
                sep = '-'
        return sep.join([f"{k}_{v}" for k, v in params.items()])
    else:
        return 'default'


def str_to_params(params_str: str, sep: str = '.') -> dict:
    """
    eg. exit_window_10.stop_multiple_1
    """
    if params_str == 'default':
        return {'params': params_str}
    else:
        d = {}
        params_list = params_str.split(sep)
        for param in params_list:
            sub_param_list = param.split('_')
            key = '_'.join(sub_param_list[0: -1])
            value = sub_param_list[-1]
            d[key] = float(value)
        return d


def run_backtest_for_portfolio(
    strategy_name: str,
    setting: dict,
    commodity: str,
    interval: str,
    start: datetime,
    end: datetime,
    capital: float,
    empty_cost: bool = False,
    cost_multiple: float = 1.0,
    hot_start: bool = True
) -> pd.DataFrame:
    """"""
    vt_symbol = comodity_to_vt_symbol(commodity, 'main')
    size = future_basic_data.loc[commodity]['size']
    pricetick = future_basic_data.loc[commodity]['pricetick']

    com_slip_ratio = future_basic_data.loc[commodity]['com_slip_ratio']
    slippage = pricetick * cost_multiple + (pricetick * com_slip_ratio)
    if empty_cost:
        slippage = 0
    rate = 0

    if hot_start:
        hot_start = get_hot_start(commodity)
        start = hot_start if hot_start >= start else start

    setting.update({'symbol_size': size, 'risk_capital': capital})

    engine = ResearchBacktestingEngine()
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=rate,
        slippage=slippage,
        size=size,
        pricetick=pricetick,
        capital=capital    
    )

    strategy_class = strategy_class_map[strategy_name]
    engine.add_strategy(strategy_class, setting)
    engine.load_data()
    engine.run_backtesting()
    df = engine.calculate_result()

    if df is None:
        return

    df = df.drop(['close_price', 'pre_close', 'trades', 'start_pos', 'end_pos'], axis=1)
    print(f'{commodity}-{strategy_name}-backtest finished.')
    return df


def run_portfolio(
    commodity_list: List[str],
    strategy_name: str,
    setting: dict,
    start: datetime,
    end: datetime,
    capital: float,
    note_str: str = 'default',
    empty_cost: bool = False,
    cost_multiple: float = 1.0,
    interval: str = '1h'
    ):
    """"""
    normal_date_seq = get_future_trade_date_index(start, end)

    print(f'Strategy:{strategy_name} portfolio backtest started.')
    first_flag = True
    df_sum = None
    for commodity in commodity_list:
        res = run_backtest_for_portfolio(strategy_name, setting, commodity, interval, start, end, capital, empty_cost, cost_multiple)
        if res is not None:
            res = res.reindex(normal_date_seq, fill_value=0)
        else:
            print(f"{commodity}没有回测结果")
            continue

        res.to_csv(get_output_path(f"{commodity}.csv", 'portfolio', f'{strategy_name}-{note_str}', 'sub_result'))
        if first_flag:
            df_sum = res
            first_flag = False
        else:
            df_sum += res
    # df_sum.dropna(inplace=True)

    params = params_to_str(setting)
    file_name = f'{strategy_name}@{params}@{note_str}.csv'
    df_sum.to_csv(get_output_path(file_name, 'portfolio', f'{strategy_name}-{note_str}'))

    print(f'Strategy:{strategy_name} portfolio backtest finished.')

    return df_sum


def run_research_backtest(
    commodity: str,
    start: datetime,
    end: datetime,
    strategy_name: Optional[str] = None,
    strategy_params: Optional[dict] = None,
    custom_note: str = 'default',
    empty_cost: bool = False,
    cost_multiple: float = 1.0, 
    trade_output: bool = False,
    curve_output: bool = False,
    capital: Optional[float] = None, 
    interval: str = '1h',
    keep_last_open = False
) -> dict:
    """Run single commodity backtest"""
    # interval = '1h'
    vt_symbol = comodity_to_vt_symbol(commodity, 'main')
    size = future_basic_data.loc[commodity]['size']
    pricetick = future_basic_data.loc[commodity]['pricetick']
    com_slip_ratio = future_basic_data.loc[commodity]['com_slip_ratio']

    if not strategy_name:
        strategy_name = 'turtle'
        strategy_class = TurtleBStrategy
    else:
        strategy_class = strategy_class_map[strategy_name]

    if strategy_params is None:
        strategy_params = {}
    strategy_params.update({'symbol_size': size})
    params_str = params_to_str(strategy_params)

    if not capital:
        capital = future_basic_data.loc[commodity]['backtest_capital'] * 2

    slippage = pricetick * cost_multiple + (pricetick * com_slip_ratio)
    if empty_cost:
        slippage = 0
    rate = 0
    
    engine = ResearchBacktestingEngine()
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=rate,
        slippage=slippage,
        size=size,
        pricetick=pricetick,
        capital=capital
    )
    engine.add_strategy(strategy_class, strategy_params)

    # run backtest
    engine.load_data()
    engine.run_backtesting()

    trades = engine.get_all_trades()
    if not trades:
        print(f"{strategy_name}.{commodity}.{params_str}.{custom_note}-无任何成交")
        return
        

    if not keep_last_open:
        last_trade = trades[-1]
        if last_trade.offset == Offset.OPEN:
            engine.trades.pop(last_trade.vt_tradeid)

    if trade_output:
        fn = f'{strategy_name}.{commodity}.{params_str}.{custom_note}.trades.csv'
        trade_df = vt_trade_to_df(engine.get_all_trades())
        trade_df = trade_zh_to_en(trade_df)
        trade_df.to_csv(get_output_path(fn, 'trades'))

    engine.calculate_result()
    day_res = engine.calculate_statistics()
    
    if curve_output:
        img_name = f'{strategy_name}.{commodity}.{params_str}.{custom_note}.pnl-curve.jpg'
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(1, 1, 1)
        ax.set_title(f'{commodity}-{params_str}-{custom_note} Balance Curve')
        engine.daily_df['balance'].plot(legend=True, ax=ax)
        fig.savefig(get_output_path(img_name, 'pnl_curves'))

    trades = engine.trades
    try:
        trade_res = exhaust_trade_result(trades, size, rate, slippage, capital, show_long_short_condition=False)
    except:
        trade_df = vt_trade_to_df(engine.get_all_trades())
        print(f"{strategy_name}.{commodity}.{params_str}.{custom_note}-回测异常")
        print(trade_df)
        return
        
    d = {
        'commodity': commodity,
        'start_date': day_res['start_date'],
        'end_date': day_res['end_date'],
        'capital': day_res['capital'],
        'day_end_balance': day_res['end_balance'],
        'trade_end_balance': trade_res['end_balance'],
        'day_max_drawdown': day_res['max_drawdown'],
        'trade_max_drawdown': trade_res['max_drawdown'],
        'day_max_ddpercent': day_res['max_ddpercent'],
        'trade_max_ddpercent': trade_res['max_ddpercent'],
        'net_pnl': day_res['total_net_pnl'],
        'commission': day_res['total_commission'],
        'slippage': day_res['total_slippage'],
        'total_return': day_res['total_return'],
        'annual_return': day_res['annual_return'],
        'sharpe_ratio': day_res['sharpe_ratio'],
        'return_drawdown_ratio': day_res['return_drawdown_ratio'],
        'trade_count': trade_res['trade_count'],
        'daily_trade_count': day_res['daily_trade_count'],
        'winning_rate': trade_res['winning_rate'],
        'win_loss_pnl_ratio': trade_res['win_loss_pnl_ratio'],
        'pos_duration': trade_res['pos_duration']
    }
    
    print(f"{strategy_name}.{commodity}.{params_str}.{custom_note}-回测完成")
    return d


def batch_run(
    commodity_list: list,
    strategy_name: str,
    params: dict,
    note_str: str = 'default',
    empty_cost: bool = False,
    cost_multiple: float = 2.0,
    interval = 'd',
    keep_last_open = True
    ):
    """Run all commodities of portfolio"""
    res_list = []
    columns = []

    print(f'Strategy:{strategy_name} multi backtest started.')
    for commodity in commodity_list:
        start = get_hot_start(commodity)
        end = datetime.now()

        res = run_research_backtest(
            commodity, start, end, strategy_name, params, note_str, empty_cost,
            cost_multiple=cost_multiple,
            interval=interval,
            keep_last_open=keep_last_open)
        if res:
            res_list.append(res)
            columns = list(res.keys())

    params = params_to_str(params)
    file_name = f'{strategy_name}@{params}@{note_str}.csv'
    df = pd.DataFrame(res_list, columns=columns)
    df.to_csv(get_output_path(file_name, 'multi_backtest', note_str), index=False)


def analyze_multi_bt(filename: str, note: str = 'default') -> dict:
    test_name = filename.replace('.csv', '')
    
    folder = 'multi_backtest'
    if note == 'default':
        file_path = get_output_path(filename, folder)
    else:
        file_path = get_output_path(filename, folder, note)

    df = pd.read_csv(file_path)

    balance_diff = df['day_end_balance'].map(lambda x: round(x)) - df['trade_end_balance'].map(lambda x: round(x))
    balance_not_same = np.abs(balance_diff) > 10
    if sum(balance_not_same) > 0:
        print(sum(balance_not_same))
        print(f"{test_name} Trade end balance is not same with Day end balance")
        # print(df[balance_not_same])

    balance_negitive = df['day_end_balance'] < 0
    neg_num = sum(balance_negitive)
    # print('neg number:', neg_num)
    if neg_num > 0:
        print(f"{test_name} End balance is negitive")

    # stats_items = ['day_max_ddpercent', 'total_return', 'annual_return', 'sharpe_ratio', 'return_drawdown_ratio',
    #                'trade_count', 'winning_rate', 'win_loss_pnl_ratio']
#     df[stats_items].describe()

    res_dict = {}
    res_dict['test_name'] = test_name
    res_dict['all_invest'] = df['trade_count'].sum()
    res_dict['daily_trade'] = df['daily_trade_count'].sum()
    res_dict['win'] = sum(df['annual_return'] > 0)
    res_dict['loss'] = sum(df['annual_return'] <= 0)
    res_dict['win_rate'] = res_dict['win'] / len(df)
    res_dict['annual_mean'] = df['annual_return'].mean()
    res_dict['max_dd'] = df['day_max_ddpercent'].mean()
    res_dict['best_rtn'] = df['total_return'].max()
    res_dict['worst_rtn'] = df['total_return'].min()
    res_dict['best_ddp'] = df['day_max_ddpercent'].max()
    res_dict['worst_ddp'] = df['day_max_ddpercent'].min()
    res_dict['sharpe_mean'] = df['sharpe_ratio'].mean()
    res_dict['win_mean'] = df['winning_rate'].mean()
    res_dict['win_to_loss'] = df['win_loss_pnl_ratio'].mean()
    res_dict['cost_ratio'] = df['slippage'].sum() / abs(df['net_pnl'].sum())
    res_dict['pos_duration'] = df['pos_duration'].mean()
    
    return res_dict