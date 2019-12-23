import pandas as pd
from typing import List
from vnpy.trader.object import BarData

def vt_bar_to_df(bars: List[BarData]) -> pd.DataFrame:
    df = pd.DataFrame()
    t = []
    o = []
    h = []
    l = []  # noqa
    c = []
    v = []

    for bar in bars:
        time = bar.datetime
        open_price = bar.open_price
        high_price = bar.high_price
        low_price = bar.low_price
        close_price = bar.close_price
        volume = bar.volume

        t.append(time)
        o.append(open_price)
        h.append(high_price)
        l.append(low_price)
        c.append(close_price)
        v.append(volume)

    df["open"] = o
    df["high"] = h
    df["low"] = l
    df["close"] = c
    df["volume"] = v
    df.index = t
    return df