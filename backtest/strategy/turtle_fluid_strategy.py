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


class TurtleFluidSizeStrategy(CtaTemplate):
    """"""
    # 改版海龟信号-ma出场-rsi过滤-atr浮动手数
    author = "turtle_fluid_size"

    entry_window = 50
    exit_window = 20
    atr_window = 20
    stop_multiple = 10
    long_rsi = 50
    short_rsi = 50
    fixed_size = 1

    entry_up = 0
    entry_down = 0
    exit_up = 0
    exit_down = 0
    atr_value = 0

    long_entry = 0
    short_entry = 0
    long_stop = 0
    short_stop = 0

    fluid_size = 1
    symbol_size = 1
    risk_percent = 0.002
    risk_capital = 1000000

    parameters = ["entry_window", "exit_window", "atr_window", "fixed_size", "stop_multiple",
                  "long_rsi", "short_rsi", "symbol_size", "risk_percent", "risk_capital"]
    variables = ["entry_up", "entry_down", "exit_up", "exit_down", "atr_value", "fluid_size"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )
        print(self.symbol_size, self.risk_percent, self.risk_capital)

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

        self.exit_up = self.exit_down = self.am.sma(self.exit_window)
        self.rsi_value = self.am.rsi(self.entry_window)

        
        if not self.pos:
            self.atr_value = self.am.atr(self.atr_window)

            risk_amount = self.risk_capital * self.risk_percent
            atr_amount = self.atr_value * self.symbol_size
            self.fluid_size = round(risk_amount / atr_amount) * self.fixed_size

            self.long_entry = 0
            self.short_entry = 0
            self.long_stop = 0
            self.short_stop = 0

            if self.fluid_size and self.rsi_value > self.long_rsi:
                self.send_buy_orders(self.entry_up)
            if self.fluid_size and self.rsi_value <= self.short_rsi:
                self.send_short_orders(self.entry_down)
        elif self.pos > 0:
            sell_price = max(self.long_stop, self.exit_down)
            self.sell(sell_price, abs(self.pos), True)
        elif self.pos < 0:
            cover_price = min(self.short_stop, self.exit_up)
            self.cover(cover_price, abs(self.pos), True)

        self.put_event()

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        if trade.direction == Direction.LONG:
            self.long_entry = trade.price
            self.long_stop = self.long_entry - self.stop_multiple * self.atr_value
        else:
            self.short_entry = trade.price
            self.short_stop = self.short_entry + self.stop_multiple * self.atr_value

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
        self.buy(price, self.fluid_size, True)

    def send_short_orders(self, price):
        """"""
        self.short(price, self.fluid_size, True)