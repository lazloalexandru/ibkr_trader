import datetime
import queue
from termcolor import colored
import threading
import time
import pandas as pd
from ibapi.contract import Contract
import common_algos as ca
import curses
from my_ibapi_app import IBApi


__params = {
    'chart_begin_hh': 15,
    'chart_begin_mm': 15,

    'chart_end_hh': 19,
    'chart_end_mm': 0,

    'trading_begin_hh': 16,
    'trading_begin_mm': 41,

    'last_entry_hh': 17,
    'last_entry_mm': 30,

    'mavs': 3,
    'mavm': 8,
    'mavl': 21,

    'min_bagholder_score': 3,
    'max_range_score': 95,
    'vol_pattern_length': 3,

    'min_close_price': 1.5,

    'min_volume_x_price': 200000,
    'volume_jump_factor': 1.01,
    'mavl_distance_factor': 1.9,

    'stop': -7,
    'target': 15,
    'account_value': 10000,
    'size_limit': 50000
    }


def run_loop(app):
    app.run()


def init_ibkr():
    app = IBApi()

    app.init_error()

    app.connect('127.0.0.1', 7497, 2112)
    api_thread = threading.Thread(target=run_loop, args=(app,), daemon=True)
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


def contract(symbol):
    c = Contract()
    c.symbol = symbol
    c.secType = 'STK'
    c.exchange = 'SMART'
    c.currency = 'USD'

    return c


def calc_bagholder_score_from_ibkr_chart(app, req_store, symbol, scr):
    scr.addstr(1, 0, "Downloading " + symbol + " daily chart ...", curses.color_pair(2))
    scr.refresh()

    app.reqHistoricalData(2000, contract(symbol), "", '3 Y', '1 day', 'TRADES', 1, 1, False, [])

    xxx = None
    while not app.wrapper.is_error() and xxx is None:
        try:
            xxx = req_store.get(timeout=1)
        except queue.Empty:
            print(".", end="", flush=True)
            xxx = None

    while app.wrapper.is_error():
        print(symbol, "  --->  ", app.get_error(timeout=5))

    message = "Queried " + symbol + " Daily chart for " + str(len(app.data)) + " days"

    scr.addstr(4, 0, message, curses.color_pair(2))
    scr.refresh()

    bs = None

    if len(app.data) == 0:
        print(colored(message, 'red'))
    else:
        print(message, "\n")
        df = pd.DataFrame(app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])

        bs = ca.get_bagholder_score1(df)

    return bs


def trader(app, scr, symbol, params):
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)

    ibkr_contract = contract(symbol)

    req_store = app.init_req_queue()

    app.data = []

    bs = calc_bagholder_score_from_ibkr_chart(app, req_store, symbol, scr)

    scr.clear()
    scr.addstr(0, 0, symbol + " bagholder_score: " + str(bs), curses.color_pair(2))
    scr.refresh()

    tr_begin_time = datetime.datetime.now()
    tr_begin_time = tr_begin_time.replace(hour=params['trading_begin_hh'], minute=params['trading_begin_mm'], second=0)
    last_entry_time = datetime.datetime.now()
    last_entry_time = last_entry_time.replace(hour=params['last_entry_hh'], minute=params['last_entry_mm'], second=0)
    forced_sell_time = datetime.datetime.now()
    forced_sell_time = forced_sell_time.replace(hour=params['chart_end_hh'], minute=params['chart_end_hh'], second=0)

    print("Trading Begins Time: ", tr_begin_time.time())
    print("Last Entry Time:     ", last_entry_time.time())
    print("Forced Sell Time:    ", forced_sell_time.time())

    app.data = []

    app.reqHistoricalData(2001, ibkr_contract, "", '1 D', '1 min', 'TRADES', 0, 1, True, [])

    while True:
        scr.addstr(0, 40, "...", curses.color_pair(2))
        scr.refresh()

        xxx = None
        num_tries = 0
        while not app.wrapper.is_error() and xxx is None:
            try:
                xxx = req_store.get(timeout=1)
            except queue.Empty:
                num_tries = num_tries + 1
                print(".", end="", flush=True)
                xxx = None

        scr.addstr(0, 40, "   ", curses.color_pair(2))
        scr.refresh()

        df = pd.DataFrame(app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])

        rs = ca.calc_last_bar_range_score(df)
        df = ca.calc_num_volumes_lower(df)

        df['mavs'] = df['Close'].rolling(window=params['mavs']).mean()
        df['mavm'] = df['Close'].rolling(window=params['mavm']).mean()
        df['mavl'] = df['Close'].rolling(window=params['mavl']).mean()

        _t = pd.to_datetime(df.iloc[-1]["Time"], format="%Y%m%d  %H:%M:%S")

        traded_value = int(df.iloc[-1]['Close'] * df.iloc[-1]['Volume'])
        if traded_value < 0:
            traded_value = 0

        ali_closed = df.iloc[-1]['mavs'] < df.iloc[-1]['mavm'] < df.iloc[-1]['mavl']
        ali_opened = df.iloc[-1]['mavs'] > df.iloc[-1]['mavm'] > df.iloc[-1]['mavl']

        scr.clear()
        scr.addstr(2, 0, "%.2f" % df.iloc[-1]["Close"] + "$", curses.color_pair(3))
        scr.refresh()

        print(colored("SELL Signal [Active]  " if ali_closed else "SELL Signal [Inactive]  ", "yellow" if ali_closed else "grey"),
              colored(str(_t.time()) + "  ", "green" if tr_begin_time < _t < last_entry_time else "red"),
              colored("%.2f" % df.iloc[-1]["Close"] + "$  ", "green" if df.iloc[-1]["Close"] > params['min_close_price'] else "red"),
              colored("  Bagholder_Score: " + str(bs), "green" if bs >= params['min_bagholder_score'] else "red"),
              colored("  Range_Score: " + str(rs), "green" if rs < params['max_range_score'] else "red"),
              colored("  Aligator", "green" if ali_opened else "red"),
              colored("  VolumesLower: " + str(df.iloc[-1]['vol_high_count']), "green" if df.iloc[-1]['vol_high_count'] >= params['vol_pattern_length'] else "red"),
              colored("  Traded_Value: $" + f'{traded_value:,}', "green" if traded_value > params['min_volume_x_price'] else "red"),

              )

        time.sleep(5)

#################################


def main(scr):
    curses.curs_set(0)

    scr.clear()
    scr.addstr(0, 0, "Connecting to TWS ...", curses.color_pair(1))
    scr.refresh()

    app = init_ibkr()

    scr.addstr(0, 30, "Connected!", curses.color_pair(3))
    scr.refresh()

    trader(app, scr, symbol="MRIN", params=__params)


curses.wrapper(main)




