import datetime
import readchar
import queue
import threading
import time
import pandas as pd
import common_algos as ca
import common as cu
import curses
from my_ibapi_app import IBApi
from watchlist import quotes
import os


__log_path = "logs"


def _run_loop(app):
    app.run()


def _init_ibkr(id):
    app = IBApi()

    app.init_error()

    app.connect('127.0.0.1', 7497, 2000+id)
    api_thread = threading.Thread(target=_run_loop, args=(app,), daemon=True)
    api_thread.start()

    app.nextorderId = None

    # Check if the API is connected via orderid
    while True:
        if isinstance(app.nextorderId, int):
            print('Connected.')
            break
        else:
            print('Waiting for connection ...')
            time.sleep(1)

    return app


def get_next_order_id(app):
    app.nextorderId = -1
    app.reqIds(-1)

    while app.nextorderId < 0:
        print('Waiting for order ID')
        time.sleep(0.05)

    print("Next Order ID:", app.nextorderId)

    return app.nextorderId


def _calc_bagholder_score_from_ibkr_chart(app, req_store, symbol, sw):
    sw.addstr(0, 0, "Downloading " + symbol + " daily chart ...", curses.color_pair(1))
    sw.refresh()

    app.data = []
    app.reqHistoricalData(2000, cu.contract(symbol), "", '3 Y', '1 day', 'TRADES', 1, 1, False, [])

    xxx = None
    counter = 0
    while not app.wrapper.is_error() and xxx is None:
        try:
            xxx = req_store.get(timeout=1)
        except queue.Empty:
            counter += 1
            if counter > 1:
                counter = 0

            sss = "/" if counter == 1 else "\\"
            sw.addstr(0, 33, sss, curses.color_pair(1))
            sw.refresh()
            xxx = None

    while app.wrapper.is_error():
        sw.clear()
        message = symbol + "  --->  " + str(app.get_error(timeout=5))
        sw.addstr(0, 0, message, curses.color_pair(2))
        sw.refresh()

    bs = None

    if len(app.data) > 0:
        message = "Queried " + symbol + " Daily chart for " + str(len(app.data)) + " days"
        sw.addstr(0, 0, message, curses.color_pair(1))
        sw.refresh()
        df = pd.DataFrame(app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])
        bs = ca.get_bagholder_score(df)

    return bs


def _server_clock(app, time_storage):
    app.reqCurrentTime()

    try:
        requested_time = time_storage.get(timeout=1)
    except queue.Empty:
        requested_time = None

    return requested_time


def _add_indicators(df):
    df['mav3'] = df['Close'].rolling(window=3).mean()
    df['mav5'] = df['Close'].rolling(window=5).mean()
    df['mav8'] = df['Close'].rolling(window=8).mean()
    df['mav13'] = df['Close'].rolling(window=13).mean()

    return df


def get_index_of_min(df, start_idx, end_idx):
    mn = df['Low'][start_idx]
    idx = start_idx

    for i in range(start_idx+1, end_idx+1):
        if df['Low'][i] < mn:
            mn = df['Low'][i]
            idx = i

    return idx, mn  # str(df.loc[idx]['Time'].time())


def get_index_of_max(df, start_idx, end_idx):
    mx = df['High'][start_idx]
    idx = start_idx

    for i in range(start_idx+1, end_idx+1):
        if df['High'][i] > mx:
            mx = df['High'][i]
            idx = i

    return idx, mx  # str(df.loc[idx]['Time'].time()), mx


def get_pivots(df):
    mm = "mav5"
    ml = "mav8"

    pivots = []
    start_idx = df.index[20]
    idx_prev = start_idx

    state_open = False
    if df[mm][start_idx] > df[ml][start_idx]:
        state_open = True

    n = len(df)

    for i in range(start_idx, n):
        prev_state = state_open

        if df[mm][i] > df[ml][i]:
            state_open = True
        elif df[mm][i] < df[ml][i]:
            state_open = False

        if prev_state == True and state_open == False:
            max_idx, val = get_index_of_max(df, idx_prev, i)
            pivots.append([val, True, df['Time'][max_idx], max_idx])
            idx_prev = i
        elif prev_state == False and state_open == True:
            min_idx, val = get_index_of_min(df, idx_prev, i)
            pivots.append([val, False, df['Time'][min_idx], min_idx])
            idx_prev = i

    return pivots


def save_trade_log(order_id, symbol, action, time_, price, size):
    path = __log_path + "\\" + "trades.txt"

    if os.path.isfile(path):
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame(columns=['sym', 'time', 'action', 'price', 'size'])

    data = {
        'sym': symbol,
        'time': time_,
        'action': action,
        'price': price,
        'size': size,
        'orderid': order_id
    }

    df = df.append(data, ignore_index=True)
    print(df)

    df.to_csv(path, index=False)


def pattern_intact(df, pivots):
    if pivots[-1][1]:
        res = True
    else:
        start_idx = pivots[-1][3]
        end_idx = df.index[-1]

        res = True
        for i in range(start_idx, end_idx):
            res = res and df.iloc[-1]["High"] < pivots[-2][0]

    return res


class Trader:
    def __init__(self, sym_id):
        self.sym_id = sym_id
        self.app = _init_ibkr(sym_id)
        self.time_queue = self.app.init_time()
        self.req_store = self.app.init_req_queue()
        self.in_a_trade = False
        self.braket = None
        self.limit = None

    def server_time(self):
        xxx = None
        unix_time = _server_clock(self.app, self.time_queue)
        if unix_time is not None:
            current_time = datetime.datetime.utcfromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S')
            xxx = current_time
        return xxx

    def get_chart_data(self):
        xxx = None
        df = None

        while not self.app.wrapper.is_error() and xxx is None:
            try:
                xxx = self.req_store.get(timeout=1)
            except queue.Empty:
                xxx = None

        if len(self.app.data) == 0:
            print("No Data ...")
            while self.app.wrapper.is_error():
                msg = self.app.get_error(timeout=5)
                print(msg)
        else:
            df = pd.DataFrame(self.app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])
            _add_indicators(df)

        return df

    def trade_loop(self):
        symbol = quotes[self.sym_id]['symbol']
        self.app.data = []
        contract = cu.contract(symbol)
        self.app.reqHistoricalData(2001, contract, "", '1 D', '1 min', 'TRADES', 0, 1, True, [])

        can_enter = False
        valid_pattern = False
        last_pivot_idx = 0
        trend = ""

        while True:
            print("\n", symbol)

            df = self.get_chart_data()

            if df is not None:
                pivots = get_pivots(df)
                num_pivots = len(pivots)

                if num_pivots >= 2:
                    print(pivots[-2:])

                    if pivots[-1][1]:  # last pivot was a high
                        trend = "DOWNTREND"
                        valid_pattern = False
                        can_enter = False
                    else:  # last pivot was a low
                        trend = "UPTREND"
                        # if pattern_intact(df, pivots):
                        valid_pattern = True
                        trend = trend + "BUY @ " + str(pivots[-2][0])

                close = df.iloc[-1]["Close"]

                if not self.in_a_trade:
                    if valid_pattern:
                        if df.iloc[-1]["Close"] >= pivots[-2][0]:
                            if last_pivot_idx != num_pivots:
                                if df.iloc[-1]["mav3"] > df.iloc[-1]["mav5"]:
                                    order_id = get_next_order_id(self.app)

                                    last_pivot_idx = num_pivots
                                    print(" BUY@", pivots[-2][0])

                                    save_trade_log(order_id, symbol, "BUY", df.iloc[-1]["Time"], pivots[-2][0], 100)

                                    buyPrice = cu.to_tick_price(close * 1.01)
                                    profitTakePrice = cu.to_tick_price(buyPrice * 1.2)
                                    stopPrice = cu.to_tick_price(buyPrice * 0.95)

                                    print("Buy:", buyPrice, "Profit:", profitTakePrice, "STOP:", stopPrice)

                                    self.braket = cu.BracketOrder(parentOrderId=order_id,
                                                                  quantity=100,
                                                                  limitPrice=buyPrice,
                                                                  takeProfitLimitPrice=profitTakePrice,
                                                                  stopLossPrice=stopPrice)

                                    print("Orders:", self.braket[0].orderId, self.braket[1].orderId, self.braket[1].orderId)

                                    self.app.placeOrder(self.braket[0].orderId, contract, self.braket[0])
                                    self.app.placeOrder(self.braket[1].orderId, contract, self.braket[1])
                                    self.app.placeOrder(self.braket[2].orderId, contract, self.braket[2])

                                    self.in_a_trade = True
                else:
                    print("In a Trade!")

                    if df.iloc[-1]["mav3"] < df.iloc[-1]["mav5"]:
                        print("SELL")
                        sellPrice = cu.to_tick_price(close * 1.2)
                        self.braket[2].auxPrice = sellPrice
                        self.app.placeOrder(self.braket[2].orderId, contract, self.braket[2])

                        save_trade_log(self.braket[2].orderId, symbol, "SELL", df.iloc[-1]["Time"], df.iloc[-1]["Close"], 100)
                        self.in_a_trade = False

                print(trend, "   ", last_pivot_idx, num_pivots, "  ", df.iloc[-1]["Close"])

            time.sleep(0.5)


def select_stock():
    i = 0
    num_quotes = len(quotes)
    if num_quotes > 0:
        print("Press key between ", 1, "..", num_quotes)

        for q in quotes:
            i += 1
            print("     %s)" % i, q['symbol'])

        selected_id = int(readchar.readchar())
        while not 1 <= selected_id <= num_quotes:
            selected_id = int(readchar.readchar())

        print("SelectedId:", selected_id)

        return selected_id


def main():

    selected_id = select_stock()
    t = Trader(selected_id-1)
    t.trade_loop()


main()
