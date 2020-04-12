import pickle
from vnpy.app.cta_strategy.backtesting import BacktestingEngine, OptimizationSetting
from fixed_hedge_strategy import FixedHedgeStrategy
from datetime import datetime
from utility import dt_to_str

if __name__ == "__main__":
    start = datetime(2014, 1, 1)

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
    engine.add_strategy(FixedHedgeStrategy, {})

    setting = OptimizationSetting()
    setting.set_target("sharpe_ratio")
    setting.add_parameter("hedge_range", 0.01, 0.2, 0.01)
    setting.add_parameter("hedge_multiple", 0.5, 1, 0.5)
    setting.add_parameter("hedge_size", 10)

    results = engine.run_optimization(setting)

    start_str = dt_to_str(start)
    with open(f'result/result_{start_str}.dat', 'wb') as f:
        pickle.dump(results, f)