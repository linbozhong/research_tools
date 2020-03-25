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
from vnpy.trader.constant import Interval, Direction, Offset


class MacdStrategy(CtaTemplate):
    # 原始的macd实现，仅用于研究
    author = "macd"
    is_say_log = True

    fast_window = 10
    slow_window = 60
    signal_period = 9
    
    limit_up = 1.04
    limit_down = 0.96

    macd = None
    signal = None
    hist = None

    pre_macd = 0.0
    now_macd = 0.0

    parameters = ["fast_window", "slow_window"]
    variables = []

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=80)


    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        # 回撤引擎，load_bar只有days(回溯交易日)和callback有作用，其他传入参数都没有作用。
        self.load_bar(80)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")
        self.put_event()

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")
        self.put_event()

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)
        
    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        # 运行新bar之前，撤销之前的委托，否则容易各种异常
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        self.macd, self.signal, self.hist = am.macd(self.fast_window, self.slow_window, self.signal_period, True)
        self.now_macd = self.macd[-1]

        macd_cross_over = self.pre_macd < 0 and self.now_macd > 0
        macd_cross_below = self.pre_macd > 0 and self.now_macd < 0


        if macd_cross_over:
            if self.pos == 0:
                self.buy(bar.close_price * self.limit_up, 1, False)
            elif self.pos < 0:
                self.cover(bar.close_price * self.limit_up, abs(self.pos), False)
                self.buy(bar.close_price * self.limit_up, 1, False)
            self.say_log('signal-long:', bar.datetime, 'pos:', self.pos, 'close:', bar.close_price)
            
        elif macd_cross_below:
            if self.pos == 0:
                self.short(bar.close_price * self.limit_down, 1, False)
            elif self.pos > 0:
                self.sell(bar.close_price * self.limit_down, abs(self.pos), False)
                self.short(bar.close_price * self.limit_down, 1, False)
            self.say_log('signal-short:', bar.datetime, 'pos:', self.pos, 'close:', bar.close_price)

        self.say_log('datetime:', bar.datetime, 'pos:', self.pos, 'now-macd:', self.now_macd, 'pre-macd', self.pre_macd)
        self.say_log('==' * 50)

        self.pre_macd = self.now_macd
        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        self.say_log("order", order.datetime, order.direction, order.offset, order.price, order.volume)

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.say_log("Trade:", trade.datetime, trade.direction, trade.offset, trade.price, trade.volume)
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        self.say_log("stop-order", stop_order.direction,
              stop_order.offset, stop_order.price, stop_order.volume)

    def say_log(self, *args):
        if self.is_say_log:
            print(*args)