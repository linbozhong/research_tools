# coding:utf-8

import os
import pymongo
import pandas as pd
from datetime import datetime, timedelta
from copy import copy



class Validator(object):
    """
    数据校验器，用于对比两套数据的差异。
    """

    def __init__(self):
        self.mongoHost = 'localhost'
        self.mongoPort = 27017
        self.dbName = 'VnTrader_1Min_Db'
        self.dbNameComp = 'VnTrader_1Min_Db_Compare'

        self.mongoClient = None
        self.db = None

    def connetDb(self, mongoHost=None, mongoPort=None):
        if not mongoHost:
            mongoHost = self.mongoHost
        if not mongoPort:
            mongoPort = self.mongoPort
        self.mongoClient = pymongo.MongoClient(host=mongoHost, port=mongoPort)
        self.db = self.mongoClient[self.dbName]
        self.dbComp = self.mongoClient[self.dbNameComp]

    def loadData(self, dbName, symbol, startDate, endDate):
        db = self.mongoClient[dbName]
        col = db[symbol]

        startDt = datetime.strptime(startDate, '%Y-%m-%d')
        endDt = datetime.strptime(endDate, '%Y-%m-%d')
        flt = {'datetime': {'$gte': startDt, '$lt': endDt}}

        data = list(col.find(flt).sort('datetime', pymongo.ASCENDING))
        # 设置要对比的项目，去掉多余的列
        compareItems = ['datetime', 'symbol', 'high', 'low', 'open', 'close', 'openInterest', 'volume']
        return pd.DataFrame(data)[compareItems]

    def mergeData(self, symbol, startDate, endDate):
        # 备用数据库的合约代码命名格式可能不一样，比如rb1810和SHFE.rb1810，先检索备用数据库是否有同合约的数据。
        colNames = self.mongoClient[self.dbNameComp].collection_names()
        symbolCom = None
        for name in colNames:
            if symbol in name:
                symbolCom = name
                break
        if not symbolCom:
            print(u"备用数据库没有找到可对比的合约")
            return

        dataLeft = self.loadData(self.dbName, symbol, startDate, endDate)
        dataRight = self.loadData(self.dbNameComp, symbolCom, startDate, endDate)
        df = pd.merge(dataLeft, dataRight, how='outer', on='datetime', suffixes=('_l', '_comp'))
        # df.to_csv('data/%s_merge.csv' % symbol)
        return df

    def compareData(self, df):
        # 筛选出OHCL存在不同值的记录
        mask = ((df.high_l == df.high_comp) &
                (df.low_l == df.low_comp) &
                (df.close_l == df.close_comp) &
                (df.open_l == df.open_comp))
        # 用~符号反转mask
        df = copy(df[~mask])

        # 把不同值的项目做减法计算
        items = ['close', 'high', 'low', 'open', 'openInterest', 'volume']
        diff_items = []
        result = {}
        print(u"\t统计结果:\n %s" % ('=' * 50))
        for item in items:
            newItem = item + '_diff'
            diff_items.append(newItem)
            df[newItem] = df[item + '_l'] - df[item + '_comp']
            result[newItem + '_count'] = df[newItem][df[newItem] != 0].count()
            result[newItem + '_std'] = df[newItem].std()
            result[newItem + '_mean'] = df[newItem].mean()
            print(u"项目%s有%s项不一致，平均差：%.2f 标准差为：%.2f" % (item,
                                                       result[newItem + '_count'],
                                                       result[newItem + '_mean'],
                                                       result[newItem + '_std']))

        if not os.path.exists('./data/'):
            os.mkdir('./data/')
        df.to_csv('./data/%s_diff.csv' % df['symbol_l'].values[0])

    def setDbName(self, dbName, dbNameComp):
        self.dbName = dbName
        self.dbNameComp = dbNameComp

    def changeDatetime(self, dbName=None):
        """
        如果数据库bar时间不是统一的，可以用此方法调整。数据量大时有些开销，建议入库的时候就做好统一，或者需要调用的时候再计算。
        datetime是索引,如果直接更新，因为存在和已有记录重合的key，就会报错
        这里采取先下载数据修改，然后删除数据库数据，再写入。
        """

        if not dbName:
            dbName = self.dbNameComp

        db = self.mongoClient[dbName]
        names = db.collection_names()

        print(u"开始更改时间，需要更改的合约：%s" % names)
        for colName in names:
            col = db[colName]
            dataList = list(col.find().sort('datetime', pymongo.ASCENDING))
            for data in dataList:
                # 通过加或减1分钟，来统一时间显示
                data['datetime'] += timedelta(minutes=1)
                data['time'] = data['datetime'].strftime('%H:%M:%S')
            db.drop_collection(colName)
            col.insert_many(dataList)
            print(u"合约%s变更完成" % colName)
        print(u"全部合约时间修改完成！")


if __name__ == '__main__':
    validator = Validator()
    validator.connetDb()

    # validator.changeDatetime()
    # validator.loadData('VnTrader_1Min_Db', 'rb1810', '2018-04-14', '2018-04-18')
    df = validator.mergeData('rb1810', '2018-04-01', '2018-05-12')
    validator.compareData(df)
