# coding:utf-8

from jaqsDataService import DataDownloader


def main():
    dl = DataDownloader()
    # 连接jaqs的api
    dl.loginJaqsApp()
    # 连接数据库
    dl.connectDb()

    # 批量下载当前交易日数据
    # dl.downloadAllData()

    # 指定要批量下载的合约
    dl.setSymbols(['m1809', 'y1805'])
    dl.downloadAllData()

    # 下载指定日期的合约
    dl.downloadAllData(trade_date='2018-03-20')

if __name__ == '__main__':
    main()
