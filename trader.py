import datetime
import queue
import curses
import torch
import pandas as pd
import utils_tws as tws

from model import Net
from watchlist import quotes
import common as cu
import chart
import gui


__IN_A_TRADE = False
__BRACKET_ORDER = None
__CONTRACT = None
__SYMBOL = None


def trade(df, app, label):
    global __IN_A_TRADE
    global __BRACKET_ORDER
    global __CONTRACT
    global __SYMBOL

    close = df.iloc[-1]["Close"]

    if __IN_A_TRADE:
        if label <= 3:
            sellPrice = cu.to_tick_price(close * 1.2)
            __BRACKET_ORDER[2].auxPrice = sellPrice
            app.placeOrder(__BRACKET_ORDER[2].orderId, __CONTRACT, __BRACKET_ORDER[2])

            cu.save_trade_log(__BRACKET_ORDER[2].orderId, __SYMBOL, "SELL", df.iloc[-1]["Time"], df.iloc[-1]["Close"], 100)
            __IN_A_TRADE = False
    else:
        if label == 6:
            order_id = tws.get_next_order_id(app)

            buyPrice = cu.to_tick_price(close * 1.01)
            profitTakePrice = cu.to_tick_price(buyPrice * 1.2)
            stopPrice = cu.to_tick_price(buyPrice * 0.95)

            print("Buy:", buyPrice, "Profit:", profitTakePrice, "STOP:", stopPrice)

            __BRACKET_ORDER = cu.BracketOrder(
                parentOrderId=order_id,
                quantity=100,
                limitPrice=buyPrice,
                takeProfitLimitPrice=profitTakePrice,
                stopLossPrice=stopPrice)

            app.placeOrder(__BRACKET_ORDER[0].orderId, __CONTRACT, __BRACKET_ORDER[0])
            app.placeOrder(__BRACKET_ORDER[1].orderId, __CONTRACT, __BRACKET_ORDER[1])
            app.placeOrder(__BRACKET_ORDER[2].orderId, __CONTRACT, __BRACKET_ORDER[2])

            __IN_A_TRADE = True
            cu.save_trade_log(order_id, __SYMBOL, "BUY", df.iloc[-1]["Time"], buyPrice, 100)


def _trade_chart(app, req_store, model):
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
            df = chart.gen_chart_prepared_for_ai(df, params)

            state = chart.create_state_vector(df, debug=True)
            state = torch.tensor(state, dtype=torch.float).unsqueeze(0).unsqueeze(0).to("cuda")

            output = model(state)
            res = output.max(1)[1].view(1, 1)
            predicted_label = res[0][0].to("cpu").numpy()
            trade(df, app, predicted_label)

            gui.show_trading_info(df, predicted_label, params)


def main(scr):
    curses.curs_set(0)
    curses.cbreak()
    curses.resize_term(20, 50)

    scr.nodelay(1)
    scr.timeout(1)

    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
    curses.init_pair(2, curses.COLOR_RED, curses.COLOR_YELLOW)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_YELLOW)
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_GREEN, curses.COLOR_WHITE)
    curses.init_pair(7, curses.COLOR_WHITE, curses.COLOR_GREEN)

    sw1 = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)
    sw2 = curses.newwin(1, curses.COLS, curses.LINES - 2, 0)
    sw3 = curses.newwin(1, curses.COLS, curses.LINES - 3, 0)

    if len(quotes) == 0:
        sw1.addstr(0, 0, "No quotes in watchlist. See \'watchilist.py\' file.", curses.color_pair(3))
        sw1.refresh()
    else:
        selected_id = gui.select_quote(scr)

        sw1.addstr(0, 0, "Connecting to TWS ...", curses.color_pair(4))
        sw1.refresh()

        app = tws.init_tws(sw3, selected_id)
        time_queue = app.init_time()

        global __SYMBOL
        __SYMBOL = quotes[selected_id]['symbol']
        req_store = app.init_req_queue()

        sw1.clear()
        sw1.addstr(0, 0, "Connected!", curses.color_pair(4))
        sw1.refresh()

        app.data = []

        app.reqHistoricalData(2001, cu.contract(__SYMBOL), "", '1 D', '1 min', 'TRADES', 0, 1, True, [])

        sw2.clear()
        sw2.refresh()

        global __CONTRACT
        __CONTRACT = cu.contract(__SYMBOL)

        model = Net(params['num_classes']).to("cuda")
        model.load_state_dict(torch.load(params['model_params_path']))
        model.eval()

        key_pressed = None
        while key_pressed != 17:
            sw1 = curses.newwin(1, curses.COLS, curses.LINES - 1, 0)

            unix_time = tws.server_clock(app, time_queue)
            current_time = datetime.datetime.utcfromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S')
            sw1.addstr(0, 0, current_time, curses.color_pair(4))
            sw1.addstr(0, 30, "Quit [Ctrl+Q]", curses.color_pair(4))
            sw1.refresh()

            gui.print_quote_info(quotes[selected_id])
            _trade_chart(app, req_store, model)

            key_pressed = scr.getch()


params = {
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

        'num_classes': 7,
        'model_params_path': 'model_params\\checkpoint_100'
}

curses.wrapper(main)




