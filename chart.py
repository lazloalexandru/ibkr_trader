import numpy as np
import pandas as pd
from termcolor import colored

import common as cu

DATA_ROWS = 5
DAY_IN_MINUTES = 390


def create_state_vector(df, debug=False):
    """ idx - is the candle index in range 0 ... 390 """

    entry_time = df.iloc[-1]['Time']
    t = df.Time.to_list()
    o = df.Open.to_list()
    c = df.Close.to_list()
    h = df.High.to_list()
    l = df.Low.to_list()
    v = df.Volume.to_list()

    n = len(o)

    if debug:
        print("calc_normalized_state")
        print('full len(o)', len(o))
        print('full len(v)', len(v))

    if debug:
        print('entry len(o)', len(o))
        print('entry len(v)', len(v))
        print('entry:', entry_time)
        print('last_candle:', t[-1])
        print('n:', n)

    price = np.concatenate((o, c, h, l))
    price = scale_to_1(price)
    price = price.reshape(4, n)

    o = price[0]
    c = price[1]
    h = price[2]
    l = price[3]
    v = scale_to_1(np.array(v))

    padding_size = DAY_IN_MINUTES - n
    padding = [0] * padding_size

    if debug:
        print('padding_size:', padding_size)

    o = np.concatenate((padding, o))
    c = np.concatenate((padding, c))
    h = np.concatenate((padding, h))
    l = np.concatenate((padding, l))
    v = np.concatenate((padding, v))
    t = np.concatenate((padding, t))

    if debug:
        print('padded len(o)', len(o))
        print('padded len(v)', len(v))

    state = np.concatenate((o, c, h, l, v))
    if debug:
        print(state.shape)

    state = np.reshape(state, (DATA_ROWS, DAY_IN_MINUTES))

    return state


def gen_chart_prepared_for_ai(df, p):
    if df is not None:
        print("Raw:")
        print(df.head())
        print(df.iloc[-1]['Time'])
        df.Time = pd.to_datetime(df.Time, format="%Y%m%d  %H:%M:%S")

        idx = get_time_index(df, p['__chart_begin_hh'], p['__chart_begin_mm'], 0)
        if idx is not None:
            df = df[idx:]
            df.reset_index(drop=True, inplace=True)

        idx = get_time_index(df, p['__chart_end_hh'], p['__chart_end_mm'], 0)
        if idx is not None:
            df = df[:idx+1]
            df.reset_index(drop=True, inplace=True)

    return df


def get_time_index(df, h, m, s):
    idx = None

    xtime = df.iloc[0]["Time"]
    xtime = xtime.replace(hour=h, minute=m, second=s)

    x_idx = df.index[df['Time'] == xtime].tolist()
    n = len(x_idx)
    if n == 1:
        idx = x_idx[0]
    elif n > 1:
        print(colored("ERROR ... Intraday chart contains more than one bars with same time stamp!!!", color='red'))
    else:
        print(colored("Warning!!! ... Intraday chart contains no timestamp: " + str(xtime) + "   n: " + str(n), color='yellow'))

    return idx


def scale_to_1(x):
    if len(x) > 0:
        mx = max(x)

        if mx > 0:
            x = x / mx

    return x
