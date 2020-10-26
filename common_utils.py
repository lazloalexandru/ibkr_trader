from ibapi.contract import Contract


def contract(symbol):
    c = Contract()
    c.symbol = symbol
    c.secType = 'STK'
    c.exchange = 'SMART'
    c.currency = 'USD'

    return c
