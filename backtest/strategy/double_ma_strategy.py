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
from vnpy.trader.constant import Interval


class DoubleMaStrategy(CtaTemplate):
    # 原始的双均线策略，但是发单模拟市价发单，既不是限价单，也不是停止单。
    # 限价单可能不会成交，无法确保信号成交。
    # 停止单的话如果碰到更有利的价格也不会成交，所以也无法确保信号成交。
    # 回测用简单方法模拟市价，运行实盘时需要做更改，用涨跌停价发限价单实现。
    author = "double_ma_original"

    fast_window = 20
    slow_window = 40

    fast_ma0 = 0.0
    fast_ma1 = 0.0

    slow_ma0 = 0.0
    slow_ma1 = 0.0

    parameters = ["fast_window", "slow_window"]
    variables = ["fast_ma0", "fast_ma1", "slow_ma0", "slow_ma1"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=60)

        self.local_stop = False
        self.limit_up = 1.04
        self.limit_down = 0.96

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        # switch from load minute bar to hour bar
        # 回撤引擎，load_bar只有days(回溯交易日)和callback有作用，其他传入参数都没有作用。
        self.load_bar(30)

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
        self.cancel_all()

        am = self.am
        am.update_bar(bar)
        if not am.inited:
            return

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]
        self.fast_ma1 = fast_ma[-2]

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]

        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 < self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 > self.slow_ma1

        if cross_over:
            if self.pos == 0:
                # self.buy(bar.close_price, 1)

                self.buy(bar.close_price * self.limit_up, 1, self.local_stop)
                # print("Signal:", bar.datetime, "pos:", self.pos, "price:", bar.close_price, "gloden-cross open long")
            elif self.pos < 0:
                # self.cover(bar.close_price, 1)
                # self.buy(bar.close_price, 1)

                self.cover(bar.close_price * self.limit_up, abs(self.pos), self.local_stop)
                self.buy(bar.close_price * self.limit_up, 1, self.local_stop)
                # print("Signal:", bar.datetime, "pos:", self.pos, "price:", bar.close_price, "gloden-cross close short and open long")

        elif cross_below:
            if self.pos == 0:
                # self.short(bar.close_price, 1)

                self.short(bar.close_price * self.limit_down, 1, self.local_stop)
                # print("Signal:", bar.datetime, "pos:", self.pos, "price:", bar.close_price, "dead-cross open short")
            elif self.pos > 0:
                # self.sell(bar.close_price, 1)
                # self.short(bar.close_price, 1)

                self.sell(bar.close_price * self.limit_down, abs(self.pos), self.local_stop)
                self.short(bar.close_price * self.limit_down, 1, self.local_stop)
                # print("Signal:", bar.datetime, "pos:", self.pos, "price:", bar.close_price, "dead-cross close long and open short")

        # print('==' * 50)
        # print('datetime:', bar.datetime, 'pos:', self.pos)

        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        # print("order", order.datetime, order.direction, order.offset, order.price, order.volume)
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        # print("Trade:", trade.datetime, trade.direction, trade.offset, trade.price, trade.volume)
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        pass
