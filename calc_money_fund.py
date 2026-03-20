#!/usr/bin/env python3
"""计算宏利货币B(000700) 2014-2026 各年度收益率"""
import urllib.request, json, time, sys

def fetch(start, end, page=1):
    url = (f'http://api.fund.eastmoney.com/f10/lsjz?callback=jQuery'
           f'&fundCode=000700&pageIndex={page}&pageSize=20'
           f'&startDate={start}&endDate={end}&fundType=hb')
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'http://fundf10.eastmoney.com/jjjz_000700.html'
    })
    resp = urllib.request.urlopen(req, timeout=15)
    raw = resp.read().decode()
    j = raw[raw.index('(') + 1 : raw.rindex(')')]
    d = json.loads(j)
    return (d.get('Data') or {}).get('LSJZList') or []

def get_year_data(year):
    start = '2014-08-06' if year == 2014 else f'{year}-01-01'
    end = '2026-03-17' if year == 2026 else f'{year}-12-31'
    all_r = []
    for p in range(1, 30):
        r = fetch(start, end, p)
        all_r.extend(r)
        if len(r) < 20:
            break
        time.sleep(0.5)
    return all_r

results = {}
for year in range(2014, 2027):
    sys.stdout.write(f'{year}...')
    sys.stdout.flush()
    recs = get_year_data(year)
    if not recs:
        results[year] = None
        print(' NO DATA')
        continue
    total = sum(float(x['DWJZ']) for x in recs)
    rate = round(total / 10000.0 * 100.0, 2)
    results[year] = rate
    print(f' {len(recs)} days, rate={rate}%')
    time.sleep(0.3)

print('\n=== 宏利货币B(000700) 年度收益率 ===')
for y in sorted(results):
    r = results[y]
    print(f'  {y}: {r}%' if r is not None else f'  {y}: null')
