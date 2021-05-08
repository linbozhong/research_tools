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


class FixedNetStrategy(CtaTemplate):
    """"""
    author = "Fixed net strategy"
    nick_name = 'fn'
    is_log = True

    price_interval = 0 

    parameters = ['price_interval']
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.price_interval = 50

        self.am = ArrayManager(size=20)
        self.day_close_list = []

        self.pos_inited = False

        self.up_price = 0
        self.down_price = 0

        self.open_pos = 40
        self.lot = 2
        self.max_pos = 90
        self.min_pos = 16

    def on_init(self):
        self.write_log("策略初始化")
        self.load_bar(6)

    def on_start(self):
        self.write_log("策略启动")

    def on_stop(self):
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        pass

    def update_day_bar(self, bar: BarData):
        if bar.datetime.hour == 14:
            self.day_close_list.append(bar.close_price)

    def get_yesterday_close(self):
        if self.day_close_list:
            return self.day_close_list[-1]
        else:
            return 0

    def create_base_pos(self):
        if not self.pos_inited:
            price = self.get_yesterday_close()
            self.buy(price, self.open_pos, False)

    def on_bar(self, bar: BarData):
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # 建立初始仓位
        self.create_base_pos()

        # 只在每天的第一根bar运行，当天后续变化靠on_trade函数
        yst_close = self.get_yesterday_close()
        if bar.datetime.hour == 9:
            self.up_price = yst_close + self.price_interval
            self.down_price = yst_close - self.price_interval

        self.log("Pos:", self.pos)
        self.log("ref:", self.get_yesterday_close(), "up:", self.up_price, 'down:', self.down_price)
        self.log("up_delta:", self.up_price - yst_close, "down_delta:", self.down_price - yst_close)

        if self.pos_inited:
            if self.pos < self.max_pos:
                self.buy(self.down_price, self.lot, False)

            if self.pos > self.min_pos:
                self.sell(self.up_price, self.lot, False)

        self.log(bar.datetime, bar.open_price, bar.high_price, bar.low_price, bar.close_price)

        # 最后更新，避免未来函数
        self.update_day_bar(bar)

    def on_order(self, order: OrderData):
        pass
        # self.log("Order:", order.datetime, order.direction, order.offset, order.price, order.volume)

    def on_trade(self, trade: TradeData):
        self.log("Trade:", trade.datetime, trade.direction, trade.offset, trade.price, trade.volume)

        if trade.volume == self.open_pos:
            self.log("初始仓位创建成功")
            self.pos_inited = True
        else:
            if trade.direction == Direction.SHORT and trade.offset == Offset.CLOSE:
                self.up_price += self.price_interval

            if trade.direction == Direction.LONG and trade.offset == Offset.OPEN:
                self.down_price -= self.price_interval

    def on_stop_order(self, stop_order: StopOrder):
        pass

    def log(self, *arg, **kwargs):
            if self.is_log:
                print(*arg, **kwargs)