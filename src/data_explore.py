import pandas as pd

file = "data/suspects.csv"

df = pd.read_csv(file, nrows=10000)

print("Columns:")
print(df.columns.tolist())

print("\nRows in sample:")
print(len(df))

print("\nData types:")
print(df.dtypes)

print("\nMissing values:")
print(df.isna().sum())

print("\nUnique members in sample:")
print(df["bene_id"].nunique())

print("\nSample rows:")
print(df.head(10).to_string(index=False))