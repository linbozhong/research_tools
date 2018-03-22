# coding:utf-8

import json
import codecs
import re
import traceback
import time
from datetime import datetime
from pymongo import MongoClient, ASCENDING

from jaqs.data import DataApi
from vnpy.trader.vtObject import VtBarData
from vnpy.trader.app.ctaStrategy.ctaBase import MINUTE_DB_NAME


class DataDownloader(object):
    def __init__(self):
        self.setting = None
        self.contractDict = None
        self.api = None
        self.dbClient = None
        self.db = None

        self.symbols = []
        self.taskList = []

        # 连接出错重试设置
        self.__retry = 0
        self.__waitTime = 10

        # 初始化设置
        self.__loadSetting()
        self.__loadContracts()

    def __loadSetting(self):
        with codecs.open('config.json', 'r', 'utf-8') as f:
            self.setting = json.load(f)
            self.symbols = self.setting['SYMBOLS'] # 默认载入json文件的合约列表

    def __loadContracts(self):
        # jaqs的数据api合约代码是基础代码加上jaqs设置的市场编号，如'cu1805.SHF'。
        # 将合约与市场的映射关系保存在json文件上，有新合约上市可以在json文件上修改 。

        with codecs.open('contract.json', 'r', 'utf-8') as f:
            self.contractDict = json.load(f)

    def __symbolConvert(self, symbol):
        # 合约代码转换方法。

        symbolAlphabet = re.match(r'^([A-Z]|[a-z])+', symbol).group()
        for market, symbols in self.contractDict.items():
            if symbolAlphabet in symbols:
                return '%s.%s' % (symbol, market)
        print(u'%s-目前期货交易所无此合约.' % symbol)

    def __generateVtBar(self, symbol, data):
        # 生成vtBar。

        bar = VtBarData()
        bar.symbol = symbol
        bar.vtSymbol = symbol
        bar.open = float(data['open'])
        bar.high = float(data['high'])
        bar.low = float(data['low'])
        bar.close = float(data['close'])
        bar.volume = int(data['volume'])
        bar.openInterest = int(data['oi'])
        dt_str = '%08d %06d' % (data['date'], data['time'])
        bar.datetime = datetime.strptime(dt_str, '%Y%m%d %H%M%S')
        bar.date = bar.datetime.strftime('%Y%m%d')
        bar.time = bar.datetime.strftime('%H:%M:%S')
        return bar

    def loginJaqsApp(self):
        # 登录jaqs的api。需要账号和token，可在官网上注册。

        self.api = DataApi(addr=self.setting['ADDR'])
        self.api.login(self.setting['PHONE'], self.setting['TOKEN'])

    def connectDb(self):
        # 连接数据库。
        self.dbClient = MongoClient(self.setting['MONGO_HOST'], self.setting['MONGO_PORT'])
        self.db = self.dbClient[MINUTE_DB_NAME]

    def setSymbols(self, symbolsList):
        # 传入要批量下载的合约列表
        self.symbols = symbolsList


    def getData(self, symbol, **kwargs):
        # jaqs的api如果传入错误的参数，会发生阻塞或异常，如果出错，可以检查传入参数是否正确。
        # **kwargs支持的参数可以在官网查询jaqs的api文档，最常用的是trade_date，可以支持自定义要下载的交易日。

        symbol = self.__symbolConvert(symbol)
        df, msg = self.api.bar(symbol=symbol, freq="1M", **kwargs)
        return df

    def saveToDb(self, symbol, **kwargs):
        # 将单一合约分钟线数据存入数据库。默认当前交易日，可通过trade_date='2018-02-03'指定交易日。

        data = self.getData(symbol, **kwargs)
        col = self.db[symbol]
        col.create_index([('datetime', ASCENDING)], unique=True)
        dataStart = None
        dataEnd = None

        for i in range(len(data)):
            bar = self.__generateVtBar(symbol, data.iloc[i])
            document = bar.__dict__
            flt = {'datetime': bar.datetime}
            col.replace_one(flt, document, upsert=True)
            if i == 0:
                dataStart = bar.datetime
            elif i == len(data) - 1:
                dataEnd = bar.datetime

        print(u'合约%s下载完成。日期区间：%s - %s' % (symbol, dataStart, dataEnd))

    def downloadAllData(self, **kwargs):
        # 批量下载多合约指定日期的分钟数据，默认当前交易日可通过trade_date='2018-02-03'指定交易日。

        self.taskList.extend(self.symbols)
        print(u'开始下载所有合约分钟线数据，任务列表：')
        print self.taskList

        # 如果网络连接出错,会重新连接，重试3次。
        # 如果不是网络连接问题，请仔细检查传入jaqsApi的参数是否正确。
        while self.taskList and self.__retry <= 3:
            # 重试计时
            if self.__retry > 0:
                print(u'%s秒后开始重试' % self.__waitTime)
                time.sleep(self.__waitTime)

            for symbol in self.symbols:
                if symbol in self.taskList:
                    try:
                        self.saveToDb(symbol, **kwargs)
                    except:
                        self.__retry += 1
                        self.__waitTime += 10
                        traceback.print_exc()
                    else:
                        self.taskList.remove(symbol)

        # 达到最大重试次数后，检查任务完成度
        if not self.taskList:
            print(u'全部合约分钟线数据下载完成')
        else:
            print(u'下载失败，达到最大重试次数。未完成合约：%s' % self.taskList)
