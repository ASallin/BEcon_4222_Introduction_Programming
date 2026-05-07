import time

import duckdb
import pandas as pd
from skimpy import skim


# ── EXTRACT ───────────────────────────────────────────────────────────────────

DATA_DIR = "week_10/data/BACI_HS22_V202601"

# Trade flows: one CSV per year
df_flows_2022 = pd.read_csv(f"{DATA_DIR}/BACI_HS22_Y2022_V202601.csv")

# Country and product reference tables
df_countries_raw = pd.read_csv(f"{DATA_DIR}/country_codes_V202601.csv")
df_products_raw = pd.read_csv(f"{DATA_DIR}/product_codes_HS22_V202601.csv")


# ── Short ANALYSE ───────────────────────────────────────────────────────────────────
# Short exploration to inform the database schema design. This helps us sketch the model.

skim(df_flows_2022)
skim(df_countries_raw)
skim(df_products_raw)

# --- Structure ---
print(df_flows_2022.dtypes)
print(df_flows_2022.head())

# --- String samples ---
df_countries_raw.head()
print(df_countries_raw.dtypes)
print(df_products_raw.dtypes)

df_products_raw.head()


# ── Sketch the model ───────────────────────────────────────────────────────────────────


# ── Create the model ───────────────────────────────────────────────────────────────────

# Always open the connection to the database
conn = duckdb.connect("week_10/trade.db")

# Drop in FK dependency order so re-runs don't crash (safety, you can also erase the .db file manually)
conn.execute("DROP TABLE IF EXISTS flows")
conn.execute("DROP TABLE IF EXISTS products")
conn.execute("DROP TABLE IF EXISTS countries")

# Countries
conn.execute("""
    CREATE OR REPLACE TABLE countries (
        country_code    INTEGER PRIMARY KEY,
        country_name    VARCHAR,
        country_iso2    VARCHAR,
        country_iso3    VARCHAR
    )
""")

# Products
conn.execute("""
    CREATE OR REPLACE TABLE products (
        code    INTEGER PRIMARY KEY,
        description    VARCHAR
    )
""")

# DDL: Create tables
conn.execute("""
    CREATE OR REPLACE TABLE flows (
        year        INTEGER NOT NULL,
        exporter_id INTEGER NOT NULL REFERENCES countries(country_code),
        importer_id INTEGER NOT NULL REFERENCES countries(country_code),
        product_id  INTEGER NOT NULL REFERENCES products(code),
        value       FLOAT,
        quantity    FLOAT,
        PRIMARY KEY (year, exporter_id, importer_id, product_id)
    )
""")

conn.execute("""
    SHOW TABLES
""").df()


# ── TRANSFORM ─────────────────────────────────────────────────────────────────

# The BACI data is already in a transformed state, because the .zip contains a star schema.


# ── LOAD  ──────────────────────────────────────────────────────────────────────

# You can bulk load all flows  together. For the sake of the exercise, we will load the tables one by one.

conn.execute("INSERT INTO countries SELECT * FROM df_countries_raw")
conn.execute("INSERT INTO products SELECT * FROM df_products_raw")

# Initial load: 2022
conn.execute("INSERT INTO flows SELECT * FROM df_flows_2022")

# Simulate receiving new data: append 2023 and 2024
df_flows_2023 = pd.read_csv(f"{DATA_DIR}/BACI_HS22_Y2023_V202601.csv")
df_flows_2024 = pd.read_csv(f"{DATA_DIR}/BACI_HS22_Y2024_V202601.csv")

# You need around 30 seconds to load the rows.
conn.execute("INSERT INTO flows SELECT * FROM df_flows_2023")
conn.execute("INSERT INTO flows SELECT * FROM df_flows_2024")

# Inspect
print(conn.execute("SHOW TABLES").df())
print(conn.execute("DESCRIBE countries").df())
print(conn.execute("DESCRIBE flows").df())

# Close the connection and reopen in read-only mode to prevent accidental modifications
conn.close()


# ── QUERIES ON FLOWS ───────────────────────────────────────────────────────────────────

# Open on read only mode to prevent accidental modifications
conn = duckdb.connect("week_10/trade.db", read_only=True)

# Q1. Query all the columsn of the first five rows
print(
    conn.execute("""
        SELECT *
            FROM flows
            LIMIT 5
      """).df()
)

# Q2. SELECT specific columns
print(
    conn.execute("""
    SELECT year, exporter_id, value
    FROM   flows
    LIMIT  5
""").df()
)

# Q3. WHERE: flows from Switzerland (country_code = 757)
print(
    conn.execute("""
    SELECT *
    FROM   flows
    WHERE  exporter_id = 757
    LIMIT  5
""").df()
)

# Q4. WHERE + AND: Swiss exports in 2022 above 1M USD (value in thousands)
print(
    conn.execute("""
    SELECT *
    FROM   flows
    WHERE  exporter_id = 757
      AND  year = 2022
      AND  value > 1000
    ORDER BY value DESC
    LIMIT  5
""").df()
)

# Q5. COUNT: how many export flows?
print(
    conn.execute("""
    SELECT   COUNT(*) AS n_flows
    FROM     flows
""").df()
)


# Q6. UNION ALL: row counts for both tables in one query
# (Note: in a UNION ALL, column names always come from the first SELECT, regardless of what you name them in subsequent selects. The aliases in the second query are simply ignored.)
# (Note: we fill the first column with a constant string to identify the table, because the column names in the result will be the same for both tables.)
conn.execute("""
    SELECT 'countries' AS table_name
            , COUNT(*) AS n
        FROM countries
    UNION ALL
    SELECT 'trade_flows' AS Idontcare
            , COUNT(*) AS bs
        FROM flows
""").df()

# Strange behavior of UNION ALL in DuckDB with coercion.
conn.execute("""
    DESCRIBE (
        SELECT country_code, country_name
            FROM countries
            WHERE country_code IN (757)
        UNION ALL
        SELECT exporter_id, value
            FROM flows
            WHERE year = 2022 AND exporter_id = 757 AND value between 1200 and 1201
    )
""").df()


# ── JOINS ───────────────────────────────────────────────────────────────────

# J1. flows joined with countries: exporter and importer names
conn.execute("""
    SELECT  f.exporter_id,              --not necessary
            f.importer_id,              --not necessary
            exp.country_name AS exporter,
            imp.country_name AS importer,
            f.value
    FROM    flows AS f
    INNER JOIN countries AS exp
            ON f.exporter_id = exp.country_code
    INNER JOIN countries AS imp
            ON f.importer_id = imp.country_code
    LIMIT   10
""").df()


# J2. flow rows with product description
print(
    conn.execute("""
    SELECT  f.year,
            exp.country_name AS exporter,
            imp.country_name AS importer,
            p.description AS product,
            f.value
    FROM    flows AS f
    INNER JOIN products AS p
            ON f.product_id = p.code
    INNER JOIN countries AS exp
            ON f.exporter_id = exp.country_code
    INNER JOIN countries AS imp
            ON f.importer_id = imp.country_code
    LIMIT   10
""").df()
)

# J3 with WHERE: Swiss exports with product description
conn.execute("""
    SELECT  f.year,
            exp.country_name AS exporter,
            imp.country_name AS importer,
            p.description AS product,
            f.value
    FROM    flows AS f
    INNER JOIN products AS p
            ON f.product_id = p.code
    INNER JOIN countries AS exp
            ON f.exporter_id = exp.country_code
    INNER JOIN countries AS imp
            ON f.importer_id = imp.country_code
    WHERE exp.country_name = 'Switzerland'
            AND imp.country_name = 'France'
            AND f.year = 2022
    LIMIT   10
""").df()


# ── GROUP BY ───────────────────────────────────────────────────────────────────

# Typical analystical questions.

# GB1. How many flows per year?
conn.execute("""
    SELECT year,
            COUNT(*) AS n_flows
    FROM flows
    GROUP BY year
    ORDER BY year
""").df()


# GB2. How many export flows to Switzerland in 2022?
conn.execute("""
    SELECT  f.year,
            imp.country_name AS importer,
            sum(f.value) as total_value
    FROM    flows AS f
    INNER JOIN countries AS imp
            ON f.importer_id = imp.country_code
    WHERE imp.country_name = 'Switzerland'
            AND year = 2022
    GROUP BY f.year, imp.country_name
""").df()


# GB3. What is the average export value per exporter in 2022?
conn.execute("""
    SELECT  f.year,
            exp.country_name AS exporter,
            AVG(f.value) as avg_value
    FROM    flows AS f
    INNER JOIN countries AS exp
            ON f.exporter_id = exp.country_code
    WHERE year = 2022
    GROUP BY f.year, exp.country_name
    ORDER BY avg_value DESC
""").df()


# GB4. Which country exported the most in 2022?
conn.execute("""
    SELECT  f.year,
            exp.country_name AS exporter,
            SUM(f.value) as sum_value
    FROM    flows AS f
    INNER JOIN countries AS exp
            ON f.exporter_id = exp.country_code
    WHERE year = 2022
    GROUP BY f.year, exp.country_name
    ORDER BY sum_value DESC
""").df()


# GB5. What product were the most exported in 2024?
conn.execute("""
    SELECT  f.year,
            p.description AS product,
            SUM(f.value) as sum_value
    FROM    flows AS f
    INNER JOIN products AS p
            ON f.product_id = p.code
    WHERE year = 2024
    GROUP BY f.year, p.description
    ORDER BY sum_value DESC
    LIMIT 5
""").df()


# GB6. What product x country were the most exported in 2024?
conn.execute("""
    SELECT  f.year,
            exp.country_name AS exporter,
            p.description AS product,
            SUM(f.value) as sum_value
    FROM    flows AS f
    INNER JOIN countries AS exp
            ON f.exporter_id = exp.country_code
    INNER JOIN products AS p
            ON f.product_id = p.code
    WHERE year = 2024
    GROUP BY f.year, exp.country_name, p.description
    ORDER BY sum_value DESC
    LIMIT 5
""").df()


# GB7. Time series of Petroleum Oil exports from Russia
conn.execute("""
    SELECT  f.year,
            exp.country_name AS exporter,
            p.description AS product,
            SUM(f.value) as sum_value
    FROM    flows AS f
    INNER JOIN countries AS exp
            ON f.exporter_id = exp.country_code
    INNER JOIN products AS p
            ON f.product_id = p.code
    WHERE exp.country_name = 'Russian Federation'
        AND SUBSTRING(p.description, 1, 15) = 'Oils: petroleum'
    GROUP BY f.year, exp.country_name, p.description
    ORDER BY f.year DESC
""").df()


# ── HAVING ───────────────────────────────────────────────────────────────────

# H1. Only products exported from France with total value above 1B USD in 2022
# BACI numbers in 1000.
conn.execute("""
    SELECT  f.year,
            exp.country_name AS exporter,
            p.description AS product,
            SUM(f.value) as sum_value
    FROM    flows AS f
    INNER JOIN countries AS exp
            ON f.exporter_id = exp.country_code
    INNER JOIN products AS p
            ON f.product_id = p.code
    WHERE exp.country_name = 'France'
        AND year = 2022
    GROUP BY f.year, exp.country_name, p.description
    HAVING SUM(f.value) > 1000000
    ORDER BY f.year DESC
""").df()


# ── CTE ───────────────────────────────────────────────────────────────────

# A trivial CTE (as a coding example, not meaningful in itself):
conn.execute("""
    WITH top_exporters AS (
        SELECT  *
        FROM    flows
        WHERE   year = 2022
             AND value > 100000
    )
    SELECT  *
    FROM    top_exporters
    LIMIT   10
""").df()


# Year-over-year export growth. Hard to do in one query, more "natural" with a CTE:

# The cte separately:
conn.execute("""
SELECT  exporter_id,
            year,
            SUM(value) AS total_value
    FROM    flows
    WHERE   year IN (2022, 2023)
    GROUP BY exporter_id, year
""").df()

# The full query:
conn.execute("""
WITH exports_by_year AS (

    SELECT  exporter_id,
            year,
            SUM(value) AS total_value
    FROM    flows
    WHERE   year IN (2022, 2023)
    GROUP BY exporter_id, year
)
SELECT  c.country_name,
        e22.total_value AS exports_2022,
        e23.total_value AS exports_2023,
        ROUND((e23.total_value - e22.total_value) / e22.total_value * 100, 1) AS growth_pct
FROM    exports_by_year AS e22
JOIN    exports_by_year AS e23
        ON e22.exporter_id = e23.exporter_id
JOIN    countries       AS c
        ON e22.exporter_id = c.country_code
WHERE   e22.year = 2022
  AND   e23.year = 2023
ORDER BY growth_pct DESC
LIMIT   10
""").df()


# ── WINDOW FUNCTION ───────────────────────────────────────────────────────

# W1. Compute the sum of exports per exporter across all years
conn.execute("""
    SELECT  f.year,
        f.exporter_id,
        f.product_id,
        f.value,
        SUM(f.value) OVER (PARTITION BY f.exporter_id) AS exporter_total
    FROM    flows AS f
    LIMIT   10
""").df()

# ... which allows us to compute the percent of total exports for each flow, and rank the flows by value:
conn.execute("""
    SELECT  f.year,
        f.exporter_id,
        f.value,
        f.product_id,
        SUM(f.value) OVER (PARTITION BY f.exporter_id) AS exporter_total,
        ROUND(f.value/SUM(f.value) OVER (PARTITION BY f.exporter_id)*100, 2) AS exporter_share
    FROM    flows AS f
    ORDER BY exporter_share DESC
    LIMIT   10
""").df()

# W2. Rank the flows by value
conn.execute("""
    SELECT  exporter_id,
        year,
        value,
        RANK() OVER (ORDER BY value DESC) AS rank
    FROM    flows
    LIMIT   20
""").df()

# W3. Cumulative sum of exports over time
conn.execute("""
    WITH flows_per_year AS (
        SELECT  exporter_id,
                year,
                SUM(value)/1000 AS value
        FROM    flows
        GROUP BY exporter_id, year
    )
    SELECT  exporter_id,
        year,
        value,
        SUM(value) OVER (PARTITION BY exporter_id ORDER BY year ASC) AS cumsum
    FROM    flows_per_year
    LIMIT   20
""").df()

# W4. Top 10 exporters per year with rank
conn.execute("""
    SELECT  c.country_name,
            f.year,
            SUM(f.value)                                    AS total_value,
            RANK() OVER (PARTITION BY f.year
                         ORDER BY SUM(f.value) DESC)        AS rank
    FROM    flows AS f
    JOIN    countries AS c ON f.exporter_id = c.country_code
    GROUP BY c.country_name, f.year
    ORDER BY f.year, rank
    LIMIT   10
""").df()


# ── TIMING: pandas vs DuckDB ───────────────────────────────────────────────────
# Same query: total export value per exporter per year, top 10

df_all = pd.concat([df_flows_2022, df_flows_2023, df_flows_2024], ignore_index=True)

# pandas
t0 = time.perf_counter()
result_pd = (
    df_all.groupby(["t", "i"])["v"]
    .sum()
    .reset_index()
    .sort_values("v", ascending=False)
    .head(10)
)
t1 = time.perf_counter()
print(f"pandas:  {t1 - t0:.3f}s")
print(result_pd)

# DuckDB
t0 = time.perf_counter()
result_db = conn.execute("""
    SELECT   year, exporter_id, SUM(value) AS total_value
    FROM     flows
    GROUP BY year, exporter_id
    ORDER BY total_value DESC
    LIMIT    10
""").df()
t1 = time.perf_counter()
print(f"DuckDB:  {t1 - t0:.3f}s")
print(result_db)


# ── Close the connection ───────────────────────────────────────────────────────
conn.close()
