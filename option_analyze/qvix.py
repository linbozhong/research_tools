import csv
import requests
import tushare as ts
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
from datetime import datetime

from utility import dt_to_str

QVIX_URL = 'http://1.optbbs.com/d/csv/d/vixk.csv'


def get_qvix_file():
    return Path.cwd().joinpath('vix_bar.csv')

def get_qvix():
    fp = get_qvix_file()
    return pd.read_csv(fp, index_col=0, parse_dates=True)


def update_qvix():
    try:
        resp = requests.get(QVIX_URL)
        csv_strings_iterator = (line.decode('utf-8')
                                for line in resp.iter_lines())
        csv_data = list(csv.DictReader(csv_strings_iterator))
    except:
        print('error occur when get qvix.')
    else:
        name_dict = {
            '1': 'datetime',
            '1 ': 'datetime',
            '2': 'open',
            '3': 'high',
            '4': 'low',
            '5': 'close'
        }
        df = pd.DataFrame(csv_data)
        df.rename(columns=name_dict, inplace=True)
        df = df[df['open'] != ''].copy()

        df[['open', 'high', 'low', 'close']] = df[[
            'open', 'high', 'low', 'close']].astype('float')
        df['datetime'] = df['datetime'].map(
            lambda t_stamp_str: dt_to_str(datetime.fromtimestamp(float(t_stamp_str) / 1000)))

        df.set_index('datetime', inplace=True)
        df.to_csv(get_qvix_file())
        print('update completely!')
        return df


def get_hist_vol():
    df = ts.get_k_data('510050', start='2005-02-23')
    df['return_sim'] = df['close'].pct_change()
    df['return_log'] = np.log(df['close'] / df['close'].shift(1))

    n_array = [5, 10, 20, 40, 60, 120, 250]
    for n in n_array: 
        name = 'HV_{}'.format(n)
        df[name] = df['return_log'].rolling(n).std() * np.sqrt(252) * 100
    return df.dropna()