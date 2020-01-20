from datetime import datetime
from vnpy.app.cta_strategy.backtesting import BacktestingEngine
from vnpy.app.cta_strategy.base import BacktestingMode

class SegBacktestingEngine(BacktestingEngine):
    def __init__(self):
        super().__init__()
        self.is_output = False

    def run_backtesting(self, real_start=None):
        """"""
        if self.mode == BacktestingMode.BAR:
            func = self.new_bar
        else:
            func = self.new_tick

        self.strategy.on_init()

        # Use the first [days] of history data for initializing strategy
        day_count = 0
        ix = 0
        for ix, data in enumerate(self.history_data):
            if not real_start:
                if self.datetime and data.datetime.day != self.datetime.day:
                    day_count += 1
                    if day_count >= self.days:
                        break
            else:
                if data.datetime >= real_start:
                    # print('backtest expected start', real_start)
                    # print('backtest break', data.datetime)
                    break

            self.datetime = data.datetime
            self.callback(data)

        self.strategy.inited = True
        self.output("策略初始化完成")

        self.strategy.on_start()
        self.strategy.trading = True
        self.output("开始回放历史数据")

        # Use the rest of history data for running backtesting
        print('backtest real start:', self.history_data[ix].datetime)
        for data in self.history_data[ix:]:
            func(data)

        self.output("历史数据回放结束")

    def output(self, msg):
        """
        Output message of backtesting engine.
        """
        if self.is_output:
            print(f"{datetime.now()}\t{msg}")