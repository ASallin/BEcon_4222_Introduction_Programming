import os
import time
import pandas as pd
import duckdb
from pathlib import Path
from dotenv import load_dotenv
from fredapi import Fred

load_dotenv()

api_key = os.getenv("FRED_API_KEY")
fred = Fred(api_key=api_key)


DATE_START = "2000-01-01"
DATE_END = "2023-12-31"

STATES = [
    # abbr, name,               census_region,  census_division
    ("CA", "California", "West", "Pacific"),
    ("OR", "Oregon", "West", "Pacific"),
    ("WA", "Washington", "West", "Pacific"),
    ("CO", "Colorado", "West", "Mountain"),
    ("AZ", "Arizona", "West", "Mountain"),
    ("TX", "Texas", "South", "West South Central"),
    ("FL", "Florida", "South", "South Atlantic"),
    ("GA", "Georgia", "South", "South Atlantic"),
    ("NC", "North Carolina", "South", "South Atlantic"),
    ("LA", "Louisiana", "South", "West South Central"),
    ("IL", "Illinois", "Midwest", "East North Central"),
    ("OH", "Ohio", "Midwest", "East North Central"),
    ("MI", "Michigan", "Midwest", "East North Central"),
    ("MN", "Minnesota", "Midwest", "West North Central"),
    ("MO", "Missouri", "Midwest", "West North Central"),
    ("NY", "New York", "Northeast", "Middle Atlantic"),
    ("PA", "Pennsylvania", "Northeast", "Middle Atlantic"),
    ("MA", "Massachusetts", "Northeast", "New England"),
    ("NJ", "New Jersey", "Northeast", "Middle Atlantic"),
    ("CT", "Connecticut", "Northeast", "New England"),
]

INDICATORS = [
    # suffix, title,                          units,       frequency
    ("UR", "Unemployment Rate", "%", "Monthly"),
    ("NA", "Total Nonfarm Employment", "Thousands", "Monthly"),
    ("PCPI", "Per Capita Personal Income", "USD", "Annual"),
]

# states
df_states = pd.DataFrame(
    STATES, columns=["abbr", "name", "census_region", "census_division"]
)
df_states = df_states.reset_index()  # <1>
df_states = df_states.rename(columns={"index": "state_id"})  # <2>
df_states["state_id"] += 1  # <3>

print(f"{len(df_states)} states")
df_states.head()

# indicators
df_indicators = pd.DataFrame(
    INDICATORS, columns=["suffix", "title", "units", "frequency"]
)
df_indicators = df_indicators.reset_index()
df_indicators = df_indicators.rename(columns={"index": "indicator_id"})
df_indicators["indicator_id"] += 1

print(f"{len(df_indicators)} indicators")
df_indicators


CACHE_FILE = Path("fred_cache.parquet")

abbr_to_id = df_states.set_index("abbr")["state_id"].to_dict()
suffix_to_id = df_indicators.set_index("suffix")["indicator_id"].to_dict()

if CACHE_FILE.exists():
    df_observations = pd.read_parquet(CACHE_FILE)
else:
    obs_frames = []
    for state in STATES:
        abbr = state[0]
        for indicator in INDICATORS:
            suffix = indicator[0]
            fred_code = abbr + suffix
            raw = fred.get_series(
                fred_code,
                observation_start=DATE_START,
                observation_end=DATE_END,
            )
            if raw is None or raw.empty:
                continue
            df_chunk = raw.dropna().reset_index()
            df_chunk.columns = ["date", "value"]
            df_chunk["state_id"] = abbr_to_id[abbr]
            df_chunk["indicator_id"] = suffix_to_id[suffix]
            df_chunk["date"] = pd.to_datetime(df_chunk["date"])
            obs_frames.append(df_chunk[["state_id", "indicator_id", "date", "value"]])
            time.sleep(0.3)
    df_observations = pd.concat(obs_frames, ignore_index=True)
    df_observations.to_parquet(CACHE_FILE)