# coding=utf-8

import os
import xlrd
import pandas as pd
import requests
import tushare as ts
import numpy as np
from datetime import datetime, timedelta
from dateutil.parser import parse
from pandas import Series, DataFrame



# ricequant支持的一次数据查询量有限，将查询期限分批到列表，循环
def sub_period(period):
    period_list = []
    while period - 2 >= 0:
        period -= 2
        period_list.append(2)
    if period == 1:
        period_list.append(period)
    return period_list


# 改进版
def sub_period_b(period, sub_period):
    quotient = period // sub_period
    reminder = period % sub_period
    period_list = [sub_period] * quotient
    if reminder != 0:
        period_list.append(reminder)
    return period_list


# 日期解析器
def date_parser(date_str=None):
    if date_str == '0' or not date_str:
        return None
    else:
        return parse(date_str)


# 从tushare获取股票信息
def get_stock_name(symbol_list):
    df = ts.get_stock_basics()
    all_names = df.name
    name_dict = {}
    for symbol in symbol_list:
        name_dict[symbol] = all_names.get(symbol)
    return name_dict


# 从ricequant网站上获取单个小期限历史市盈率和市净率df，注意此函数只能在rq网站的研究模块上运行，注意此函数不能在本地直接运行。
def get_pe_and_pb(time_period, entry_date):
    months = time_period * 12
    interval = '%dm' % months
    panel = get_fundamentals(
        query(fundamentals.eod_derivative_indicator.pe_ratio, fundamentals.eod_derivative_indicator.pb_ratio),
        entry_date=entry_date, interval=interval
    )
    return panel['pe_ratio'], panel['pb_ratio']


# 将rq网站查询到的几个历史市盈率和市净率数据合并成df，保存成csv，然后人工下载。注意次函数不能直接在本地运行。
def combine_pepb_data(time_period=10, entry_date=None):
    if not entry_date:
        now = datetime.now() - timedelta(1)
        entry_date = datetime.strftime(now, '%Y-%m-%d')
    periods = sub_period(time_period)
    pe_ratio = DataFrame()
    pb_ratio = DataFrame()
    for period in periods:
        pe_ratio_part, pb_ratio_part = get_pe_and_pb(period, entry_date)
        pe_ratio = pd.concat([pe_ratio, pe_ratio_part])
        pb_ratio = pd.concat([pb_ratio, pb_ratio_part])
        entry_date = datetime.strptime(entry_date, '%Y-%m-%d')
        entry_date = entry_date - timedelta(365 * period)
        entry_date = datetime.strftime(entry_date, '%Y-%m-%d')
    return pe_ratio, pb_ratio


# 从文件中读取股票代码
def get_code_from_singlefile(filename):
    try:
        book = xlrd.open_workbook(filename, encoding_override='utf-8')
    except:
        print('IO Error.')
    else:
        code_list = []
        table = book.sheets()[0]
        for row_index in range(1, table.nrows):
            row_value = table.row_values(row_index, start_colx=0, end_colx=1)
            code_list.extend(row_value)
        code_list = [str(code)[:6] for code in code_list[:]]
        return code_list


# 读取特定路径的所有文件，并将股票代码合并
def combine_code_from_files(directory):
    code_list = []
    filenames = os.listdir(directory)
    for filename in filenames:
        code = get_code_from_singlefile(directory + filename)
        code_list.extend(code)
    return code_list


# 获取IPO低于一年或者尚未上市的股票代码
def get_new_stocks(years=1):
    df = ts.get_stock_basics()
    df.timeToMarket = df.timeToMarket.map(str)
    df.timeToMarket = df.timeToMarket.map(date_parser)
    days = years * 365
    today = datetime.now()
    today_1year_ago = today - timedelta(days)
    df2 = df[(df.timeToMarket > today_1year_ago) | (df.timeToMarket.isnull())]
    return list(df2.index.values)


# 不需要本地文件，直接从巨潮资讯爬取上海或深圳的终止上市的股票代码
def get_terminated_stock():
    """
    Get terminated stock symbol from cninfo.com
    :return: dict{string: [list]}
    """
    stocks = {'sz': [], 'sh': []}
    for market in stocks.keys():
        url = 'http://www.cninfo.com.cn/cninfo-new/information/delistinglist-1'
        parameter = {'market': market}
        r = requests.post(url, data=parameter)
        data = r.json()
        for i in range(0, len(data)):
            symbol = data[i]['y_seccode_0007']
            stocks[market].append(symbol)
    return stocks

# 不需要本地文件，直接从巨潮资讯爬取上海或深圳的暂停上市的股票代码
def get_suspend_stock():
    """
     Get suspended stock symbol from cninfo.com
     :return: dict{string: [list]}
     """
    stocks = {'sz': [], 'sh': []}
    for market in stocks.keys():
        url = 'http://www.cninfo.com.cn/cninfo-new/information/suspendlist-1'
        parameter = {'market': market}
        r = requests.post(url, data=parameter)
        data = r.json()
        for i in range(0, len(data)):
            symbol = data[i]['seccode']
            stocks[market].append(symbol)
    return stocks

# 获取没有盈利的股票代码
def get_unprofitable_stock(filename):
    df = load_file(filename)
    df = df.T
    df.index = df.index.map(lambda x: x[:6])
    newest_pe_colname = df.columns.values[0]
    df2 = df[df[newest_pe_colname] <= 0]
    return list(df2.index.values)


# 打开csv文件
def load_file(filename):
    try:
        df = pd.read_csv(filename, encoding='utf-8', index_col=0)
    except:
        print('IO Error.Retry later.')
    else:
        return df


# 将不符合条件的股票代码汇总
def get_excluded_stocks():
    suspended_stocks = combine_code_from_files('./suspended/')
    terminated_stocks = combine_code_from_files('./terminated/')
    st_stocks_df = ts.get_st_classified()
    st_stocks = list(st_stocks_df.code.values)
    new_stocks = get_new_stocks()
    unprofitable_stocks = get_unprofitable_stock('pe_ratio.csv')
    all_excluded = set(suspended_stocks + terminated_stocks + st_stocks + new_stocks + unprofitable_stocks)
    return [str(i) for i in all_excluded]


# 排除不符合条件的股票
def exclude_stock(filename):
    df = load_file(filename)
    df = df.T
    df.index = df.index.map(lambda x: x[:6])
    excluded_list = get_excluded_stocks()
    mask = df.index.isin(excluded_list)
    mask = np.array([not i for i in mask])
    df2 = df[mask]
    return df2


# 计算当前市盈率和市净率位于某个区间低位的股票
def select_stocks(df, output_filename, prefix, threshold=0.1, std=50):
    df2 = df[df.std(axis=1) < std]
    f = lambda x: min(x) if min(x) > 0 else 0
    new_df = DataFrame(index=df2.index)
    new_df['name'] = Series(get_stock_name(df2.index))
    new_df[prefix + '_min'] = df2.apply(f, axis=1)
    new_df[prefix + '_max'] = df2.max(axis=1)
    new_df[prefix + '_newest'] = df2.iloc[:, 0]
    position = (new_df[prefix + '_newest'] - new_df[prefix + '_min']) / (
    new_df[prefix + '_max'] - new_df[prefix + '_min'])
    new_df[prefix + '_position'] = position
    selected_df = new_df[new_df[prefix + '_position'] < threshold]
    selected_df.to_csv(output_filename)
    return selected_df


if __name__ == '__main__':
    print 'Get Pe data...'
    pe_data = exclude_stock('pe_ratio.csv')
    print 'Get Pb data...'
    pb_data = exclude_stock('pb_ratio.csv')
    print 'Generating pe data...'
    pe_df = select_stocks(pe_data, 'pe_selected.csv', prefix='pe')
    print 'Generating pb data...'
    pb_df = select_stocks(pb_data, 'pb_selected.csv', prefix='pb', threshold=0.1, std=3)
    print 'Merging pb and pe...'
    pe_and_pb = pd.merge(pe_df, pb_df)
    pe_and_pb.to_csv('pe_and_pb.csv')
    print 'Complete.'
