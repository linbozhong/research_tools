# coding=utf-8
# @author: linbozhong
# =======================
# 1. Dowonload RongZiRongQuan Data from Stock Exchange of shenzhen and shanghai website
# 2. Create a directory named 'rzrq'.
# 3. Open the two files and convert to csv file.
# 4. Rename the two files as 'sz_rzrq.csv' and 'sh_rzrq.csv'
# 5. The shenzhen data must be convert into numerical form
# Refine this features later.


import pandas as pd
import tushare as ts
import re


def prepare_data(filename):
    try:
        df = pd.read_csv(filename, index_col=[0], encoding='gb2312')
    except IOError:
        print('IO Error')
    else:
        df.index = df.index.map(lambda x: '%06d' % x)
        return df


def normalize_sz(df):
    new_columns = ['name', 'rzmr', 'rzye', 'rqmc', 'rqyl', 'rqye', 'rzrqye']
    df.columns = new_columns
    df.index.name = 'code'
    return df[['name', 'rzye']]


def normalize_sh(df):
    new_columns = ['name', 'rzye', 'rzmr', 'rzch', 'rqyl', 'rqmc', 'rqch']
    df.columns = new_columns
    df.index.name = 'code'
    return df[['name', 'rzye']]


def get_industry_dict():
    df = ts.get_stock_basics()
    return df.industry


def convert_to_industry(code_str, industry_dict):
    industry = industry_dict.get(code_str)
    if not industry:
        etf_pattern = re.compile(r'^(51|15)\d{4}$')
        m = re.match(etf_pattern, code_str)
        if m:
            return 'ETF'
        else:
            return 'Unknown'
    return industry


def add_industry(code_list, industry_dict):
    new_dict = {}
    for code in code_list:
        new_dict[code] = convert_to_industry(code, industry_dict)
    return pd.Series(new_dict)


if __name__ == '__main__':
    filenames = {'sz': './rzrq/sz_rzrq.csv', 'sh': './rzrq/sh_rzrq.csv'}
    data = {}
    industry_dict = get_industry_dict()
    for market, filename in filenames.items():
        df = prepare_data(filename)
        if market == 'sz':
            df = normalize_sz(df)
        else:
            df = normalize_sh(df)
        df['industry'] = add_industry(df.index, industry_dict)
        data[market] = df
    all_data = pd.concat([data['sz'], data['sh']], axis=0)
    grouped = all_data['rzye'].groupby(all_data['industry'])
    result = grouped.sum()
    result = result / 100000000
    output = pd.DataFrame(result)
    output.to_csv('rzye_reslut.csv')
