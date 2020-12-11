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
from gui import __TEXT_COLOR


def init_model(p):
    model = Net(p['num_classes']).to("cuda")
    model.load_state_dict(torch.load(p['model_params_path']))
    model.eval()

    return model


def init_tws_connection(w, ibkr_message_window, connection_id):
    w.addstr(0, 0, "Connecting to TWS ...", curses.color_pair(__TEXT_COLOR))
    w.refresh()

    app = tws.init_tws(ibkr_message_window, connection_id)

    app.data = []

    time_queue = app.init_time()
    req_store = app.init_req_queue()

    w.clear()
    w.addstr(0, 0, "Connected!", curses.color_pair(__TEXT_COLOR))
    w.refresh()

    return app, time_queue, req_store


def trade(df, label, app, p):
    close = df.iloc[-1]["Close"]

    if p['position_size'] > 0:
        if label <= 3:
            sellPrice = cu.to_tick_price(close * 1.2)
            p['bracket_order'][2].auxPrice = sellPrice
            app.placeOrder(p['bracket_order'].orderId, p['contract'], p['bracket_order'][2])

            cu.save_trade_log(p['bracket_order'][2].orderId, p['symbol'], "SELL", df.iloc[-1]["Time"], close, 100)
            p['position_size'] = 0
    else:
        if label == 9:
            order_id = tws.get_next_order_id(app)

            buyPrice = cu.to_tick_price(close * 1.03)
            profitTakePrice = cu.to_tick_price(buyPrice * 1.2)
            stopPrice = cu.to_tick_price(buyPrice * 0.9)

            print("Buy:", buyPrice, "Profit:", profitTakePrice, "STOP:", stopPrice)

            p['bracket_order'] = cu.BracketOrder(
                parentOrderId=order_id,
                quantity=100,
                limitPrice=buyPrice,
                takeProfitLimitPrice=profitTakePrice,
                stopLossPrice=stopPrice)

            app.placeOrder(p['bracket_order'][0].orderId, p['contract'], p['bracket_order'][0])
            app.placeOrder(p['bracket_order'][1].orderId, p['contract'], p['bracket_order'][1])
            app.placeOrder(p['bracket_order'][2].orderId, p['contract'], p['bracket_order'][2])

            p['position_size'] = 100
            cu.save_trade_log(order_id, p['symbol'], "BUY", df.iloc[-1]["Time"], buyPrice, 100)


def trade_chart(app, req_store, p):
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
            df = chart.gen_chart_prepared_for_ai(df, p)

            state = chart.create_state_vector(df, debug=True)
            state = torch.tensor(state, dtype=torch.float).unsqueeze(0).unsqueeze(0).to("cuda")

            output = p['model'](state)
            res = output.max(1)[1].view(1, 1)
            predicted_label = res[0][0].to("cpu").numpy()
            trade(df, app, predicted_label, p)

            gui.print_quote_info(df, p)

            gui.show_trading_info(df, predicted_label, output.to("cpu").numpy()[0], p)


def main(scr):
    main_window, status_bar, tws_message_window = gui.init_curses(scr)
    gui.init_colors()

    if quotes is None or len(quotes) == 0:
        main_window.addstr(0, 0, "No quotes in watchlist. See \'watchilist.py\' file.", curses.color_pair(3))
        main_window.refresh()
    else:
        p = get_params()

        selected_id = gui.select_quote(scr)

        p['symbol'] = quotes[selected_id]
        p['contract'] = cu.contract(p['symbol'])
        p['position_size'] = 0

        app, time_queue, req_store = init_tws_connection(main_window, tws_message_window, selected_id)
        gui.print_quote_name(p['symbol'])
        app.reqHistoricalData(2001, p['contract'], "", '1 D', '1 min', 'TRADES', 0, 1, True, [])
        gui.clear_window(status_bar)

        p['model'] = init_model(p)

        key_pressed = None
        while key_pressed != 17:
            gui.show_status_bar(tws.server_clock(app, time_queue))
            trade_chart(app, req_store, p)
            key_pressed = scr.getch()


def get_params():
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
            'model_params_path': 'model_params\\checkpoint_10'
    }

    return params


curses.wrapper(main)




