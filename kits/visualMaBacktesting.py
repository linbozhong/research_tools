#!/usr/bin/env python
# encoding: utf-8

from __future__ import division


import talib
import copy
import numpy as np

from datetime import datetime, time
from pprint import pprint


from pyecharts import Kline, Line, Bar, Scatter, Overlap, Page

from vnpy.trader.vtConstant import *
from vnpy.trader.vtObject import VtOrderData

from examples.CtaBacktesting.strategyDoubleMa import DoubleMaStrategy
from vnpy.trader.app.ctaStrategy.ctaBacktesting import BacktestingEngine, TradingResult

import seaborn as sns
import matplotlib.pyplot as plt

# CTA引擎中涉及到的交易方向类型
CTAORDER_BUY = u'买开'
CTAORDER_SELL = u'卖平'
CTAORDER_SHORT = u'卖开'
CTAORDER_COVER = u'买平'

MINUTE_DB_NAME = 'VnTrader_1Min_Db'



class VisualBacktestingEngine(BacktestingEngine):
    def __init__(self):
        super(VisualBacktestingEngine, self).__init__()

        self.backtestTimeId = datetime.now().strftime('%Y%m%d%H%M')
        self.backtestResultDbName = 'Backtest_Result'

        self.displaySetting = {
            'width': 1380,
            'height': 500,
        }
        self.titlePosition = '10%'

        self.tradeList = []
        self.dailyResultList = []

    def sendOrder(self, vtSymbol, orderType, price, volume, strategy):
        """重写发单的方法，增加了保存order的dt"""
        self.limitOrderCount += 1
        orderID = str(self.limitOrderCount)

        order = VtOrderData()
        order.vtSymbol = vtSymbol
        order.price = self.roundToPriceTick(price)
        order.totalVolume = volume
        order.orderID = orderID
        order.vtOrderID = orderID
        order.dt = self.dt  # 重新sendOrder方法，只加了本行代码，用于保存委托单的dt
        order.orderTime = self.dt.strftime('%H:%M:%S')

        if orderType == CTAORDER_BUY:
            order.direction = DIRECTION_LONG
            order.offset = OFFSET_OPEN
        elif orderType == CTAORDER_SELL:
            order.direction = DIRECTION_SHORT
            order.offset = OFFSET_CLOSE
        elif orderType == CTAORDER_SHORT:
            order.direction = DIRECTION_SHORT
            order.offset = OFFSET_OPEN
        elif orderType == CTAORDER_COVER:
            order.direction = DIRECTION_LONG
            order.offset = OFFSET_CLOSE

        self.workingLimitOrderDict[orderID] = order
        self.limitOrderDict[orderID] = order

        return [orderID]

    def calculateBacktestingResult(self):
        """
        重写计算回测结果，最后一行增加把resultList返回
        """
        self.output(u'计算回测结果')

        # 首先基于回测后的成交记录，计算每笔交易的盈亏
        resultList = []  # 交易结果列表

        longTrade = []  # 未平仓的多头交易
        shortTrade = []  # 未平仓的空头交易

        tradeTimeList = []  # 每笔成交时间戳
        posList = [0]  # 每笔成交后的持仓情况

        for trade in self.tradeDict.values():
            # 复制成交对象，因为下面的开平仓交易配对涉及到对成交数量的修改
            # 若不进行复制直接操作，则计算完后所有成交的数量会变成0
            trade = copy.copy(trade)

            # 多头交易
            if trade.direction == DIRECTION_LONG:
                # 如果尚无空头交易
                if not shortTrade:
                    longTrade.append(trade)
                # 当前多头交易为平空
                else:
                    while True:
                        entryTrade = shortTrade[0]
                        exitTrade = trade

                        # 清算开平仓交易
                        closedVolume = min(exitTrade.volume, entryTrade.volume)
                        result = TradingResult(entryTrade.price, entryTrade.dt,
                                               exitTrade.price, exitTrade.dt,
                                               -closedVolume, self.rate, self.slippage, self.size)
                        resultList.append(result)

                        posList.extend([-1, 0])
                        tradeTimeList.extend([result.entryDt, result.exitDt])

                        # 计算未清算部分
                        entryTrade.volume -= closedVolume
                        exitTrade.volume -= closedVolume

                        # 如果开仓交易已经全部清算，则从列表中移除
                        if not entryTrade.volume:
                            shortTrade.pop(0)

                        # 如果平仓交易已经全部清算，则退出循环
                        if not exitTrade.volume:
                            break

                        # 如果平仓交易未全部清算，
                        if exitTrade.volume:
                            # 且开仓交易已经全部清算完，则平仓交易剩余的部分
                            # 等于新的反向开仓交易，添加到队列中
                            if not shortTrade:
                                longTrade.append(exitTrade)
                                break
                            # 如果开仓交易还有剩余，则进入下一轮循环
                            else:
                                pass

            # 空头交易
            else:
                # 如果尚无多头交易
                if not longTrade:
                    shortTrade.append(trade)
                # 当前空头交易为平多
                else:
                    while True:
                        entryTrade = longTrade[0]
                        exitTrade = trade

                        # 清算开平仓交易
                        closedVolume = min(exitTrade.volume, entryTrade.volume)
                        result = TradingResult(entryTrade.price, entryTrade.dt,
                                               exitTrade.price, exitTrade.dt,
                                               closedVolume, self.rate, self.slippage, self.size)
                        resultList.append(result)

                        posList.extend([1, 0])
                        tradeTimeList.extend([result.entryDt, result.exitDt])

                        # 计算未清算部分
                        entryTrade.volume -= closedVolume
                        exitTrade.volume -= closedVolume

                        # 如果开仓交易已经全部清算，则从列表中移除
                        if not entryTrade.volume:
                            longTrade.pop(0)

                        # 如果平仓交易已经全部清算，则退出循环
                        if not exitTrade.volume:
                            break

                        # 如果平仓交易未全部清算，
                        if exitTrade.volume:
                            # 且开仓交易已经全部清算完，则平仓交易剩余的部分
                            # 等于新的反向开仓交易，添加到队列中
                            if not longTrade:
                                shortTrade.append(exitTrade)
                                break
                            # 如果开仓交易还有剩余，则进入下一轮循环
                            else:
                                pass

                                # 到最后交易日尚未平仓的交易，则以最后价格平仓
        if self.mode == self.BAR_MODE:
            endPrice = self.bar.close
        else:
            endPrice = self.tick.lastPrice

        for trade in longTrade:
            result = TradingResult(trade.price, trade.dt, endPrice, self.dt,
                                   trade.volume, self.rate, self.slippage, self.size)
            resultList.append(result)

        for trade in shortTrade:
            result = TradingResult(trade.price, trade.dt, endPrice, self.dt,
                                   -trade.volume, self.rate, self.slippage, self.size)
            resultList.append(result)

            # 检查是否有交易
        if not resultList:
            self.output(u'无交易结果')
            return {}

        # 然后基于每笔交易的结果，我们可以计算具体的盈亏曲线和最大回撤等
        capital = 0  # 资金
        maxCapital = 0  # 资金最高净值
        drawdown = 0  # 回撤

        totalResult = 0  # 总成交数量
        totalTurnover = 0  # 总成交金额（合约面值）
        totalCommission = 0  # 总手续费
        totalSlippage = 0  # 总滑点

        timeList = []  # 时间序列
        pnlList = []  # 每笔盈亏序列
        capitalList = []  # 盈亏汇总的时间序列
        drawdownList = []  # 回撤的时间序列

        winningResult = 0  # 盈利次数
        losingResult = 0  # 亏损次数
        totalWinning = 0  # 总盈利金额
        totalLosing = 0  # 总亏损金额

        for result in resultList:
            capital += result.pnl
            maxCapital = max(capital, maxCapital)
            drawdown = capital - maxCapital

            pnlList.append(result.pnl)
            timeList.append(result.exitDt)  # 交易的时间戳使用平仓时间
            capitalList.append(capital)
            drawdownList.append(drawdown)

            totalResult += 1
            totalTurnover += result.turnover
            totalCommission += result.commission
            totalSlippage += result.slippage

            if result.pnl >= 0:
                winningResult += 1
                totalWinning += result.pnl
            else:
                losingResult += 1
                totalLosing += result.pnl

        # 计算盈亏相关数据
        winningRate = winningResult / totalResult * 100  # 胜率

        averageWinning = 0  # 这里把数据都初始化为0
        averageLosing = 0
        profitLossRatio = 0

        if winningResult:
            averageWinning = totalWinning / winningResult  # 平均每笔盈利
        if losingResult:
            averageLosing = totalLosing / losingResult  # 平均每笔亏损
        if averageLosing:
            profitLossRatio = -averageWinning / averageLosing  # 盈亏比

        # 返回回测结果
        d = {}
        d['capital'] = capital
        d['maxCapital'] = maxCapital
        d['drawdown'] = drawdown
        d['totalResult'] = totalResult
        d['totalTurnover'] = totalTurnover
        d['totalCommission'] = totalCommission
        d['totalSlippage'] = totalSlippage
        d['timeList'] = timeList
        d['pnlList'] = pnlList
        d['capitalList'] = capitalList
        d['drawdownList'] = drawdownList
        d['winningRate'] = winningRate
        d['averageWinning'] = averageWinning
        d['averageLosing'] = averageLosing
        d['profitLossRatio'] = profitLossRatio
        d['posList'] = posList
        d['tradeTimeList'] = tradeTimeList
        d['resultList'] = resultList

        return d, resultList

    def insertData(self, dbName, collectionName, data):
        """插入数据库"""
        db = self.dbClient[dbName]
        db[collectionName].insert_many(data)

    @staticmethod
    def calculateMa(array, period):
        """计算均线"""
        ma = talib.SMA(array, period)
        ma = [round(value, 2) for value in ma]
        return ma

    def setCollectionName(self, dataType, idPostfix=None):
        """设置要写入的数据库集合名，由策略名+合约编号+数据类型（委托、成交、回测报告等）+回测时间构成"""
        if not idPostfix:
            idPostfix = self.backtestTimeId
        strategyName = self.strategy.className
        return '%s_%s_%s_%s' % (strategyName, self.symbol, dataType, idPostfix)

    def saveOrders(self):
        """把限价委托记录写入数据库"""
        data = []
        # 限制要写入数据库的字段
        saveItem = ['orderID', 'dt', 'orderTime', 'cancelTime', 'status', 'direction', 'offset', 'price', 'totalVolume']
        for order in self.limitOrderDict.values():
            allItem = order.__dict__
            doc = {key: value for key, value in allItem.items() if key in saveItem}
            data.append(doc)

        collectionName = self.setCollectionName('order')
        # print collectionName
        self.insertData(self.backtestResultDbName, collectionName, data)

    def saveTrades(self):
        """把成交记录写入数据库"""
        data = []
        saveItem = ['orderID', 'tradeID', 'dt', 'tradeTime', 'direction', 'offset', 'price', 'volume']
        for trade in self.tradeDict.values():
            allItem = trade.__dict__
            doc = {key: value for key, value in allItem.items() if key in saveItem}
            data.append(doc)
        # print data
        self.tradeList.extend(data)
        collectionName = self.setCollectionName('trade')
        self.insertData(self.backtestResultDbName, collectionName, data)

    def savaDailyResult(self):
        """把回测结果写入数据库"""
        df = self.calculateDailyResult()
        df, result = self.calculateDailyStatistics(df)

        # 把date数据转成datetime
        df.index = df.index.map(lambda date: datetime.combine(date, time()))
        df['datetime'] = df.index
        df.drop(['tradeList'], axis=1, inplace=True)
        # print df.head(2)
        # print 'index', type(df.index.values[0])
        # for column in df.columns:
        #     print type(df[column][0]), column, df[column][0]
        data = df.to_dict(orient='records')

        self.dailyResultList.extend(data)
        pprint(result)
        collectionName = self.setCollectionName('dailyResult')
        self.insertData(self.backtestResultDbName, collectionName, data)

    def loadDisaplayData(self):
        """从数据库读取回测期间的价格数据"""
        collection = self.dbClient[self.dbName][self.symbol]

        flt = {'datetime': {'$gte': self.dataStartDate, '$lt': self.dataEndDate}}
        cursor = collection.find(flt).sort('datetime')
        # print curso.count()
        # doc = curso.next()
        # print type(doc), doc

        data_index = []
        data_values = []
        for doc in cursor:
            data_index.append(doc['datetime'])
            oclh = [doc['open'], doc['close'], doc['low'], doc['high']]
            data_values.append(oclh)
        # print len(data_index), data_index
        # print len(data_values), data_values
        return data_index, data_values

    def loadTradePoint(self):
        """读取买卖点，并分成4个列表，供pyechart模块调用"""
        buyTradeIndex = []
        buyTradeValue = []
        sellTradeIndex = []
        sellTradeValue = []
        for trade in self.tradeList:
            if trade['direction'] == DIRECTION_LONG:
                buyTradeIndex.append(trade['dt'])
                buyTradeValue.append(trade['price'])
            else:
                sellTradeIndex.append(trade['dt'])
                sellTradeValue.append(trade['price'])
        return buyTradeIndex, buyTradeValue, sellTradeIndex, sellTradeValue

    def displayTradePoint(self, barNum):
        """显示k线数据和买卖点，可设置需要显示多少数量的k线"""
        klineBarIndex, klinBarValue = self.loadDisaplayData()
        klineBarIndex = klineBarIndex[0:barNum]
        klinBarValue = klinBarValue[0:barNum]

        closeArray = [price[1] for price in klinBarValue]
        closeArray = np.array(closeArray)
        # print closeArray
        ma1_period = 30
        ma2_period = 60
        sma1 = self.calculateMa(closeArray, ma1_period)
        sma2 = self.calculateMa(closeArray, ma2_period)

        # k线数据是不完全的，所以超出k线时间段的交易记录要排除掉
        lastDt = klineBarIndex[-1]
        count = 0
        for trade in self.tradeList:
            count += 1
            if trade['dt'] > lastDt:
                break

        buyIndex, buy, sellIndex, sell = self.loadTradePoint()

        line = Line()
        line.add(u'ma%s' % ma1_period, klineBarIndex, sma1, is_symbol_show=False)
        line.add(u'ma%s' % ma2_period, klineBarIndex, sma2, is_symbol_show=False)

        kline = Kline(u'%s分钟线' % self.symbol, title_pos=self.titlePosition)
        kline.add(u'1分钟线', klineBarIndex, klinBarValue,
                  is_datazoom_show=True,
                  datazoom_type='inside',
                  tooltip_tragger='axis',
                  tooltip_axispointer_type='cross')

        scatter = Scatter()
        scatter.add('Sell', sellIndex[0:count], sell[0:count], symbol_size=18, symbol='')
        scatter.add('Buy', buyIndex[0:count], buy[0:count], symbol_size=18, symbol='triangle')

        tradePoint = Overlap(**self.displaySetting)
        # tradePoint = Overlap()
        tradePoint.add(kline)
        tradePoint.add(line)
        tradePoint.add(scatter)
        return tradePoint

    def displayPnl(self):
        """显示净值曲线"""
        index = [result['datetime'].date() for result in self.dailyResultList]
        balance = [result['balance'] for result in self.dailyResultList]
        # print index
        # print balance

        line = Line(u'净值曲线', title_pos=self.titlePosition, **self.displaySetting)
        line.add(u'Pnl', index, balance, yaxis_min="dataMin")

        return line

    def displayDrawdown(self):
        """显示回撤曲线"""
        index = [result['datetime'].date() for result in self.dailyResultList]
        ddPercent = [round(result['ddPercent'], 2) for result in self.dailyResultList]

        line = Line(u'最大回撤比例', title_pos=self.titlePosition, **self.displaySetting)
        line.add(u'dd', index, ddPercent, yaxis_formatter='%', is_fill=True, area_color='#000', area_opacity=0.3)

        return line

    def displayDailyReturn(self):
        """显示每日收益率"""
        index = [result['datetime'].date() for result in self.dailyResultList]
        dailyReturn = [round(result['return'] * 100, 2) for result in self.dailyResultList]

        bar = Bar(u'每日收益率', title_pos=self.titlePosition, **self.displaySetting)
        bar.add(u'DailyReturn', index, dailyReturn, yaxis_formatter='%')

        return bar

    def displayPnlHist(self):
        """显示盈亏分布，pyechart没有特别好的方案支持直方图显示，用matplotlib"""
        sns.set_style('whitegrid')
        resultList = self.calculateBacktestingResult()[1]
        # print resultList
        pnl = [result.pnl for result in resultList]
        # print pnl

        figure = plt.figure()
        ax = figure.add_subplot(1, 1, 1)
        ax.hist(pnl, bins=30)
        plt.show()
        plt.savefig('hist.png')

    def displayAll(self):
        page = Page()

        pnl = self.displayPnl()
        page.add(pnl)

        ddPercent = self.displayDrawdown()
        page.add(ddPercent)

        bar = self.displayDailyReturn()
        page.add(bar)

        tradePoint = self.displayTradePoint(2000)
        page.add(tradePoint)

        page.render()


def runBacktesting(start, end, symbol):
    engine = VisualBacktestingEngine()

    engine.setStartDate(start, 1)
    engine.setEndDate(end)
    engine.setDatabase(MINUTE_DB_NAME, symbol)

    engine.setCapital(100000)
    engine.setSlippage(1)
    engine.setRate(1 / 10000)
    engine.setSize(10)
    engine.setPriceTick(1)

    setting = {}
    engine.initStrategy(DoubleMaStrategy, setting)

    engine.runBacktesting()

    engine.saveOrders()
    engine.saveTrades()
    engine.savaDailyResult()
    # engine.displayPnl()
    engine.displayPnlHist()

    engine.displayAll()


def main():
    start = '20150105'
    end = '20150311'
    symbol = 'rb1505'

    runBacktesting(start, end, symbol)


if __name__ == '__main__':
    main()
