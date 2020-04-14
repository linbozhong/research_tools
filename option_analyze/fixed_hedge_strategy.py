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


class FixedHedgeStrategy(CtaTemplate):
    """"""
    author = "option underlying Fixed hedge"
    nick_name = 'fixed_hedge'
    is_log = False

    base_price = 0
    entry_range = 0.05

    hedge_range_param = 100
    hedge_multiple_param = 50

    hedge_range = 0.0
    hedge_multiple = 0.0
    hedge_size = 10

    last_trade_dt = None

    parameters = ['hedge_range_param', 'hedge_multiple_param', 'hedge_size']
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )
        
        self.bg5 = BarGenerator(self.on_bar, 5, self.on_5min_bar)
        self.am5 = ArrayManager(size=20)

        self.hedge_range = self.hedge_range_param / 1000
        self.hedge_multiple = self.hedge_multiple_param / 100

        self.hedge_size = round(self.hedge_range / 0.1 * 30)
        setting['hedge_size'] = self.hedge_size
        print("params:", self.hedge_range, self.hedge_multiple, self.hedge_size, self.strategy_name)

    def on_init(self):
        self.write_log("策略初始化")
        self.load_bar(10)

    def on_start(self):
        self.write_log("策略启动")

    def on_stop(self):
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        pass

    def on_bar(self, bar: BarData):
        self.bg5.update_bar(bar)

    def on_5min_bar(self, bar: BarData):
        """"""
        self.log(bar.datetime, bar.open_price, bar.high_price, bar.low_price, bar.close_price)

        self.cancel_all()

        self.am5.update_bar(bar)
        if not self.am5.inited:
            return

        if not self.base_price:
            self.base_price = round(bar.open_price, 2)
        else:
            up = self.base_price + self.hedge_range
            down = self.base_price - self.hedge_range
            self.log('base:', self.base_price, 'up:', up, 'down:', down, 'pos:', self.pos)

            if self.pos == 0:
                self.buy(up, self.hedge_size * self.hedge_multiple, True)
                self.short(down, self.hedge_size * self.hedge_multiple, True)
            elif self.pos > 0:
                # 条件触发用本地单
                self.sell(down, self.hedge_size * self.hedge_multiple, True)
                # self.short(down, self.hedge_size * self.hedge_multiple, True)
                self.buy(up, self.hedge_size * self.hedge_multiple, True)

                # 多单止盈用限价单
                self.sell(up, self.hedge_size * self.hedge_multiple, False)
            elif self.pos < 0:
                # 条件触发用本地单
                self.cover(up, self.hedge_size * self.hedge_multiple, True)
                # self.buy(up, self.hedge_size * self.hedge_multiple, True)
                self.short(down, self.hedge_size * self.hedge_multiple, True)

                # 空单止盈用限价单
                self.cover(down, self.hedge_size * self.hedge_multiple, False)

    def on_order(self, order: OrderData):
        pass

    def on_trade(self, trade: TradeData):
        self.log("Trade:", trade.datetime, trade.direction, trade.offset, trade.price, trade.volume)
        if trade.datetime != self.last_trade_dt:
            if trade.direction == Direction.LONG:
                self.base_price += self.hedge_range * self.hedge_multiple
            elif trade.direction == Direction.SHORT:
                self.base_price -= self.hedge_range * self.hedge_multiple
        else:
            # 如果平仓后跟着开仓，说明前一次基线调错了，补回来后还要相应移动1档
            # self.log('trades at the same time')
            if trade.direction == Direction.LONG and trade.offset == Offset.OPEN:
                self.base_price += self.hedge_range * self.hedge_multiple * 2
            elif trade.direction == Direction.SHORT and trade.offset == Offset.OPEN:
                self.base_price -= self.hedge_range * self.hedge_multiple * 2

        self.last_trade_dt = trade.datetime


    def on_stop_order(self, stop_order: StopOrder):
        pass

    def log(self, *arg, **kwargs):
            if self.is_log:
                print(*arg, **kwargs)