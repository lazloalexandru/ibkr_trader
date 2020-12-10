from ibapi.contract import Contract
from ibapi.order import Order
import pandas as pd
from termcolor import colored


def contract(symbol):
    c = Contract()
    c.symbol = symbol
    c.secType = 'STK'
    c.exchange = 'SMART'
    c.currency = 'USD'

    return c


def to_tick_price(x):
    x = int(100 * x) / 100.0
    return x


def BracketOrder(parentOrderId: int,
                 quantity: float,
                 limitPrice: float,
                 takeProfitLimitPrice: float,
                 stopLossPrice: float):
    parent = Order()
    parent.orderId = parentOrderId
    parent.action = "BUY"
    parent.orderType = "LMT"
    parent.totalQuantity = quantity
    parent.lmtPrice = to_tick_price(limitPrice)
    parent.transmit = False

    takeProfit = Order()
    takeProfit.orderId = parent.orderId + 1
    takeProfit.action = "SELL"
    takeProfit.orderType = "LMT"
    takeProfit.totalQuantity = quantity
    takeProfit.lmtPrice = to_tick_price(takeProfitLimitPrice)
    takeProfit.parentId = parentOrderId
    takeProfit.transmit = False

    stopLoss = Order()
    stopLoss.orderId = parent.orderId + 2
    stopLoss.action = "SELL"
    stopLoss.orderType = "STP"
    stopLoss.auxPrice = to_tick_price(stopLossPrice)
    stopLoss.totalQuantity = quantity
    stopLoss.parentId = parentOrderId
    stopLoss.transmit = True

    bracketOrder = [parent, takeProfit, stopLoss]
    return bracketOrder

# ! [bracket]


def gen_chart_data_prepared_for_ai(df, p):
    if df is not None:
        df.Time = pd.to_datetime(df.Time, format="%Y-%m-%d  %H:%M:%S")

        idx = get_time_index(df, p['__chart_begin_hh'], p['__chart_begin_mm'], 0)
        if idx is not None:
            df = df[idx:]
            df.reset_index(drop=True, inplace=True)

        idx = get_time_index(df, p['__chart_end_hh'], p['__chart_end_mm'], 0)
        if idx is not None:
            df = df[:idx+1]
            df.reset_index(drop=True, inplace=True)

    return df


def get_time_index(df, h, m, s):
    idx = None

    xtime = df.iloc[0]["Time"]
    xtime = xtime.replace(hour=h, minute=m, second=s)

    x_idx = df.index[df['Time'] == xtime].tolist()
    n = len(x_idx)
    if n == 1:
        idx = x_idx[0]
    elif n > 1:
        print(colored("ERROR ... Intraday chart contains more than one bars with same time stamp!!!", color='red'))
    else:
        print(colored("Warning!!! ... Intraday chart contains no timestamp: " + str(xtime) + "   n: " + str(n), color='yellow'))

    return idx
