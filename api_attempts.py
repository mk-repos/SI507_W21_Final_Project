# Import modules --------------------------------------------------------------
import datetime
import json
import requests
import sqlite3  # database
import os  # file handling
import shutil  # file handling
import pandas as pd  # data handling
import mplfinance as mpf  # showing candle plots

# API keys --------------------------------------------------------------------
import secrets

OEG_APP_ID = secrets.OEG_APP_ID  # Open Exchange Rates
FMP_API_KEY = secrets.FMP_API_KEY  # FMP
ALPHA_API_KEY = secrets.ALPHA_API_KEY  # Alpha Vantage
POLYGON_API_KEY = secrets.POLYGON_API_KEY  # polygon.io

# Set up SQL DB ---------------------------------------------------------------
DB = "db.sqlite"
conn = sqlite3.connect(DB)
conn.execute("PRAGMA foreign_keys = 1")

# Set up cache file for News --------------------------------------------------
NEWS_CACHE = "cached_news.json"


# Helper Functions (General) --------------------------------------------------
def make_request(baseurl: str, params: dict):
    '''Make a request to the Web API

    Parameters
    ----------
    baseurl: str
        The URL for the API endpoint
    params: dict
        A dictionary of param:value pairs

    Returns
    -------
    dict
        the data returned from making the request
    '''
    response = requests.get(baseurl, params=params)
    return response.json()


def open_cache(filename: str):
    ''' Opens the cache file if it exists and loads the JSON
    if the cache file doesn't exist, creates a new cache dictionary

    Parameters
    ----------
    filename: str
        filename for the cache

    Returns
    -------
    dict
        The opened cache
    '''
    try:
        with open(filename, 'r') as fobj:
            cache_dict = json.load(fobj)
    except FileNotFoundError:
        cache_dict = {}
    return cache_dict


def save_cache(cache_dict: dict, filename: str):
    ''' Saves the current state of the cache to disk

    Parameters
    ----------
    cache_dict: dict
        The dictionary to save
    filename: str
        filename for the cache

    Returns
    -------
    None
    '''
    with open(filename, 'w') as fobj:
        json.dump(cache_dict, fobj, indent=4)


def check_table_exist(conn, tablename: str):
    cur = conn.cursor()
    statement = f"""
        SELECT count(name)
        FROM sqlite_master
        WHERE type ='table' AND name = '{tablename}';
    """
    cur.execute(statement)
    if cur.fetchone()[0] == 1:
        return True
    else:
        return False


def load_table_as_pd(conn, tablename: str):
    # get table as a pandas dataframe
    statement = f"""
        SELECT *
        FROM '{tablename}';
    """
    df = pd.read_sql_query(statement, conn)
    return df


# Exchange Rates --------------------------------------------------------------
def gen_table_for_currency(conn, currency: str):
    cur = conn.cursor()
    statement = f'''
        CREATE TABLE IF NOT EXISTS "Rates{currency}" (
            "Date" NUMERIC PRIMARY KEY UNIQUE,
            "Rates" REAL NOT NULL
        );
    '''
    cur.execute(statement)


def load_table_currency(conn, currency: str):
    # if there is no such table, generate new one
    if not check_table_exist(conn, f"Rates{currency}"):
        gen_table_for_currency(conn, currency)
    # get table as a pandas dataframe
    statement = f"""
        SELECT *
        FROM 'Rates{currency}';
    """
    df = pd.read_sql_query(statement, conn)
    # format as Datetime
    df.Date = pd.to_datetime(df.Date)
    return df


def insert_rate(conn, currency, date, rate):
    cur = conn.cursor()
    statement = f"""
        INSERT INTO "Rates{currency}"
        VALUES ('{date}', {rate})
    """
    cur.execute(statement)
    conn.commit()


def get_rates_for(currency: str, date: str):
    baseurl = f"https://openexchangerates.org/api/historical/{date}.json"
    params = {"app_id": OEG_APP_ID, "symbols": currency, "base": "USD"}
    return make_request(baseurl=baseurl, params=params)


def get_rates_with_cache(conn, currency: str, date: str):
    df = load_table_currency(conn, currency)
    # if not cached
    if not df.Date.isin([date]).any():
        response = get_rates_for(currency=currency, date=date)
        # update database
        insert_rate(conn, currency, date, response["rates"][currency])
        # reload database
        df = load_table_currency(conn, currency)
    return df.query(f'Date == "{date}"')["Rates"]


# Sample Cases ------------------------
sample_currencies = ["JPY", "AUD", "CAD"]
sample_dates = []
for m in ["01", "04", "07", "10"]:
    for d in ["01", "05", "10", "15", "20", "25"]:
        sample_dates.append(f"2020-{m}-{d}")

for currency in sample_currencies:
    for date in sample_dates:
        get_rates_with_cache(conn, currency, date)


# Stock Info ------------------------------------------------------------------

# ETFs --------------------------------
def gen_table_for_ETF(conn):
    cur = conn.cursor()
    statement = f"""
        CREATE TABLE IF NOT EXISTS "ETFs"(
            "Symbol" TEXT PRIMARY KEY UNIQUE,
            "Name" TEXT,
            "Exchange" TEXT,
            "LastUpdate" NUMERIC
        );
    """
    cur.execute(statement)


def insert_etf(conn, symbol, name, exchange):
    cur = conn.cursor()
    statement = f"""
        INSERT INTO "ETFs"
        VALUES (?, ?, ?, ?)
    """
    today = datetime.date.today()
    row = [symbol, name, exchange, today.strftime("%Y-%m-%d")]
    cur.execute(statement, row)
    conn.commit()


def fill_table_for_ETF(conn):
    baseurl = f"https://financialmodelingprep.com/api/v3/etf/list"
    params = {"apikey": FMP_API_KEY}
    etfs = make_request(baseurl=baseurl, params=params)
    for etf in etfs:
        insert_etf(conn, etf["symbol"], etf["name"], etf["exchange"])


def delete_table_for_ETF(conn):
    cur = conn.cursor()
    statement = f"""
        DELETE FROM ETFs
    """
    cur.execute(statement)
    conn.commit()


def get_all_ETFs_with_cache(conn):
    # if there is no such table, generate new one
    if not check_table_exist(conn, tablename="ETFs"):
        gen_table_for_ETF(conn)
    df = load_table_as_pd(conn, tablename="ETFs")
    # if the table is empty
    if len(df) == 0:
        fill_table_for_ETF(conn)
    else:
        # check when it's updated
        today = datetime.date.today()
        latest = datetime.datetime.strptime(df.LastUpdate.iloc[0],
                                            '%Y-%m-%d').date()
        delta = today - latest
        # if too old (more than 30 days)
        if delta.days >= 30:
            # delete old records
            delete_table_for_ETF(conn)
            # fill in new records
            fill_table_for_ETF(conn)
    # reload latest list
    df = load_table_as_pd(conn, tablename="ETFs")
    return df


etfs = get_all_ETFs_with_cache(conn)
etfs


# Companies --------------------------------
def gen_table_for_company(conn):
    cur = conn.cursor()
    statement = f'''
        CREATE TABLE IF NOT EXISTS "Companies" (
            "Symbol" TEXT PRIMARY KEY UNIQUE,
            "Name" TEXT,
            "Exchange" TEXT
        );
    '''
    cur.execute(statement)


def insert_company(conn, symbol, name, exchange):
    cur = conn.cursor()
    statement = f"""
        INSERT INTO "Companies"
        VALUES (?, ?, ?)
    """
    today = datetime.date.today()
    row = [symbol, name, exchange]
    cur.execute(statement, row)
    conn.commit()


def get_company_info_for(symbol: str):
    baseurl = "https://financialmodelingprep.com/api/v3/search"
    params = {"query": symbol, "apikey": FMP_API_KEY, "limit": "1"}
    return make_request(baseurl=baseurl, params=params)


def get_market_cap_for(symbol: str):
    baseurl = f"https://financialmodelingprep.com/api/v3/"\
        f"market-capitalization/{symbol}"
    params = {"apikey": FMP_API_KEY}
    return make_request(baseurl=baseurl, params=params)


def fill_record_for_company(conn, symbol):
    # call APIs
    info = get_company_info_for(symbol)
    # insert new record into db
    insert_company(conn=conn,
                   symbol=symbol,
                   name=info[0]["name"],
                   exchange=info[0]["exchangeShortName"])


def get_company_info_with_cache(conn, symbol: str):
    # if there is no such table, generate new one
    if not check_table_exist(conn, tablename="Companies"):
        gen_table_for_company(conn)
    df = load_table_as_pd(conn, tablename="Companies")
    # if not cached
    if not df.Symbol.isin([symbol]).any():
        fill_record_for_company(conn, symbol)
        # reload df
        df = load_table_as_pd(conn, tablename="Companies")
    return df.query(f"Symbol == '{symbol}'")


# EPS ---------------------------------
def gen_table_for_eps(conn):
    cur = conn.cursor()
    statement = f'''
        CREATE TABLE IF NOT EXISTS "EPS" (
            "Symbol" TEXT PRIMARY KEY UNIQUE,
            "EPS1Date" NUMERIC,
            "EPS1Reported" REAL,
            "EPS1Expected" REAL,
            "EPS2Date" NUMERIC,
            "EPS2Reported" REAL,
            "EPS2Expected" REAL,
            "EPS3Date" NUMERIC,
            "EPS3Reported" REAL,
            "EPS3Expected" REAL,
            "EPS4Date" NUMERIC,
            "EPS4Reported" REAL,
            "EPS4Expected" REAL,
            "LastUpdate" NUMERIC,
            FOREIGN KEY(Symbol)
                REFERENCES Companies(Symbol)
        );
    '''
    cur.execute(statement)


def insert_eps(conn, symbol,
               eps1date, eps1reported, eps1expected,
               eps2date, eps2reported, eps2expected,
               eps3date, eps3reported, eps3expected,
               eps4date, eps4reported, eps4expected):
    cur = conn.cursor()
    statement = f"""
        INSERT INTO "EPS"
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    today = datetime.date.today()
    row = [
        symbol, eps1date, eps1reported, eps1expected,
        eps2date, eps2reported, eps2expected,
        eps3date, eps3reported, eps3expected,
        eps4date, eps4reported, eps4expected,
        today.strftime("%Y-%m-%d")
    ]
    cur.execute(statement, row)
    conn.commit()


def get_eps_for(symbol: str):
    baseurl = "https://www.alphavantage.co/query"
    params = {
        "function": "EARNINGS",
        "symbol": symbol,
        "apikey": ALPHA_API_KEY
    }
    return make_request(baseurl=baseurl, params=params)


def fill_record_for_eps(conn, symbol):
    try:
        # call APIs
        eps = get_eps_for(symbol)
        # insert new record into db
        insert_eps(conn=conn,
                   symbol=symbol,
                   eps1date=eps["quarterlyEarnings"][0]["fiscalDateEnding"],
                   eps1reported=eps["quarterlyEarnings"][0]["reportedEPS"],
                   eps1expected=eps["quarterlyEarnings"][0]["estimatedEPS"],
                   eps2date=eps["quarterlyEarnings"][1]["fiscalDateEnding"],
                   eps2reported=eps["quarterlyEarnings"][1]["reportedEPS"],
                   eps2expected=eps["quarterlyEarnings"][1]["estimatedEPS"],
                   eps3date=eps["quarterlyEarnings"][2]["fiscalDateEnding"],
                   eps3reported=eps["quarterlyEarnings"][2]["reportedEPS"],
                   eps3expected=eps["quarterlyEarnings"][2]["estimatedEPS"],
                   eps4date=eps["quarterlyEarnings"][3]["fiscalDateEnding"],
                   eps4reported=eps["quarterlyEarnings"][3]["reportedEPS"],
                   eps4expected=eps["quarterlyEarnings"][3]["estimatedEPS"])
    except KeyError:
        print(f"EPS({symbol}): API call limit reached. Try again later.")


def delete_record_for_eps(conn, symbol):
    cur = conn.cursor()
    statement = f"""
        DELETE FROM EPS
        WHERE Symbol='{symbol}'
    """
    cur.execute(statement)
    conn.commit()


def get_eps_with_cache(conn, symbol: str):
    # if there is no such table, generate new one
    if not check_table_exist(conn, tablename="EPS"):
        gen_table_for_eps(conn)
    df = load_table_as_pd(conn, tablename="EPS")
    # if not cached
    if not df.Symbol.isin([symbol]).any():
        fill_record_for_eps(conn, symbol)
    else:
        # check when it's updated
        today = datetime.date.today()
        update = df.query(f"Symbol == '{symbol}'").LastUpdate.iloc[0]
        update = datetime.datetime.strptime(update, '%Y-%m-%d').date()
        delta = today - update
        # if too old (more than 10 days)
        if delta.days >= 10:
            # delete old record
            delete_record_for_eps(conn, symbol)
            # fill new record
            fill_record_for_eps(conn, symbol)
    # reload db
    df = load_table_as_pd(conn, tablename="EPS")
    return df.query(f"Symbol == '{symbol}'")


# Sample Cases ------------------------
sample_companies = ["AAPL", "BNTX", "DAL", "MAR", "NVAX", "MRNA"]
for company in sample_companies:
    company_record = get_company_info_with_cache(conn, company)
    eps_record = get_eps_with_cache(conn, company)

# should give error (not in parent table)
try:
    get_eps_with_cache(conn, "CVS")
except sqlite3.IntegrityError:
    print("EPS: Foreign key constraint is working correctly")


# Time Series -----------------------------------------------------------------
def gen_table_for_history(conn, year: str):
    cur = conn.cursor()
    statement = f'''
        CREATE TABLE IF NOT EXISTS "History{year}" (
            "Date" NUMERIC,
            "Symbol" TEXT,
            "Open" REAL,
            "High" REAL,
            "Low" REAL,
            "Close" REAL,
            "Volume" REAL,
            "AdjustedClose" REAL,
            "Ratio" REAL,
            FOREIGN KEY(Symbol)
                REFERENCES Companies(Symbol)
        );
    '''
    cur.execute(statement)


def get_history_for(symbol: str):
    baseurl = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",  # account for split/dividend
        "symbol": symbol,
        "outputsize": "full",  # if "full", get 20 years of data
        "apikey": ALPHA_API_KEY
    }
    return make_request(baseurl=baseurl, params=params)


def insert_history(conn, symbol, date, open, high, low, close, volume,
                   adjusted):
    # if there is no such table, generate new one
    if not check_table_exist(conn, f"History{date[:4]}"):
        gen_table_for_history(conn, date[:4])
    cur = conn.cursor()
    statement = f"""
        INSERT INTO "History{date[:4]}"
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    ratio = float(adjusted)/float(close)
    row = [date, symbol, open, high, low, close, volume, adjusted, ratio]
    cur.execute(statement, row)
    conn.commit()


def load_table_history(conn, year: str):
    # if there is no such table, generate new one
    if not check_table_exist(conn, f"History{year}"):
        gen_table_for_history(conn, year)
    # get table as a pandas dataframe
    statement = f"""
        SELECT *
        FROM 'History{year}';
    """
    df = pd.read_sql_query(statement, conn)
    # format as Datetime
    df.Date = pd.to_datetime(df.Date)
    return df


def get_history_with_cache(conn, symbol: str, year: str):
    if not check_table_exist(conn, f"History{year}"):
        gen_table_for_history(conn, year)
    # load db as pandas Dataframe
    df = load_table_history(conn, year)
    # if not cached
    if not df.Symbol.isin([symbol]).any():
        try:
            response = get_history_for(symbol=symbol)
            for k, v in response["Time Series (Daily)"].items():
                if k.startswith(year):
                    insert_history(conn,
                                   symbol=symbol,
                                   date=k,
                                   open=v["1. open"],
                                   high=v["2. high"],
                                   low=v["3. low"],
                                   close=v["4. close"],
                                   volume=v["6. volume"],
                                   adjusted=v["5. adjusted close"])
        # when API call limit (5 per minute) reached
        except KeyError:
            print(
                f"History({symbol}, {year}): API call limit reached.",
                "Try again later."
            )
        # reload database
        df = load_table_history(conn, year)
    # return price history for the given symbol & year
    return df.query(f"Symbol == '{symbol}'")


# Sample Cases ------------------------
sample_symbols = ["AAPL", "BNTX"]
sample_years = ["2020"]

for symbol in sample_symbols:
    for year in sample_years:
        df = get_history_with_cache(conn, symbol, year)

# should give error (not in parent table)
try:
    get_history_with_cache(conn, "CVS", "2020")
except sqlite3.IntegrityError:
    print("History: Foreign key constraint is working correctly")


# Sample Graphs -----------------------
def gen_plot_history(conn, symbol: str, year: str):
    df = get_history_with_cache(conn, symbol, year)
    # remove existing plot
    if os.path.exists("images/history.png"):
        os.remove("images/history.png")
    # when API call limit reached
    if len(df) == 0:
        # show error message as an image
        shutil.copy("images/history-error.png", "images/history.png")
    # when data available
    else:
        # adjust values accounting for split/dividend
        df["Close"] = df["AdjustedClose"]
        df["Open"] = df["Open"] * df["Ratio"]
        df["High"] = df["High"] * df["Ratio"]
        df["Low"] = df["Low"] * df["Ratio"]
        # generate new plot
        df.set_index("Date", inplace=True)
        mpf.plot(df.sort_values(by=["Date"]),
                 type="candle",
                 style="charles",
                 title=f"{symbol}, {year}, Adjusted Daily OHLC Prices",
                 volume=True,
                 savefig="images/history.png")


# if more than 5 new API call made,
# we show an error message as an image
sample_symbols = ["MAR", "MRNA", "NVAX"]
sample_years = ["2019", "2020"]
for symbol in sample_symbols:
    for year in sample_years:
        gen_plot_history(conn, symbol, year)


# Financial News --------------------------------------------------------------
def get_news(symbol):
    baseurl = f"https://api.polygon.io/v1/meta/symbols/{symbol}/news"
    params = {"perpage": "5",
              "page": "1",
              "apiKey": POLYGON_API_KEY}
    response = make_request(baseurl=baseurl, params=params)
    today = datetime.date.today()
    response = {"Fetched": today.strftime("%Y-%m-%d"), "News": response}
    return response


def get_news_with_cache(symbol):
    cache_dict = open_cache(filename=NEWS_CACHE)
    # if already cached
    if symbol in cache_dict:
        today = datetime.date.today()
        update = cache_dict[symbol]["Fetched"]
        update = datetime.datetime.strptime(update, '%Y-%m-%d').date()
        delta = today - update
        # if cache is old, get news again
        if delta.days >= 1:
            cache_dict[symbol] = get_news(symbol)
            save_cache(cache_dict=cache_dict, filename=NEWS_CACHE)
    # if never cached, get news
    else:
        cache_dict[symbol] = get_news(symbol)
        save_cache(cache_dict=cache_dict, filename=NEWS_CACHE)
    return cache_dict[symbol]


# Sample Cases ------------------------
sample_companies = ["AAPL", "BNTX"]
for company in sample_companies:
    get_news_with_cache(company)
