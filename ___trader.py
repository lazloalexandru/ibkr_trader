from datetime import date
import common_algos as ca
import datetime
import queue
from termcolor import colored
from ibapi.client import EClient
from ibapi.wrapper import EWrapper, BarData
import threading
import time
import pandas as pd
from ibapi.contract import Contract
import curses
from curses import textpad


class IBApi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        self.data = []

    def init_error(self):
        error_queue = queue.Queue()
        self.my_errors_queue = error_queue

    def get_error(self, timeout=6):
        if self.is_error():
            try:
                return self.my_errors_queue.get(timeout=timeout)
            except queue.Empty:
                return None
        return None

    def is_error(self):
        error_exist = not self.my_errors_queue.empty()
        return error_exist

    def init_req_queue(self):
        req_queue = queue.Queue()
        self.req_queue = req_queue
        return req_queue

    def nextValidId(self, orderId: int):
        super().nextValidId(orderId)
        self.nextorderId = orderId

    def error(self, id, errorCode, errorString):
        if errorCode != 2104 and errorCode != 2106 and errorCode != 2158:
            errormessage = "IB returns an error with %d errorcode %d that says %s" % (id, errorCode, errorString)
            print(colored(errormessage, color='red'))
            self.my_errors_queue.put(errormessage)

    def historicalData(self, reqId, bar):
        # date_time_obj = datetime.datetime.strptime(bar.date, '%Y%m%d')
        # print(date_time_obj.date())
        # print(f'Time: {bar.date} Open: {bar.open} Close: {bar.close}')
        # if bar.date == "20190329":
        #    print(bar)

        self.data.append([bar.date, bar.open, bar.close,  bar.high, bar.low, bar.volume * 100])

    def historicalDataUpdate(self, reqId: int, bar: BarData):
        if bar.date == self.data[-1][0]:
            self.data[-1] = [bar.date, bar.open, bar.close, bar.high, bar.low, bar.volume * 100]
        else:
            self.data.append([bar.date, bar.open, bar.close, bar.high, bar.low, bar.volume * 100])
        self.req_queue.put(reqId)

    def historicalDataEnd(self, reqId:int, start:str, end:str):
        self.req_queue.put(reqId)


class Trader:
    def __init__(self):
        self.app = IBApi()
        self.app.init_error()

        self.app.connect('127.0.0.1', 7497, 2112)
        self.api_thread = threading.Thread(target=Trader.run_loop, daemon=True)
        self.api_thread.start()

        self.app.nextorderId = None

        # Check if the API is connected via orderid
        while True:
            if isinstance(self.app.nextorderId, int):
                print('Connected.')
                break
            else:
                print('Waiting for connection ...')
                time.sleep(1)

    def run_loop(self):
        self.app.run()

    def trader(self, params, symbol="MRIN"):
        # Create contract object
        contract = Contract()
        contract.symbol = symbol
        contract.secType = 'STK'
        contract.exchange = 'SMART'
        contract.currency = 'USD'

        req_store = self.app.init_req_queue()

        self.app.data = []

        self.app.reqHistoricalData(2000, contract, "", '3 Y', '1 day', 'TRADES', 1, 1, False, [])

        xxx = None
        while not self.app.wrapper.is_error() and xxx is None:
            try:
                xxx = req_store.get(timeout=1)
            except queue.Empty:
                print(".", end="", flush=True)
                xxx = None

        while self.app.wrapper.is_error():
            print(symbol, "  --->  ", self.app.get_error(timeout=5))

        message = "Queried " + symbol + " Daily chart for " + str(len(app.data)) + " days"

        bs = 0

        if len(self.app.data) == 0:
            print(colored(message, 'red'))
        else:
            print(message, "\n")
            df = pd.DataFrame(self.app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])

            bs = ca.get_bagholder_score(df)

        tr_begin_time = datetime.datetime.now()
        tr_begin_time = tr_begin_time.replace(hour=params['trading_begin_hh'], minute=params['trading_begin_mm'], second=0)
        last_entry_time = datetime.datetime.now()
        last_entry_time = last_entry_time.replace(hour=params['last_entry_hh'], minute=params['last_entry_mm'], second=0)
        forced_sell_time = datetime.datetime.now()
        forced_sell_time = forced_sell_time.replace(hour=params['chart_end_hh'], minute=params['chart_end_hh'], second=0)

        print("Trading Begins Time: ", tr_begin_time.time())
        print("Last Entry Time:     ", last_entry_time.time())
        print("Forced Sell Time:    ", forced_sell_time.time())

        self.app.data = []

        self.app.reqHistoricalData(2001, contract, "", '1 D', '1 min', 'TRADES', 0, 1, True, [])

        while True:

            xxx = None
            num_tries = 0
            while not self.app.wrapper.is_error() and xxx is None:
                try:
                    xxx = req_store.get(timeout=1)
                except queue.Empty:
                    num_tries = num_tries + 1
                    print(".", end="", flush=True)
                    xxx = None

            df = pd.DataFrame(self.app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])

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
            print(colored("SELL Signal [Active]  " if ali_closed else "SELL Signal [Inactive]  ", "yellow" if ali_closed else "grey"),
                  colored(str(_t.time()) + "  ", "green" if tr_begin_time < _t < last_entry_time else "red"),
                  colored("%.2f" % df.iloc[-1]["Close"] + "$  ", "green" if df.iloc[-1]["Close"] > params['min_close_price'] else "red"),
                  colored("  Bagholder_Score: " + str(bs), "green" if bs >= params['min_bagholder_score'] else "red"),
                  colored("  Range_Score: " + str(rs), "green" if rs < params['max_range_score'] else "red"),
                  colored("  Aligator", "green" if ali_opened else "red"),
                  colored("  VolumesLower: " + str(df.iloc[-1]['vol_high_count']), "green" if df.iloc[-1]['vol_high_count'] >= params['vol_pattern_length'] else "red"),
                  colored("  Traded_Value: $" + f'{traded_value:,}', "green" if traded_value > params['min_volume_x_price'] else "red"),
                  colored("  POSITION SIZE: " + str(params['account_value'] * 0.2), color="white"))

            time.sleep(5)


#################################


__params = {'chart_begin_hh': 15,
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
            'size_limit': 50000}


trader = Trader()
trader.trader(params=__params)
