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
from vnpy.trader.constant import Interval, Direction


class DoubleMaExitMaStrategy(CtaTemplate):
    # 入场用快均线和慢均线交叉加过滤器，快均线一般固定为5，相当于使用单均线入场
    # 出场用满均线的.x系数的均线出场，相当于更快出场，但是有可能会错过很大的行情。
    author = "double_ma_exit_ma"
    is_say_log = False

    fast_window = 20
    slow_window = 40
    atr_multi = 0.5
    mid_multi = 0.8

    fast_ma0 = 0.0
    fast_ma1 = 0.0

    slow_ma0 = 0.0
    slow_ma1 = 0.0

    parameters = ["fast_window", "slow_window", "atr_multi", "mid_multi"]
    variables = ["fast_ma0", "fast_ma1", "slow_ma0", "slow_ma1"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        """"""
        super().__init__(
            cta_engine, strategy_name, vt_symbol, setting
        )

        self.bg = BarGenerator(self.on_bar)
        self.am = ArrayManager(size=80)

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
            self.say_log("WatchLong:", bar.datetime, "boll_up:", self.boll_up)

        if self.watch_short and self.pos == 0:
            self.short(self.boll_down, 1, True)
            self.say_log("watchShort:", bar.datetime, "boll_down:", self.boll_down)

        # 提前平仓
        if self.pos > 0:
            mid_ma = am.sma(int(self.slow_window * self.mid_multi))
            self.sell(mid_ma, abs(self.pos), True)
            self.say_log("Close-Long-Ahead:", bar.datetime, 'mid_ma:', mid_ma)

        if self.pos < 0:
            mid_ma = am.sma(int(self.slow_window * self.mid_multi))
            self.cover(mid_ma, abs(self.pos), True)
            self.say_log("Close-Short-Ahead:", bar.datetime, 'mid_ma:', mid_ma)


        # 交叉信号是一次性的，只在触发的bar运行，没成交的单在下一根bar计算之前会被撤销
        if cross_over:
            # 金叉，撤销做空监测单并取消做空监测
            self.cancel_all()
            self.watch_short = False

            # 通道只在触发信号的时候计算，后续不再改变。
            atr_value = am.atr(self.slow_window) * self.atr_multi
            self.boll_up = bar.close_price + atr_value

            if self.pos == 0:
                # 立即发本地单，等待下一根撮合，同时开始监测做多
                self.buy(self.boll_up, 1, True)

                if self.trading:
                    self.watch_long = True

                self.say_log("Signal:", bar.datetime, "pos:", self.pos, "close_up:", self.boll_up,
                      "close:", bar.close_price, "gloden-cross open", "trading:", self.trading)

            elif self.pos < 0:
                # 有空头，碰到金叉后，先超价立即平仓
                # 反向单先发本地单，等待下一根bar一起撮合，并且开启做多监测
                self.cover(bar.close_price * self.limit_up, abs(self.pos), False)
                self.buy(self.boll_up, 1, True)
                self.watch_long = True

                self.say_log("Signal:", bar.datetime, "pos:", self.pos, "close_up:", self.boll_up,
                      "close:", bar.close_price, "gloden-cross close and open")

        elif cross_below:
            self.cancel_all()
            self.watch_long = False

            atr_value = am.atr(self.slow_window) * self.atr_multi
            self.boll_down = bar.close_price - atr_value

            if self.pos == 0:
                self.short(self.boll_down, 1, True)

                if self.trading:
                    self.watch_short = True

                self.say_log("Signal:", bar.datetime, "pos:", self.pos, "close_down:", self.boll_down,
                      "close:", bar.close_price, "dead-cross open", "trading:", self.trading)
            elif self.pos > 0:
                self.sell(bar.close_price * self.limit_down, abs(self.pos), False)
                self.short(self.boll_down, 1, True)
                self.watch_short = True

                self.say_log("Signal:", bar.datetime, "pos:", self.pos, "close_down:", self.boll_down,
                      "close:", bar.close_price, "dead-cross close and open")
        
        self.say_log('datetime:', bar.datetime, 'pos:', self.pos, 'watch-long:',
              self.watch_long, 'watch_short:', self.watch_short)
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
        if trade.direction == Direction.LONG:
            self.watch_long = False
        else:
            self.watch_short = False

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