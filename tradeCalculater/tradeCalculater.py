#!/usr/bin/env python
# encoding: utf-8

import pandas as pd
import copy
from constant import *
from datetime import datetime
from collections import OrderedDict

columnMap = {
    'account': u'资金账号',
    'trader': u'子账号',
    'tradeTime': u'成交日期',
    'direction': u'操作',
    'symbol': u'证券代码',
    'name': u'证券名称',
    'volume': u'成交数量',
    'price': u'成交价格',
    'turnOver': u'成交金额',
    'tradeID': u'成交编号',
    'orderID': u'委托编号',
    'entryPrice': u'入场价格',
    'exitPrice': u'出场价格',
    'entryDt': u'进场时间',
    'exitDt': u'出场时间',
    'stampTax': u'印花税',
    'commission': u'手续费',
    'transferFee': u'过户费',
    'slippage': u'滑点',
    'pnl': u'盈亏'
}
columnMapReverse = {v: k for k, v in columnMap.items()}

# 收市后如果还未未全部对冲的单子，在这里更新收盘价
endPriceMap = {
    '600993': 19.85,
    '000571': 5.36
}


class TradeData(object):
    def __init__(self):
        self.account = EMPTY_UNICODE
        self.trader = EMPTY_STRING

        self.tradeID = EMPTY_INT
        self.orderID = EMPTY_INT

        self.tradeTime = EMPTY_STRING
        self.dt = None
        self.direction = EMPTY_UNICODE
        self.price = EMPTY_FLOAT
        self.volume = EMPTY_INT

        self.symbol = EMPTY_STRING
        self.name = EMPTY_UNICODE


class TradingResult(object):
    def __init__(self, entryTrade, entryPrice, entryDt, exitPrice, exitDt, volume, rate, slippage, size):
        self.symbol = entryTrade.symbol
        self.name = entryTrade.name

        self.entryPrice = entryPrice
        self.exitPrice = exitPrice

        self.entryDt = entryDt
        self.exitDt = exitDt

        self.volume = volume  # 正数表示入场是多单

        self.turnOver = (self.entryPrice + self.exitPrice) * abs(volume) * size
        self.stampTax = self.turnOver * STAMP_TAX_RATE
        self.commission = self.turnOver * rate
        self.transferFee = self.turnOver * TRANSFER_FEE
        self.slippage = slippage * 2 * size * abs(volume)
        self.pnl = ((self.exitPrice - self.entryPrice) * volume * size
                    - self.stampTax - self.transferFee - self.commission - self.slippage)

    def __getitem__(self, key):
        return self.__dict__.get(key, None)


class TradeCalculator(object):
    def __init__(self):
        self.rate = 0.0003
        self.slippage = 0
        self.size = 1
        self.allTradeDict = dict()

        self.allResultDict = dict()
        # 收盘后的时间，用来计算未全部平仓的盈亏
        self.dt = datetime.now()

    def loadTradeData(self, filename):
        df = pd.read_csv(filename, encoding='gb2312')
        columns = df.columns.values

        for tradeIndex in range(len(df)):
            tradeValue = df.iloc[tradeIndex]  # 获取每条成交记录，series格式

            trade = TradeData()
            tradeInfo = dict()
            for column_zh in columns:
                column_en = columnMapReverse[column_zh]
                tradeInfo[column_en] = tradeValue[column_zh]

            # 成交数量若按成交反向设为正负数，在后面的计算会产生bug，或者计算的时候需要abs（）全部转为正数
            # if tradeInfo['direction'] == DIRECTION_SHORT:
            #     tradeInfo['volume'] = - tradeInfo['volume']
            tradeInfo['symbol'] = '%06d' % tradeInfo['symbol']
            tradeInfo['dt'] = datetime.strptime(tradeInfo['tradeTime'], '%Y-%m-%d %H:%M:%S')

            trade.__dict__ = tradeInfo

            # 把成交记录按代码分组，存入字典
            symbol = tradeInfo['symbol']
            self.allTradeDict.setdefault(symbol, []).append(trade)

            # print self.allTradeDict
            # tradeList = self.allTradeDict.values()
            # testList = [trade.__dict__ for trade in tradeList[1]]
            # testDf = pd.DataFrame(testList)
            # testDf.to_csv('test1.csv', encoding='utf-8', index=False)

    def calculateTradeResult(self, symbol):
        longTrade = []
        shortTrade = []
        tradeTimeList = []
        resultList = []

        for trade in self.allTradeDict[symbol]:
            # print 'before calculate:'
            # print trade.__dict__
            trade = copy.copy(trade)

            # 多头交易
            if trade.direction == DIRECTION_LONG:
                # 如果尚无空头交易，等于多头开仓，加入列表中，等着后面对冲计算盈亏
                if not shortTrade:
                    longTrade.append(trade)
                # 如果有空头交易，当前的多头交易是为了平掉空头，所以这里其实是计算空头的盈亏
                else:
                    while True:
                        entryTrade = shortTrade[0]
                        exitTrade = trade

                        # 清算开平仓交易
                        closedVolume = min(exitTrade.volume, entryTrade.volume)
                        result = TradingResult(entryTrade, entryTrade.price, entryTrade.dt,
                                               exitTrade.price, exitTrade.dt,
                                               -closedVolume, self.rate, self.slippage, self.size)
                        resultList.append(result)
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
                if not longTrade:
                    shortTrade.append(trade)
                else:
                    while True:
                        entryTrade = longTrade[0]
                        exitTrade = trade

                        closedVolume = min(exitTrade.volume, entryTrade.volume)
                        result = TradingResult(entryTrade, entryTrade.price, entryTrade.dt,
                                               exitTrade.price, exitTrade.dt,
                                               closedVolume, self.rate, self.slippage, self.size)
                        resultList.append(result)

                        tradeTimeList.extend([result.entryDt, result.exitDt])

                        entryTrade.volume -= closedVolume
                        exitTrade.volume -= closedVolume

                        if not entryTrade.volume:
                            longTrade.pop(0)
                        if not exitTrade.volume:
                            break
                        if exitTrade.volume:
                            if not longTrade:
                                shortTrade.append(exitTrade)
                                break
                            else:
                                pass

        # 如果存在隔夜仓
        if longTrade:
            endPrice = endPriceMap[symbol]
            for trade in longTrade:
                result = TradingResult(trade, trade.price, trade.dt, endPrice, self.dt,
                                       trade.volume, self.rate, self.slippage, self.size)
                resultList.append(result)

        if shortTrade:
            endPrice = endPriceMap[symbol]
            for trade in shortTrade:
                result = TradingResult(trade, trade.price, trade.dt, endPrice, self.dt,
                                       -trade.volume, self.rate, self.slippage, self.size)
                resultList.append(result)

        # for result in resultList:
        #     print result.__dict__
        self.allResultDict[symbol] = resultList

    def saveTradeResult(self, symbol):
        exportItem = ['symbol', 'name', 'entryDt', 'entryPrice', 'exitDt', 'exitPrice', 'volume',
                      'turnOver', 'stampTax', 'commission', 'transferFee', 'pnl']
        exportItemZh = [columnMap[item] for item in exportItem]

        outputList = []
        for result in self.allResultDict[symbol]:
            resultDict = OrderedDict()
            for item in exportItem:
                resultDict[item] = result[item]
            print resultDict
            outputList.append(resultDict)

        outputDf = pd.DataFrame(outputList)
        outputDf.columns = exportItemZh
        return outputDf
        # outputDf.to_csv('test_out.csv', encoding='utf-8', index=False)

    def mergeAllResult(self):
        initDf = pd.DataFrame()
        for symbol in self.allTradeDict.keys():
            self.calculateTradeResult(symbol)
            newDf = self.saveTradeResult(symbol)
            initDf = pd.concat([initDf, newDf])
        # print initDf
        initDf.to_csv('test_out.csv', encoding='utf-8', index=False)

if __name__ == '__main__':
    # for k, v in titleMapReverse.items():
    #     print k, v

    calculator = TradeCalculator()
    calculator.loadTradeData('20180523_20041.csv')

    # symbols = calculator.allTradeDict.keys()

    # calculator.calculateTradeResult(symbols[0])
    # calculator.saveTradeResult()
    calculator.mergeAllResult()

