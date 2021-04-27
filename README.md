# W21 SI507 Final Project

## Project Summary

This program will convert your US brokerage trading history into any currency and recalculate your gains and losses.

In addition, it provides analytical information about the companies in your portfolio, including EPS, historical prices, and the latest news.

## Required API Keys

You need to get the following four API keys and create a variable for each of them in `secrets.py`.

 - [Open Exchange Rates JSON API](https://docs.openexchangerates.org/) as `OEG_APP_ID`
 - [Financial Modeling Prep API](https://financialmodelingprep.com/developer/docs/) as `FMP_API_KEY`
 - [Alpha Vantage API](https://www.alphavantage.co/documentation/) as `ALPHA_API_KEY`
 - [Financial Market Data APIs](https://polygon.io/) as `POLYGON_API_KEY`

## Required Packages

 - SQL: `sqlite3`
 - File Handling: `os`, `shutil`, `glob`
 - Data Handling: `pandas`, `numpy`
 - Visualization: `matplotlib`, `seaborn`, `mlpfinance`
 - HTML: `flask`
 - Other Utilities: `json`, `request`, `datetime`

## Brief Instruction

 - Run `app.py` to get the flask app running
 - On the top page, the user uploads a `.csv` file and selects the brokerage firm and the currency to be converted from the pull-down menus.
 - On the next page, the user can view a graph of the annual net profit/loss changes, as well as the converted table. A button to download the converted `.csv` is also displayed.
 - If the user clicks on the ticker symbol on the table, the user will be redirected to the company's analytical report.
 - On the report page, the user can view basic information about its ticker symbol, EPS trends, stock price trends, and the latest news.
