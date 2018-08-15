import alpaca_trade_api as tradeapi
import concurrent.futures
import hashlib
import logbook
import numpy as np
import pandas as pd
import os
import pickle

log = logbook.Logger(__name__)


def parallelize(mapfunc, workers=10, splitlen=10):

    def wrapper(symbols):
        result = {}
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=workers) as executor:
            tasks = []
            for i in range(0, len(symbols), splitlen):
                part = symbols[i:i + splitlen]
                task = executor.submit(mapfunc, part)
                tasks.append(task)

            total_count = len(symbols)
            report_percent = 10
            processed = 0
            for task in concurrent.futures.as_completed(tasks):
                task_result = task.result()
                result.update(task_result)
                processed += len(task_result)
                percent = processed / total_count * 100
                if percent >= report_percent:
                    log.debug('{}: {:.2f}% completed'.format(
                        mapfunc.__name__, percent))
                    report_percent = (percent + 10.0) // 10 * 10
        return result

    return wrapper


def daily_cache(filename):
    kwd_mark = '||'

    def decorator(func):
        def wrapper(*args, **kwargs):
            key = args + (kwd_mark,) + tuple(sorted(kwargs.items()))
            hash = hashlib.md5()
            hash.update(str(key).encode('utf-8'))
            hash.update(pd.Timestamp.utcnow().strftime(
                '%Y-%m-%d').encode('utf-8'))
            digest = hash.hexdigest()
            dirpath = '/root/.zipline/dailycache'
            os.makedirs(dirpath, exist_ok=True)
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'rb') as fp:
                        ret = pickle.load(fp)
                        if ret['digest'] == digest:
                            return ret['body']
                        print('digest mismatch {} != {}'.format(
                            ret['digest'], digest
                        ))
                except Exception as e:
                    print('cache error {}'.format(e))
            body = func(*args, **kwargs)

            with open(filepath, 'wb') as fp:
                pickle.dump({
                    'digest': digest,
                    'body': body,
                }, fp)
            return body
        return wrapper
    return decorator


def _all_symbols():
    return [
        a.symbol for a in tradeapi.REST().list_assets()
        if a.tradable and a.status == 'active'
    ]


@daily_cache(filename='polygon_companies.pkl')
def companies():
    all_symbols = _all_symbols()

    def fetch(symbols):
        api = tradeapi.REST()
        params = {
            'symbols': ','.join(symbols),
        }
        response = api.polygon.get('/meta/symbols/company', params=params)
        return {
            o['symbol']: o for o in response
        }

    return parallelize(fetch, workers=25, splitlen=50)(all_symbols)


@daily_cache(filename='polygon_financials.pkl')
def financials():
    all_symbols = _all_symbols()

    def fetch(symbols):
        api = tradeapi.REST()
        params = {
            'symbols': ','.join(symbols),
        }
        return api.polygon.get('/meta/symbols/financials', params=params)

    return parallelize(fetch, workers=25, splitlen=50)(all_symbols)
