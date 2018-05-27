#!/usr/bin/env python
# encoding: utf-8

import sys
from tradeCalculater import TradeCalculator


if __name__ == '__main__':
    print sys.argv

    # filename = '20180524_20041.xls'
    filename = sys.argv[1]

    calculator = TradeCalculator(filename)
    df = calculator.loadXlsFile()
    calculator.generateTradeData(df)
    calculator.generateAllResult()
    calculator.generateTradePointImage()