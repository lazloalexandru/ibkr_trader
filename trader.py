import datetime
import queue
import threading
import time
import curses
import torch
import  numpy as np
import pandas as pd

from my_ibapi_app import IBApi
from model import Net
from watchlist import quotes
import common_utils as cu
import chart


def _run_loop(app):
    app.run()


def _init_ibkr(sw, id):
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


def print_quote_info(sym_params):
    qw = curses.newwin(2, curses.COLS, 0, 0)

    qw.clear()
    qw.addstr(0, 0, 'Quote', curses.color_pair(1))
    qw.addstr(1, 0, sym_params['symbol'], curses.color_pair(3))

    initial_market_cap = round(sym_params['shares_outstanding'] * sym_params['base_price'])
    qw.addstr(0, 8, 'MCap', curses.color_pair(1))
    cg = 4 if initial_market_cap < 10 else 5
    qw.addstr(1, 8, '%sM' % initial_market_cap, curses.color_pair(cg))

    qw.addstr(0, 15, 'Shares/Float', curses.color_pair(1))
    cg = 4 if sym_params['float'] < 3 else 5
    qw.addstr(1, 15, '%sM / %sM' % (sym_params['shares_outstanding'], sym_params['float']), curses.color_pair(cg))

    qw.addstr(0, 30, 'News', curses.color_pair(1))
    news = "-" if sym_params['news'] is None else sym_params['news']
    qw.addstr(1, 30, '%s' % news, curses.color_pair(3))

    qw.refresh()


def select_quote(scr):
    idx = None
    n = len(quotes)

    scr.clear()
    scr.refresh()

    if n > 0:
        scr.addstr(4, 5, "Select Quote")
        scr.addstr(5, 5, "(press a key between  1 .. " + str(n) + ")")

        for i in range(0, n):
            scr.addstr(7 + i, 5, str(i+1) + " -> " + quotes[i]['symbol'])

        while idx not in range(0, n):
            key_pressed = scr.getch()
            idx = key_pressed - ord('1')
            scr.refresh()

    scr.clear()
    scr.refresh()

    return idx


def _server_clock(app, time_storage):
    app.reqCurrentTime()

    try:
        requested_time = time_storage.get(timeout=1)
    except queue.Empty:
        requested_time = None

    return requested_time


def _info_box(df, label):
    pw = curses.newwin(20, curses.COLS, 4, 0)

    pw.clear()

    sd = 10
    r = 0

    ########################################################################

    pw.addstr(r, 0, 'AI  =>', curses.color_pair(1))
    pw.addstr(r, 10, 'BUY', curses.color_pair(6))
    pw.addstr(r, 20, 'SELL', curses.color_pair(6))
    pw.addstr(r, 30, 'Label: %s' % label, curses.color_pair(6))
    r += 2

    ########################################################################

    close = df.iloc[-1]['Close']
    cg = 5 if close > trading_params['__min_close_price'] else 4
    pw.addstr(r, 0, 'Price', curses.color_pair(1))
    pw.addstr(r, sd, '%.2f$' % close, curses.color_pair(cg))
    r += 1

    ########################################################################

    vol = df.iloc[-1]['Volume']
    cg = 5

    pw.addstr(r, 0, '1MinVol', curses.color_pair(1))
    pw.addstr(r, sd, '%sk' % round(vol/1000), curses.color_pair(cg))
    r += 1

    ########################################################################

    current_volume = sum(df['Volume'].tolist())
    cg = 5

    pw.addstr(r, 0, 'Volume', curses.color_pair(1))
    pw.addstr(r, sd, '%1.fM' % (current_volume / 1000000), curses.color_pair(cg))
    r += 1

    ########################################################################

    pxv = close * current_volume
    cg = 5 if pxv > trading_params['min_volume_x_price'] else 4
    pw.addstr(r, 0, 'PxV', curses.color_pair(1))
    pw.addstr(r, sd, '%.2fM' % (pxv / 1000000), curses.color_pair(cg))
    r += 1

    ########################################################################

    pw.refresh()


def _asses_1min_chart(app, req_store, model):
    sw = curses.newwin(1, curses.COLS, curses.LINES - 2, 0)

    xxx = None
    while not app.wrapper.is_error() and xxx is None:
        try:
            xxx = req_store.get(timeout=1)
        except queue.Empty:
            xxx = None

    if len(app.data) == 0:
        sw.addstr(0, 0, "No data", curses.color_pair(2))
        sw.refresh()
    else:
        df = pd.DataFrame(app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])
        _t = pd.to_datetime(df.iloc[-1]["Time"], format="%Y%m%d  %H:%M:%S")

        with torch.no_grad():
            df = cu.gen_chart_data_prepared_for_ai(df, trading_params)
            state = chart.create_padded_state_vector(df)

            state = np.reshape(state, (5, 390))
            state = torch.tensor(state, dtype=torch.float).unsqueeze(0).unsqueeze(0).to("cuda")

            buy_output = model(state)
            res = buy_output.max(1)[1].view(1, 1)
            predicted_label = res[0][0].to("cpu").numpy()

            _info_box(df, predicted_label)


def main(scr):
    curses.curs_set(0)
    curses.cbreak()
    curses.resize_term(30, 45)

    scr.nodelay(1)
    scr.timeout(1)

    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_RED)
    curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_GREEN)
    curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_WHITE)

    sw1 = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)
    sw2 = curses.newwin(1, curses.COLS, curses.LINES - 2, 0)
    sw3 = curses.newwin(1, curses.COLS, curses.LINES - 3, 0)

    if len(quotes) == 0:
        sw1.addstr(0, 0, "No quotes in watchlist. See \'watchilist.py\' file.", curses.color_pair(3))
        sw1.refresh()
    else:
        selected_id = select_quote(scr)

        sw1.addstr(0, 0, "Connecting to TWS ...", curses.color_pair(1))
        sw1.refresh()

        app = _init_ibkr(sw3, selected_id)
        time_queue = app.init_time()
        symbol = quotes[selected_id]['symbol']
        req_store = app.init_req_queue()

        sw1.clear()
        sw1.addstr(0, 0, "Connected!", curses.color_pair(1))
        sw1.refresh()

        app.data = []

        app.reqHistoricalData(2001, cu.contract(symbol), "", '1 D', '1 min', 'TRADES', 0, 1, True, [])

        sw2.clear()
        sw2.refresh()

        model = Net(trading_params[])

        key_pressed = None
        while key_pressed != 17:
            sw1 = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)

            unix_time = _server_clock(app, time_queue)
            current_time = datetime.datetime.utcfromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S')
            sw1.addstr(0, 0, current_time, curses.color_pair(1))
            sw1.addstr(0, 30, "Quit [Ctrl+Q]", curses.color_pair(1))
            sw1.refresh()

            print_quote_info(quotes[selected_id])
            _asses_1min_chart(app, req_store)

            key_pressed = scr.getch()


trading_params = {
        '__chart_begin_hh': 9,
        '__chart_begin_mm': 30,
        '__chart_end_hh': 15,
        '__chart_end_mm': 59,

        '__min_close_price': 1.5,
        '__max_close_price': 20,

        'trading_begin_hh': 9,
        'trading_begin_mm': 40,
        'last_entry_hh': 15,
        'last_entry_mm': 55,

        'stop': -5,

        'min_volume': 0,
        'min_volume_x_price': 10000000,

        'num_classes': 7
}

curses.wrapper(main)




