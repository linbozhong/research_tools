import pandas as pd

dominant_data = pd.read_csv('source_data/dominant_data.csv', parse_dates=[1, 2])
future_basic_data = pd.read_csv('source_data/future_basic_data.csv', index_col=0)
future_hot_start = pd.read_csv('source_data/future_hot_start.csv', index_col=0,  header=None, names=['hot_start'])