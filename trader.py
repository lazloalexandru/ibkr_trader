from datetime import date
from datetime import datetime
import queue
from termcolor import colored
from ibapi.client import EClient
from ibapi.wrapper import EWrapper, BarData
import threading
import time
import pandas as pd
from ibapi.contract import Contract


class IBApi(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
        bar_data = []

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
        if bar.date == app.data[-1][0]:
            self.data[-1] = [bar.date, bar.open, bar.close, bar.high, bar.low, bar.volume * 100]
        else:
            self.data.append([bar.date, bar.open, bar.close, bar.high, bar.low, bar.volume * 100])
        self.req_queue.put(reqId)

    def historicalDataEnd(self, reqId:int, start:str, end:str):
        self.req_queue.put(reqId)


def run_loop():
    app.run()


def init_ibkr():
    app.init_error()

    app.connect('127.0.0.1', 7497, 2112)
    api_thread = threading.Thread(target=run_loop, daemon=True)
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


def _get_bagholder_score(dff):
    score = 0

    df = dff.copy()

    df["Time"] = pd.to_datetime(df["Time"], format="%Y%m%d")

    date_ = pd.to_datetime(date.today(), format="%Y-%m-%d")

    x_idx = df.index[df['Time'] == date_].tolist()
    if len(x_idx) > 0:
        x_pos = x_idx[0]
        i = x_pos-1
        bvol = 0
        while i > 0 and x_pos-i < 200:
            if df.loc[i]['High'] > df.loc[x_pos]['Open']:
                bvol = bvol + df.loc[i]['Volume']
            i = i-1

        if bvol == 0:
            score = 5
        elif bvol < 1000000:
            score = 4
        elif bvol < 10000000:
            score = 3
        elif bvol < 30000000:
            score = 2
        elif bvol > 30000000:
            score = 1

        print("Bagholder Volume: " + f'{bvol:,}')

    return score


def _calc_last_bar_range_score(df):
    n = len(df)

    zzz = pd.DataFrame(columns=['idx', 'range'])

    for i in range(0, n):
        data = {'idx': i,
                'range': df.iloc[i]['High'] - df.iloc[i]['Low']}
        zzz = zzz.append(data, ignore_index=True)

    zzz = zzz.set_index(zzz.idx)
    zzz = zzz.sort_values(by='range', ascending=True)

    score = [0] * n
    for i in range(0, n-1):
        score[int(zzz.iloc[i]['idx'])] = int(100 * i / n)

    return score[-1]


def _calc_num_volumes_lower(df):
    num = []
    n = len(df)
    for i in range(0, n):
        j = i
        is_bigger = True
        cnt = 0
        while j > 0 and is_bigger:
            j = j - 1
            is_bigger = df.iloc[j]['Volume'] < df.iloc[i]['Volume']
            if is_bigger:
                cnt = cnt + 1

        num.append(cnt)

    df.insert(2, "vol_high_count", num)

    return df


def trader(symbol, params):
    # Create contract object
    contract = Contract()
    contract.symbol = symbol
    contract.secType = 'STK'
    contract.exchange = 'SMART'
    contract.currency = 'USD'

    req_store = app.init_req_queue()

    app.data = []

    app.reqHistoricalData(2000, contract, "", '3 Y', '1 day', 'TRADES', 1, 1, False, [])

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

    bs = 0

    if len(app.data) == 0:
        print(colored(message, 'red'))
    else:
        print(message, "\n")
        df = pd.DataFrame(app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])

        bs = _get_bagholder_score(df)

    tr_begin_time = pd.datetime.datetime.now()
    tr_begin_time = tr_begin_time.replace(hour=params['trading_begin_hh'], minute=params['trading_begin_mm'], second=0)
    last_entry_time = pd.datetime.datetime.now()
    last_entry_time = last_entry_time.replace(hour=params['last_entry_hh'], minute=params['last_entry_mm'], second=0)
    forced_sell_time = pd.datetime.datetime.now()
    forced_sell_time = forced_sell_time.replace(hour=params['chart_end_hh'], minute=params['chart_end_hh'], second=0)

    print("Trading Begins Time: ", tr_begin_time.time())
    print("Last Entry Time:     ", last_entry_time.time())
    print("Forced Sell Time:    ", forced_sell_time.time())

    app.data = []

    app.reqHistoricalData(2001, contract, "", '1 D', '1 min', 'TRADES', 0, 1, True, [])

    while True:

        xxx = None
        num_tries = 0
        while not app.wrapper.is_error() and xxx is None:
            try:
                xxx = req_store.get(timeout=1)
            except queue.Empty:
                num_tries = num_tries + 1
                print(".", end="", flush=True)
                xxx = None

        df = pd.DataFrame(app.data, columns=["Time", "Open", "Close", "High", "Low", "Volume"])

        rs = _calc_last_bar_range_score(df)
        df = _calc_num_volumes_lower(df)

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

              )

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


app = IBApi()
init_ibkr()

trader(symbol="HTZ", params=__params)

