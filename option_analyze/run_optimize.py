import pandas as pd
from vnpy.app.cta_strategy.backtesting import BacktestingEngine, OptimizationSetting
from fixed_hedge_strategy import FixedHedgeStrategy
from datetime import datetime
from utility import dt_to_str
from pathlib import Path

if __name__ == "__main__":
    start = datetime(2019, 4, 1)
    test_strategy_cls = FixedHedgeStrategy

    engine = BacktestingEngine()
    engine.set_parameters(
        vt_symbol="510050.SSE",
        interval="1m",
        start=start,
        end=datetime(2020, 4, 1),
        rate=1/10000,
        slippage=0.002,
        size=10000,
        pricetick=0.001,
        capital=1_000_000,
    )
    engine.add_strategy(test_strategy_cls, {})

    setting = OptimizationSetting()
    setting.set_target("sharpe_ratio")
    setting.add_parameter("hedge_range_param", 10, 200, 10)
    setting.add_parameter("hedge_multiple_param", 40, 100, 20)
    setting.add_parameter("hedge_size", 10)

    results = engine.run_optimization(setting)

    start_str = dt_to_str(start)
    result_dict_list = []
    for (setting_str, _target, res_dict) in results:
        res_dict['setting'] = setting_str
        result_dict_list.append(res_dict)
    df = pd.DataFrame(result_dict_list)

    fp = Path.cwd().joinpath('result', f'{test_strategy_cls.nick_name}_{start_str}.csv')
    df.to_csv(fp, index=False)