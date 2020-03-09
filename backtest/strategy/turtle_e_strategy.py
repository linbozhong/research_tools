from vnpy.app.cta_strategy import (
    CtaTemplate,
    StopOrder,
    Direction,
    TickData,
    BarData,
    TradeData,
    OrderData,
    BarGenerator,
    ArrayManager,
)


class TurtleEStrategy(CtaTemplate):
    """"""
    # 改版海龟信号-吊灯止损法出场
    author = "turtle_entry_following_stop"

    entry_window = 50
    exit_window = 20
    atr_window = 20
    # stop_multiple = 10
    fixed_size = 1

    entry_up = 0
    entry_down = 0
    exit_up = 0
    exit_down = 0
    atr_value = 0

    long_entry = 0
    short_entry = 0
    # long_stop = 0
    # short_stop = 0

    sl_multiplier = 3
    intra_trade_high = 0
    intra_trade_low = 0
    long_stop = 0
    short_stop = 0

    parameters = ["entry_window", "exit_window", "atr_window", "fixed_size", "sl_multiplier"]
    variables = ["entry_up", "entry_down", "exit_up", "exit_down", "atr_value"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")
        self.load_bar(20)

    def on_start(self):
        """
        Callback when strategy is started.
        """
        self.write_log("策略启动")

    def on_stop(self):
        """
        Callback when strategy is stopped.
        """
        self.write_log("策略停止")

    def on_tick(self, tick: TickData):
        """
        Callback of new tick data update.
        """
        self.bg.update_tick(tick)

    def on_bar(self, bar: BarData):
        """
        Callback of new bar data update.
        """
        self.cancel_all()

        self.am.update_bar(bar)
        if not self.am.inited:
            return

        # Only calculates new entry channel when no position holding
        
        if not self.pos:
            self.entry_up, self.entry_down = self.am.donchian(self.entry_window)
            self.atr_value = self.am.atr(self.atr_window)
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            self.send_buy_orders(self.entry_up)
            self.send_short_orders(self.entry_down)
        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            self.long_stop = self.intra_trade_high - self.atr_value * self.sl_multiplier
            self.sell(self.long_stop, abs(self.pos), True)
        elif self.pos < 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)

            self.short_stop = self.intra_trade_low + self.atr_value * self.sl_multiplier
            self.cover(self.short_stop, abs(self.pos), True)

        self.put_event()

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        # if trade.direction == Direction.LONG:
        #     self.long_entry = trade.price
        #     self.long_stop = self.long_entry - self.stop_multiple * self.atr_value
        # else:
        #     self.short_entry = trade.price
        #     self.short_stop = self.short_entry + self.stop_multiple * self.atr_value

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass

    def send_buy_orders(self, price):
        """"""
        self.buy(price, self.fixed_size, True)

    def send_short_orders(self, price):
        """"""
        self.short(price, self.fixed_size, True)