import queue
from termcolor import colored
from ibapi.client import EClient
from ibapi.wrapper import EWrapper, BarData


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
        if bar.date == self.data[-1][0]:
            self.data[-1] = [bar.date, bar.open, bar.close, bar.high, bar.low, bar.volume * 100]
        else:
            self.data.append([bar.date, bar.open, bar.close, bar.high, bar.low, bar.volume * 100])
        self.req_queue.put(reqId)

    def historicalDataEnd(self, reqId:int, start:str, end:str):
        self.req_queue.put(reqId)