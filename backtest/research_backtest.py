# 用于多进程，jupyter notebook在win环境下无法运行多进程
import sys
import os
from pathlib import Path
new_version_path = Path(os.getenv('VNPY2.0.8'))
sys.path.insert(0, str(new_version_path))

import multiprocessing
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from typing import Optional
from itertools import product
from multiprocessing import Pool

from vnpy.app.cta_strategy.backtesting import BacktestingEngine, OptimizationSetting
from vnpy.trader.constant import Offset

from utility import comodity_to_vt_symbol, get_output_path, vt_trade_to_df, trade_zh_to_en, get_output_folder
from backtesting import ResearchBacktestingEngine
from trade_match import calculate_trades_result, generate_trade_df, exhaust_trade_result
from turtle_b_strategy import TurtleBStrategy

import vnpy
print(vnpy.__version__)

future_basic_data = pd.read_csv('future_basic_data.csv', index_col=0)
future_hot_start = pd.read_csv('future_hot_start.csv', index_col=0,  header=None, names=['hot_start'])

def get_hot_start(commodity: str) -> datetime:
    start = future_hot_start.loc[commodity.upper()]['hot_start']
    start = datetime.strptime(start, '%Y-%m-%d')
    if not pd.isna(start):
        return start
    
def params_to_str(params: dict) -> str:
    if params:
        return '.'.join([f"{k}_{v}" for k, v in params.items()])
    else:
        return 'default'

def str_to_params(params_str: str) -> dict:
    """
    eg. exit_window_10.stop_multiple_1
    """
    if params_str == 'default':
        return {'params': params_str}
    else:
        d = {}
        params_list = params_str.split('.')
        for param in params_list:
            sub_param_list = param.split('_')
            key = '_'.join(sub_param_list[0: -1])
            value = sub_param_list[-1]
            d[key] = float(value)
        return d

def run_research_backtest(
    commodity: str,
    start: datetime,
    end: datetime,
    trade_output = False,
    curve_output = False,
    strategy_params: Optional[dict] = None,
    custom_note: str = 'default'
) -> dict:
    """Run single commodity backtest"""
    params_str = params_to_str(strategy_params)
    # print('run research backtest', params_str)
    interval = '1h'
    strategy_name = 'turtle'
    if strategy_params is None:
        strategy_params = {}
    rate = 0

    vt_symbol = comodity_to_vt_symbol(commodity, 'main')
    size = future_basic_data.loc[commodity]['size']
    pricetick = future_basic_data.loc[commodity]['pricetick']
    capital = future_basic_data.loc[commodity]['backtest_capital'] * 2
    
    engine = ResearchBacktestingEngine()
    engine.set_parameters(
        vt_symbol=vt_symbol,
        interval=interval,
        start=start,
        end=end,
        rate=rate,
        slippage=pricetick,
        size=size,
        pricetick=pricetick,
        capital=capital
    )
    engine.add_strategy(TurtleBStrategy, strategy_params)

    # run backtest
    engine.load_data()
    engine.run_backtesting()

    trades = engine.get_all_trades()
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
        fig = plt.figure(figsize=(16, 10))
        ax = fig.add_subplot(1, 1, 1)
        ax.set_title(f'{commodity}-{params_str}-{custom_note} Balance Curve')
        engine.daily_df['balance'].plot(legend=True, ax=ax)
        fig.savefig(get_output_path(img_name, 'pnl_curves'))

    trades = engine.trades
    trade_res = exhaust_trade_result(trades, size, rate, pricetick, capital, show_long_short_condition=False)

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
        'win_loss_pnl_ratio': trade_res['win_loss_pnl_ratio']
    }
    
    print(f"{strategy_name}.{commodity}.{params_str}-回测完成")
    return d

def batch_run(strategy_name: str, params: dict, note_str: str = 'default'):
    """Run all commodities of portfolio"""
    # commodities = [
    #     "cu", "al", "zn"
    # ]

    commodities = [
        "cu", "al", "zn", "pb", "ni", "sn", "au", "ag", "rb", "hc", "bu", "ru", "sp",
        "m", "y", "a", "b", "p", "c", "cs", "jd", "l", "v", "pp", "j", "jm", "i",
        "SR", "CF", "ZC", "FG", "TA", "MA", "OI", "RM", "SF", "SM"
    ]
    
    res_list = []
    columns = []

    # print('batch run', params)
    for commodity in commodities:
        start = get_hot_start(commodity)
        end = datetime(2019, 12, 1)

        res = run_research_backtest(commodity, start, end, strategy_params=params)
        res_list.append(res)
        columns = list(res.keys())

    params = params_to_str(params)
    file_name = f'{strategy_name}@{params}@{note_str}.csv'
    df = pd.DataFrame(res_list, columns=columns)
    df.to_csv(get_output_path(file_name, 'multi_backtest'), index=False)

def analyze_multi_bt(filename: str) -> dict:
    test_name = filename.rstrip('.csv')
    
    folder = 'multi_backtest'
    file_path = get_output_path(filename, folder)
    df = pd.read_csv(file_path)

    balance_not_same = df['day_end_balance'].map(lambda x: round(x)) != df['trade_end_balance'].map(lambda x: round(x))
    if len(df[balance_not_same]) > 0:
        print("Trade end balance is not same with Day end balance")
        print(df[balance_not_same])

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
    
    return res_dict

if __name__ == "__main__":
    strategy_name = 'turtle'
    note_str = 'atr_stop'

    turtle_gen = OptimizationSetting()
    turtle_gen.add_parameter("exit_window", 5, 50, 5)
    turtle_gen.add_parameter("stop_multiple", 7)
    turtle_settings = turtle_gen.generate_setting()

    # print(turtle_settings)
    # while 1:
    #     pass

    # 多线程回测
    pool = multiprocessing.Pool(multiprocessing.cpu_count())
    print("Multi process backtest started.")
    for setting_dict in turtle_settings:
        # print(setting_dict)
        pool.apply_async(batch_run, args=(strategy_name, setting_dict, note_str))
    pool.close()
    pool.join()

    print("=" * 60)
    print("All finished.")


    # 同步回测
    # turtle_gen = OptimizationSetting()
    # turtle_gen.add_parameter("exit_window", 15, 20, 5)
    # turtle_gen.add_parameter("stop_multiple", 2, 4, 1)
    # turtle_settings = turtle_gen.generate_setting()

    # strategy_name = 'turtle'
    # for setting_dict in turtle_settings:
    #     batch_run(strategy_name, setting_dict)
    #     print(f"{params_to_str(setting_dict)} is finished.")

    # print("=" * 60)
    # print("All finished.")