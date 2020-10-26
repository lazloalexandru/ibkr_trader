import datetime
import queue
from termcolor import colored
import threading
import time
import pandas as pd
import common_algos as ca
import common_utils as cu
import curses
from my_ibapi_app import IBApi
from params import ms_params
from watchlist import quotes


def _run_loop(app):
    app.run()


def _init_ibkr(sw):
    app = IBApi(sw)

    app.init_error()

    app.connect('127.0.0.1', 7497, 2112)
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


def print_quote_info(sym_params):
    qw = curses.newwin(2, curses.COLS, 0, 0)

    qw.clear()
    qw.addstr(0, 0, 'Quote', curses.color_pair(1))
    qw.addstr(1, 0, sym_params['symbol'], curses.color_pair(3))

    initial_market_cap = round(sym_params['shares_outstanding'] * sym_params['base_price'])
    qw.addstr(0, 10, 'MCap', curses.color_pair(1))
    cg = 4 if initial_market_cap < 10 else 5
    qw.addstr(1, 10, '%sM' % initial_market_cap, curses.color_pair(cg))

    qw.addstr(0, 20, 'Shares/Float', curses.color_pair(1))
    cg = 4 if sym_params['float'] < 3 else 5
    qw.addstr(1, 20, '%sM / %sM' % (sym_params['shares_outstanding'], sym_params['float']), curses.color_pair(cg))

    qw.addstr(0, 35, 'News', curses.color_pair(1))
    news = "-" if sym_params['news'] is None else sym_params['news']
    qw.addstr(1, 35, '%s' % news, curses.color_pair(3))

    qw.refresh()


def select_quote(scr):
    idx = None
    n = len(quotes)

    scr.clear()
    scr.refresh()

    if n > 0:
        scr.addstr(5, 20, "Select Quote (press a key between  1 .. " + str(n) + ")")

        for i in range(0, n):
            scr.addstr(7 + i, 25, str(i+1) + " -> " + quotes[i]['symbol'])

        key_pressed = None
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


def _add_indicators(df):
    df_range = pd.DataFrame(columns=['idx', 'range'])

    # tr = []
    vwap = []
    cur_vol = []

    sum_vxp = 0
    sumv = 0

    n = len(df)
    for i in range(0, n):

        ####################################################################
        # Range Score

        data = {'idx': i,
                'range': df.iloc[i]['High'] - df.iloc[i]['Low']}
        df_range = df_range.append(data, ignore_index=True)

        ####################################################################
        # VWAP & Current volume

        sum_vxp = sum_vxp + df.loc[i]['Volume'] * (df.loc[i]['High'] + df.loc[i]['Close'] + df.loc[i]['Low'])/3
        sumv = sumv + df.loc[i]['Volume']

        vwap.append(0 if sumv == 0 else sum_vxp / sumv)
        cur_vol.append(sumv)

        ####################################################################
        # TR

        # tr.append(df.loc[j]['High'] - df.loc[j]['Low'])

    ##################################################################
    # Range Score Continued ...

    df_range = df_range.set_index(df_range.idx)
    df_range = df_range.sort_values(by='range', ascending=True)

    range_score = [0] * n
    for i in range(0, n):
        range_score[int(df_range.iloc[i]['idx'])] = int(100 * i / n)

    df["range_score"] = range_score
    df["vwap"] = vwap
    df["current_volume"] = cur_vol
    # df["trading_range"] = tr

    # df["atr3"] = df["trading_range"].rolling(window=3).mean()
    # df["atr5"] = df["trading_range"].rolling(window=5).mean()
    # df["atr8"] = df["trading_range"].rolling(window=8).mean()
    # df["atr13"] = df["trading_range"].rolling(window=13).mean()

    df['mav3'] = df['Close'].rolling(window=3).mean()
    df['mav5'] = df['Close'].rolling(window=5).mean()
    # df['mav8'] = df['Close'].rolling(window=8).mean()
    # df['mav9'] = df['Close'].rolling(window=9).mean()
    # df['mav13'] = df['Close'].rolling(window=13).mean()
    df['mav21'] = df['Close'].rolling(window=21).mean()

    # df['vmav3'] = df['Volume'].rolling(window=3).mean()
    # df['vmav5'] = df['Volume'].rolling(window=5).mean()
    # df['vmav8'] = df['Volume'].rolling(window=8).mean()
    # df['vmav13'] = df['Volume'].rolling(window=13).mean()
    # df['vmav21'] = df['Volume'].rolling(window=21).mean()

    return df


def _ms_pattern(df, bs):
    pw = curses.newwin(3, curses.COLS, 4, 0)

    _add_indicators(df)

    pw.clear()

    pw.addstr(0, 0, '                                                                                      ', curses.color_pair(6))
    pw.addstr(0, 20, 'MS Pattern', curses.color_pair(6))
    pw.addstr(0, 0, 'BUY', curses.color_pair(6))
    pw.addstr(0, 10, 'SELL', curses.color_pair(6))

    close = df.iloc[-1]['Close']

    pw.addstr(1, 0, 'Price', curses.color_pair(1))
    cg = 4 if close < ms_params['__min_close_price'] else 5
    pw.addstr(2, 0, '%.2f$' % close, curses.color_pair(cg))

    pw.addstr(1, 10, 'BScore', curses.color_pair(1))
    if bs is None:
        pw.addstr(2, 10, 'error', curses.color_pair(2))
    else:
        pw.addstr(2, 12, '%s' % bs, curses.color_pair(3))

    pw.addstr(1, 20, '1MinVol', curses.color_pair(1))
    vol = df.iloc[-1]['Volume']
    cg = 4 if vol < ms_params['min_sig_volume'] else 5
    pw.addstr(2, 20, '%sk' % round(vol/1000), curses.color_pair(cg))

    pw.addstr(1, 32, 'Aligator', curses.color_pair(1))
    avg3 = ca.average_last_period(df, 3)
    avg5 = ca.average_last_period(df, 5)
    avg21 = ca.average_last_period(df, 21)
    cg = 5 if avg3 > avg5 > avg21 else 4
    pw.addstr(2, 32, '%.2f %.2f %.2f' % (avg3, avg5, avg21), curses.color_pair(cg))

    cnt = ca.calc_num_volumes_lower_last(df)
    pw.addstr(1, 50, 'VScore', curses.color_pair(1))
    cg = 5 if cnt >= ms_params['vol_pattern_length'] else 4
    pw.addstr(2, 50, '%s' % cnt, curses.color_pair(cg))

    recent_low = ca.get_last_period_low(df, ms_params['recent_duration'])
    xxx_high = ca.get_last_period_high(df, ms_params['extended_duration'])
    xxx_low = ca.get_last_period_low(df, ms_params['extended_duration'])

    ratio = (recent_low / xxx_high)
    pw.addstr(1, 60, 'Crash', curses.color_pair(1))
    cg = 5 if ratio > ms_params['extended_crash_min_factor'] else 4
    pw.addstr(2, 60, '%.2f %.2f' % (recent_low, xxx_high), curses.color_pair(cg))

    current_high = df.iloc[-1]['High']
    ratio = (current_high / xxx_low)
    pw.addstr(1, 75, 'XRun', curses.color_pair(1))
    cg = 5 if ratio < ms_params['extended_run_max_factor'] else 4
    pw.addstr(2, 75, '%.2f %.2f' % (xxx_low, current_high), curses.color_pair(cg))

    pw.refresh()


def _asses_1min_chart(app, req_store, bs):
    sw = curses.newwin(1, curses.COLS, curses.LINES - 2, 0)

    '''
    tr_begin_time = datetime.datetime.now()
    tr_begin_time = tr_begin_time.replace(hour=params['trading_begin_hh'], minute=params['trading_begin_mm'], second=0)
    last_entry_time = datetime.datetime.now()
    last_entry_time = last_entry_time.replace(hour=params['last_entry_hh'], minute=params['last_entry_mm'], second=0)
    forced_sell_time = datetime.datetime.now()
    forced_sell_time = forced_sell_time.replace(hour=params['chart_end_hh'], minute=params['chart_end_hh'], second=0)
    '''

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

        _ms_pattern(df, bs)


def main(scr):
    curses.curs_set(0)
    curses.cbreak()
    curses.resize_term(20, 100)

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

        app = _init_ibkr(sw3)
        time_queue = app.init_time()
        symbol = quotes[selected_id]['symbol']
        req_store = app.init_req_queue()

        sw1.clear()
        sw1.addstr(0, 0, "Connected!", curses.color_pair(1))
        sw1.refresh()

        bs = _calc_bagholder_score_from_ibkr_chart(app, req_store, symbol, sw2)

        app.data = []

        app.reqHistoricalData(2001, cu.contract(symbol), "", '1 D', '1 min', 'TRADES', 0, 1, True, [])

        key_pressed = None
        while key_pressed != 17:
            sw1 = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)

            sw1.addstr(0, 0, "Connected!", curses.color_pair(1))
            unix_time = _server_clock(app, time_queue)
            current_time = datetime.datetime.utcfromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S')
            sw1.addstr(0, 40, current_time, curses.color_pair(1))
            sw1.addstr(0, 85, "Quit [Ctrl+Q]", curses.color_pair(1))
            sw1.refresh()

            print_quote_info(quotes[selected_id])

            _asses_1min_chart(app, req_store, bs)

            key_pressed = scr.getch()


curses.wrapper(main)




