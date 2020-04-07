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


class MacdMinHoutReinStrategy(CtaTemplate):
    # macd穿刺零轴产生入场信号，hist穿刺零轴产生出场信号，一般出场信号先于反向的入场信号
    # 出场（初始止损）+ ATR跟踪止损结合
    author = "macd_m_in_hist_out_rein"
    is_say_log = True

    fast_window = 15
    slow_window = 30
    signal_period = 10

    atr_multi = 0
    init_exit_atr_multi = 2
    exit_atr_multi = 3
    max_rein = 3

    limit_up = 1.04
    limit_down = 0.96

    macd = None
    signal = None
    hist = None

    pre_hist = 0.0
    now_hist = 0.0
    pre_macd = 0.0
    now_macd = 0.0

    atr_value = 0.0

    watch_long = False
    watch_short = False
    entry_long = 0.0
    entry_short = 0.0

    pre_highest = 0.0
    pre_lowest = 0.0
    init_long_stop = 0.0
    init_short_stop = 0.0
    follow_long_stop = 0.0
    follow_short_stop = 0.0

    long_rein = False
    short_rein = False
    long_rein_count = 0
    short_rein_count = 0

    parameters = ["fast_window", "slow_window", "atr_multi", "exit_atr_multi", "max_rein", "signal_period"]
    variables = ["pre_hist", "now_hist"]

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

        self.atr_value = am.atr(self.slow_window)

        self.macd, self.signal, self.hist = am.macd(self.fast_window, self.slow_window, self.signal_period, True)
        self.now_macd = self.macd[-1]
        self.now_hist = self.hist[-1]

        # 计算前高前低
        if self.pos == 0:
            if not self.long_rein and not self.short_rein:
                self.pre_highest = bar.high_price
                self.pre_lowest = bar.low_price
        elif self.pos > 0:
            self.pre_highest = max(self.pre_highest, bar.high_price)
        elif self.pos < 0:
            self.pre_lowest = min(self.pre_lowest, bar.low_price)


        macd_cross_over = self.pre_macd < 0 and self.now_macd > 0
        macd_cross_below = self.pre_macd > 0 and self.now_macd < 0

        hist_cross_over = self.pre_hist < 0 and self.now_hist > 0
        hist_cross_below = self.pre_hist > 0 and self.now_hist < 0

        self.pre_macd = self.now_macd
        self.pre_hist = self.now_hist

        # 根据条件发出本地单
        if self.watch_long and self.pos == 0:
            self.buy(self.entry_long, 1, True)
            self.say_log("WatchLong:", bar.datetime, "entry_long:", self.entry_long)

        if self.watch_short and self.pos == 0:
            self.short(self.entry_short, 1, True)
            self.say_log("watchShort:", bar.datetime, "entry_short:", self.entry_short)

        # 发出重新入场监测的本地单，防止止损后继续走出大行情
        if self.long_rein and self.pos == 0:
            self.buy(self.pre_highest, 1, True)
            self.say_log("ReinLong:", bar.datetime, "pre-high:", self.pre_highest, "long_rein_count:", self.long_rein_count)

        if self.short_rein and self.pos == 0:
            self.short(self.pre_lowest, 1, True)
            self.say_log("ReinShort:", bar.datetime, "pre-low:", self.pre_lowest, "short_rein_count:", self.short_rein_count)

        # 出场信号
        if hist_cross_below and self.pos > 0:
            self.sell(bar.close_price * self.limit_down, abs(self.pos), False)
            self.say_log("Close-Long:", bar.datetime, 'close:', bar.close_price)

        if hist_cross_over and self.pos < 0:
            self.cover(bar.close_price * self.limit_up, abs(self.pos), False)
            self.say_log("Close-short:", bar.datetime, 'close:', bar.close_price)
            

        # 初始止损 + ATR跟踪止损 + 补入场
        # if self.pos > 0:
            # self.pre_highest = max(self.pre_highest, bar.high_price)
        #     self.follow_long_stop = self.pre_highest - self.atr_value * self.exit_atr_multi
        #     price = max(self.init_long_stop, self.follow_long_stop)
        #     self.sell(price, abs(self.pos), True)

        #     self.say_log("Sell-long-stop:", bar.datetime, 'init_long_stop:',
        #                  self.init_long_stop, 'follow_long_stop:', self.follow_long_stop)

        #     # 持有多头尚未平仓发现触发空头信号，则发出本地单，待平仓时立即反向开仓
        #     if self.watch_short:
        #         self.short(price, 1, True)

        # if self.pos < 0:
        #     self.pre_lowest = min(self.pre_lowest, bar.low_price)
        #     self.follow_short_stop = self.pre_lowest + self.atr_value * self.exit_atr_multi
        #     price = min(self.init_short_stop, self.follow_short_stop)
        #     self.cover(price, abs(self.pos), True)

        #     self.say_log("Cover-short-stop:", bar.datetime, 'init_short_stop:',
        #                  self.init_short_stop, 'follow_short_stop:', self.follow_short_stop)

        #     if self.watch_long:
        #         self.buy(price, 1, True)

        # 入场信号
        if macd_cross_over:
            self.cancel_all()

            # 取消做空监测和重新做空监测
            self.watch_short = False
            self.short_rein = False
            self.short_rein_count = 0

            # 重新计算前高
            self.pre_highest = bar.high_price

            # 通道只在触发信号的时候计算，后续不再改变。
            self.entry_long = bar.close_price + self.atr_value * self.atr_multi

            if self.pos == 0:
                # 立即发本地单，等待下一根撮合，同时开始监测做多
                self.buy(self.entry_long, 1, True)

                if self.trading:
                    self.watch_long = True

                self.say_log("Signal-long:", bar.datetime, "pos:", self.pos, "entry_long:", self.entry_long,
                      "close:", bar.close_price, "trading:", self.trading)
            elif self.pos < 0:
                # 空头立即平仓，同时发出多头本地单
                self.cover(bar.close_price * self.limit_up, abs(self.pos), False)
                self.buy(self.entry_long, 1, True)
                self.watch_long = True

                self.say_log("Signal-long-neg-pos:", bar.datetime, "pos:", self.pos, "entry_long:", self.entry_long,
                      "close:", bar.close_price, "trading:", self.trading)


        elif macd_cross_below:
            self.cancel_all()

            self.watch_long = False
            self.long_rein = False
            self.long_rein_count = 0

            self.pre_lowest = bar.low_price

            self.entry_short = bar.close_price - self.atr_value * self.atr_multi

            if self.pos == 0:
                self.short(self.entry_short, 1, True)

                if self.trading:
                    self.watch_short = True
                    
                self.say_log("Signal-short:", bar.datetime, "pos:", self.pos, "entry_short:", self.entry_short,
                      "close:", bar.close_price, "trading:", self.trading)

            elif self.pos > 0:
                self.sell(bar.close_price * self.limit_down, abs(self.pos), False)
                self.short(self.entry_short, 1, True)
                self.watch_short = True

                self.say_log("Signal-short-potv-pos:", bar.datetime, "pos:", self.pos, "entry_short:", self.entry_short,
                      "close:", bar.close_price, "trading:", self.trading)

        self.say_log('datetime:', bar.datetime, 'pos:', self.pos, 'watch-long:',
                     self.watch_long, 'watch_short:', self.watch_short, 'long-rein:',
                     self.long_rein, 'short-rein:', self.short_rein,
                     'highest:', self.pre_highest, 'lowest:', self.pre_lowest)
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
        if trade.offset == Offset.OPEN:
            if trade.direction == Direction.LONG:
                self.init_long_stop = trade.price - self.atr_value * self.init_exit_atr_multi
                self.watch_long = False
                self.long_rein = False
            else:
                self.init_short_stop = trade.price + self.atr_value * self.init_exit_atr_multi
                self.watch_short = False
                self.short_rein = False
        else:
            # 交易时做多平仓（平空头），开启重新入场监测
            if trade.direction == Direction.LONG and not self.watch_long:
                # 重入空头次数小于最大限制，才能重入空头
                if self.short_rein_count < self.max_rein:
                    self.short_rein = True
                    self.short_rein_count += 1

            if trade.direction == Direction.SHORT and not self.watch_short:
                if self.long_rein_count < self.max_rein:
                    self.long_rein = True
                    self.long_rein_count += 1
            
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
