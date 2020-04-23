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


class AtrRsiStrategy(CtaTemplate):
    """"""

    author = "用Python的交易员"

    is_say_log = False

    atr_length = 22
    atr_ma_length = 10
    rsi_length = 5
    rsi_entry = 16
    trailing_percent = 0.8
    fixed_size = 1

    atr_value = 0
    atr_ma = 0
    rsi_value = 0
    rsi_buy = 0
    rsi_sell = 0
    intra_trade_high = 0
    intra_trade_low = 0

    limit_up = 1.04
    limit_down = 0.96

    parameters = ["atr_length", "atr_ma_length", "rsi_length",
                  "rsi_entry", "trailing_percent", "fixed_size", "is_say_log"]
    variables = ["atr_value", "atr_ma", "rsi_value", "rsi_buy", "rsi_sell"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super(AtrRsiStrategy, self).__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )
        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager()
        self.say_log({key: getattr(self, key) for key in self.parameters})

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        self.rsi_buy = 50 + self.rsi_entry
        self.rsi_sell = 50 - self.rsi_entry

        self.load_bar(10)

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

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        atr_array = am.atr(self.atr_length, array=True)
        self.atr_value = atr_array[-1]
        self.atr_ma = atr_array[-self.atr_ma_length:].mean()
        self.rsi_value = am.rsi(self.rsi_length)

        self.rsi_array = am.rsi(self.rsi_length, True)
        self.say_log('today:', self.rsi_array[-1], 'yesterday:', self.rsi_array[-2])

        if self.pos == 0:
            self.intra_trade_high = bar.high_price
            self.intra_trade_low = bar.low_price

            # if self.atr_value > self.atr_ma:
            if self.rsi_value > self.rsi_buy:
                self.say_log("signal_long:", 'atr:', self.atr_value, 'atr-ma:', self.atr_ma, 'rsi:', self.rsi_value)
                self.buy(bar.close_price * self.limit_up, self.fixed_size)
            elif self.rsi_value < self.rsi_sell:
                self.say_log("signal_short:", 'atr:', self.atr_value, 'atr-ma:', self.atr_ma, 'rsi:', self.rsi_value)
                self.short(bar.close_price * self.limit_down, self.fixed_size)

        elif self.pos > 0:
            self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            self.intra_trade_low = bar.low_price

            long_stop = self.intra_trade_high * \
                (1 - self.trailing_percent / 100)
            self.sell(long_stop, abs(self.pos), stop=True)

        elif self.pos < 0:
            self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            self.intra_trade_high = bar.high_price

            short_stop = self.intra_trade_low * \
                (1 + self.trailing_percent / 100)
            self.cover(short_stop, abs(self.pos), stop=True)

        self.say_log('datetime:', bar.datetime, 'pos:', self.pos, 'atr:',
                     self.atr_value, 'atr-ma:', self.atr_ma, 'rsi:',
                     self.rsi_value)
        self.say_log('==' * 50)

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
        pass

    def say_log(self, *args):
        if self.is_say_log:
            print(*args)
