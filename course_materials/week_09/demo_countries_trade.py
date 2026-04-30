import duckdb
import pandas as pd


# ── CREATE RAW CSVs ───────────────────────────────────────────────────────────

pd.DataFrame({
    "name":   ["Switzerland", "Germany", "Brazil"],
    "region": ["Europe",      "Europe",  "LATAM"],
    "gdp_bn": [905,           4072,      2081],
}).to_csv("course_materials/week_09/data/countries_raw.csv", index=False)

pd.DataFrame({
    "exporter": ["Switzerland", "Germany"],
    "importer": ["Germany",     "Brazil"],
    "year":     [2022,          2022],
    "value_mn": [45,            120],
}).to_csv("course_materials/week_09/data/trade_flows_raw.csv", index=False)



# ── EXTRACT ───────────────────────────────────────────────────────────────────

df_countries_raw = pd.read_csv("course_materials/week_09/data/countries_raw.csv")
df_flows_raw     = pd.read_csv("course_materials/week_09/data/trade_flows_raw.csv")


# ── TRANSFORM ─────────────────────────────────────────────────────────────────

# Assign integer IDs (there is no natural unique key in the raw files)
df_countries = df_countries_raw.copy()
df_countries["country_id"] = range(1, len(df_countries) + 1)
df_countries["gdp_usd"] = df_countries["gdp_bn"] * 1e9
df_countries = df_countries.drop(columns=["gdp_bn"])

# Map country names -> integer IDs and convert value units
name_to_id = df_countries.set_index("name")["country_id"].to_dict()
df_flows = df_flows_raw.copy()
df_flows["flow_id"] = range(1, len(df_flows) + 1)
df_flows["exporter_id"] = df_flows["exporter"].map(name_to_id)
df_flows["importer_id"] = df_flows["importer"].map(name_to_id)
df_flows["value_usd"]   = df_flows["value_mn"] * 1e6
df_flows = df_flows[["flow_id", "exporter_id", "importer_id", "year", "value_usd"]]



# ── LOAD ──────────────────────────────────────────────────────────────────────

# Always open the connection to the database
conn = duckdb.connect("course_materials/week_09/trade.db")

# DDL: Create tables
conn.execute("""
    CREATE TABLE countries (
        country_id INTEGER PRIMARY KEY,
        name       VARCHAR NOT NULL UNIQUE,
        region     VARCHAR,
        gdp_usd    FLOAT   CHECK (gdp_usd >= 0)
    )
""")

conn.execute("""
    CREATE TABLE trade_flows (
        flow_id     INTEGER PRIMARY KEY,
        exporter_id INTEGER NOT NULL REFERENCES countries(country_id),
        importer_id INTEGER NOT NULL REFERENCES countries(country_id),
        year        INTEGER NOT NULL,
        value_usd   FLOAT   CHECK (value_usd >= 0)
    )
""")


# Option 1: INSERT row by row (as in the slides)
for _, row in df_countries.iterrows():
    conn.execute(
        "INSERT INTO countries VALUES (?, ?, ?, ?)",
        [int(row.country_id), row["name"], row.region, row.gdp_usd]
    )

# Option 2: Load directly from a pandas DataFrame
# SELECT * FROM df_countries is a special syntax that DuckDB recognizes and allows us to load the DataFrame directly into the table
conn.execute("INSERT INTO trade_flows SELECT * FROM df_flows")



# ── KEYS ──────────────────────────────────────────────────────────────────────

# This works: country 1 exists in countries
conn.execute("INSERT INTO trade_flows VALUES (3, 1, 2, 2022, 45000000)")

# This fails: country 99 does not exist
conn.execute("INSERT INTO trade_flows VALUES (4, 99, 2, 2022, 10000000)")

# This fails: country 1 is referenced by trade_flows
conn.execute("DELETE FROM countries WHERE country_id = 1")

# You must delete the child rows first
conn.execute("DELETE FROM trade_flows WHERE exporter_id = 1 OR importer_id = 1")
# conn.execute("DELETE FROM countries  WHERE country_id = 1")  # now this works


# ── INSPECT ───────────────────────────────────────────────────────────────────

print(conn.execute("SHOW TABLES").df())
print(conn.execute("DESCRIBE countries").df())
print(conn.execute("DESCRIBE trade_flows").df())


# ── QUERIES ───────────────────────────────────────────────────────────────────

# SELECT *
conn.execute("SELECT * FROM countries").df()

# WHERE
conn.execute("""
    SELECT name
    FROM   countries
    WHERE  region = 'Europe'
""").df()

# WHERE with AND
conn.execute("""
    SELECT name, gdp_usd
    FROM   countries
    WHERE  region = 'Europe'
      AND  gdp_usd > 1000000000000
""").df()

# ORDER BY + LIMIT 1: country with highest GDP
conn.execute("""
    SELECT   name, gdp_usd
    FROM     countries
    ORDER BY gdp_usd DESC
    LIMIT    1
""").df()

# COUNT(*): how many countries per region
conn.execute("""
    SELECT   COUNT(*) AS n
    FROM     countries
    WHERE    region = 'Europe'
""").df()

# UNION ALL: row counts for both tables in one query
conn.execute("""
    SELECT 'countries'   AS table_name, COUNT(*) AS n FROM countries
    UNION ALL
    SELECT 'trade_flows' AS table_name, COUNT(*) AS n FROM trade_flows
""").df()


# ── ALTER and UPDATE ───────────────────────────────────────────────────────

# ALTER TABLE: add a new column to an existing table (existing rows get NULL)
conn.execute("ALTER TABLE countries ADD COLUMN income_group VARCHAR")

conn.execute("""
    SELECT *
    FROM   countries
""").df()

# UPDATE: fill in values for the new column
conn.execute(
    "UPDATE countries SET income_group = 'High income'  WHERE region = 'Europe'"
)
conn.execute(
    "UPDATE countries SET income_group = 'Upper middle' WHERE region = 'LATAM'"
)

conn.execute("SELECT * FROM countries").df()


# ── Close the connection ───────────────────────────────────────────────────────
conn.close()

# END