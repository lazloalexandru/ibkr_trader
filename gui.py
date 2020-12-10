import curses
from watchlist import quotes

__NORMAL = 8


def print_quote_info(sym_params):
    qw = curses.newwin(2, curses.COLS, 0, 0)

    qw.clear()
    qw.addstr(0, 0, 'Quote', curses.color_pair(__NORMAL))
    qw.addstr(1, 0, sym_params['symbol'], curses.color_pair(6))

    qw.refresh()


def select_quote(scr):
    idx = None
    n = len(quotes)

    scr.clear()
    scr.refresh()

    if n > 0:
        scr.addstr(1, 5, "Select Quote")
        scr.addstr(2, 5, "(press a key between  1 .. " + str(n) + ")")

        for i in range(0, n):
            scr.addstr(4 + i, 5, str(i+1) + " -> " + quotes[i]['symbol'])

        while idx not in range(0, n):
            key_pressed = scr.getch()
            idx = key_pressed - ord('1')
            scr.refresh()

    scr.clear()
    scr.refresh()

    return idx


def show_trading_info(df, label, p):
    pw = curses.newwin(10, curses.COLS, 4, 0)

    pw.clear()

    sd = 10
    r = 0

    cg = 4
    text = "---ERROR---"

    if label == 0:
        text = "Gain < -10%"
    elif label == 1:
        text = "-10% < Gain < -5%"
    elif label == 2:
        text = "-5% < Gain < -2%"
    elif label == 3:
        text = "-2% < Gain < 2%"
    elif label == 4:
        text = "2% < Gain < 5%"
    elif label == 5:
        text = "5% < Gain < 10%"
    elif label == 6:
        text = "10% < Gain"

    pw.addstr(r, 0, 'AI  =>', curses.color_pair(__NORMAL))
    pw.addstr(r, 22, text, curses.color_pair(label + 1))
    pw.addstr(r, 10, 'Label: %s' % label, curses.color_pair(label + 1))
    r += 2

    ########################################################################

    close = df.iloc[-1]['Close']
    cg = 8 if close > p['__min_close_price'] else 1
    pw.addstr(r, 0, 'Price', curses.color_pair(1))
    pw.addstr(r, sd, '%.2f$' % close, curses.color_pair(cg))
    pw.addstr(r, 22, str(df.iloc[-1]['Time']), curses.color_pair(__NORMAL))

    r += 1

    ########################################################################

    vol = df.iloc[-1]['Volume']
    pw.addstr(r, 0, '1MinVol', curses.color_pair(__NORMAL))
    pw.addstr(r, sd, '%sk' % round(vol/1000), curses.color_pair(__NORMAL))
    r += 1

    ########################################################################

    current_volume = sum(df['Volume'].tolist())
    pw.addstr(r, 0, 'Volume', curses.color_pair(__NORMAL))
    pw.addstr(r, sd, '%1.fM' % (current_volume / 1000000), curses.color_pair(__NORMAL))
    r += 1

    ########################################################################

    pxv = close * current_volume
    cg = 7 if pxv > p['min_volume_x_price'] else 1
    pw.addstr(r, 0, 'PxV', curses.color_pair(__NORMAL))
    pw.addstr(r, sd, '%.2fM' % (pxv / 1000000), curses.color_pair(cg))
    r += 1

    ########################################################################

    pw.refresh()
