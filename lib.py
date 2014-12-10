from datetime import datetime, timedelta
import time

import requests

USER_AGENT = ('Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/32.0.1667.0 Safari/537.36')


def http_get(url, retries=10, user_agent=USER_AGENT, cookies=None):
    """Wrapper for requests.get for retries"""
    if cookies is None:
        cookies = {}
    if retries:
        try:
            retval = requests.get(
                url, headers={'User-Agent': user_agent}, cookies=cookies)
        except Exception as e:
            time.sleep(1)
            return http_get(url, retries=retries-1)
        else:
            return retval
    else:
        # Try one last time, if it fails, it fails
        return requests.get(url)


def create_date_range(from_date):
    now = datetime.strptime('20141125', '%Y%m%d') #datetime.now()
    from_date = from_date.replace(hour=0, minute=0, second=0)
    retval = [from_date + timedelta(days=x) for x in range(0,(now-from_date).days)]
    retval.reverse()
    return retval
