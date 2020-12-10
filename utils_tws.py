import queue
import threading
import time

from my_ibapi_app import IBApi


def _run_loop(app):
    app.run()


def init_tws(sw, id):
    app = IBApi()

    app.init_error()

    app.connect('127.0.0.1', 7497, 2000+id)
    api_thread = threading.Thread(target=_run_loop, args=(app,), daemon=True)
    api_thread.start()

    app.nextorderId = None

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


def server_clock(app, time_storage):
    app.reqCurrentTime()

    try:
        requested_time = time_storage.get(timeout=1)
    except queue.Empty:
        requested_time = None

    return requested_time


