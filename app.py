# Import modules --------------------------------------------------------------
import datetime
import json
import requests
import sqlite3  # database
import os  # file handling
import glob
import shutil  # file handling
import pandas as pd  # data handling
import numpy as np
import mplfinance as mpf  # showing candle plots
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from flask import Flask, request, send_file, render_template


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


# Change matplotlib to backend mode -------------------------------------------
matplotlib.use('Agg')


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
    """Check if a table with the same name already exists in the database

    Parameters
    ----------
    conn
        connection to database
    tablename : str
        table to be checked if it exists

    Returns
    -------
    bool
        True if it exists
    """
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
    """Load a table in the database as a pandas DataFrame

    Parameters
    ----------
    conn
        connection to database
    tablename : str
        table to be converted

    Returns
    -------
    pd.DataFrame
        dataframe converted from a table in SQL DB
    """
    # get table as a pandas dataframe
    statement = f"""
        SELECT *
        FROM '{tablename}';
    """
    df = pd.read_sql_query(statement, conn)
    return df


# Exchange Rates --------------------------------------------------------------
def gen_table_for_currency(conn, currency: str):
    '''Generate a table of the currency in the database if not exist

    Parameters
    ----------
    conn
        connection to database
    currency: str
        currency of choice

    Returns
    -------
    None
    '''
    cur = conn.cursor()
    statement = f'''
        CREATE TABLE IF NOT EXISTS "Rates{currency}" (
            "Date" NUMERIC PRIMARY KEY UNIQUE,
            "Rates" REAL NOT NULL
        );
    '''
    cur.execute(statement)


def load_table_currency(conn, currency: str):
    """Load a table of the curency in the database as a pandas DataFrame

    Parameters
    ----------
    conn
        connection to database
    currency : str
        currency of choice

    Returns
    -------
    pd.DataFrame
        dataframe converted from a table
    """
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
    '''Insert a record of exchange rate to the database

    Parameters
    ----------
    conn
        connection to database
    currency: str
        currency of choice
    date: str
        date of choice
    rate: str
        exchange rate of that currency on that day

    Returns
    -------
    None
    '''
    cur = conn.cursor()
    statement = f"""
        INSERT INTO "Rates{currency}"
        VALUES ('{date}', {rate})
    """
    cur.execute(statement)
    conn.commit()


def get_rates_for(currency: str, date: str):
    """Make a API call to get the daily exchange rates against USD

    Parameters
    ----------
    currency : str
        currency to be acquired
    date : str
        date to be acquired

    Returns
    -------
    dict
        returned json from the api call
    """
    baseurl = f"https://openexchangerates.org/api/historical/{date}.json"
    params = {"app_id": OEG_APP_ID, "symbols": currency, "base": "USD"}
    return make_request(baseurl=baseurl, params=params)


def get_rates_with_cache(conn, currency: str, date: str):
    """Get the daily exchange rates against USD with caching to database

    Parameters
    ----------
    conn
        connection to database
    currency : str
        currency to be acquired
    date : str
        date to be acquired

    Returns
    -------
    float
        exchange rate on that day
    """
    df = load_table_currency(conn, currency)
    # if not cached
    if not df.Date.isin([date]).any():
        response = get_rates_for(currency=currency, date=date)
        # update database
        insert_rate(conn, currency, date, response["rates"][currency])
        # reload database
        df = load_table_currency(conn, currency)
    return df.query(f'Date == "{date}"')["Rates"].iloc[-1]


# Sample Cases ------------------------
# sample_currencies = ["JPY", "AUD", "CAD"]
# sample_dates = []
# for m in ["01", "04", "07", "10"]:
#     for d in ["01", "05", "10", "15", "20", "25"]:
#         sample_dates.append(f"2020-{m}-{d}")

# for currency in sample_currencies:
#     for date in sample_dates:
#         get_rates_with_cache(conn, currency, date)


# Stock Info ------------------------------------------------------------------

# ETFs --------------------------------
def gen_table_for_ETF(conn):
    '''Generate a table for ETFs in the database if not exist

    Parameters
    ----------
    conn
        connection to database

    Returns
    -------
    None
    '''
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
    '''Insert a record of etf to the database

    Parameters
    ----------
    conn
        connection to database
    symbol: str
        ticker symbol of the ETF
    name: str
        full name of the ETF
    exchange: str
        exchange in which the ETF is traded

    Returns
    -------
    None
    '''
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
    """Insert all ETFs available in the market into the database

    Parameters
    ----------
    conn
        connection to the database
    """
    baseurl = f"https://financialmodelingprep.com/api/v3/etf/list"
    params = {"apikey": FMP_API_KEY}
    etfs = make_request(baseurl=baseurl, params=params)
    for etf in etfs:
        insert_etf(conn, etf["symbol"], etf["name"], etf["exchange"])


def delete_table_for_ETF(conn):
    """Delete old records of ETF in the database

    Parameters
    ----------
    conn
        connection to the database
    """
    cur = conn.cursor()
    statement = f"""
        DELETE FROM ETFs
    """
    cur.execute(statement)
    conn.commit()


def get_all_ETFs_with_cache(conn):
    """Get all ETFs available in the market and cache them in the database

    Parameters
    ----------
    conn
        connection to the database

    Returns
    -------
    pd.DataFrame
        dataframe containing all the ETFs
    """
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

# Sample Code ------------------------------
# etfs = get_all_ETFs_with_cache(conn)
# etfs


# Companies --------------------------------
def gen_table_for_company(conn):
    '''Generate a table for companies in the database if not exist

    Parameters
    ----------
    conn
        connection to database

    Returns
    -------
    None
    '''
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
    '''Insert a record of a company to the database

    Parameters
    ----------
    conn
        connection to database
    symbol: str
        ticker symbol of the company
    name: str
        full name of the company
    exchange: str
        exchange in which the company is traded

    Returns
    -------
    None
    '''
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
    """Make an API call to get company info

    Parameters
    ----------
    symbol : str
        ticker symbol of the company

    Returns
    -------
    dict
        returned json
    """
    baseurl = "https://financialmodelingprep.com/api/v3/search"
    params = {"query": symbol, "apikey": FMP_API_KEY, "limit": "1"}
    return make_request(baseurl=baseurl, params=params)


# def get_market_cap_for(symbol: str):
#     baseurl = f"https://financialmodelingprep.com/api/v3/"\
#         f"market-capitalization/{symbol}"
#     params = {"apikey": FMP_API_KEY}
#     return make_request(baseurl=baseurl, params=params)


def fill_record_for_company(conn, symbol):
    """Insert a record of the company into the database
       after making an API request

    Parameters
    ----------
    conn
        connection to the database
    symbol : str
        ticker symbol of the company
    """
    # call APIs
    info = get_company_info_for(symbol)
    # insert new record into db
    insert_company(conn=conn,
                   symbol=symbol,
                   name=info[0]["name"],
                   exchange=info[0]["exchangeShortName"])


def get_company_info_with_cache(conn, symbol: str):
    """Get company info using a API call & caches in the database

    Parameters
    ----------
    conn
        connection to the database
    symbol : str
        ticker symbol of the company

    Returns
    -------
    pd.DataFrame
        pandas DataFrame containing info of the company
    """
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
    '''Generate a table for EPSs in the database if not exist

    Parameters
    ----------
    conn
        connection to database

    Returns
    -------
    None
    '''
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
    '''Insert a record of EPS in the latest 4 quarters for the company

    Parameters
    ----------
    conn
        connection to database
    symbol: str
        ticker symbol of the company
    eps1date: str
        closing date of the quarter
    eps1reported:
        actual EPS reported
    eps1expected:
        consensus estimates of EPS

    Returns
    -------
    None
    '''
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
    """For the selected companym, get EPSs in the latest four quarters

    Parameters
    ----------
    symbol : str
        ticker symbol of the company

    Returns
    -------
    dict
        returned json from the API call
    """
    baseurl = "https://www.alphavantage.co/query"
    params = {
        "function": "EARNINGS",
        "symbol": symbol,
        "apikey": ALPHA_API_KEY
    }
    return make_request(baseurl=baseurl, params=params)


def fill_record_for_eps(conn, symbol):
    """Insert a record of EPSs for the selected company
       using API. If it reaches API limit, pass

    Parameters
    ----------
    conn
        connection to the database
    symbol : str
        ticker symbol of the company
    """
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
    """Delete a record of the company from EPS table in the database

    Parameters
    ----------
    conn
        connection to the database
    symbol : str
        ticker symbol of the company
    """
    cur = conn.cursor()
    statement = f"""
        DELETE FROM EPS
        WHERE Symbol='{symbol}'
    """
    cur.execute(statement)
    conn.commit()


def get_eps_with_cache(conn, symbol: str):
    """Get EPSs of the company using API & caches in the database

    Parameters
    ----------
    conn
        connection to the database
    symbol : str
        ticker symbol of the company

    Returns
    -------
    pd.DataFrame
        DataFrame containing EPSs of the company
    """
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
# sample_companies = ["AAPL", "BNTX", "DAL", "MAR", "NVAX", "MRNA"]
# for company in sample_companies:
#     company_record = get_company_info_with_cache(conn, company)
#     eps_record = get_eps_with_cache(conn, company)

# # should give error (not in parent table)
# try:
#     get_eps_with_cache(conn, "CVS")
# except sqlite3.IntegrityError:
#     print("EPS: Foreign key constraint is working correctly")


# Time Series -----------------------------------------------------------------
def gen_table_for_history(conn, year: str):
    '''Generate a table of timeseries for a year in the database if not exist

    Parameters
    ----------
    conn
        connection to database
    year: str
        year of choice

    Returns
    -------
    None
    '''
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
            "Ratio" REAL
        );
    '''
    cur.execute(statement)


def get_history_for(symbol: str):
    """Make an API call to get time series of the company

    Parameters
    ----------
    symbol : str
        ticker symbol of the company

    Returns
    -------
    dict
        returned json
    """
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
    '''Insert a record of daily price data of the selected company/date

    Parameters
    ----------
    conn
        connection to database
    symbol: str
        ticker symbol of the company/ETF
    date: str
        date of this record
    open: str
        open price of the stock on that day
    high: str
        highest price of the stock on that day
    low: str
        lowest price of the stock on that day
    close: str
        closing price of the stock on that day
    volume: str
        trading volume of the stock on that day
    adjusted: str
        adjusted closing price accounting for split/devidend


    Returns
    -------
    None
    '''
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
    """Load a table of timeseries of the year in the database
       as a pandas DataFrame

    Parameters
    ----------
    conn
        connection to database
    year : str
        year of choice

    Returns
    -------
    pd.DataFrame
        dataframe converted from a table
    """
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
    """Get time series of the selected company/year
       using API call and cache in the database

    Parameters
    ----------
    conn
        connection to the database
    symbol : str
        ticker symbol of the copany
    year : str
        year of choice

    Returns
    -------
    pd.DataFrame
        DataFrame containing time series data
    """
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
# sample_symbols = ["AAPL", "BNTX"]
# sample_years = ["2020"]

# for symbol in sample_symbols:
#     for year in sample_years:
#         df = get_history_with_cache(conn, symbol, year)


# Draw TimeSeries Graphs ------------------------------------------------------
def gen_plot_history(conn, symbol: str, year: str, timestamp: str):
    """Draw&save time series plot of the selected company/year

    Parameters
    ----------
    conn
        connection to the server
    symbol : str
        ticker symbol of the company
    year : str
        year of choice
    timestamp : str
        timestamp indicating when this function called,
        used for filenames in order to prevent browser cache
    """
    df = get_history_with_cache(conn, symbol, year)
    # remove existing plot
    if glob.glob('images/history*.png'):
        for f in glob.glob("images/history*.png"):
            os.remove(f)
    # when API call limit reached
    if len(df) == 0:
        # show error message as an image
        shutil.copy("error_hist_not_shown.png",
                    f"images/history{timestamp}.png")
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
                 savefig=f"images/history{timestamp}.png")


# Sample Cases ------------------------
# if more than 5 new API call made,
# we show an error message as an image
# sample_symbols = ["MAR", "MRNA", "NVAX"]
# sample_years = ["2019", "2020"]
# for symbol in sample_symbols:
#     for year in sample_years:
#         gen_plot_history(conn, symbol, year)


# Financial News --------------------------------------------------------------
def get_news(symbol):
    """Get latest 5 news for the company by making API call

    Parameters
    ----------
    symbol : str
        ticker symbol of the company

    Returns
    -------
    dict
        returned json
    """
    baseurl = f"https://api.polygon.io/v1/meta/symbols/{symbol}/news"
    params = {"perpage": "5",
              "page": "1",
              "apiKey": POLYGON_API_KEY}
    response = make_request(baseurl=baseurl, params=params)
    today = datetime.date.today()
    response = {"Fetched": today.strftime("%Y-%m-%d"), "News": response}
    return response


def get_news_with_cache(symbol):
    """Get latest 5 news for the company using API call and cache

    Parameters
    ----------
    symbol : str
        ticker symbol of the company

    Returns
    -------
    dict
        returned json
    """
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
# sample_companies = ["AAPL", "BNTX"]
# for company in sample_companies:
#     get_news_with_cache(company)


# Flask App -------------------------------------------------------------------

# Helper funcs ------------------------
def clean_dollar_to_float(value):
    """Remove "$" signs and "," from string

    Parameters
    ----------
    value : str
        value with "$" signs and "," (ex. $5,444.00)

    Returns
    -------
    str
        cleaned string
    """
    return (value.replace('$', '').replace(',', ''))


def clean_date_firstrade(datestr):
    """Format datetime of original CSV

    Parameters
    ----------
    datestr : str
        a string of the date in original format

    Returns
    -------
    str
        converted string of the date (i.e. 2020-01-01)
    """
    return datetime.datetime.strptime(datestr, '%m/%d/%Y').strftime('%Y-%m-%d')


def clean_firstrade(df):
    """Clean a transaction history of Firstrade Inc.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame directly generated by pd.read_csv()

    Returns
    -------
    pd.DataFrame
        cleaned dataframe
    """
    # set column names
    df.columns = df.iloc[0]
    # drop unnecessary rows
    df = df[1:-3]
    # select columns we need
    df = df.loc[:, [
        'Symbol', 'Quantity', 'Date Acquired', 'Date Sold', 'Sales Proceeds',
        'Cost'
    ]]
    # clean gain/loss in string, and convert them to float
    df['Sales'] = df['Sales Proceeds'].apply(clean_dollar_to_float).astype(
        'float')
    df = df.drop(['Sales Proceeds'], axis=1)
    df['Cost'] = df['Cost'].apply(clean_dollar_to_float).astype('float')
    # clean datetime format
    df['Date Acquired'] = df['Date Acquired'].apply(clean_date_firstrade)
    df['Date Sold'] = df['Date Sold'].apply(clean_date_firstrade)
    return df


def convert_transaction_history(conn, df, broker, currency):
    """Convert the original transaction history uploaded by the user
       to the selected currency

    Parameters
    ----------
    conn
        connection to the database
    df : pd.DataFrame
        original DataFrame directly generated by pd.read_csv()
    broker : str
        string indicating the brokeage firm the user is using
    currency : str
        string indicating the currency user want to convert to

    Returns
    -------
    pd.DataFrame
        cleaned and converted DataFrame
    """
    # clean data according to brokerage firm
    if broker == "firstrade":
        df = clean_firstrade(df)

    # get exchange rates of the selected currency
    df['Rate Acquired'] = df.apply(lambda x: get_rates_with_cache(
        conn=conn, currency=currency, date=x['Date Acquired']),
                                   axis=1)
    df['Rate Sold'] = df.apply(lambda x: get_rates_with_cache(
        conn=conn, currency=currency, date=x['Date Sold']),
                               axis=1)
    df = df.round({'Rate Acquired': 2, 'Rate Sold': 2})

    # calculate gain/loss in the selected currency
    df['Converted Cost'] = df['Cost'] * df['Rate Acquired']
    df['Converted Sales'] = df['Sales'] * df['Rate Sold']
    df = df.round({'Converted Cost': 2, 'Converted Sales': 2})

    # arrange columns
    df = df[[
        'Symbol', 'Quantity', 'Date Acquired', 'Cost', 'Rate Acquired',
        'Converted Cost', 'Date Sold', 'Sales', 'Rate Sold', 'Converted Sales'
    ]]

    # calculate gain/loss
    df['Gain&Loss'] = df['Converted Sales'] - df['Converted Cost']
    df = df.round({'Gain&Loss': 2})

    return df.sort_values(["Symbol", "Date Sold"])


def gen_plot_cumulative_gain(df, currency, filename):
    """Draw&save cumulative gain/loss plot

    Parameters
    ----------
    conn
        connection to the server
    currency : str
        currency of choice
    timestamp : str
        timestamp indicating when this function called,
        used for filenames in order to prevent browser cache
    """
    # remove existing plot
    if glob.glob('images/cumulative*.png'):
        for f in glob.glob("images/cumulative*.png"):
            os.remove(f)

    # find year
    tax_year = df.iat[0, 2][:4]

    # summing transactions by date
    cum = df.groupby(by=["Date Sold"]).sum().sort_index()[['Gain&Loss']]

    # fill in empty dates
    cum.index = pd.DatetimeIndex(cum.index)
    all_dates = pd.date_range(start=f"{tax_year}-01-01",
                              end=f"{tax_year}-12-31")

    # calculate cumulative sum for all dates
    cum = cum.reindex(all_dates).fillna(0.0).rename_axis('Date Sold').cumsum()

    # generate cumulative plot
    cum_plot = sns.lineplot(data=cum, x="Date Sold", y="Gain&Loss")
    cum_plot.set_title(f"Cumulative Gain and Loss in {tax_year} in {currency}")
    cum_plot.set_xlabel('')
    cum_plot.get_figure().savefig(f"images/{filename}")
    plt.close()


def output_csv(df):
    """Export pandas DataFrame to CSV

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame to be exported
    """
    # remove existing plot
    if os.path.exists("files/converted.csv"):
        os.remove("files/converted.csv")
    # save csv
    df.to_csv('files/converted.csv')


def clean_eps(eps):
    """Clean EPS data to draw a plot later

    Parameters
    ----------
    eps : pd.DataFrame
        original DataFrame

    Returns
    -------
    pd.DataFrame
        cleaned DataFrame in long format
    """
    # create dates column
    dates = eps[['EPS1Date', 'EPS2Date', 'EPS3Date', 'EPS4Date']]
    dates = dates.transpose().reset_index(drop=True)

    # create reported eps column
    reported = eps[[
        'EPS1Reported', 'EPS2Reported', 'EPS3Reported', 'EPS4Reported'
    ]]
    reported = reported.transpose().reset_index(drop=True)
    reported['Type'] = 'Reported'
    # join horizontally with dates
    reported = pd.concat([reported, dates], axis=1, ignore_index=True)
    reported = reported.rename(columns={0: "EPS", 1: "Type", 2: "Date"})

    # create expected eps column
    expected = eps[[
        'EPS1Expected', 'EPS2Expected', 'EPS3Expected', 'EPS4Reported'
    ]]
    expected = expected.transpose().reset_index(drop=True)
    expected['Type'] = 'Expected'
    # join horizontally with dates
    expected = pd.concat([expected, dates], axis=1, ignore_index=True)
    expected = expected.rename(columns={0: "EPS", 1: "Type", 2: "Date"})

    # join vertically
    return pd.concat([reported,
                      expected]).sort_values(['Type',
                                              'Date']).reset_index(drop=True)


def gen_plot_eps(eps, symbol, timestamp):
    """Draw&save EPS plot of the company

    Parameters
    ----------
    conn
        connection to the server
    symbol : str
        ticker symbol of the company
    timestamp : str
        timestamp indicating when this function called,
        used for filenames in order to prevent browser cache
    """
    if glob.glob('images/eps*.png'):
        for f in glob.glob("images/eps*.png"):
            os.remove(f)
    eps_plot = sns.barplot(x="Date", y="EPS", hue="Type", data=eps)
    eps_plot.set_title(
        f"Consensus Earnings Estimates vs Reported for {symbol}")
    eps_plot.get_figure().savefig(f"images/eps{timestamp}")
    plt.close()


# App ------------------------
app = Flask(__name__, static_url_path="", static_folder="images")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/converted', methods=['POST'])
def converted():
    conn = sqlite3.connect(DB)
    # get constants
    df = pd.read_csv(request.files.get('file'))
    broker = request.form['brokerage']
    currency = request.form['currency']
    # convert
    df = convert_transaction_history(conn=conn,
                                     df=df,
                                     broker=broker,
                                     currency=currency)
    # generate plot in '/images'
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    filename = f"cumulative{timestamp}.png"  # prevent browser cache
    gen_plot_cumulative_gain(df=df, currency=currency, filename=filename)
    # generate converted csv in '/files'
    output_csv(df)
    # prepare HTML table
    df_dict = df.to_dict('records')
    return render_template('converted.html',
                           df_dict=df_dict,
                           currency=currency,
                           filename=filename)


@app.route('/analysis/<symbol>')
def symbol(symbol):
    conn = sqlite3.connect(DB)
    # get timestamp for plots (prevent browser cache)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    # show plots of the latest tax year
    year = str(datetime.date.today().year - 1)
    # check if the symbol is an ETF
    etfs = get_all_ETFs_with_cache(conn)
    WHETHER_ETF = etfs.Symbol.isin([symbol]).any()
    # get info to display
    news_dict = get_news_with_cache(symbol)
    # draw time series plot
    gen_plot_history(conn=conn, symbol=symbol, year=year, timestamp=timestamp)
    history_filename = f"history{timestamp}.png"
    # for an ETF, we only display basic info
    if WHETHER_ETF:
        # get basic info
        info_dict = etfs[etfs['Symbol'] == symbol].to_dict('records')
        # ignore EPS
        eps = "Not Applicable"
        eps_filename = "Not Applicable"
    # for a company, we display more detailed info
    elif not WHETHER_ETF:
        # get basic info
        info_dict = get_company_info_with_cache(conn, symbol).to_dict('records')
        # draw EPS plot
        eps = get_eps_with_cache(conn, symbol)
        eps = clean_eps(eps)
        gen_plot_eps(eps=eps, symbol=symbol, timestamp=timestamp)
        eps_filename = f"eps{timestamp}.png"
    return render_template('symbol.html',
                           symbol=symbol,
                           year=year,
                           whether_etf=WHETHER_ETF,
                           info_dict=info_dict[0],
                           news_dict=news_dict,
                           history_filename=history_filename,
                           eps_filename=eps_filename)


@app.route('/download')
def download_file():
    path = "files/converted.csv"
    return send_file(path, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
