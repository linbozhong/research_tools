import pandas as pd
from datetime import datetime
from vnpy.trader.constant import Direction, Offset
from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class DynamicHedgeAtrStrategy(CtaTemplate):
    """"""
    author = "option underlying dynamic hedge"
    nick_name = 'dynamic_atr_hedge'
    is_log = False

    gamma = 300

    # 10倍，使参数整数显示
    atr_range = 10
    atr_window = 20

    # 千分之
    # hedge_range_percent = 20

    # 百分之
    hedge_multiple_percent = 100

    base_price = 0
    hedge_range = 0.0
    move_range = 0.0
    hedge_size = 0
    atr_value = 0.0

    last_trade_dt = None


    parameters = ['atr_range', 'hedge_multiple_percent']
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )
        
        self.bg5 = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am5 = ArrayManager(size=20)

        self.daily_atr = self.load_daily_art()

        print("params:", self.atr_range, self.hedge_multiple_percent)

    def on_init(self):
        self.write_log("策略初始化")
        self.load_bar(5)

    def on_start(self):
        self.write_log("策略启动")

    def on_stop(self):
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        pass

    def load_daily_art(self):
        df = pd.read_csv('510050_atr.csv', parse_dates=[1], index_col=1)
        df['id'] = list(range(len(df)))
        return df

    def get_last_day_atr(self, dt):
        df = self.daily_atr
        new_dt = datetime(dt.year, dt.month, dt.day)
        last_day_id = int(df.loc[new_dt]['id'] - 1)
        return df.iloc[last_day_id]['atr']

    def on_bar(self, bar: BarData):
        self.bg5.update_bar(bar)

    def on_5min_bar(self, bar: BarData):
        """"""
        self.atr_value = self.get_last_day_atr(bar.datetime)
        self.log(bar.datetime, bar.open_price, bar.high_price, bar.low_price, bar.close_price, 'atr:', self.atr_value)

        self.cancel_all()

        self.am5.update_bar(bar)
        if not self.am5.inited:
            return

        # 初始入场，确定首次对冲范围和对冲基准手数
        if not self.base_price:
            if self.trading:
                self.base_price = round(bar.open_price, 2)
                self.hedge_range = round(self.atr_range / 10 * self.atr_value, 2)
                self.hedge_size = round(self.hedge_range * self.gamma)
        else:
            up = self.base_price + self.hedge_range
            down = self.base_price - self.hedge_range
            self.log('base:', self.base_price, 'up:', up, 'down:', down, 'pos:', self.pos, 'range:', self.hedge_range)

            action_size = round(self.hedge_size * (self.hedge_multiple_percent / 100))

            if self.pos == 0:
                self.buy(up, action_size, True)
                self.short(down, action_size, True)
            elif self.pos > 0:
                # 条件触发用本地单
                self.sell(down, abs(self.pos), True)
                self.buy(up, action_size, True)

                # 多单止盈用限价单
                self.sell(up, abs(self.pos), False)
            elif self.pos < 0:
                # 条件触发用本地单
                self.cover(up, abs(self.pos), True)
                self.short(down, action_size, True)

                # 空单止盈用限价单
                self.cover(down, abs(self.pos), False)

    def on_order(self, order: OrderData):
        pass

    def on_trade(self, trade: TradeData):
        self.log("Trade:", trade.datetime, trade.direction, trade.offset, trade.price, trade.volume)
        if trade.datetime != self.last_trade_dt:
            # 和上次成交不是同一个时间的成交单，是下一个对冲点的第一笔成交（或只有一笔成交）
            self.hedge_range = round(self.atr_range / 10 * self.atr_value, 2)
            self.move_range = round(self.hedge_range * (self.hedge_multiple_percent / 100), 2)
            self.hedge_size = round(self.move_range * self.gamma)

            if trade.direction == Direction.LONG:
                self.base_price += self.move_range
            elif trade.direction == Direction.SHORT:
                self.base_price -= self.move_range
        else:
            # 时间一致，说明平仓后跟着开仓，这样前一次基线调错了，补回来后还要相应移动1档
            # self.log('trades at the same time')
            if trade.direction == Direction.LONG and trade.offset == Offset.OPEN:
                self.base_price += self.move_range * 2
            elif trade.direction == Direction.SHORT and trade.offset == Offset.OPEN:
                self.base_price -= self.move_range * 2
        
        self.last_trade_dt = trade.datetime

    def on_stop_order(self, stop_order: StopOrder):
        pass

    def log(self, *arg, **kwargs):
            if self.is_log:
                print(*arg, **kwargs)