# coding:utf-8

import traceback
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from turtleEngine import BacktestingEngine


def get_instrument():
    df = pd.read_csv('instrument.csv')
    df['listDate'] = df['listDate'].map(lambda date_string: datetime.strptime(str(date_string), '%Y%m'))
    return df


def select_instrument(start, exchange='all', exclude=None):
    df = get_instrument()
    df = df[df.listDate < start]
    if exchange != 'all':
        try:
            df = df[df.exchange == exchange]
        except:
            traceback.print_exc()
    if exclude is not None:
        mask = ~df.vtSymbol.isin(exclude)
        df = df[mask]
    # print(df)
    filename = '{}_setting.csv'.format(exchange)
    df.to_csv(filename, index=False)
    return filename


def generate_setting_file():
    df = get_instrument()
    # df2 = df.drop(['exchange'], axis=1)
    # print(df)
    for i in range(len(df)):
        split_df = df[i: i + 1]
        symbol = split_df.iloc[0]['vtSymbol']
        filename = '{}_setting.csv'.format(symbol)
        print(filename)
        split_df.to_csv(filename, index=False)


def get_setting_file(symbol_list=None):
    if symbol_list is None:
        symbol_list = get_instrument()['vtSymbol'].values
    return ['{}_setting.csv'.format(symbol) for symbol in symbol_list]


def run_backtesting(filename, start, end, capital=1000000, show_trade=False):
    engine = BacktestingEngine()
    engine.setPeriod(start, end)
    engine.initPortfolio(filename, capital)

    engine.loadData()
    engine.runBacktesting()

    if show_trade:
        tradeList = engine.get_trade()
        for dt, trade in tradeList:
            print '%s : %s %s %s %s@%s' % (dt, trade.vtSymbol, trade.direction, trade.offset,
                                           trade.volume, trade.price)
    engine.showResult()
    return engine.bt_result


def run_portfolio_backtesting():
    start = datetime(2016, 1, 1)
    end = datetime(2017, 1, 1)
    exchange = 'SHFE'
    # exclude = ['B888', 'ZC888', 'MA888']
    exclude = ['B888']

    filename = select_instrument(start, exchange, exclude)
    run_backtesting(filename, start, end, capital=10000000, show_trade=True)


def run_batch_backtesting(start, end, symbol_list=None, capital=10000000, exchange='all'):
    setting_file_names = get_setting_file(symbol_list)
    results_list = []
    for filename in setting_file_names:
        try:
            result_dict = run_backtesting(filename, start, end, capital)
            result_dict.update({'vtSymbol': filename.split('_')[0]})
            results_list.append(result_dict)
        except:
            print('{}-error'.format(filename))
            traceback.print_exc()
    result_df = pd.DataFrame.from_records(results_list, index='vtSymbol')
    result_df.to_csv('{}_result.csv'.format(exchange), encoding='utf-8')


if __name__ == '__main__':
    # generate_setting_file()

    start = datetime(2015, 1, 1)
    end = datetime(2016, 1, 1)

    run_backtesting('SF888_setting.csv', start, end, show_trade=True)
    # run_batch_backtesting(start, end)
    # run_backtesting('IC888_setting.csv', start, end, show_trade=True, capital=10000000)

    # select_instrument(start=start)
    # select_instrument(start=start, exclude=['B888'])
    # select_instument(start=start, exchange='DCE')
    # select_instument(start=start, exchange='DCE', exclude=['B888'])

    # run_portfolio_backtesting()
