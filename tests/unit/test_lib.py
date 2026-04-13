# -*- coding: utf-8 -*-
"""
Unit tests for scraper.lib utilities.
Compatible with Python 2.7 and 3.x
"""
import pytest
import pytz
from datetime import datetime, date, timedelta
try:
    from unittest import mock
except ImportError:
    # Python 2.7
    import mock

from scraper import lib


class TestCreateDateRange(object):
    """Test cases for create_date_range function."""

    def test_single_day_range(self):
        """Test creating a range for a single day."""
        start_date = date(2020, 1, 1)
        result = lib.create_date_range(start_date, start_date)
        assert len(result) == 0  # range doesn't include end date

    def test_multi_day_range(self):
        """Test creating a range spanning multiple days."""
        start_date = date(2020, 1, 1)
        end_date = date(2020, 1, 5)
        result = lib.create_date_range(start_date, end_date)
        
        expected = [
            date(2020, 1, 4),
            date(2020, 1, 3),
            date(2020, 1, 2),
            date(2020, 1, 1),
        ]
        assert result == expected

    def test_range_reversed_ordering(self):
        """Test that dates are returned in reverse order."""
        start_date = date(2020, 1, 1)
        end_date = date(2020, 1, 3)
        result = lib.create_date_range(start_date, end_date)
        
        assert result[0] > result[-1]
        assert result[0] == date(2020, 1, 2)
        assert result[-1] == date(2020, 1, 1)

    def test_range_with_none_end_date(self):
        """Test creating a range without specifying end_date."""
        start_date = date(2020, 1, 1)
        with mock.patch('scraper.lib.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2020, 1, 5, 12, 0, 0)
            result = lib.create_date_range(start_date)
            
            assert len(result) > 0
            assert result[0] > result[-1]


class TestUtcDatetime(object):
    """Test cases for utc_datetime function."""

    def test_naive_datetime_conversion(self):
        """Test converting naive datetime to UTC."""
        class MockStation(object):
            timezone = 'Europe/London'
        
        station = MockStation()
        naive_dt = datetime(2020, 1, 1, 12, 0, 0)
        result = lib.utc_datetime(naive_dt, station)
        
        assert result.tzinfo is not None
        assert result.tzinfo == pytz.utc

    def test_aware_datetime_conversion(self):
        """Test converting aware datetime to UTC."""
        class MockStation(object):
            timezone = 'Europe/Berlin'
        
        station = MockStation()
        berlin_tz = pytz.timezone('Europe/Berlin')
        aware_dt = berlin_tz.localize(datetime(2020, 1, 1, 12, 0, 0))
        result = lib.utc_datetime(aware_dt, station)
        
        assert result.tzinfo == pytz.utc
        # UTC time should be different from Berlin time
        assert result.hour != 12

    def test_timezone_conversion_accuracy(self):
        """Test accurate timezone conversion."""
        class MockStation(object):
            timezone = 'America/New_York'
        
        station = MockStation()
        naive_dt = datetime(2020, 1, 1, 12, 0, 0)
        result = lib.utc_datetime(naive_dt, station)
        
        # 12:00 EST is 17:00 UTC
        ny_tz = pytz.timezone('America/New_York')
        expected = ny_tz.localize(naive_dt).astimezone(pytz.utc)
        
        assert result.hour == expected.hour
        assert result.day == expected.day

    def test_multiple_timezones(self):
        """Test conversion with various timezones."""
        test_cases = [
            ('Europe/London', 0),
            ('Europe/Paris', 1),
            ('Asia/Tokyo', 9),
            ('America/Los_Angeles', -8),
        ]
        
        for tz_name, _ in test_cases:
            class MockStation(object):
                timezone = tz_name
            
            station = MockStation()
            naive_dt = datetime(2020, 1, 1, 12, 0, 0)
            result = lib.utc_datetime(naive_dt, station)
            
            assert result.tzinfo == pytz.utc


class TestLocalizeDatetime(object):
    """Test cases for localize_datetime function."""

    def test_datetime_localization(self):
        """Test localizing UTC datetime to station timezone."""
        station = {'timezone': 'Europe/London'}
        utc_dt = pytz.utc.localize(datetime(2020, 1, 1, 12, 0, 0))
        result = lib.localize_datetime(utc_dt, station)
        
        assert result.tzinfo is not None
        assert str(result.tzinfo) == 'Europe/London'

    def test_localization_time_accuracy(self):
        """Test that localization produces correct time values."""
        station = {'timezone': 'America/New_York'}
        utc_dt = pytz.utc.localize(datetime(2020, 1, 1, 17, 0, 0))
        result = lib.localize_datetime(utc_dt, station)
        
        # 17:00 UTC should be 12:00 EST
        assert result.hour == 12


class TestHttpGet(object):
    """Test cases for http_get function."""

    @mock.patch('scraper.lib.requests.get')
    def test_http_get_success(self, mock_get):
        """Test successful HTTP GET request."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.text = '<html>Test</html>'
        mock_get.return_value = mock_response
        
        result = lib.http_get('http://example.com')
        
        assert result.text == '<html>Test</html>'
        mock_get.assert_called_once()

    @mock.patch('scraper.lib.requests.get')
    @mock.patch('scraper.lib.time.sleep')
    def test_http_get_retry_on_failure(self, mock_sleep, mock_get):
        """Test HTTP GET retries on failure."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.text = 'Success'
        
        # Fail twice, then succeed
        mock_get.side_effect = [
            Exception('Connection error'),
            Exception('Connection timeout'),
            mock_response
        ]
        
        result = lib.http_get('http://example.com', retries=3)
        
        assert result.text == 'Success'
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @mock.patch('scraper.lib.requests.get')
    @mock.patch('scraper.lib.time.sleep')
    def test_http_get_max_retries_reached(self, mock_sleep, mock_get):
        """Test HTTP GET when max retries is reached."""
        mock_get.side_effect = Exception('Connection failed')
        
        with pytest.raises(Exception):
            lib.http_get('http://example.com', retries=2)

    @mock.patch('scraper.lib.requests.get')
    def test_http_get_custom_user_agent(self, mock_get):
        """Test HTTP GET with custom user agent."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        custom_agent = 'CustomBot/1.0'
        lib.http_get('http://example.com', user_agent=custom_agent)
        
        call_args = mock_get.call_args
        assert call_args[1]['headers']['User-Agent'] == custom_agent

    @mock.patch('scraper.lib.requests.get')
    def test_http_get_with_cookies(self, mock_get):
        """Test HTTP GET with cookies."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        cookies = {'session': 'test123'}
        lib.http_get('http://example.com', cookies=cookies)
        
        call_args = mock_get.call_args
        assert call_args[1]['cookies'] == cookies


class TestHttpPost(object):
    """Test cases for http_post function."""

    @mock.patch('scraper.lib.requests.post')
    def test_http_post_success(self, mock_post):
        """Test successful HTTP POST request."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.text = '{"result": "ok"}'
        mock_post.return_value = mock_response
        
        result = lib.http_post('http://example.com', data={'key': 'value'})
        
        assert result.text == '{"result": "ok"}'
        mock_post.assert_called_once()

    @mock.patch('scraper.lib.requests.post')
    def test_http_post_with_user_agent(self, mock_post):
        """Test HTTP POST sets correct user agent."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        lib.http_post('http://example.com')
        
        call_args = mock_post.call_args
        assert 'User-Agent' in call_args[1]['headers']


class TestHttpReq(object):
    """Test cases for http_req function."""

    @mock.patch('scraper.lib.requests.get')
    def test_http_req_get_method(self, mock_get):
        """Test http_req with get method."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        lib.http_req('http://example.com', method='get')
        mock_get.assert_called_once()

    @mock.patch('scraper.lib.requests.post')
    def test_http_req_post_method(self, mock_post):
        """Test http_req with post method."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        lib.http_req('http://example.com', method='post')
        mock_post.assert_called_once()

    @mock.patch('scraper.lib.requests.get')
    def test_http_req_zero_retries(self, mock_get):
        """Test http_req with no retries."""
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = lib.http_req('http://example.com', retries=0)
        assert result is not None
