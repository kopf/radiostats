from datetime import datetime, timedelta
import pytz
import time

import logbook
import requests

log = logbook.Logger()

USER_AGENT = ('Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/32.0.1667.0 Safari/537.36')

def http_get(*args, **kwargs):
    kwargs['method'] = 'get'
    return http_req(*args, **kwargs)

def http_post(*args, **kwargs):
    kwargs['method'] = 'post'
    return http_req(*args, **kwargs)

def http_req(url, retries=10, user_agent=USER_AGENT, cookies=None, method='get', **kwargs):
    """Wrapper for requests.get for retries"""
    if cookies is None:
        cookies = {}
    requests_func = getattr(requests, method)
    if retries:
        try:
            retval = requests_func(
                url, headers={'User-Agent': user_agent}, cookies=cookies, **kwargs)
            retval.raise_for_status()
        except Exception as e:
            time.sleep(1)
            log.error(e.message)
            return http_get(url, retries=retries-1)
        else:
            return retval
    else:
        # Try one last time, if it fails, it fails
        return requests_func(
            url, headers={'User-Agent': user_agent}, cookies=cookies)


def create_date_range(from_date, to_date=None):
    if to_date is None:
        to_date = datetime.now().date()
    retval = [from_date + timedelta(days=x) for x in range(0, (to_date - from_date).days)]
    retval.reverse()
    return retval


def utc_datetime(dt, station):
    """Returns the datetime dt converted to the UTC timezone"""
    if not dt.tzinfo:
        timezone = pytz.timezone(station.timezone)
        dt = timezone.localize(dt)
    return dt.astimezone(pytz.utc)


def localize_datetime(dt, station):
    """Returns the datetime dt in the station's local timezone"""
    return dt.astimezone(pytz.timezone(station['timezone']))
