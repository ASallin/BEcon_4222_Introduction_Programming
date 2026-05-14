
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import duckdb


# ══════════════════════════════════════════════════════════════════════════════
# HOW THE THREE EXAMPLES DIFFER
# ──────────────────────────────────────────────────────────────────────────────
#
# All three classes connect to the same DuckDB database, but they differ in
# *when* and *how much* data they load:
#
#  Example 1  –  Load everything upfront
#    The entire database is fetched once in __init__ and stored as a DataFrame.
#    All methods then work purely in pandas, without touching the database again.
#    Simple to write, but loads data you may never use.
#
#  Example 2A  –  Query on demand (broad query)
#    __init__ only stores the database path — no data is loaded at creation.
#    Each method opens a connection and fetches the data it needs at call time.
#    The query still pulls all countries but is already limited to the
#    three relevant indicators and a single year.
#
#  Example 2B  –  Query on demand (targeted query)
#    Same on-demand approach as 2A, but the SQL is built dynamically so it
#    fetches only the indicator(s) the chosen measure actually needs, and
#    optionally restricts to the requested countries — minimising the data
#    transferred from the database to Python.
#
# ══════════════════════════════════════════════════════════════════════════════



# ──────────────────────────────────────────────────────────────────────────────
# EXAMPLE 1: Class retrieves all data initially
# ──────────────────────────────────────────────────────────────────────────────
#
# The simplest approach: when the object is created, _get_data() loads the
# entire dataset into memory as self.df and self.indicators. The database
# connection is then closed and never reopened. All methods work from the
# in-memory DataFrames.
#
# Upside:  easy to reason about — data is always available as plain pandas.
# Downside: pays the full loading cost upfront, regardless of what you need.

class InequalityExplorerV1:

    def __init__(self, db_path):
        self.db_path = db_path      # store the path as an attribute
        self.df   = None            # store full data as an attribute
        self.indicators = None      # store info on indicators as an attribute
        self._get_data()            # Attributes are initialised as None and populated by _get_data()


    def _get_data(self):
        # Open a connection, run all queries, then close automatically when the block exits
        # It is important to close the connection after we are done
        with duckdb.connect(self.db_path, read_only=True) as conn:

            # Create one big dataframe with all the data
            # we rename the name column from the country table to country_name to avoid confusion with the indicator name
            # we rename the name column from the indicator table to indicator_name to avoid confusion with the country name
            df = conn.execute("""
                SELECT
                    c.iso3,
                    c.name AS country_name,
                    c.region,
                    c.income_group,
                    o.year,
                    i.code,
                    o.value
                FROM observations o
                INNER JOIN countries  c
                    ON o.country_id   = c.country_id
                INNER JOIN indicators i
                    ON o.indicator_id = i.indicator_id
            """).df()

            # store the information on the indicators as an attribute as well
            self.indicators   = conn.execute("SELECT * FROM indicators").df()

        # Pivot from long to wide so each indicator becomes its own column.
        # The result has one row per country-year and one column per indicator code.
        # (You could also work with a long table)
        df = df.pivot_table(
            index   = ["iso3", "country_name", "year"],
            columns = "code",
            values  = "value"
        ).reset_index()

        df.columns.name = None

        # Store the whole dataframe as an attribute
        self.df = df



    def _prepare_kuznets(self, start_year=None, end_year=None):
        df = self.df.copy()
        df = df.sort_values(["iso3", "year"])

        if start_year is not None:
            df = df[df["year"] >= start_year]
        if end_year is not None:
            df = df[df["year"] <= end_year]

        df["NY.GDP.PCAP.KD"] = df.groupby("iso3")["NY.GDP.PCAP.KD"].transform(
            lambda x: x.interpolate(method="linear")
        )
        df["SI.POV.GINI"] = df.groupby("iso3")["SI.POV.GINI"].transform(
            lambda x: x.interpolate(method="linear")
        )

        df["log_gdp"] = np.log(df["NY.GDP.PCAP.KD"])

        df_avg = df.groupby(["iso3", "country_name"])[["log_gdp", "SI.POV.GINI"]].mean().reset_index()
        df_avg = df_avg.dropna(subset=["log_gdp", "SI.POV.GINI"])

        return df_avg



    def plot_kuznets(self, start_year=None, end_year=None, label_countries=None):
        df = self._prepare_kuznets(start_year=start_year, end_year=end_year)

        year_start = start_year if start_year is not None else self.df["year"].min()
        year_end   = end_year   if end_year   is not None else self.df["year"].max()

        coeffs = np.polyfit(df["log_gdp"], df["SI.POV.GINI"], deg=2)
        x_line = np.linspace(df["log_gdp"].min(), df["log_gdp"].max(), 200)
        y_line = np.polyval(coeffs, x_line)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(df["log_gdp"], df["SI.POV.GINI"], alpha=0.7, s=55)
        ax.plot(x_line, y_line, color="#DB1717", linewidth=2)

        # Highlighted dots for labeled countries
        if label_countries is not None:
            df_labels = df[df["iso3"].isin(label_countries)]
            ax.scatter(df_labels["log_gdp"], df_labels["SI.POV.GINI"], color="#1f77b4", alpha=0.7,
                edgecolors="black", linewidths=0.7, zorder=5)
            for _, row in df_labels.iterrows():
                ax.annotate(row["country_name"], (row["log_gdp"], row["SI.POV.GINI"]),
                    fontsize=10, xytext=(4, 4), textcoords="offset points")

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)



        ax.set_xlabel("Average Log GDP per capita (constant 2015 USD)")

        ax.set_ylabel("Average Gini index")
        ax.set_title(f"Kuznets curve ({year_start}–{year_end})", fontsize=14)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        ax.grid(axis='x', visible=False) # Keep x-axis clean

        plt.tight_layout()
        plt.show()


# ──────────────────────────────────────────────────────────────────────────────
# EXAMPLE 2A: Query on demand — broad query
# ──────────────────────────────────────────────────────────────────────────────
#
# __init__ stores only the database path; no data is loaded at object creation.
# Each time plot_inequality_ranking is called, _prepare_inequality_ranking
# opens a fresh connection, fetches the three inequality indicators for the
# requested year (all countries), and closes the connection before any pandas
# work begins.
#
# Compared to V1:
#   - No memory used between method calls.
#   - SQL filters by year and by three specific indicator codes,
#     so Python only ever handles the slice it needs.
#   - The decile ratio is still computed in pandas after the query.


class InequalityExplorerV2A:

    def __init__(self, db_path):
        self.db_path = db_path


    def _prepare_inequality_ranking(self, year, measure="gini", countries=None, top_n=10):

        # Fetch the three inequality indicators for the given year
        # ? is a placeholder for the year value — see conn.execute() below
        query = """
            SELECT
                c.iso3,
                c.name,
                i.code,
                o.value
            FROM observations o
            JOIN countries  c ON o.country_id   = c.country_id
            JOIN indicators i ON o.indicator_id = i.indicator_id
            WHERE i.code IN ('SI.POV.GINI', 'SI.DST.10TH.10', 'SI.DST.FRST.10')
              AND o.value IS NOT NULL
              AND o.year  = ?
            ORDER BY c.name
        """

        # Open a connection, run the query, then close automatically when the block exits
        with duckdb.connect(self.db_path, read_only=True) as conn:
            df = conn.execute(query, [year]).df()  # [year] maps to the ? placeholder


        # Pivot from long to wide so each indicator becomes its own column
        df = df.pivot_table(
            index   = ["iso3", "name"],
            columns = "code",
            values  = "value"
        ).reset_index()
        df.columns.name = None

        # Compute the decile ratio from the two income share columns
        df["decile_ratio"] = df["SI.DST.10TH.10"] / df["SI.DST.FRST.10"]

        # Keep only the selected measure and rename it to a generic column name
        if measure == "gini":
            df = df[["iso3", "name", "SI.POV.GINI"]].rename(columns={"SI.POV.GINI": "inequality"})
            df = df.dropna(subset=["inequality"])
        elif measure == "decile_ratio":
            df = df[["iso3", "name", "decile_ratio"]].rename(columns={"decile_ratio": "inequality"})
            df = df.dropna(subset=["inequality"])
        else:
            raise ValueError(f"Unknown measure '{measure}'. Choose 'gini' or 'decile_ratio'.")

        df = df.sort_values("inequality", ascending=False)

        # Either filter to the requested countries or take the top_n most unequal
        if countries is not None:
            df = df[df["iso3"].isin(countries)]
        else:
            df = df.head(top_n)

        return df



    def plot_inequality_ranking(self, year, measure="gini", countries=None, top_n=10):
        """
        Plot a horizontal bar chart of countries ranked by inequality.

        Parameters
        ----------
        year : int
            The year to query.
        measure : str
            Inequality measure: 'gini' (default) or 'decile_ratio'.
        countries : list of str, optional
            ISO3 codes to include. If None, shows the top_n most unequal countries.
        top_n : int
            Number of countries to show when no country list is given. Default 10.
        """

        measure_labels = {
            "gini":         "Gini index",
            "decile_ratio": "Decile ratio (top 10% / bottom 10%)",
        }

        # Use the helper method _prepare_inequality_ranking to get the data
        df = self._prepare_inequality_ranking(year=year, measure=measure, countries=countries)

        # Code for plotting
        fig, ax = plt.subplots(figsize=(8, max(4, len(df) * 0.35)))

        ax.barh(df["name"], df["inequality"], color="#4C72B0", alpha=0.85)
        ax.invert_yaxis()

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(True)
        ax.tick_params(left=False)
        ax.grid(axis="x", linestyle="--", alpha=0.4)
        ax.set_xlabel(measure_labels[measure])
        ax.set_title(f"Inequality ranking – {year}", fontsize=14, pad=30, loc='left')
        ax.text(
            x=0, y=1.07,
            s=measure_labels[measure],
            fontsize=11,
            color="#484646",
            transform=ax.transAxes
        )

        plt.tight_layout()
        plt.show()


# ──────────────────────────────────────────────────────────────────────────────
# EXAMPLE 2B: Query on demand — targeted query
# ──────────────────────────────────────────────────────────────────────────────
#
# Extends 2A by pushing more of the filtering work into SQL:
#   - Only the indicator(s) the chosen measure actually needs are fetched
#     (e.g. just 'SI.POV.GINI' for gini, or the two decile columns for the ratio).
#   - If a country list is provided, the query is extended with an IN clause so
#     only those rows are retrieved.
#
# This requires building the SQL string dynamically in Python using f-strings,
# which is slightly more advanced. The core idea: placeholders (?) are generated
# programmatically and the corresponding values are collected in a `params` list.
#
# Note: this level of optimisation is beyond what is expected for the group projects


class InequalityExplorerV2B:

    def __init__(self, db_path):
        self.db_path = db_path


    def _prepare_inequality_ranking(self, year, measure="gini", countries=None, top_n=10):

        params = [year]

        # Build the country filter if needed — one ? placeholder per country
        if countries is not None:
            placeholders   = ", ".join(["?"] * len(countries))
            country_filter = f"AND c.iso3 IN ({placeholders})"
            params.extend(countries)
        else:
            country_filter = ""

        # Only fetch the indicator(s) the chosen measure actually needs
        if measure == "gini":
            code_filter = "AND i.code = 'SI.POV.GINI'"
        elif measure == "decile_ratio":
            code_filter = "AND i.code IN ('SI.DST.10TH.10', 'SI.DST.FRST.10')"
        else:
            raise ValueError(f"Unknown measure '{measure}'. Choose 'gini' or 'decile_ratio'.")

        query = f"""
            SELECT
                c.iso3,
                c.name,
                i.code,
                o.value
            FROM observations o
            JOIN countries  c ON o.country_id   = c.country_id
            JOIN indicators i ON o.indicator_id = i.indicator_id
            WHERE o.value IS NOT NULL
              AND o.year  = ?
              {code_filter}
              {country_filter}
            ORDER BY c.name
        """

        with duckdb.connect(self.db_path, read_only=True) as conn:
            df = conn.execute(query, params).df()

        # The rest of the tasks is done with pandas (drop missing values, calculate decile ratio, sort values, pick top n)
        if measure == "gini":
            df = df.rename(columns={"value": "inequality"})[["iso3", "name", "inequality"]]
            df = df.dropna(subset=["inequality"])
        elif measure == "decile_ratio":
            df = df.pivot_table(index=["iso3", "name"], columns="code", values="value").reset_index()
            df.columns.name = None
            df["inequality"] = df["SI.DST.10TH.10"] / df["SI.DST.FRST.10"]
            df = df[["iso3", "name", "inequality"]].dropna(subset=["inequality"])

        df = df.sort_values("inequality", ascending=False)

        if countries is None:
            df = df.head(top_n)

        return df



    def plot_inequality_ranking(self, year, measure="gini", countries=None, top_n=10):
        """
        Plot a horizontal bar chart of countries ranked by inequality.

        Parameters
        ----------
        year : int
            The year to query.
        measure : str
            Inequality measure: 'gini' (default) or 'decile_ratio'.
        countries : list of str, optional
            ISO3 codes to include. If None, shows the top_n most unequal countries.
        top_n : int
            Number of countries to show when no country list is given. Default 10.
        """

        measure_labels = {
            "gini":         "Gini index",
            "decile_ratio": "Decile ratio (top 10% / bottom 10%)",
        }

        # Use the helper method _prepare_inequality_ranking to get the data
        df = self._prepare_inequality_ranking(year=year, measure=measure, countries=countries)

        # Code for plotting
        fig, ax = plt.subplots(figsize=(8, max(4, len(df) * 0.35)))

        ax.barh(df["name"], df["inequality"], color="#4C72B0", alpha=0.85)
        ax.invert_yaxis()

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(True)
        ax.tick_params(left=False)
        ax.grid(axis="x", linestyle="--", alpha=0.4)
        ax.set_xlabel(measure_labels[measure])
        ax.set_title(f"Inequality ranking – {year}", fontsize=14, pad=30, loc='left')
        ax.text(
            x=0, y=1.07,
            s=measure_labels[measure],
            fontsize=11,
            color="#484646",
            transform=ax.transAxes
        )

        plt.tight_layout()
        plt.show()




if __name__ == "__main__":
 
    path_to_database = "lecture11/wdi.db"      

    # ── Example 1 ─────────────────────────────────────────────────────────────
    test_v1 = InequalityExplorerV1(db_path=path_to_database)
 
    # Inspect the loaded data
    print(test_v1.df.head())
    print(test_v1.indicators)
 
    # Plot — label_countries takes ISO3 codes (e.g. 'DEU' not 'GER')
    test_v1.plot_kuznets(start_year=2000, end_year=2022, label_countries=["CHN", "USA", "DEU"])
 
    # Debug tip: call the helper directly to inspect the data before plotting
    debug_df = test_v1._prepare_kuznets(start_year=2000, end_year=2022)
    print(debug_df[debug_df["country_name"] == "Germany"])
 
    # ── Example 2A ────────────────────────────────────────────────────────────
    test_v2a = InequalityExplorerV2A(path_to_database)
    test_v2a.plot_inequality_ranking(
        year=2022, measure="decile_ratio",
        countries=["CHE", "USA", "MEX", "CHN", "DEU", "FRA", "CAN"],
    )
 
    # ── Example 2B ────────────────────────────────────────────────────────────
    test_v2b = InequalityExplorerV2B(path_to_database)
    test_v2b.plot_inequality_ranking(
        year=2022, measure="decile_ratio",
        countries=["CHE", "USA", "MEX", "CHN", "DEU", "FRA", "CAN"],
    )



