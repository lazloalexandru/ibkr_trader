from termcolor import colored
import pandas as pd
import datetime


def get_recent_low(df, idx, duration):
    res = None

    if duration < 0:
        print(colored("Warning! Duration value " + str(duration) + " below zero!", color='red'))
        duration = 0

    idx_s = idx - duration
    if idx_s < 0:
        idx_s = 0

    n = df.index[-1]
    if idx_s < idx < n:
        res = min(df.loc[idx_s:idx]['Low'])

    return res


def get_recent_high(df, idx, duration):
    res = None

    if duration < 0:
        print(colored("Warning! Duration value " + str(duration) + " below zero!", color='red'))
        duration = 0

    idx_s = idx - duration

    if idx_s < 0:
        idx_s = 0

    n = df.index[-1]
    if idx_s < idx < n:
        res = max(df.loc[idx_s:idx]['High'])

    return res


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
        print(colored("Warning!!! ... Intraday chart contains no timestamp: " + str(xtime) + "   n: " + str(n),
                      color='yellow'))

    return idx


def get_premarket_high(df):
    val = df["Open"][0]

    xtime = df["Time"][0]
    xtime = xtime.replace(hour=16, minute=30, second=0)

    x_idx = df.index[df['Time'] == xtime].tolist()

    n = len(x_idx)

    if n == 1:
        x_idx = x_idx[0]
        if x_idx > 0:
            val = max(df['High'][0:x_idx])
    elif n > 1:
        print(colored("ERROR ... Intraday chart contains more than one bars with same time stamp!!!"))

    return val


def get_bagholder_score1(dff):
    score = 0

    df = dff.copy()

    df["Time"] = pd.to_datetime(df["Time"], format="%Y%m%d")

    date_ = pd.to_datetime(str(datetime.datetime.now().date()), format="%Y-%m-%d")

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


def calc_last_bar_range_score(df):
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


def calc_num_volumes_lower(df):
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