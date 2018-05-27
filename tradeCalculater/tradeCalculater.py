#!/usr/bin/env python
# encoding: utf-8

import copy
import os
import pandas as pd
import tushare as ts
import xlrd
import pymongo
import matplotlib.pyplot as plt
import seaborn as sns
from constant import *
from datetime import datetime

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

        if self.volume > 0:
            self.stampTax = exitPrice * abs(volume) * size * STAMP_TAX_RATE
        else:
            self.stampTax = entryPrice * abs(volume) * size * STAMP_TAX_RATE
        self.turnOver = (self.entryPrice + self.exitPrice) * abs(volume) * size
        self.commission = self.turnOver * rate
        self.transferFee = self.turnOver * TRANSFER_FEE
        self.slippage = slippage * 2 * size * abs(volume)
        self.pnl = ((self.exitPrice - self.entryPrice) * volume * size
                    - self.stampTax - self.transferFee - self.commission - self.slippage)

    def __getitem__(self, key):
        return self.__dict__.get(key, None)


class TradePointer(object):
    def __init__(self, symbol, date):
        self.symbol = symbol
        self.symbolName = ''
        self.date = date
        self.tickData = None

        self.dbName = 'Ts_tick_Db'
        self.collectionName = 'stock_%s' % self.symbol
        self.dbClient = None

        self.displayTimeLabel = ['09:30', '10:00', '10:30', '11:00', '13:00',
                                 '13:30', '14:00', '14:30', '15:00']
        self.displayIndex = []

        self.buyTimeIndex = []
        self.sellTimeIndex = []
        self.buyPrice = []
        self.sellPrice = []

    def connectDb(self, host=None, port=None, dbName=None):
        if not dbName:
            dbName = self.dbName
        self.dbClient = pymongo.MongoClient(host=host, port=port)
        db = self.dbClient[dbName]
        return db

    def getTickData(self):
        df = None
        db = self.connectDb()

        flt = {'date': self.date}
        result = db[self.collectionName].find_one(flt)
        if not result:
            print(u'数据库无数据，正在尝试从tushare获取数据..')
            cons = ts.get_apis()
            df = ts.tick(self.symbol, conn=cons, date=self.date)
            if df is not None:
                df['date'] = self.date
                db[self.collectionName].insert_many(df.to_dict('records'))
                print(u'成功获取并写入数据库。')
            else:
                print(u'获取数据出错，可能接口问题，或者日期设置不正确。')
        else:
            print(u'数据库有匹配数据')
            data = list(db[self.collectionName].find(flt, projection={'_id': False}))
            df = pd.DataFrame(data)
            # print df

        if df is not None:
            df.drop_duplicates('datetime', keep='last', inplace=True)
            df.reset_index(inplace=True, drop=True)
            df.datetime = df.datetime.map(lambda dateStr: dateStr[-5:])
            self.tickData = df
            # print df

    def getTradeData(self, tradeDataList):
        dtList = list(self.tickData.datetime.values)
        self.symbolName = tradeDataList[0].name
        for trade in tradeDataList:
            if trade.direction == DIRECTION_LONG:
                tradeTime = trade.dt.strftime('%H:%M')
                self.buyTimeIndex.append(dtList.index(tradeTime))
                self.buyPrice.append(trade.price)
            elif trade.direction == DIRECTION_SHORT:
                tradeTime = trade.dt.strftime('%H:%M')
                self.sellTimeIndex.append(dtList.index(tradeTime))
                self.sellPrice.append(trade.price)

    def display(self, filePath):
        sns.set_style('whitegrid')
        plt.rcParams['font.sans-serif'] = ['SimHei']  # 显示中文
        plt.rcParams['axes.unicode_minus'] = False  # 显示负号

        prices = self.tickData.price

        dtList = list(self.tickData.datetime.values)
        self.displayIndex = [dtList.index(time) for time in self.displayTimeLabel]

        fig = plt.figure(figsize=(20, 8))
        ax = fig.add_subplot(1, 1, 1)

        ax.set_xticks(self.displayIndex)
        ax.set_xticklabels(self.displayTimeLabel)

        ax.plot(prices, label=u'分时价格')
        ax.scatter(self.buyTimeIndex, self.buyPrice, s=80, c='r', marker='^')
        ax.scatter(self.sellTimeIndex, self.sellPrice, s=80, c='g', marker='v')

        ax.set_title(self.symbol + self.symbolName)
        ax.legend(loc='best')

        # plt.show()
        plt.savefig(filePath, bbox_inches='tight')


class TradeCalculator(object):
    def __init__(self, sourceFileName):
        self.sourceFolder = 'source'
        self.outputFolder = 'output'
        self.imageFolder = 'image'
        self.sourceFileName = sourceFileName

        self.rate = 0.0003
        self.slippage = 0
        self.size = 1
        self.allTradeDict = dict()

        self.allResultDict = dict()
        # 收盘后的时间，用来计算未全部平仓的盈亏
        self.dt = datetime.now()

        self.createFolders()

    def createFolders(self):
        if not os.path.exists(self.outputFolder):
            os.mkdir(self.outputFolder)
        if not os.path.exists(self.imageFolder):
            os.mkdir(self.imageFolder)

    def loadXlsFile(self, filename=None):
        if not filename:
            filename = self.sourceFileName

        sourceFile = '%s/%s' % (self.sourceFolder, filename)
        data = xlrd.open_workbook(sourceFile)
        table = data.sheets()[0]
        records = [table.row_values(i) for i in range(table.nrows)]
        df = pd.DataFrame(records[1:], columns=records[0])
        # print df
        return df

    def loadCsvFile(self, filename=None):
        if not filename:
            filename = self.sourceFileName
        sourceFile = '%s/%s' % (self.sourceFolder, filename)
        df = pd.read_csv(sourceFile, encoding='gb2312')
        # print df
        return df

    def generateTradeData(self, df):
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
            if isinstance(tradeInfo['symbol'], int):
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

    def generateSingleResult(self, symbol):
        exportItem = ['symbol', 'name', 'entryDt', 'entryPrice', 'exitDt', 'exitPrice', 'volume',
                      'turnOver', 'stampTax', 'commission', 'transferFee', 'pnl']
        exportItemZh = [columnMap[item] for item in exportItem]

        outputList = []
        for result in self.allResultDict[symbol]:
            resultDict = dict()
            for item in exportItem:
                resultDict[item] = result[item]
            # print resultDict
            outputList.append(resultDict)
            # print outputList

        outputDf = pd.DataFrame(outputList)
        outputDf = outputDf[exportItem]  # 变更df顺序
        outputDf.columns = exportItemZh
        return outputDf
        # outputDf.to_csv('test_out.csv', encoding='utf-8', index=False)

    def generateAllResult(self):
        initDf = pd.DataFrame()
        for symbol in self.allTradeDict.keys():
            self.calculateTradeResult(symbol)
            newDf = self.generateSingleResult(symbol)
            initDf = pd.concat([initDf, newDf])
        # print initDf

        filenameList = self.sourceFileName.split('.')
        self.sourceFileName = filenameList[0] + '.csv'
        # print(self.sourceFileName)

        outPath = self.outputFolder + '/' + self.sourceFileName
        # print outPath
        initDf.to_csv(outPath, encoding='gb2312', index=False)

    def generateTradePointImage(self):
        for symbol in self.allTradeDict.keys():
            trades = self.allTradeDict[symbol]
            date = trades[0].dt.strftime('%Y-%m-%d')

            tradePointer = TradePointer(symbol, date)
            tradePointer.getTickData()
            tradePointer.getTradeData(trades)

            filePath = '%s/%s_%s' % (self.imageFolder, date, symbol)
            tradePointer.display(filePath)

# def t_tradeCalculator(filename):
#     calculator = TradeCalculator()
#     # df = calculator.loadCsvFile('20180524_20041.csv')
#     tradeDf = calculator.loadXlsFile(filename)
#
#     calculator.generateTradeData(tradeDf)
#
#     # symbols = calculator.allTradeDict.keys()
#
#     # calculator.calculateTradeResult(symbols[0])
#     # calculator.saveTradeResult()
#     calculator.generateAllResult()
#
#
# def t_tradePointer():
#     calculator = TradeCalculator()
#     tradeDf = calculator.loadXlsFile('20180525_20041.xls')
#     calculator.generateTradeData(tradeDf)
#     tradeData = calculator.allTradeDict['000571']
#
#     pointer = TradePointer('000571', '2018-05-25')
#     pointer.getTickData()
#     pointer.getTradeData(tradeData)
#     pointer.display()


# if __name__ == '__main__':
    # t_tradePointer()

    # t_tradeCalculator('20180525_20041.xls')
