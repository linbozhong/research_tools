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


class DoubleMaStdStrategy(CtaTemplate):
    author = "double_ma_std"

    fast_window = 20
    slow_window = 40
    std_dev = 2.0

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

        self.local_stop = True
        self.limit_up = 1.04
        self.limit_down = 0.96

        self.watch_long = False
        self.watch_short = False
        self.boll_up = 0
        self.boll_down = 0

    def on_init(self):
        """
        Callback when strategy is inited.
        """
        self.write_log("策略初始化")

        # 回撤引擎，load_bar只有days(回溯交易日)和callback有作用，其他传入参数都没有作用。
        self.load_bar(60)

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

        fast_ma = am.sma(self.fast_window, array=True)
        self.fast_ma0 = fast_ma[-1]
        self.fast_ma1 = fast_ma[-2]

        slow_ma = am.sma(self.slow_window, array=True)
        self.slow_ma0 = slow_ma[-1]
        self.slow_ma1 = slow_ma[-2]

        cross_over = self.fast_ma0 > self.slow_ma0 and self.fast_ma1 < self.slow_ma1
        cross_below = self.fast_ma0 < self.slow_ma0 and self.fast_ma1 > self.slow_ma1

        # 监测状态是持续性的，在状态未撤销之前且没有成交（没有仓位），每根bar都会发本地单
        if self.watch_long and self.pos == 0:
            self.buy(self.boll_up, 1, True)
            print("WatchLong:", bar.datetime, "boll_up:", self.boll_up)

        if self.watch_short and self.pos == 0:
            self.short(self.boll_down, 1, True)
            print("watchShort:", bar.datetime, "boll_down:", self.boll_down)

        # 交叉信号是一次性的，只在触发的bar运行，没成交的单在下一根bar计算之前会被撤销
        if cross_over:
            # 金叉，撤销做空监测单并取消做空监测
            self.cancel_all()
            self.watch_short = False

            if self.pos == 0:
                # 通道只在触发信号的时候计算，后续不再改变。
                self.boll_up, self.boll_down = am.boll(self.slow_window, self.std_dev)

                # 立即发本地单，等待下一根撮合，同时开始监测做多
                self.buy(self.boll_up, 1, True)
                self.watch_long = True

                print("Signal:", bar.datetime, "pos:", self.pos, "boll_up:", self.boll_up,
                      "price:", bar.close_price, "gloden-cross open")

            elif self.pos < 0:
                # 有空头，碰到金叉后，先超价立即平仓
                # 反向单先发本地单，等待下一根bar一起撮合，并且开启做多监测
                self.boll_up, self.boll_down = am.boll(self.slow_window, self.std_dev)

                self.cover(bar.close_price * self.limit_up, abs(self.pos), False)
                self.buy(self.boll_up, 1, True)
                self.watch_long = True

                print("Signal:", bar.datetime, "pos:", self.pos, "boll_up:", self.boll_up,
                      "price:", bar.close_price, "gloden-cross close and open")

        elif cross_below:
            self.cancel_all()
            self.watch_long = False

            if self.pos == 0:
                self.boll_up, self.boll_down = am.boll(self.slow_window, self.std_dev)

                self.short(self.boll_down, 1, True)
                self.watch_short = True

                print("Signal:", bar.datetime, "pos:", self.pos, "boll_down:", self.boll_down,
                      "close:", bar.close_price, "dead-cross open")
            elif self.pos > 0:
                self.boll_up, self.boll_down = am.boll(self.slow_window, self.std_dev)

                self.sell(bar.close_price * self.limit_down, abs(self.pos), False)
                self.short(self.boll_down, 1, True)
                self.watch_short = True

                print("Signal:", bar.datetime, "pos:", self.pos, "boll_down:", self.boll_down,
                      "close:", bar.close_price, "dead-cross close and open")
        
        print('==' * 50)
        print('datetime:', bar.datetime, 'pos:', self.pos, 'watch-long:',
              self.watch_long, 'watch_short:', self.watch_short)

        self.put_event()

    def on_order(self, order: OrderData):
        """
        Callback of new order data update.
        """
        print("order", order.datetime, order.direction, order.offset, order.price, order.volume)
        pass

    def on_trade(self, trade: TradeData):
        """
        Callback of new trade data update.
        """
        print("Trade:", trade.datetime, trade.direction, trade.offset, trade.price, trade.volume)
        self.put_event()

    def on_stop_order(self, stop_order: StopOrder):
        """
        Callback of stop order update.
        """
        print("stop-order", stop_order.direction,
              stop_order.offset, stop_order.price, stop_order.volume)
        pass
