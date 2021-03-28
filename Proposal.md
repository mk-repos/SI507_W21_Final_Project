# Data Sources

- [Open Exchange Rates JSON API](https://docs.openexchangerates.org/) (Score 4, API key) - Usage: Get exchange rate for the specified currency and date.
- [Time Series Stock APIs](https://www.alphavantage.co/documentation/) (Score 4, API key) - Usage: Get historical time-series data of the specified stock.
- [Financial Market Data APIs (Stock)](https://polygon.io/) (Score 4, API key) - Usage: Get latest news of the specified ticker symbol.

I've already made the following requests, and successfully cached the results in json files.
- Based on combinations of date and currency, get the exchange rate against USD
- Based on a ticker symbol, get the historical daily prices of the stock in the past 20 years
- Based on a ticker symbol, get the latest news (title, URL, summary, etc.)
The number of records retrieved was kept small, but it can be easily expanded in the final version by changing some of the parameters. Since the currency/stock data will be huge, they will likely to be stored using SQL, not in json.


# Project Summary

If a non-US foreign citizen trades stocks in the US, they must calculate the gain/loss in their home currency and report it to the tax authorities in their home country. This is an extremely tedious task, because in addition to the stock prices on the dates of acquisition/sale, the exchange rates on the dates of acquisition/sale must be taken into account going back one year in the past.

This program automatically performs this calculation based on the transaction history of US brokerages uploaded by the user, and also displays useful information such as historical price changes and latest news.

# Features to be Implemented

 - **Import** a CSV file of the trading history issued by an US broker for a tax year.
 - **Convert** gains/losses in USD to gains/losses in a currency chosen by the user, based on the exchange rates on each trading day.
 - **Display and export** the converted transaction history as a HTML table and a CSV file.
 - **Display** the changes in net gain/loss in a currency chosen by the user for that tax year by graphs.
 - **Display** the end-of-day prices of the stock selected by the user for that tax year by graphs.
 - **Display** the latest news of the stock selected by the user.

# Notes on Compatibility

 We need to know the format of the transaction history of every US brokerage firm, but for this project we will limit ourselves to **Firstrade Securities Inc.**, for which we were able to obtain a sample file.
 
 However, the program will be designed with expandability in mind, so that it can support the formats of other brokers by adding functions in the future.