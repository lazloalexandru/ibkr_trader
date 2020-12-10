import numpy as np
import common as cu
import pandas as pd

DATA_ROWS = 5
DAY_IN_MINUTES = 390


def save_state_chart(state, t, symbol, date, idx):
    s = state.reshape(DATA_ROWS, DAY_IN_MINUTES)

    o = s[0]
    c = s[1]
    h = s[2]
    l = s[3]
    v = s[4]

    dx = pd.DataFrame({
        'Time': t,
        'Open': o,
        'Close': c,
        'High': h,
        'Low': l,
        'Volume': v})

    filename = symbol + "_" + date + "_" + str(idx)

    images_dir_path = "trades\\"
    cu.show_1min_chart_normalized(dx, idx, symbol, date, images_dir_path, filename)


def create_padded_state_vector(df, debug=False):
    """ idx - is the candle index in range 0 ... 390 """

    t = df.Time.to_list()
    o = df.Open.to_list()
    c = df.Close.to_list()
    h = df.High.to_list()
    l = df.Low.to_list()
    v = df.Volume.to_list()

    if debug:
        print("calc_normalized_state")
        print('full len(o)', len(o))
        print('full len(v)', len(v))

    if debug:
        print('entry len(o)', len(o))
        print('entry len(v)', len(v))
        print('o:', len(o), " >>> ", o)
        print('entry:', t[-1])

    price = np.concatenate((o, c, h, l))
    price = cu.scale_to_1(price)
    price = price.reshape(4, len(df))

    o = price[0]
    c = price[1]
    h = price[2]
    l = price[3]
    v = cu.scale_to_1(np.array(v))

    padding_size = DAY_IN_MINUTES - (len(df) + 1)
    padding = [0] * padding_size

    if debug:
        print('padding_size:', padding_size)

    o = np.concatenate((padding, o))
    c = np.concatenate((padding, c))
    h = np.concatenate((padding, h))
    l = np.concatenate((padding, l))
    v = np.concatenate((padding, v))

    if debug:
        print('padded len(o)', len(o))
        print('padded len(v)', len(v))

    state = np.concatenate((o, c, h, l, v))

    return state
