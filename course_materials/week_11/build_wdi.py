import os
import pandas as pd
import duckdb



# ── Paths ──────────────────────────────────────────────────────────────────────
HERE     = os.path.dirname(__file__)            # directory where this script is located
DATA_DIR = os.path.join(HERE, "data")           # must contain WDICountry.csv, WDISeries.csv, and WDICSV.csv
DB_PATH  = os.path.join(HERE, "wdi.db")         # the database will be created (or overwritten) at this path



# ── Time range ─────────────────────────────────────────────────────────────────
YEAR_START = 2000
YEAR_END   = 2022

# ── Indicator selection ────────────────────────────────────────────────────────
INDICATOR_CODES = [
    "NY.GDP.PCAP.KD",   # GDP per capita (constant 2015 USD)
    "SL.UEM.TOTL.ZS",   # Unemployment rate (% of labor force)
    "SI.POV.GINI",      # Gini index
    "SI.DST.10TH.10",   # Income share held by the highest 10%
    "SI.DST.FRST.10",   # Income share held by the lowest 10%
]


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACT & TRANSFORM
# ══════════════════════════════════════════════════════════════════════════════


year_cols = [str(y) for y in range(YEAR_START, YEAR_END + 1)]

raw_country = pd.read_csv(
    os.path.join(DATA_DIR, "WDICountry.csv"),
    usecols=["Country Code", "Short Name", "Region", "Income Group"],
)
raw_country.columns = ["iso3", "name", "region", "income_group"]

raw_series = pd.read_csv(
    os.path.join(DATA_DIR, "WDISeries.csv"),
    usecols=["Series Code", "Indicator Name", "Topic", "Unit of measure"],
)
raw_series.columns = ["code", "name", "topic", "unit"]

raw_data = pd.read_csv(
    os.path.join(DATA_DIR, "WDICSV.csv"),
    usecols=["Country Code", "Indicator Code"] + year_cols,
)


# ── Build the countries table ──────────────────────────────────────────────────
df_countries = raw_country.copy()

# Remove rows without a region (aggregates like "World" or "Euro area")
df_countries = df_countries.dropna(subset=["region"])

# Add an integer primary key starting from 1
df_countries = df_countries.reset_index(drop=True)
df_countries.insert(0, "country_id", range(1, len(df_countries) + 1))



# ── Build the indicators table ─────────────────────────────────────────────────

# Filter the indicators to only those in our list
df_indicators = raw_series[raw_series["code"].isin(INDICATOR_CODES)].copy()

# Convert the string code index to an integer — best practice for a star schema
df_indicators = df_indicators.reset_index(drop=True)
df_indicators.insert(0, "indicator_id", range(1, len(df_indicators) + 1))

# Fill NAs in the unit column with empty strings
df_indicators["unit"] = df_indicators["unit"].fillna("")

# Select only the columns we need for the database
df_indicators = df_indicators[["indicator_id", "code", "name", "topic", "unit"]]



# ── Build the observations table ───────────────────────────────────────────────
# Subset the data to only the indicators and years we need, then reshape to long format
# Note: subsetting here is a choice, you could do it in the database instead, but it's easier to do it here before we reshape
subset = raw_data[raw_data["Indicator Code"].isin(INDICATOR_CODES)].copy()

# Reshape to long format
df_observations = subset.melt(
    id_vars   = ["Country Code", "Indicator Code"],
    value_vars = year_cols,
    var_name  = "year",
    value_name = "value",
)

# Select columns, convert year to integer, and drop NAs in the value column
df_observations.columns = ["iso3", "indicator_code", "year", "value"]
df_observations["year"] = df_observations["year"].astype(int)
df_observations = df_observations.dropna(subset=["value"])

# Replace iso3/code with integer foreign keys
iso3_to_id = df_countries.set_index("iso3")["country_id"].to_dict()
code_to_id = df_indicators.set_index("code")["indicator_id"].to_dict()
df_observations["country_id"]   = df_observations["iso3"].map(iso3_to_id)
df_observations["indicator_id"] = df_observations["indicator_code"].map(code_to_id)
df_observations = df_observations.dropna(subset=["country_id", "indicator_id"])

df_observations = df_observations[["country_id", "indicator_id", "year", "value"]]
df_observations["country_id"]   = df_observations["country_id"].astype(int)
df_observations["indicator_id"] = df_observations["indicator_id"].astype(int)



# ══════════════════════════════════════════════════════════════════════════════
# LOAD
# ══════════════════════════════════════════════════════════════════════════════

# Open a fresh database connection
# If the database already exists, delete it so we start clean
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

conn = duckdb.connect(DB_PATH)

# Create tables with constraints
conn.execute("""
    CREATE TABLE countries (
        country_id   INTEGER PRIMARY KEY,
        iso3         VARCHAR NOT NULL UNIQUE,
        name         VARCHAR NOT NULL,
        region       VARCHAR NOT NULL,
        income_group VARCHAR
    )
""")

conn.execute("""
    CREATE TABLE indicators (
        indicator_id INTEGER PRIMARY KEY,
        code         VARCHAR NOT NULL UNIQUE,
        name         VARCHAR NOT NULL,
        topic        VARCHAR,
        unit         VARCHAR
    )
""")

conn.execute("""
    CREATE TABLE observations (
        country_id   INTEGER NOT NULL REFERENCES countries(country_id),
        indicator_id INTEGER NOT NULL REFERENCES indicators(indicator_id),
        year         INTEGER NOT NULL,
        value        DOUBLE  NOT NULL,
        PRIMARY KEY (country_id, indicator_id, year)
    )
""")


# Insert data
conn.execute("INSERT INTO countries    SELECT * FROM df_countries")
conn.execute("INSERT INTO indicators   SELECT * FROM df_indicators")
conn.execute("INSERT INTO observations SELECT * FROM df_observations")

# Close the connection
conn.close()

# Confirm end of script
print(f"Database created at: {DB_PATH}")
