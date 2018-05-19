# coding:utf-8

from datetime import datetime
from jaqsDataService import JaqsDataDownloader


# 下载主力连续合约数据
def downloadMainContract(downloader, mainContractSymbol, startDate, endDate=None):
    settings = downloader.getMainContract(mainContractSymbol, startDate, endDate)
    for setting in settings:
        downloader.saveToDb(setting[0], trade_date=setting[1])


# 下载多合约数据
def downloadMultiContract(downloader, symbols, startDate, endDate=None):
    # 获取交易日历
    tradingDays = downloader.getTradingday(startDate, endDate)

    # 下载数据
    settings = [(symbol, date) for date in tradingDays for symbol in symbols]
    for setting in settings:
        downloader.saveToDb(symbol=setting[0], trade_date=setting[1])


def main():
    start = datetime.now()

    # 设置任务
    startDate = '2015-01-01'
    endDate = None
    symbols = ['rb1810', 'm1809', 'TA809']
    mainContractSymbol = 'rb'

    # 创建下载器
    dl = JaqsDataDownloader()
    dl.loginJaqsApp()
    dl.connectDb()

    # 任务开始
    # downloadMultiContract(dl, symbols, startDate, endDate)
    downloadMainContract(dl, mainContractSymbol, startDate, endDate)

    print(u'全部任务完成，耗时%s秒' % (datetime.now() - start).seconds)


if __name__ == '__main__':
    main()
