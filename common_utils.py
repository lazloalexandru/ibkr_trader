from ibapi.contract import Contract
from ibapi.order import Order


def contract(symbol):
    c = Contract()
    c.symbol = symbol
    c.secType = 'STK'
    c.exchange = 'SMART'
    c.currency = 'USD'

    return c


# ! [bracket]
def BracketOrder(parentOrderId: int, action: str, quantity: float, limitPrice: float, takeProfitLimitPrice: float, stopLossPrice: float):
    parent = Order()
    parent.orderId = parentOrderId
    parent.action = action
    parent.orderType = "MKT"
    parent.totalQuantity = quantity
    parent.lmtPrice = limitPrice
    # The parent and children orders will need this attribute set to False to prevent accidental executions.
    # The LAST CHILD will have it set to True,
    parent.transmit = False

    takeProfit = Order()
    takeProfit.orderId = parent.orderId + 1
    takeProfit.action = "SELL"
    takeProfit.orderType = "LMT"
    takeProfit.totalQuantity = quantity
    takeProfit.lmtPrice = takeProfitLimitPrice
    takeProfit.parentId = parentOrderId
    takeProfit.transmit = False

    stopLoss = Order()
    stopLoss.orderId = parent.orderId + 2
    stopLoss.action = "SELL"
    stopLoss.orderType = "STP"
    # Stop trigger price
    stopLoss.auxPrice = stopLossPrice
    stopLoss.totalQuantity = quantity
    stopLoss.parentId = parentOrderId
    # In this case, the low side order will be the last child being sent. Therefore, it needs to set this attribute to True
    # to activate all its predecessors
    stopLoss.transmit = True

    bracketOrder = [parent, takeProfit, stopLoss]
    return bracketOrder

# ! [bracket]
