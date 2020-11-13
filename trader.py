import datetime
import queue
import threading
import time
import pandas as pd
import common_algos as ca
import common_utils as cu
import curses
from my_ibapi_app import IBApi
from watchlist import quotes


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
    mm = "mav8"
    ml = "mav13"

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
            pivots.append([val, True, df['Time'][max_idx]])
            idx_prev = i
        elif prev_state == False and state_open == True:
            min_idx, val = get_index_of_min(df, idx_prev, i)
            pivots.append([val, False, df['Time'][min_idx]])
            idx_prev = i

    return pivots


def show_time(app, time_queue):
    unix_time = _server_clock(app, time_queue)
    if unix_time is not None:
        current_time = datetime.datetime.utcfromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S')
        print(current_time, end="")


class Trader:
    def __init__(self, sym_id):
        self.sym_id = sym_id
        self.app = _init_ibkr(sym_id)
        self.time_queue = self.app.init_time()
        self.req_store = self.app.init_req_queue()
        self.in_a_trade = False

    def get_chart_data(self):
        xxx = None
        while not self.app.wrapper.is_error() and xxx is None:
            try:
                xxx = self.req_store.get(timeout=1)
            except queue.Empty:
                xxx = None

        if len(self.app.data) == 0:
            print("No Data ...")
        else:
            df = pd.DataFrame(self.app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])
            _add_indicators(df)

        return df

    def trade_loop(self):
        symbol = quotes[self.sym_id]['symbol']
        self.app.data = []
        self.app.reqHistoricalData(2001, cu.contract(symbol), "", '1 D', '1 min', 'TRADES', 0, 1, True, [])

        can_enter = False
        valid_pattern = False

        while True:
            print("\n")

            can_enter_prev = can_enter
            # show_time(app, time_queue)

            df = self.get_chart_data()

            pivots = get_pivots(df)
            if len(pivots) >= 2:
                pivots = pivots[-2:]

                print(pivots)

                if pivots[-1][1]:  # last pivot was a high
                    print("DOWNTREND")
                    valid_pattern = False
                    can_enter = False
                else:  # last pivot was a low
                    print("UPTREND  BUY@", pivots[-2][0], end="")
                    valid_pattern = True

            if not self.in_a_trade:
                if valid_pattern:
                    print("  Can Enter:", can_enter)

                    if df.iloc[-1]["Close"] < pivots[-2][0]:
                        can_enter = True
                    else:
                        can_enter = False

                    if can_enter_prev and not can_enter:
                        print("BUY@", pivots[-2][0])
                        self.in_a_trade = True
            else:
                if df.iloc[-1]["mav3"] < df.iloc[-1]["mav5"]:
                    print("SELL")
                    self.in_a_trade = False

            print(df.iloc[-1]["Close"])


def main():
    t = Trader(0)
    t.trade_loop()


main()
