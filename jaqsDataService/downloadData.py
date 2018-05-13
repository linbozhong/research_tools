# coding:utf-8

from datetime import datetime
from jaqsDataService import JaqsDataDownloader


def syncMethod(downloader, tradingDays, symbols):
    start = datetime.now()
    settings = [(symbol, date) for date in tradingDays for symbol in symbols]
    for setting in settings:
        downloader.saveToDb(symbol=setting[0], trade_date=setting[1])
    print(u'普通同步方式任务完成，耗时%s秒' % (datetime.now() - start).seconds)


def main():
    dl = JaqsDataDownloader()
    dl.loginJaqsApp()
    dl.connectDb()

    # 获取交易日历
    tradingDays = dl.getTradingday('20180415')
    func = lambda dateStr: '%s-%s-%s' % (dateStr[0:4], dateStr[4:6], dateStr[6:8])  # 把20180401转成2018-04-01格式
    tradingDays = [func(date) for date in tradingDays]

    # 盘中获取，去掉当前交易日
    tradingDays = tradingDays[:-1]

    # 要下载的合约代码
    symbols = ['rb1810', 'm1809', 'TA809']

    # 同步方式下载
    syncMethod(dl, tradingDays, symbols)


if __name__ == '__main__':
    main()
