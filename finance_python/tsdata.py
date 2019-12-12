import json
import tushare as ts
import pandas as pd
from typing import Sequence
from pandas import DataFrame


with open("token.json") as f:
    tokens = json.load(f)
ts_token = tokens.get("ts_token")
ts.set_token(ts_token)


def get_data(symbols: Sequence, start: str, end: str) -> DataFrame:
    df_dict = dict()
    for symbol in symbols:
        df = ts.pro_bar(symbol, start_date=start, end_date=end, adj="qfq")
        df.set_index("trade_date", inplace=True)
        df_dict[symbol] = df
        
    price = pd.DataFrame({symbol: df["close"] for symbol, df in df_dict.items()})
    price.fillna(method="ffill", inplace=True)
    return price