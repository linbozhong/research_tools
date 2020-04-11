import tushare as ts
import numpy as np
from datetime import datetime
from vnpy.trader.utility import ArrayManager

from utility import dt_to_str

OHLC_TO_VNPYOHLC = {
    'open': 'open_price',
    'high': 'high_price',
    'low': 'low_price',
    'close': 'close_price',
}

class OptionBacktest():
    def __init__(self, symbol='510050', start='2005-02-23', end=None):
        self.symbol = symbol
        self.start = start
        if end is None:
            self.end = dt_to_str(datetime.now())
        self.data = None

        self.am = ArrayManager(size=60)

        self.trade_count = 0
        self.trades = []

        self.base_price = 0.0
        self.entry_range = 0.05

        self.hedge_range = 0.1
        self.hedge_value = 0.05

        self.parameters = []

        self.is_log = False

    def log(self, *arg, **kwargs):
        if self.is_log:
            print(*arg, **kwargs)

    def set_parameters(self, setting: dict):
        for name in self.parameters:
            if name in setting:
                setattr(self, name, setting[name])

    def load_data(self):
        df = ts.get_k_data(self.symbol, start=self.start, end=self.end)
        df.rename(columns=OHLC_TO_VNPYOHLC, inplace=True)
        self.data = df
    
    def trade(self, date, offset, price):
        self.trade_count += 1
        trade_id = f"backtest.{self.trade_count}"
        trade = (date, offset, price, trade_id)
        self.log(trade)
        self.trades.append(trade)

    def stats_result(self):
        hedge_count = (len(self.trades) - 1) / 2
        hedge_loss = self.hedge_value * hedge_count
        hedge_cost = hedge_count * 0.01
        print(f"开始:{self.start} 结束:{self.end} 对冲阈值:{self.hedge_range} 对冲幅度:{self.hedge_value} 对冲次数:{hedge_count} 对冲成本:{hedge_cost} 已对冲:{hedge_loss} 总成本:{hedge_cost + hedge_loss}")

    def on_bar(self, bar):
        pass

    def run_backtest(self):
        self.load_data()
        for _idx, bar in self.data.iterrows():
            self.on_bar(bar)
        self.stats_result()


class FixedHedge(OptionBacktest):
    def __init__(self, start):
        super().__init__(start=start)
        self.hedge_range = 0.1
        self.hedge_value = 0.05
        self.hedge_long_count = 0
        self.hedge_short_count = 0

        self.parameters = ['hedge_range', 'hedge_value']

    def on_bar(self, bar):
        self.log(bar.date, bar.open_price, bar.high_price, bar.low_price, bar.close_price)

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        if not self.base_price:
            open_ma = am.open[-3:].mean()
            self.log('open_ma:', open_ma)
            if open_ma - bar.open_price > self.entry_range:
                self.base_price = round(bar.open_price + self.entry_range, 2)
            elif bar.open_price - open_ma > self.entry_range:
                self.base_price = round(bar.open_price - self.entry_range, 2)
            else:
                self.base_price = round(open_ma, 2)

            self.trade(bar.date, 'entry', self.base_price)

        if self.base_price:
            # 因为有些交易日涨跌幅特别大或大幅度跳开，可能需要多次对冲，需要循环检查
            while True:                
                long_hedge = (bar.high_price - self.base_price) > self.hedge_range
                short_hedge = (self.base_price - bar.low_price) > self.hedge_range

                # 防止无限循环调用
                if self.hedge_long_count >= 2:
                    short_hedge = False
                if self.hedge_short_count >= 2:
                    long_hedge = False

                if long_hedge:
                    self.log('long-hedge:', 'high:', bar.high_price, 'target_high:', self.base_price + self.hedge_range)
                    self.base_price = self.base_price + self.hedge_value
                    self.hedge_long_count += 1
                elif short_hedge:
                    self.log('short_hedge:', 'low:', bar.low_price, 'target_low:', self.base_price - self.hedge_range)
                    self.base_price = self.base_price - self.hedge_value
                    self.hedge_short_count += 1
                else:
                    self.hedge_long_count = 0
                    self.hedge_short_count = 0
                    break

                self.trade(bar.date, 'exit', self.base_price)
                self.trade(bar.date, 'entry', self.base_price)


class DynamicHedge(OptionBacktest):
    def __init__(self, start):
        super().__init__(start=start)
        self.hedge_range = 0.1
        self.hedge_value = 0.05
        self.hedge_long_count = 0
        self.hedge_short_count = 0

        self.atr_multiple = 2.0
        self.hedge_multiple = 0.5

        self.parameters = ['atr_multiple', 'hedge_multiple']


    def stats_result(self):
        hedge_count = (len(self.trades) - 1) / 2
        hedge_loss = self.hedge_value * hedge_count
        hedge_cost = hedge_count * 0.01
        print(f"开始:{self.start} 结束:{self.end} atr倍数:{self.atr_multiple} 对冲折数:{self.hedge_multiple} 对冲次数:{hedge_count} 对冲成本:{hedge_cost} 已对冲:{hedge_loss} 总成本:{hedge_cost + hedge_loss}")

    def update_hedge_range(self):
        atr_range = self.am.atr(20) * self.atr_multiple
        self.hedge_range = max(atr_range, 0.1)
        self.hedge_value = self.hedge_range * self.hedge_multiple
        self.log('atr_range:', atr_range, 'hedge_range:', self.hedge_range, 'hedge_value:', self.hedge_value)

    def on_bar(self, bar):
        self.log(bar.date, bar.open_price, bar.high_price, bar.low_price, bar.close_price)

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        if not self.base_price:
            open_ma = am.open[-3:].mean()
            self.log('open_ma:', open_ma)
            self.update_hedge_range()
            if open_ma - bar.open_price > self.entry_range:
                self.base_price = round(bar.open_price + self.entry_range, 2)
            elif bar.open_price - open_ma > self.entry_range:
                self.base_price = round(bar.open_price - self.entry_range, 2)
            else:
                self.base_price = round(open_ma, 2)

            self.trade(bar.date, 'entry', self.base_price)

        if self.base_price:
            # 因为有些交易日涨跌幅特别大或大幅度跳开，可能需要多次对冲，需要循环检查
            while True:                
                long_hedge = (bar.high_price - self.base_price) > self.hedge_range
                short_hedge = (self.base_price - bar.low_price) > self.hedge_range

                # 防止无限循环调用
                if self.hedge_long_count >= 2:
                    short_hedge = False
                if self.hedge_short_count >= 2:
                    long_hedge = False

                if long_hedge:
                    self.log('long-hedge:', 'high:', bar.high_price, 'target_high:', self.base_price + self.hedge_range)
                    self.base_price = self.base_price + self.hedge_value
                    self.hedge_long_count += 1
                elif short_hedge:
                    self.log('short_hedge:', 'low:', bar.low_price, 'target_low:', self.base_price - self.hedge_range)
                    self.base_price = self.base_price - self.hedge_value
                    self.hedge_short_count += 1
                else:
                    self.hedge_long_count = 0
                    self.hedge_short_count = 0
                    break

                self.trade(bar.date, 'exit', self.base_price)
                self.trade(bar.date, 'entry', self.base_price)
                self.update_hedge_range()
