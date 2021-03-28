# Import modules --------------------------------------------------------------
import json
import requests
import yfinance
# import mplfinance  # to show candle plot using matplotlib

# API keys --------------------------------------------------------------------
import secrets

OEG_APP_ID = secrets.OEG_APP_ID  # Open Exchange Rates
ALPHA_API_KEY = secrets.ALPHA_API_KEY  # Alpha Vantage
POLYGON_API_KEY = secrets.POLYGON_API_KEY  # polygon.io


# Helper Functions ------------------------------------------------------------
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


# Testing Open Exchange Rates -------------------------------------------------
def get_rates_for(symbol: str, date: str):
    baseurl = f"https://openexchangerates.org/api/historical/{date}.json"
    params = {
        "app_id": OEG_APP_ID,
        "symbols": symbol,
        "base": "USD"
    }
    return make_request(baseurl=baseurl, params=params)


def get_rates_with_cash(symbol: str,
                        date: str,
                        cache_file: str = "cached_rates.json"):
    cache_dict = open_cache(filename=cache_file)
    # if already cached
    if symbol in cache_dict and date in cache_dict[symbol]:
        print("fetching cached data")
        return cache_dict[symbol][date]
    else:
        # if the given currency is never cached
        if symbol not in cache_dict:
            cache_dict[symbol] = {}
        # get the rate for the given date
        response = get_rates_for(symbol=symbol, date=date)
        cache_dict[symbol][date] = response["rates"][symbol]
        save_cache(cache_dict, cache_file)
        return cache_dict[symbol][date]


rate = get_rates_with_cash(symbol="CAD", date="2020-01-01")
print(rate)


# Testing Time Series Stock APIs ----------------------------------------------
symbol = "BNTX"

baseurl = "https://www.alphavantage.co/query"
params = {
    "function": "TIME_SERIES_DAILY_ADJUSTED",  # account for split/dividend
    "symbol": symbol,
    "outputsize": "compact",  # if "full", get 20 years of data
    "apikey": ALPHA_API_KEY
}

response = make_request(baseurl=baseurl, params=params)

with open("cached_time_series.json", "w") as fobj:
    json.dump(response, fobj, indent=4)


# Testing Financial Data API --------------------------------------------------
symbol = "AAPL"
baseurl = f"https://api.polygon.io/v1/meta/symbols/{symbol}/news"
params = {"perpage": "10",
          "page": "1",
          "apiKey": POLYGON_API_KEY}

response = make_request(baseurl=baseurl, params=params)

with open("cached_news.json", "w") as fobj:
    json.dump(response, fobj, indent=4)
