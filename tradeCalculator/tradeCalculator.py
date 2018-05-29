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

        # x轴index和时间标签的映射
        self.displayTimeLabel = ['09:30', '10:00', '10:30', '11:00', '13:00',
                                 '13:30', '14:00', '14:30', '15:00']
        self.displayIndex = []

        # 成交时间序列和成交价格序列
        self.buyTimeIndex = []
        self.sellTimeIndex = []
        self.buyPrice = []
        self.sellPrice = []

    def setDbName(self, dbName):
        self.dbName = dbName

    def setCollectionName(self, colName):
        self.collectionName = colName

    def connectDb(self, host=None, port=None, dbName=None):
        if not dbName:
            dbName = self.dbName
        self.dbClient = pymongo.MongoClient(host=host, port=port)
        db = self.dbClient[dbName]
        return db

    def getTickData(self):
        """
        通过tushare获取分时数据，并存入数据库，避免后面运行重复获取。
        """
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

        if df is not None:
            df.drop_duplicates('datetime', keep='last', inplace=True)
            df.reset_index(inplace=True, drop=True)
            df.datetime = df.datetime.map(lambda dateStr: dateStr[-5:])
            self.tickData = df
            return df

    def getTradeData(self, tradeDataList):
        """
        从tradeData对象列表中获取成交信息（时间、方向和价格）
        """
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
        try:
            self.displayIndex = [dtList.index(time) for time in self.displayTimeLabel]
        except ValueError:
            print(u'找不到要显示的时间点对应的数据，数据可能不完整！')

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

    def setSourceFolder(self, folderName):
        self.sourceFolder = folderName

    def setOutputFolder(self, folderName):
        self.outputFolder = folderName

    def setImageFolder(self, folderName):
        self.imageFolder = folderName

    def setSourceFileName(self, fileName):
        self.sourceFileName = fileName

    def createFolders(self):
        if not os.path.exists(self.outputFolder):
            os.mkdir(self.outputFolder)
        if not os.path.exists(self.imageFolder):
            os.mkdir(self.imageFolder)

    def loadXlsFile(self, filename=None):
        """
        把xls表格文件转化为DataFrame对象
        """
        if not filename:
            filename = self.sourceFileName

        sourceFile = '%s/%s' % (self.sourceFolder, filename)
        data = xlrd.open_workbook(sourceFile)
        table = data.sheets()[0]
        records = [table.row_values(i) for i in range(table.nrows)]
        df = pd.DataFrame(records[1:], columns=records[0])
        return df

    def loadCsvFile(self, filename=None):
        if not filename:
            filename = self.sourceFileName
        sourceFile = '%s/%s' % (self.sourceFolder, filename)
        df = pd.read_csv(sourceFile, encoding='gb2312')
        # print df
        return df

    def generateTradeData(self, df):
        """
        生成tradeData对象，并以股票代码分组，存入allTradeDict
        """

        # 获取中文列名
        columns = df.columns.values

        for tradeIndex in range(len(df)):
            tradeSeries = df.iloc[tradeIndex]  # 获取每条成交记录，series格式

            trade = TradeData()
            tradeInfo = dict()
            for column_zh in columns:
                column_en = columnMapReverse[column_zh]
                tradeInfo[column_en] = tradeSeries[column_zh]

            if isinstance(tradeInfo['symbol'], int):
                tradeInfo['symbol'] = '%06d' % tradeInfo['symbol']

            tradeInfo['dt'] = datetime.strptime(tradeInfo['tradeTime'], '%Y-%m-%d %H:%M:%S')

            trade.__dict__ = tradeInfo

            # 把成交记录按代码分组，存入字典
            symbol = tradeInfo['symbol']
            self.allTradeDict.setdefault(symbol, []).append(trade)

    def calculateTradeResult(self, symbol):
        """
        通过tradeData对象计算交易盈亏（计算方法来自vnpy），并以股票代码分组存入allResultDict
        """
        longTrade = []
        shortTrade = []
        tradeTimeList = []
        resultList = []

        for trade in self.allTradeDict[symbol]:
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

        self.allResultDict[symbol] = resultList

    def generateSingleResult(self, symbol):
        """
        把单个股票的tradeResult对象按需要输出的项目转化成DataFrame对象
        """

        # 可以指定要输出的项及其顺序
        exportItem = ['symbol', 'name', 'entryDt', 'entryPrice', 'exitDt', 'exitPrice', 'volume',
                      'turnOver', 'stampTax', 'commission', 'transferFee', 'pnl']
        exportItemZh = [columnMap[item] for item in exportItem]

        outputList = []
        for result in self.allResultDict[symbol]:
            resultDict = dict()
            for item in exportItem:
                resultDict[item] = result[item]
            outputList.append(resultDict)

        outputDf = pd.DataFrame(outputList)
        outputDf = outputDf[exportItem]  # 变更df顺序
        outputDf.columns = exportItemZh  # 列名转化为中文
        return outputDf
        # outputDf.to_csv('test_out.csv', encoding='utf-8', index=False)

    def generateAllResult(self):
        """
        把多个股票的交易盈亏DataFrame对象合并为一个df，并输出成csv文件
        """
        initDf = pd.DataFrame()
        for symbol in self.allTradeDict.keys():
            self.calculateTradeResult(symbol)
            newDf = self.generateSingleResult(symbol)
            initDf = pd.concat([initDf, newDf])

        filenameList = self.sourceFileName.split('.')
        self.sourceFileName = filenameList[0] + '.csv'

        outPath = self.outputFolder + '/' + self.sourceFileName
        initDf.to_csv(outPath, encoding='gb2312', index=False)

    def generateTradePointImage(self):
        """
        生成成交记录点位图
        """
        for symbol in self.allTradeDict.keys():
            trades = self.allTradeDict[symbol]
            date = trades[0].dt.strftime('%Y-%m-%d')

            tradePointer = TradePointer(symbol, date)
            tradePointer.getTickData()
            tradePointer.getTradeData(trades)

            filePath = '%s/%s_%s' % (self.imageFolder, date, symbol)
            tradePointer.display(filePath)
