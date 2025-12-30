import pandas as pd

data = pd.read_csv("dataset/dynamic_data.csv")
'''datas = pd.read_csv("dataset/static_data.csv")'''
print(data.head())
print(data.info())
'''print(datas.head())
print(datas.info())'''