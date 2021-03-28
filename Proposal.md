# Datasources

 - Foreign Exchange Rates API
	 - Provider: European Central Bank
	 - Challenge Score: 3 (No authorization)
	 - URL: https://exchangeratesapi.io/
	 - Usage: Get historical rate for the specified currency pair.
 - Financial Data API
	 - Provider: Quandle
	 - Challenge Score: 4 (API key)
	 - URL: https://www.quandl.com/tools/api
	 - Usage: Get historical time-series data of the specified stock.
 - Financial Market Data APIs, Stock API
	 - Provider: polygon.io
	 - Challenge Score: 4 (API key)
	 - URL: https://polygon.io/
	 - Usage: Get latest news of the specified ticker symbol.


# Project Summary

If a non-US foreign citizen trades stocks in the US, they must calculate the gain/loss in their home currency and report it to the tax authorities in their home country. This is an extremely tedious task, because in addition to the stock prices on the dates of acquisition/sale, the exchange rates on the dates of acquisition/sale must be taken into account going back one year in the past.

This program automatically performs this calculation based on the transaction history of US brokerages uploaded by the user, and also displays useful information such as historical price changes and latest news.

We will use Flask, which allows us to build a simple user interface. Users can import files in a browser and we display series of tables and graphs on a page.


# Features to be Implemented

 - **Import** a CSV file of the trading history issued by an US broker for a tax year.
 - **Convert** gains and losses in USD to those in a currency chosen by the user, based on the exchange rates on each trading day.
 - **Display** the changes in net gain/loss in both currencies by graphs.
 - **Display** the historical price of the company selected by the user for that tax year by graphs.
 - **Display** the latest news of the company selected by the user.
 - **Display and export** the converted transaction history as a table/CSV.

# Notes on Compatibility

 We need to know the format of the transaction history of every US brokerage firm, but for this project we will limit ourselves to **Firstrade Securities Inc.**, for which we were able to obtain a sample file.
 
 However, the program will be designed with expandability in mind, so that it can support the formats of other brokers by adding functions in the future.