from ibapi.contract import Contract
from ibapi.order import Order


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
