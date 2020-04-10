import tushare as ts
import numpy as np
from datetime import datetime

from utility import dt_to_str

class OptionBacktest():
    def __init__(self, symbol='510050', start='2005-02-23', end=None):
        self.symbol = symbol
        self.start = start
        if end is None:
            self.end = dt_to_str(datetime.now())
        self.data = None

        self.init_size = 10
        self.open_array = []
        self.close_array = []

        self.trade_count = 0
        self.trades = []

        self.base_price = 0.0
        self.entry_range = 0.05

        self.hedge_range = 0.1
        self.hedge_value = 0.05

        self.hedge_long_count = 0
        self.hedge_short_count = 0

        self.parameters = ['hedge_range', 'hedge_value']

        self.is_log = False

    def log(self, *arg, **kwargs):
        if self.is_log:
            print(*arg, **kwargs)

    def set_parameters(self, setting: dict):
        for name in self.parameters:
            if name in setting:
                setattr(self, name, setting[name])

    def load_data(self):
        self.data = ts.get_k_data(self.symbol, start=self.start, end=self.end)
    
    def trade(self, date, offset, price):
        self.trade_count += 1
        trade_id = f"backtest.{self.trade_count}"
        trade = (date, offset, price, trade_id)
        self.log(trade)
        self.trades.append(trade)

    def stats_result(self):
        hedge_count = (len(self.trades) - 1) / 2
        hedge_loss = self.hedge_value * hedge_count
        print(f"开始:{self.start} 结束:{self.end} 对冲阈值:{self.hedge_range} 对冲幅度:{self.hedge_value} 对冲次数:{hedge_count} 已对冲累计:{hedge_loss}")

    def run_backtest(self):
        for _idx, bar in self.data.iterrows():
            self.log(bar.date, bar.open, bar.high, bar.low, bar.close)
            self.open_array.append(bar.open)
            self.close_array.append(bar.close)

            if len(self.open_array) < 10:
                continue

            if not self.base_price:
                open_ma = np.mean(self.open_array[-3:])
                self.log('open_ma:', open_ma)
                if open_ma - bar.open > self.entry_range:
                    self.base_price = round(bar.open + self.entry_range, 2)
                elif bar.open - open_ma > self.entry_range:
                    self.base_price = round(bar.open - self.entry_range, 2)
                else:
                    self.base_price = round(open_ma, 2)

                self.trade(bar.date, 'entry', self.base_price)

            if self.base_price:
                # 因为有些交易日涨跌幅特别大或大幅度跳开，可能需要多次对冲，需要循环检查
                while True:                
                    long_hedge = (bar.high - self.base_price) > self.hedge_range
                    short_hedge = (self.base_price - bar.low) > self.hedge_range

                    # 防止无限循环调用
                    if self.hedge_long_count >= 2:
                        short_hedge = False
                    if self.hedge_short_count >= 2:
                        long_hedge = False

                    if long_hedge:
                        self.log('long-hedge:', 'high:', bar.high, 'target_high:', self.base_price + self.hedge_range)
                        self.base_price = self.base_price + self.hedge_value
                        self.hedge_long_count += 1
                    elif short_hedge:
                        self.log('short_hedge:', 'low:', bar.low, 'target_low:', self.base_price - self.hedge_range)
                        self.base_price = self.base_price - self.hedge_value
                        self.hedge_short_count += 1
                    else:
                        self.hedge_long_count = 0
                        self.hedge_short_count = 0
                        break


                    self.trade(bar.date, 'exit', self.base_price)
                    self.trade(bar.date, 'entry', self.base_price)


