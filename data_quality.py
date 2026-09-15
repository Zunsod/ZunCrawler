import pandas as pd
import json

with open("data/raw/zangia_jobs_selected.json", encoding="utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data)

print(df.shape)
print(df.isnull().sum())          
print(df["address"].value_counts())
print(df["branch"].value_counts())   