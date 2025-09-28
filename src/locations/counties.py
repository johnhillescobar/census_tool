import pandas as pd
import os

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
excel_file = os.path.join(script_dir, "counties.xlsx")

df = pd.read_excel(excel_file)
df = df.loc[df["Geographic area name"].str.len() > 2, :].copy()
df["counties"] = [county.split(",")[0] for county in df["Geographic area name"]]

output_file = os.path.join(script_dir, "counties_processed.csv")
df.to_csv(output_file, index=False)
