# 此文件代码只能在米宽的研究环境下运行

import json
from datetime import datetime


def strip_digt(symbol: str):
    res = ""
    for char in symbol:
        if not char.isdigit():
            res += char
        else:
            break
    return res


def get_contracts():
    today = datetime.now()
    return all_instruments(type="Future", market="cn", date=today)


def process_contracts():
    df = get_contracts()
    df["order_book_id"] = df["order_book_id"].map(strip_digt)
    df.drop_duplicates(subset="order_book_id", inplace=True)
    df.set_index("order_book_id", inplace=True)
    return df


def export_multiplier():
    df = process_contracts()
    multi_df = df["contract_multiplier"]
#     multi_df.to_csv("contract_multiplier.csv", encoding="utf-8")
    d = dict(multi_df)
    with open("multiplier.json", "w+") as f:
        json.dump(d, f, indent=4)
    return d
