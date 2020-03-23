import sys
import os
import numpy as np
from pathlib import Path
new_version_path = Path(os.getenv('VNPY2.0.8'))
sys.path.insert(0, str(new_version_path))

import multiprocessing
from vnpy.app.cta_strategy.backtesting import BacktestingEngine, OptimizationSetting

from research_backtest import batch_run


if __name__ == "__main__":
    strategy_name = 'double_ma_exit_atr_rein'
    empty_cost = False
    cost_multiple = 2.0
    interval = 'd'
    keep_last_open = True
    note_str = 'double_ma_exit_atr_rein_daily'

    commodity_list = [
        "cu", "al", "zn", "pb", "ni", "sn", "au", "ag", "rb", "hc", "bu", "ru", "sp",
        "m", "y", "a", "b", "p", "c", "cs", "jd", "l", "v", "pp", "j", "jm", "i",
        "SR", "CF", "ZC", "FG", "TA", "MA", "OI", "RM", "SF", "SM"
    ]
    
    # for test
    # commodity_list = ["cu", "al", "zn"]
    # commodity_list = ["sp"]

    turtle_gen = OptimizationSetting()
    turtle_gen.add_parameter("fast_window", 5)
    turtle_gen.add_parameter("slow_window", 50)
    turtle_gen.add_parameter("atr_multi", 1.0, 2.5, 0.5)
    turtle_gen.add_parameter("exit_atr_multi", 2, 4, 1)
    turtle_gen.add_parameter("max_rein", 1, 3, 1)


    # turtle_gen.add_parameter("entry_window", 5, 10, 5)
    # turtle_gen.add_parameter("exit_window", 20)
    # turtle_gen.add_parameter("sl_multiplier", 3.5)

    turtle_settings = turtle_gen.generate_setting()

    # load custom setting
    # df = pd.read_csv('custom_turtle_settings.csv')
    # series = dict(df.iterrows()).values()
    # turtle_settings = [dict(s) for s in series]

    # # 多线程回测
    pool = multiprocessing.Pool(multiprocessing.cpu_count())
    print("Multi process backtest started.")
    for setting_dict in turtle_settings:
        # print(setting_dict)
        pool.apply_async(batch_run, args=(commodity_list, strategy_name, setting_dict, note_str, empty_cost))
    pool.close()
    pool.join()

    print("=" * 60)
    print("All finished.")


    # 同步回测，可用于检测bug
    # for setting_dict in turtle_settings:
    #     batch_run(commodity_list, strategy_name, setting_dict,
    #               note_str, empty_cost, cost_multiple, interval, keep_last_open)
    #     # print(f"{params_to_str(setting_dict)} is finished.")

    # print("=" * 60)
    # print("All finished.")
