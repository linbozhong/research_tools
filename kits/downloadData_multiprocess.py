# coding:utf-8

"""
cpu密集型的任务，使用多进程可以有效提高效率。
但是可能会造成入库时间不会按照实际数据时间排列。后期读取数据库时可以通过排序修正。如果介意的话，可以采用单进程普通模式。
"""

import multiprocessing
from datetime import datetime
from jaqsDataService import JaqsDataDownloader

# 实例化jaqs下载器，并连接
dl = JaqsDataDownloader()
dl.loginJaqsApp()
dl.connectDb()


def download(**kwargs):
    # 调用下载器的方法，多线程是独立内存，会创建多个dl实例对象。
    dl.saveToDb(**kwargs)


def main():
    start = datetime.now()

    # 生成交易日列表
    tradingDays = dl.getTradingday('2018-05-01')

    # 指定合约列表
    symbols = ['rb1810', 'm1809', 'TA809']

    # 生成下载参数
    settings = [(symbol, date) for date in tradingDays for symbol in symbols]

    # 线程池
    pool = multiprocessing.Pool(multiprocessing.cpu_count())
    for setting in settings:
        kwargs = {'symbol': setting[0], 'trade_date': setting[1]}
        # 多线程不能直接传入对象的方法名，不会运行，会直接退出。要把调用对象方法的代码写在一个全局函数里面。
        pool.apply_async(download, kwds=kwargs)
    pool.close()
    pool.join()

    print(u'任务完成，耗时%s秒' % (datetime.now() - start).seconds)


if __name__ == '__main__':
    main()
