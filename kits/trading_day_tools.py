# coding=utf-8
# @author: linbozhong


import os
import tushare as ts
import pandas as pd
from datetime import date, datetime, timedelta


def is_newest(filename=None):
    """
    Judge whether a given trading day file is newest.
    :param filename: string
    :return: Bool
    """

    if not filename:
        filename = 'tradedays.csv'
    current_year = date.today().year
    try:
        df = pd.read_csv(filename)
    except IOError:
        print 'IO Error. Retry please.'
    else:
        last_date = df.iloc[-1, 1]
        last_year = int(last_date[:4])
        return last_year == current_year


def get_trading_day_cal(filename=None):
    """
    Get trading day calender from tushare module and write into csv file.
    :param filename: string
    :return:
    """

    if not filename:
        filename = 'tradedays.csv'
    print 'Downloading ...'
    df = ts.trade_cal()
    print 'Download complete, Writing to File...'
    try:
        df.to_csv(filename)
        print 'Write Finished.'
    except IOError:
        print 'IO Error '


def is_trading_day(date_str, filename=None):
    """
    Judge whether a given date is a trading day via a trading day file.
    :param date_str: string format:YYYY-MM-DD
    :param filename: string
    :return: Bool
    """

    if not filename:
        filename = 'tradedays.csv'
    if not os.path.exists(filename) or not is_newest(filename):
        get_trading_day_cal(filename)
    else:
        try:
            df = pd.read_csv(filename, index_col=1)
        except IOError:
            print 'IO Error Retry'
        else:
            return bool(df.loc[date_str, 'isOpen'])


def get_pre_next_trading_day(date_str, mode='next'):
    """
    Get previous or next trading day base on a given date from a trading calender file.
    :param date_str: String format:YYYY-MM-DD
    :param mode: String Option:next or pre
    :return: date:String format:YYYY-MM-DD
    """
    date_format = '%Y-%m-%d'
    source_date = datetime.strptime(date_str, date_format)
    if mode == 'pre':
        target_date = source_date - timedelta(1)
    else:
        target_date = source_date + timedelta(1)
    target_date_str = datetime.strftime(target_date, date_format)

    # if given day is not trading day. keep add or subtract one day until get trading day.
    while not is_trading_day(target_date_str):
        target_date_str = get_pre_next_trading_day(target_date_str, mode=mode)
    return target_date_str
