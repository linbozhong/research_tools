#!/usr/bin/env python
# encoding: utf-8

import unittest
import os

from .. import tradeCalculator


class TestTradeCalculator(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testCreateFolder(self):
        cal = tradeCalculator.TradeCalculator('testFile')
        cal.createFolders()
        dirList = os.listdir(os.getcwd())
        self.assertTrue('output' in dirList)
        self.assertTrue('image' in dirList)
        os.rmdir('output')
        os.rmdir('image')

    def testSetProperty(self):
        cal = tradeCalculator.TradeCalculator('testFile')
        cal.setSourceFolder('testSource')
        cal.setOutputFolder('testOutput')
        cal.setImageFolder('testImage')

        self.assertEqual(cal.sourceFileName, 'testFile')
        self.assertEqual(cal.sourceFolder, 'testSource')
        self.assertEqual(cal.outputFolder, 'testOutput')
        self.assertEqual(cal.imageFolder, 'testImage')

    def testLoadXlsFile(self):
        cal = tradeCalculator.TradeCalculator('20180525_20041.xls')
        cal.setSourceFolder('tradeCalculator/test_source')
        df = cal.loadXlsFile()
        print('Printing XLS')
        print(df.head(2))
        print(df.columns.values[0])

    def testLoadCsvFile(self):
        cal = tradeCalculator.TradeCalculator('20180523_20041.csv')
        cal.setSourceFolder('tradeCalculator/test_source')
        df = cal.loadCsvFile()
        print('Printing Csv')
        print(df.head(2))
        print(df.columns.values[0])

    def testGenerateTradeData(self):
        cal = tradeCalculator.TradeCalculator('20180525_20041.xls')
        cal.setSourceFolder('tradeCalculator/test_source')
        df = cal.loadXlsFile()
        cal.generateTradeData(df)
        print('Printing tradeData')
        print(cal.allTradeDict.keys())
        print(cal.allTradeDict.values()[0])
        print(cal.allTradeDict.values()[0][0].__dict__)

    def testCalculateTradeResult(self):
        cal = tradeCalculator.TradeCalculator('20180525_20041.xls')
        cal.setSourceFolder('tradeCalculator/test_source')
        df = cal.loadXlsFile()
        cal.generateTradeData(df)
        cal.calculateTradeResult('000571')
        print('Printing Trade Result')
        print(cal.allResultDict.keys())
        print(cal.allResultDict.values()[0])
        print(cal.allResultDict.values()[0][0].__dict__)

    def testGenerateSingleResult(self):
        cal = tradeCalculator.TradeCalculator('20180525_20041.xls')
        cal.setSourceFolder('tradeCalculator/test_source')
        cal.setOutputFolder('tradeCalculator/test_output')
        cal.createFolders()
        df = cal.loadXlsFile()
        cal.generateTradeData(df)
        cal.calculateTradeResult('000571')
        df2 = cal.generateSingleResult('000571')
        df2.to_csv(cal.outputFolder + '/single_test.csv', encoding='utf-8', index=False)

    def testGenerateAllResult(self):
        cal = tradeCalculator.TradeCalculator('20180525_20041.xls')
        cal.setSourceFolder('tradeCalculator/test_source')
        cal.setOutputFolder('tradeCalculator/test_output')
        cal.createFolders()
        df = cal.loadXlsFile()
        cal.generateTradeData(df)
        cal.generateAllResult()


class TestTradePointer(unittest.TestCase):
    def testConnectDb(self):
        pointer = tradeCalculator.TradePointer('000571', '2018-05-25')
        db = pointer.connectDb()
        print(db.collection_names())

    def testGetTickData(self):
        pointer = tradeCalculator.TradePointer('000571', '2018-05-25')
        df = pointer.getTickData()
        df.to_csv('tradeCalculator/test_output/tick_data.csv', encoding='utf-8')

    def testDisplay(self):
        cal = tradeCalculator.TradeCalculator('20180525_20041.xls')
        cal.setSourceFolder('tradeCalculator/test_source')
        df = cal.loadXlsFile()
        cal.generateTradeData(df)
        tradeList = cal.allTradeDict['000571']

        pointer = tradeCalculator.TradePointer('000571', '2018-05-25')
        pointer.getTickData()
        pointer.getTradeData(tradeList)
        print(pointer.buyTimeIndex, pointer.buyPrice)
        print(pointer.sellTimeIndex, pointer.sellPrice)

        pointer.display('tradeCalculator/test_output/test_display.png')


class TestChineseDisplay(unittest.TestCase):
    def testChineseShow(self):
        print(u'中文显示')


if __name__ == '__main__':
    unittest.main()
