#!/usr/bin/env python
# encoding: utf-8


"""
期货历史主力合约获取思路：
1、从ricequant（米筐web量化交易平台）的数据api获取数据，因为ricequant的api没有对外开放，必须在它的研究环境下才能调用，但是可以生成csv下载到本地。
2、读取下载好的csv文件，按市场字母缩写划分数据集合（数据表），存入mongoDB

========  以下代码无法在本地运行，请在ricequant的研究环境下运行 ============

    import pandas as pd

    def get_contracts():
      # 获取今日的交易合约并去重
      df = all_instruments(type="Future")
      df = df.drop_duplicates(['underlying_symbol'])
      df = df[['exchange', 'underlying_symbol']]
      return df

    def get_contracts_dict():
      # 把合约按市场分类，合约代码针对部分交易所转换为字母小写，返回字典
      df = get_contracts()
      symbols = {}
      for i in range(len(df)):
        key = df.iloc[i].exchange
        value = df.iloc[i].underlying_symbol
        if key not in ['CZCE', 'CFFEX']:
          value = value.lower()
        symbols.setdefault(key, []).append(value)
      return symbols

    def get_data():
      contracts_dict = get_contracts_dict()

      # 要先初始化df容器，因为空df无法与其他df做merge操作
      main_hist = pd.DataFrame()
      fg = get_dominant_future('FG')
      main_hist['FG'] = fg
      main_hist['date'] = main_hist.index
      main_hist['exchange'] = 'CZCE'

      # 遍历合约字典，merge数据
      for exchange, symbols in contracts_dict.items():
        for symbol in symbols:
          # 跳过用来初始化的合约
          if symbol == 'FG':
            continue
          df_symbol = pd.DataFrame()
          series = get_dominant_future(symbol.upper())
          df_symbol[symbol] = series
          df_symbol['date'] = df_symbol.index
          df_symbol['exchange'] = exchange
          main_hist = pd.merge(main_hist, df_symbol, how='outer')

      main_hist.to_csv('main_contract_history.csv')

    # ====== 运行分割线 =========
    # get_contracts()
    # get_contracts_dict()
    get_data()

========  代码结束分割线 ============

下载好的csv文件处理流程：
1、读取文件，把date列转换为日期格式
2、筛选出某个市场的数据，去掉所有数据都为空的列（即去掉不属于这个市场的合约），根据日期进行升序排列。
3、转换为dict，并存入mongo数据库


"""

import pandas as pd
import pymongo


def load_data(filename):
    try:
        print(u'正在读取数据..')
        df = pd.read_csv(filename, parse_dates=['date'], index_col=0)
        return df
    except IOError:
        print(u'文件读取出错，稍后重试')


def connect_db(mongo_host, mongo_port, db_name):
    client = pymongo.MongoClient(host=mongo_host, port=mongo_port)
    db = client[db_name]
    return db


def save_single_market(data_df, exchange, db):
    """
    处理csv文件并存入数据库
    """

    print(u'正在调整数据..')
    data_df = data_df[data_df.exchange == exchange]
    data_df = data_df.dropna(axis=1, how='all')
    data_df = data_df.sort_values(by=['date'])
    doc_list = data_df.to_dict('records')
    db[exchange].create_index([('date', pymongo.ASCENDING)], unique=True)
    print(u'正在写入数据库..')
    for doc in doc_list:
        flt = {'date': doc['date']}
        db[exchange].replace_one(flt, doc, upsert=True)
    print(u'交易所%s: 历史主力合约列表保存完成。' % exchange)


def main():
    # 参数配置
    filename = 'main_contract_history.csv'
    mongo_host = 'localhost'
    mongo_port = 27017
    db_name = 'VnTrader_MainContract'
    exchange_list = ['CFFEX', 'CZCE', 'DCE', 'INE', 'SHFE']

    # 读取数据、连接数据库
    data_df = load_data(filename)
    db = connect_db(mongo_host, mongo_port, db_name)

    # 全部写入数据
    # save_single_market(data_df, 'CZCE', db)
    for exchange in exchange_list:
        save_single_market(data_df, exchange, db)


if __name__ == '__main__':
    main()
