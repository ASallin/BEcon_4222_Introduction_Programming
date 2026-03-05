# Import the pandas library to create and manipulate data
# This script generates a CSV file containing GDP data for several European countries in the year 2023.

import pandas as pd

data = pd.DataFrame({
    "country": ["Switzerland", "Germany", "France", "Italy", "Spain"],
    "gdp_bn_usd": [800, 4000, 2800, 2100, 1400],
    "year": 2023
})
data.to_csv("gdp_data.csv", index=False)
print("File written: gdp_data.csv")