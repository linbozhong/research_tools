#!/usr/bin/env python
# encoding: utf-8

import sys
from tradeCalculator import TradeCalculator


if __name__ == '__main__':
    print sys.argv

    # filename = '20180524_20041.xls'
    filename = sys.argv[1]

    calculator = TradeCalculator(filename)
    calculator.createFolders()
    df = calculator.loadXlsFile()
    calculator.generateTradeData(df)
    calculator.generateAllResult()
    calculator.generateTradePointImage()