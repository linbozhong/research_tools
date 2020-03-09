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


class BollMaStrategy(CtaTemplate):
    """"""
    # 布尔通道入场-同样窗口数的均线出场
    author = "boll_exit_ma"

    boll_window = 20
    boll_dev = 3
    cci_window = 10
    atr_window = 30
    sl_multiplier = 3.5
    fixed_size = 1

    boll_up = 0
    boll_down = 0
    cci_value = 0
    atr_value = 0

    intra_trade_high = 0
    intra_trade_low = 0
    long_stop = 0
    short_stop = 0

    parameters = ["boll_window", "boll_dev", "cci_window",
                  "atr_window", "sl_multiplier", "fixed_size"]
    variables = ["boll_up", "boll_down", "cci_value", "atr_value",
                 "intra_trade_high", "intra_trade_low", "long_stop", "short_stop"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )
        print(self.author)

        # 用于实盘引擎的Xminbar合成，和回测引擎关系不大
        # self.bg = BarGenerator(self.on_bar, 15, self.on_bar)
        self.am = ArrayManager()

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        # 对于回撤引擎这里是关键，要设置好callback函数
        # 回测的new_bar函数内，仍然是调用on_bar，如果不需要合成的bar逻辑，比如直接用hour线的，就是直接用on_bar作为回调函数
        # 回测引擎使用的days是交易日，即开始日期+n日交易日才是真正的开始。而实盘引擎是从现在开始往历史倒推n个自然日。
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

    # def on_tick(self, tick: TickData):
    #     """
    #     Callback of new tick data update.
    #     """
    #     self.bg.update_tick(tick)

    # def on_bar(self, bar: BarData):
    #     """
    #     Callback of new bar data update.
    #     """
    #     self.bg.update_bar(bar)

    def on_bar(self, bar: BarData):
        """"""

        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        # print(bar.datetime, bar.close_price)
        self.boll_up, self.boll_down = am.boll(self.boll_window, self.boll_dev)
        self.exit_ma = am.sma(self.boll_window)

        self.cci_value = am.cci(self.cci_window)
        self.atr_value = am.atr(self.atr_window)

        if self.pos == 0:
            # 追踪止损
            # self.intra_trade_high = bar.high_price
            # self.intra_trade_low = bar.low_price

            # 不用过滤器
            self.buy(self.boll_up, self.fixed_size, True)
            self.short(self.boll_down, self.fixed_size, True)

            # 添加cci过滤器
            # if self.cci_value > 0:
            #     self.buy(self.boll_up, self.fixed_size, True)
            # elif self.cci_value < 0:
            #     self.short(self.boll_down, self.fixed_size, True)

        elif self.pos > 0:
            # 追踪止损
            # self.intra_trade_high = max(self.intra_trade_high, bar.high_price)
            # self.intra_trade_low = bar.low_price
            # self.long_stop = self.intra_trade_high - self.atr_value * self.sl_multiplier

            self.sell(self.exit_ma, abs(self.pos), True)

        elif self.pos < 0:
            # 追踪止损
            # self.intra_trade_high = bar.high_price
            # self.intra_trade_low = min(self.intra_trade_low, bar.low_price)
            # self.short_stop = self.intra_trade_low + self.atr_value * self.sl_multiplier

            self.cover(self.exit_ma, abs(self.pos), True)

        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
