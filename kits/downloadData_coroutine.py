# coding:utf-8
"""
学习用协程的方式来批量下载。注意：这里的下载任务不是IO密集任务，所以协程在这里几乎没什么作用！仅作为协程的调度学习范例。
在cpu密集任务里面，因为python的多线程有全局锁的问题，所以要加快效率可以考虑使用多进程。
如果是IO任务，用协程可以提高效率，也免去进程或线程切换的开销。
"""

from datetime import datetime
from jaqsDataService import JaqsDataDownloader


class Event(object):
    """
    事件类，实际上就是对应某个要运行的操作。
    如果是IO任务，比如读取url之类的，此类任务cpu几乎不参与计算，完全是在等待对方响应。可以用sleep()模拟。
    大体思路：
    任务分发器创建多个生成器，并把生成器返回的对象设置为事件类的实例，如果事件是IO事件，则几乎不会阻塞。
    注意：如果是cpu密集任务，这里其实是会发生阻塞的，这就是本例为什么用协程
    事件实例有个状态属性，如果事件完成后，就会运行回调函数，这里的回调函数是个递归函数，作用是唤醒生成器，以生成下一个事件，如果生成器迭代结束，递归函数退出。
    分发器分发完任务后，运行一个轮询函数，检查已有的事件是否完成任务。

    """

    def __init__(self, jaqsDownloader, date, symbol):
        # 通过eventID来判断事件是否完成。
        self._eventID = '.'.join([date, symbol])
        self._downloader = jaqsDownloader
        self._callback = None
        self._downloader.saveToDb(symbol, trade_date=date)

    def setCallback(self, callback):
        self._callback = callback

    def get_eventID(self):
        return self._eventID

    def isReady(self):
        ready = self._eventID in self._downloader.finishedSymbols
        if ready:
            self._callback()
        return ready


class Dispatcher(object):
    def __init__(self, jaqsDownloader):
        self.downloader = jaqsDownloader
        self.tasks = []
        self.eventList = []
        self.start()

    def setTask(self, dateList, symbolList):
        # 创建任务，即创建多个生成器
        self.tasks = [self.generator(date, symbolList) for date in dateList]

    # 生成器函数
    def generator(self, date, symbolList):
        for symbol in symbolList:
            yield self.addEvent(date, symbol)

    # 把生成器返回的事件加入事件列表，以便分发器轮询任务状态
    def addEvent(self, date, symbol):
        event = Event(self.downloader, date, symbol)
        self.eventList.append(event)
        return event

    def start(self):
        for task in self.tasks:
            self._next(task)

    # 用于唤醒生成器的递归函数
    def _next(self, task):
        try:
            #
            yield_event = next(task)
            yield_event.setCallback(lambda: self._next(task))  # 用lambda可以传入需要附带参数的函数
        except StopIteration:
            pass

    # 轮询事件状态
    def polling(self):
        while len(self.eventList):
            for event in self.eventList[:]:
                if event.isReady():
                    self.eventList.remove(event)


# 协程调度函数运行入口
def coroutineMethod(downloader, tradingDays, symbols):
    start = datetime.now()
    dispatcher = Dispatcher(downloader)
    dispatcher.setTask(tradingDays, symbols)
    dispatcher.start()
    dispatcher.polling()
    print(u'协程方式任务完成，耗时%s秒' % (datetime.now() - start).seconds)


def main():
    dl = JaqsDataDownloader()
    dl.loginJaqsApp()
    dl.connectDb()

    # 获取交易日历
    tradingDays = dl.getTradingday('2018-04-15')
    # print tradingDays

    # 要下载的合约代码
    symbols = ['rb1810', 'm1809', 'TA809']

    # 协程调度
    coroutineMethod(dl, tradingDays, symbols)


if __name__ == '__main__':
    main()
