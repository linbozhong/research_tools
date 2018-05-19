# coding:utf-8

"""
jaqs的数据api期货的1分钟线数据从2012年开始支持。
"""

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


class JaqsDataDownloader(object):
    MAIN_CONTRACT_DB_NAME = 'VnTrader_MainContract'

    def __init__(self):
        self.setting = None
        self.contractDict = None
        self.api = None
        self.dbClient = None
        self.db = None

        self.symbols = []
        self.taskList = []
        self.finishedSymbols = []  # 学习协程使用的，普通和多线程下载用不上。

        # 连接出错重试设置
        self._retry = 0
        self._waitTime = 10

        # 初始化设置
        self._loadSetting()
        self._loadContracts()

    def _loadSetting(self):
        """
        默认载入json文件的合约列表
        """

        with codecs.open('config.json', 'r', 'utf-8') as f:
            self.setting = json.load(f)
            self.symbols = self.setting['SYMBOLS']

    def _loadContracts(self):
        """
        jaqs的数据api合约代码是基础代码加上jaqs设置的市场编号，如'cu1805.SHF'。
        将合约与市场的映射关系保存在json文件上，有新合约上市可以在json文件上修改 。
        """

        with codecs.open('contract.json', 'r', 'utf-8') as f:
            self.contractDict = json.load(f)

    def _symbolConvert(self, symbol):
        """
        把合约代码格式转换成jaqs的合约代码格式。
        """

        symbolAlphabet = re.match(r'^([A-Z]|[a-z])+', symbol).group()
        for market, symbols in self.contractDict.items():
            if symbolAlphabet in symbols:
                return '%s.%s' % (symbol, market)
        print(u'%s-目前期货交易所无此合约.' % symbol)

    def _generateVtBar(self, symbol, data):
        """
        生成vtBar（vnpy的bar类对象）
        """
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
        """
        # 登录jaqs的api。需要账号和token，可在官网上注册。
        """
        print(u'正在登陆JaqsAPI.')
        self.api = DataApi(addr=self.setting['ADDR'])
        self.api.login(self.setting['PHONE'], self.setting['TOKEN'])

    def connectDb(self, dbName=MINUTE_DB_NAME):
        """
        连接数据库。
        """
        self.dbClient = MongoClient(self.setting['MONGO_HOST'], self.setting['MONGO_PORT'])
        self.db = self.dbClient[dbName]
        # print(self.db.collection_names())

    def setSymbols(self, symbolsList):
        """
        设置要批量下载的合约列表，覆盖配置文件合约代码的设置
        """
        self.symbols = symbolsList

    def getData(self, symbol, *args, **kwargs):
        """
        调用jaqs的api方法，如果传入错误的参数，可能会发生阻塞或异常，如果出错，可以检查传入参数是否正确。
        **kwargs
        :param symbol: 交易合约代码，如rb1810
        :param args: 其他支持的参数可以在官网查询jaqs的api文档，最常用的是trade_date，可以支持自定义要下载的交易日。
        :param kwargs: 同上
        :return:
        """

        symbol = self._symbolConvert(symbol)
        df, msg = self.api.bar(symbol=symbol, freq="1M", *args, **kwargs)
        # print df, msg
        return df

    def getTradingday(self, startDate, endDate=None):
        """
        :param startDate: 开始日期，格式YYYY-MM-DD
        :param endDate: 结束日期，格式同上
        :return: 交易日列表，格式同上
        """

        # jaqs交易日api传入参数的日期格式是YYYYMMDD，需要先转换
        if not endDate:
            endDate = datetime.now().strftime('%Y%m%d')
        else:
            endDate = '%s%s%s' % (endDate[0:4], endDate[5:7], endDate[8:10])
        startDate = '%s%s%s' % (startDate[0:4], startDate[5:7], startDate[8:10])

        flt = 'start_date=%s&end_date=%s' % (startDate, endDate)
        df, msg = self.api.query(view='jz.secTradeCal', filter=flt)
        dates = df['trade_date'].values
        dates = map(lambda dateStr: '%s-%s-%s' % (dateStr[0:4], dateStr[4:6], dateStr[6:8]), dates)
        return dates

    def getMainContract(self, symbol, startDate='2012-01-01', endDate=None):
        """
        获取从2012年1月1日开始的历史主力合约列表（jaqs数据从2012年开始）。
        jaqs不提供历史主力合约数据，本方法依赖本地数据库，需要先用附带的模块从ricequant获取数据并入库。
        :param symbol: 合约字母，不包含日期，如螺纹钢是rb
        :param startDate: 开始日期，格式YYYY-MM-DD
        :param endDate: 结束日期，格式同上，默认今日
        :return: tuple（实际合约代码，日期）
        """

        if not endDate:
            endDate = datetime.now()
        else:
            endDate = datetime.strptime(endDate, '%Y-%m-%d')
        startDate = datetime.strptime(startDate, '%Y-%m-%d')
        # print startDate, endDate

        db = self.dbClient[self.MAIN_CONTRACT_DB_NAME]
        # print db.collection_names()

        # 搜索合约所在的交易所
        exchange = None
        for colName in db.collection_names():
            doc = db[colName].find_one()
            if symbol in doc.keys():
                exchange = colName
        # print(exchange)

        if exchange:
            flt = {'date': {'$gte': startDate, '$lt': endDate}}
            projection = {'date': True, '_id': False, symbol: True}
            cursor = db[exchange].find(flt, projection).sort('date', ASCENDING)
            docs = list(cursor)
            docs = [(doc[symbol].lower(), doc['date'].strftime('%Y-%m-%d')) for doc in docs]
            # print(docs)
            return docs
        else:
            print(u'数据库找不该合约的数据')

    def getExistedDay(self, symbol):
        """
        查找数据库已经存在的数据的日期，避免重复下载
        """

        col = self.db[symbol]
        docs = list(col.find({}, {'datetime': True, '_id': False}).sort('datetime', ASCENDING))
        dateList = [doc['datetime'].strftime('%Y-%m-%d') for doc in docs]

        # 如果下载过程出错，已经保存好的数据最后一天很可能不是完整的，所以数据库最后一天从已有数据集合删除，重新下载。
        lastDay = dateList[-1]
        dates = set(dateList)
        dates.remove(lastDay)
        return dates

    def saveToDb(self, symbol, overwrite=True, *args, **kwargs):
        """
        将单一合约分钟线数据存入数据库。
        默认当前交易日，可通过trade_date='2018-02-03'指定交易日。
        默认覆盖已有数据库资料，overwrite设为
        :param symbol: 交易合约代码，如rb1810
        :param overwrite: 是否覆盖数据库已有数据，默认是True（覆盖）。False：若数据库存在重复的日期，跳过。
        :param args: jaqs其他支持的参数通过这里传入，请查询官方文档。
        :param kwargs: jaqs其他支持的参数通过这里传入，请查询官方文档。
        :return:
        """

        # 如果当前日期的数据在数据已经存在，并且模式为不覆盖，则忽略任务
        if not overwrite and 'trade_date' in kwargs:
            qryDate = kwargs['trade_date']
            existedDate = self.getExistedDay(symbol)
            if qryDate in existedDate:
                print(u'数据库已存在该日期数据，忽略')
                return

        # 调用jaqs的api
        data = self.getData(symbol, *args, **kwargs)
        if data.empty:
            print (u'无数据！可能是节假日或超过jaqs数据库的保存范围。')
            return

        col = self.db[symbol]
        col.create_index([('datetime', ASCENDING)], unique=True)
        dataStart = None
        dataEnd = None

        for i in range(len(data)):
            bar = self._generateVtBar(symbol, data.iloc[i])
            document = bar.__dict__
            flt = {'datetime': bar.datetime}
            col.replace_one(flt, document, upsert=True)
            if i == 0:
                dataStart = bar.datetime
            elif i == len(data) - 1:
                dataEnd = bar.datetime

        # 判断当前任务是否完成，协程方式使用，普通和多线程方式用不上
        dateStr = '%s' % dataEnd
        missionID = '.'.join([dateStr[0:10], symbol])
        self.finishedSymbols.append(missionID)

        print(u'合约%s下载完成。日期区间：%s - %s' % (symbol, dataStart, dataEnd))

    def downloadAllSymbol(self, *args, **kwargs):
        """
        多合约单日下载，适用于每日收市后的数据更新，默认当前交易日，可通过trade_date='2018-02-03'指定交易日。
        """

        self.taskList.extend(self.symbols)
        print(u'开始下载所有合约分钟线数据，任务列表：')
        print(self.taskList)

        # 如果网络连接出错,会重新连接，重试3次。
        # 如果不是网络连接问题，请仔细检查传入jaqsApi的参数是否正确。
        while self.taskList and self._retry <= 3:
            # 重试计时
            if self._retry > 0:
                print(u'%s秒后开始重试' % self._waitTime)
                time.sleep(self._waitTime)

            for symbol in self.taskList:
                try:
                    self.saveToDb(symbol, *args, **kwargs)
                except:
                    self._retry += 1
                    self._waitTime += 10
                    traceback.print_exc()
                else:
                    self.taskList.remove(symbol)

        # 达到最大重试次数后，检查任务完成度
        if not self.taskList:
            print(u'全部合约分钟线数据下载完成')
        else:
            print(u'下载失败，达到最大重试次数。未完成合约：%s' % self.taskList)


if __name__ == '__main__':
    # 测试

    # 创建下载器对象、连接jaqs的api和本地数据库
    dl = JaqsDataDownloader()
    dl.loginJaqsApp()
    dl.connectDb()

    dl.getExistedDay('rb1810')

    # 测试数据api
    # df = dl.getData('rb1810', trade_date='2018-05-09')
    # df = dl.getData('rb1810', trade_date='2018-05-10')
    # df = dl.getData('rb1810')
    #
    # df.to_csv('test.csv')
    # print df

    # 下载单一合约当日分钟数据并存入数据库
    # dl.saveToDb('rb1810')
    # dl.saveToDb('AP810')
    # dl.saveToDb('MA809')

    # dl.saveToDb('rb1810', trade_date='2018-04-13')
    # dl.saveToDb('rb1810', trade_date='2018-04-13', overwrite=False)
    # dl.saveToDb('rb1801', trade_date='2017-09-12')
    # dl.saveToDb('rb1205', trade_date='2011-12-30')
    # dl.saveToDb('cu1203', trade_date='2012-01-04')

    # 批量下载当前交易日数据
    # dl.downloadAllData()

    # 指定要批量下载的合约
    # dl.setSymbols(['rb1810', 'm1809', 'TA809'])
    # dl.setSymbols(['rb1810'])
    # dl.downloadAllData(trade_date='2018-05-10')
    # dl.downloadAllData(trade_date='2018-05-08')

    # 下载指定日期的合约
    # dl.downloadAllData(trade_date='2018-05-09')

    # 获取交易日历
    # tdlist = dl.getTradingday('20180401')
    # tdlist = dl.getTradingday('20180401', '20180501')
    # tdlist = dl.getTradingday('2018-04-01', '2018-05-01')
    # print(tdlist)

    # dl.getMainContract('rb', '2018-01-01', '2018-02-02')
