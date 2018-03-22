# coding=utf-8
# @author: linbozhong


import os
import json
import codecs
import tushare as ts
import numpy as np
import multiprocessing
from datetime import date, datetime, timedelta
from trading_day_tools import is_trading_day, get_pre_next_trading_day


def convert_proper_date(start_date=None, end_date=None):
    """
    :param start_date: str format: YYYY-mm-dd
    :param end_date: str format: YYYY-mm-dd
    :return: tuple([str, str])
    """

    date_format = '%Y-%m-%d'
    if not end_date:
        today = date.today()
        end_date = today - timedelta(1)
        end_date = date.strftime(end_date, date_format)
    if not start_date:
        start_date = datetime.strptime(end_date, date_format) - timedelta(365)
        start_date = datetime.strftime(start_date, date_format)
    if not is_trading_day(start_date):
        start_date = get_pre_next_trading_day(start_date)
    if not is_trading_day(end_date):
        end_date = get_pre_next_trading_day(end_date, mode='pre')
    return start_date, end_date


def get_change_rate(code, start_date, end_date):
    """
    :param code: str
    :param start_date: String format: YYYY-mm-dd
    :param end_date: String format: YYYY-mm-dd
    :return: int
    """

    df1 = ts.get_k_data(code=code, start=start_date, end=start_date)
    df2 = ts.get_k_data(code=code, start=end_date, end=end_date)
    if df1.empty or df2.empty:
        df3 = ts.get_k_data(code=code, start=start_date, end=end_date)
        if df3.empty:
            change_rate = 0
        else:
            change_rate = (df3.iloc[-1, 2] - df3.iloc[0, 2]) / df3.iloc[0, 2]
    else:
        change_rate = (df2.iloc[-1, 2] - df1.iloc[0, 2]) / df1.iloc[0, 2]
    return change_rate


def batch_change_rate(index_list, start_date, end_date, file_name, retry=3):
    """
    :param index_list: list
    :param start_date: String format: YYYY-mm-dd
    :param end_date: String format: YYYY-mm-dd
    :param file_name: str
    :param retry: int
    :return: None
    """

    error_times = 0
    result_list = []
    index_done = []
    proper_date = convert_proper_date(start_date, end_date)
    print proper_date

    while error_times <= retry:
        if error_times > 0:
            print('Retrying[%s/%s]...' % (error_times, retry))
        code = None
        ok_num = 0
        all_num = len(index_list)
        try:
            for code in index_list:
                result = get_change_rate(code, start_date=proper_date[0], end_date=proper_date[1])
                t = code, result
                result_list.append(t)
                index_done.append(code)
                ok_num += 1
                progress = float(ok_num) / float(all_num) * 100
                print('[Done:%s of %s, Progress:%.2f%%] %s : %.2f' % (ok_num, all_num, progress, code, result))
        except Exception, e:
            print('Error Message: %r' % e)
            print('All:%s. Finished:%s, Unfinished:%s' % (all_num, ok_num, all_num - ok_num))
            print('Error Code: %s' % code)
            error_times += 1
            index_list = list(set(index_list) - set(index_done))
        else:
            with codecs.open(file_name, 'w', 'utf-8') as f:
                json.dump(result_list, f)
            print ('Save complete. Reslut length is: %s' % len(result_list))
            return


def split_code_list(code_list, group_num=10):
    """
    :param code_list: ndarray
    :param group_num: int
    :return: 2d list: list[ndarray[]]
    """

    size = len(code_list)
    if group_num > size:
        print ('The code number must be larger than group number')
    else:
        member_num = len(code_list) // group_num
        code_main_list = code_list[0: member_num * group_num].reshape((group_num, member_num))
        code_tail_list = code_list[member_num * group_num:]
        final = list(code_main_list)
        final[-1] = np.append(code_main_list[-1], code_tail_list)
        return final


def save_to_files(start_date, end_date, data_directory):
    """
    :param start_date: String format: YYYY-mm-dd
    :param end_date: String format: YYYY-mm-dd
    :param data_directory: str
    :return: None
    """

    process_num = multiprocessing.cpu_count()
    if not os.path.exists(data_directory):
        print ('Creating data directory.')
        os.mkdir(data_directory)
        print ('Directory is ok.')

    print ('Getting task...')
    code_list = ts.get_stock_basics().index.values
    code_list = split_code_list(code_list, group_num=process_num)

    processes_list = []
    for i in range(process_num):
        file_name = '%sprocess_%02d%s' % (data_directory, i, '.txt')
        p = multiprocessing.Process(target=batch_change_rate, args=(code_list[i], start_date, end_date, file_name))
        processes_list.append(p)
    for p in processes_list:
        p.start()
        print ('Process is running. p.pid: %s, p.name: %s' % (p.pid, p.name))
    for p in processes_list:
        p.join()
        print ('%s is over.' % p.name)

    print ('All tasks Completed.')


def converge_data_files(data_directory):
    """
    :param data_directory: str
    :return: dict{str: int}
    """

    files_list = os.listdir(data_directory)
    result = {}
    for data_file in files_list:
        file_name = data_directory + data_file
        with codecs.open(file_name, 'r', 'utf-8') as f:
            data = json.load(f)
        for datum in data:
            result[datum[0]] = datum[1]
    print('Converge Complete. Result is %s' % len(result))
    return result


def main():
    start_date = '2017-01-01'
    end_date = '2017-12-31'
    data_directory = './cr_data/'

    save_to_files(start_date, end_date, data_directory)
    result = converge_data_files(data_directory)
    return result


if __name__ == '__main__':
    res = main()
