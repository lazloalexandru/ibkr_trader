import curses
import datetime
from watchlist import quotes
import numpy as np

__TEXT_COLOR = 8
__VARIABLE_COLOR = 3
__HIGHLIGHT_COLOR = 4


def print_quote_name(sym):
    qw = curses.newwin(2, 7, 0, 0)
    qw.clear()

    qw.addstr(0, 0, 'Quote', curses.color_pair(__TEXT_COLOR))
    qw.addstr(1, 0, sym, curses.color_pair(__VARIABLE_COLOR))

    qw.refresh()


def print_quote_info(df, p):
    price = df.iloc[-1]['Close']
    vol = df.iloc[-1]['Volume']
    cur_vol = sum(df['Volume'].tolist())

    w = curses.newwin(2, curses.COLS - 7, 0, 7)

    color_id = 3 if price > p['__min_close_price'] else 1
    w.addstr(0, 0, 'Price', curses.color_pair(__TEXT_COLOR))
    w.addstr(1, 0, '%.2f$' % price, curses.color_pair(color_id))

    w.addstr(0, 7, '1MinVol', curses.color_pair(__TEXT_COLOR))
    w.addstr(1, 8, '%sk' % round(vol / 1000), curses.color_pair(__VARIABLE_COLOR))

    w.addstr(0, 16, 'Volume', curses.color_pair(__TEXT_COLOR))
    w.addstr(1, 17, '%1.fM' % (cur_vol / 1000000), curses.color_pair(__VARIABLE_COLOR))

    pxv = price * cur_vol
    color_id = 3 if pxv > p['min_volume_x_price'] else 1
    w.addstr(0, 24, 'PxV', curses.color_pair(__TEXT_COLOR))
    w.addstr(1, 24, '%.0fM' % (pxv / 1000000), curses.color_pair(color_id))

    w.refresh()


def select_quote(scr):
    idx = None
    n = len(quotes)

    scr.clear()
    scr.refresh()

    if n > 0:
        scr.addstr(1, 5, "Select Quote")
        scr.addstr(2, 5, "(press a key between  1 .. " + str(n) + ")")

        for i in range(0, n):
            scr.addstr(4 + i, 5, str(i+1) + " -> " + quotes[i])

        while idx not in range(0, n):
            key_pressed = scr.getch()
            idx = key_pressed - ord('1')
            scr.refresh()

    scr.clear()
    scr.refresh()

    return idx


def get_label_description(label):
    if label == 0:
        text = "        Gain  <-10% "
    elif label == 1:
        text = "-10% <  Gain  < -5% "
    elif label == 2:
        text = " -5% <  Gain  < -2% "
    elif label == 3:
        text = " -2% <  Gain  <  2% "
    elif label == 4:
        text = "  2% <  Gain  <  5% "
    elif label == 5:
        text = "  5% <  Gain  < 10% "
    elif label == 6:
        text = " 10% <  Gain        "
    return text


def _show_label_stats(window, row, probability, label, color):
    window.addstr(row, 2, str(label) + "    ->        ", curses.color_pair(color))
    window.addstr(row, 17, '%.1f' % (100*probability) + " %", curses.color_pair(color))


def show_trading_info(label, probabilities, p):
    pw = curses.newwin(11, curses.COLS, 3, 0)

    pw.clear()

    if p['position_size'] > 0:
        c = __HIGHLIGHT_COLOR
    else:
        c = __TEXT_COLOR

    r = 0
    pw.addstr(r, 0, 'POS:', curses.color_pair(__TEXT_COLOR))
    pw.addstr(r, 5, str(p['position_size']), curses.color_pair(c))
    r += 2

    ########################################################################

    pw.addstr(r, 0, 'Label', curses.color_pair(__TEXT_COLOR))
    pw.addstr(r, 7, '=>', curses.color_pair(__TEXT_COLOR))
    pw.addstr(r, 10, get_label_description(label), curses.color_pair(label + 1))
    r += 2

    for label_id in range(7):
        color = __TEXT_COLOR
        if label == label_id:
            color = __HIGHLIGHT_COLOR

        _show_label_stats(pw, r, np.exp(probabilities[label_id]), label_id, color)
        r += 1

    pw.refresh()


def show_system_status(unix_time):
    if unix_time is not None:
        w = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)

        current_time = datetime.datetime.utcfromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S')
        w.addstr(0, 0, current_time, curses.color_pair(__TEXT_COLOR))
        w.addstr(0, 25, "Quit [Ctrl+Q]", curses.color_pair(__TEXT_COLOR))
        w.refresh()


def init_colors():
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_YELLOW)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_GREEN, curses.COLOR_WHITE)
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_GREEN)
    curses.init_pair(8, curses.COLOR_WHITE, curses.COLOR_BLACK)


def init_curses(scr):
    curses.curs_set(0)
    curses.cbreak()
    curses.resize_term(20, 40)

    scr.nodelay(1)
    scr.timeout(1)

    w1 = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)
    w2 = curses.newwin(1, curses.COLS, curses.LINES - 2, 0)
    w3 = curses.newwin(3, curses.COLS, curses.LINES - 5, 0)

    return w1, w2, w3


def clear_window(w):
    w.clear()
    w.refresh()
