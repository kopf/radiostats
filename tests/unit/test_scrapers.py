# -*- coding: utf-8 -*-
"""
Unit tests for scraper.scrapers with mocked HTTP requests.
Compatible with Python 2.7 and 3.x
"""
import pytest
from datetime import datetime, date
import json
try:
    from unittest import mock
except ImportError:
    # Python 2.7
    import mock

from scraper.scrapers import ScraperBase, GenericScraper, GenericLastFMScraper


class TestScraperBase(object):
    """Test cases for ScraperBase class."""

    def test_scraper_base_initialization(self):
        """Test ScraperBase initialization."""
        test_date = date(2020, 1, 1)
        scraper = ScraperBase(test_date)
        
        assert scraper.date == test_date
        assert scraper.tracks == []
        assert scraper.log is not None

    def test_scraper_base_type_name(self):
        """Test that logger uses correct class name."""
        test_date = date(2020, 1, 1)
        scraper = ScraperBase(test_date)
        
        assert scraper.log.name == 'ScraperBase'


class TestGenericScraper(object):
    """Test cases for GenericScraper class."""

    def test_generic_scraper_initialization(self):
        """Test GenericScraper initialization."""
        test_date = date(2020, 1, 1)
        scraper = GenericScraper(test_date)
        
        assert scraper.date == test_date
        assert scraper.tracks == []
        assert scraper.cookies == {}
        assert scraper.terminate_early is False
        assert scraper.utc_datetimes is False

    def test_time_to_datetime_with_seconds(self):
        """Test time_to_datetime with seconds."""
        scraper = GenericScraper(date(2020, 1, 15))
        result = scraper.time_to_datetime('12:30:45', ':')
        
        assert result.year == 2020
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_time_to_datetime_without_seconds(self):
        """Test time_to_datetime without seconds (default to 0)."""
        scraper = GenericScraper(date(2020, 1, 15))
        result = scraper.time_to_datetime('14:20', ':')
        
        assert result.hour == 14
        assert result.minute == 20
        assert result.second == 0

    def test_time_to_datetime_custom_separator(self):
        """Test time_to_datetime with custom separator."""
        scraper = GenericScraper(date(2020, 6, 10))
        result = scraper.time_to_datetime('16-45', '-')
        
        assert result.hour == 16
        assert result.minute == 45

    @mock.patch('scraper.scrapers.http_get')
    def test_generic_scraper_scrape(self, mock_http_get):
        """Test GenericScraper.scrape method."""
        mock_response = mock.Mock()
        mock_response.text = '<html><body>Test</body></html>'
        mock_http_get.return_value = mock_response
        
        class TestScraper(GenericScraper):
            tracklist_urls = ['http://example.com/tracks']
            
            def extract_tracks(self):
                # Mock extract_tracks to add a track
                self.tracks.append(('Artist', 'Title', datetime(2020, 1, 1, 12, 0, 0)))
                return True
        
        scraper = TestScraper(date(2020, 1, 1))
        scraper.scrape()
        
        assert len(scraper.tracks) == 1
        assert scraper.tracks[0] == ('Artist', 'Title', datetime(2020, 1, 1, 12, 0, 0))

    @mock.patch('scraper.scrapers.http_get')
    def test_generic_scraper_multiple_urls(self, mock_http_get):
        """Test GenericScraper with multiple URLs."""
        mock_response = mock.Mock()
        mock_response.text = '<html></html>'
        mock_http_get.return_value = mock_response
        
        class TestScraper(GenericScraper):
            tracklist_urls = [
                'http://example.com/page1',
                'http://example.com/page2',
                'http://example.com/page3',
            ]
            
            def extract_tracks(self):
                return True
        
        scraper = TestScraper(date(2020, 1, 1))
        scraper.scrape()
        
        assert mock_http_get.call_count == 3

    @mock.patch('scraper.scrapers.http_get')
    def test_generic_scraper_with_cookies(self, mock_http_get):
        """Test GenericScraper passes cookies to requests."""
        mock_response = mock.Mock()
        mock_response.text = '<html></html>'
        mock_http_get.return_value = mock_response
        
        class TestScraper(GenericScraper):
            tracklist_urls = ['http://example.com']
            cookies = {'session_id': 'test123'}
            
            def extract_tracks(self):
                return True
        
        scraper = TestScraper(date(2020, 1, 1))
        scraper.scrape()
        
        call_args = mock_http_get.call_args
        assert call_args[1]['cookies'] == {'session_id': 'test123'}


class TestGenericLastFMScraper(object):
    """Test cases for GenericLastFMScraper class."""

    def test_lastfm_scraper_initialization(self):
        """Test GenericLastFMScraper initialization."""
        test_date = date(2020, 1, 15)
        scraper = GenericLastFMScraper(test_date)
        
        assert scraper.date == test_date
        assert scraper.start.date() == test_date
        assert scraper.end.date() == test_date
        assert scraper.utc_datetimes is True
        assert scraper.terminate_early is False

    def test_lastfm_scraper_start_end_times(self):
        """Test that start and end times span full day."""
        test_date = date(2020, 6, 15)
        scraper = GenericLastFMScraper(test_date)
        
        assert scraper.start.hour == 0
        assert scraper.start.minute == 0
        assert scraper.start.second == 0
        
        # Start time should be same date
        assert scraper.start.date() == test_date
        # End time should be same date
        assert scraper.end.date() == test_date

    @mock.patch('scraper.scrapers.requests.get')
    @mock.patch('scraper.scrapers.settings')
    @mock.patch('scraper.scrapers.time.sleep')
    def test_lastfm_scraper_single_page(self, mock_sleep, mock_settings, mock_get):
        """Test LastFM scraper with single page of results."""
        mock_settings.LASTFM_API_KEY = 'test-api-key'
        
        track_data = {
            'recenttracks': {
                'track': [
                    {
                        'artist': {'#text': 'The Beatles'},
                        'name': 'Let It Be',
                        'date': {'uts': '1577836800'}  # 2020-01-01 12:00:00 UTC
                    }
                ]
            }
        }
        
        mock_response = mock.Mock()
        mock_response.json.return_value = track_data
        mock_get.return_value = mock_response
        
        class TestLastFMScraper(GenericLastFMScraper):
            username = 'testuser'
        
        scraper = TestLastFMScraper(date(2020, 1, 1))
        scraper.scrape()
        
        assert len(scraper.tracks) == 1
        artist, title, timestamp = scraper.tracks[0]
        assert artist == 'The Beatles'
        assert title == 'Let It Be'

    @mock.patch('scraper.scrapers.requests.get')
    @mock.patch('scraper.scrapers.settings')
    @mock.patch('scraper.scrapers.time.sleep')
    def test_lastfm_scraper_multiple_pages(self, mock_sleep, mock_settings, mock_get):
        """Test LastFM scraper with multiple pages."""
        mock_settings.LASTFM_API_KEY = 'test-api-key'
        
        page1_data = {
            'recenttracks': {
                'track': [
                    {
                        'artist': {'#text': 'Artist1'},
                        'name': 'Title1',
                        'date': {'uts': '1577836800'}
                    }
                ]
            }
        }
        
        page2_data = {
            'recenttracks': {
                'track': [
                    {
                        'artist': {'#text': 'Artist1'},
                        'name': 'Title1',
                        'date': {'uts': '1577836800'}
                    }
                ]
            }
        }
        
        mock_response = mock.Mock()
        mock_response.json.side_effect = [page1_data, page2_data]
        mock_get.return_value = mock_response
        
        class TestLastFMScraper(GenericLastFMScraper):
            username = 'testuser'
        
        scraper = TestLastFMScraper(date(2020, 1, 1))
        scraper.scrape()
        
        # Should stop after second page (same track as first)
        assert len(scraper.tracks) == 1

    @mock.patch('scraper.scrapers.requests.get')
    @mock.patch('scraper.scrapers.settings')
    @mock.patch('scraper.scrapers.time.sleep')
    def test_lastfm_scraper_skip_now_playing(self, mock_sleep, mock_settings, mock_get):
        """Test that currently playing tracks (without date) are skipped."""
        mock_settings.LASTFM_API_KEY = 'test-api-key'
        
        track_data = {
            'recenttracks': {
                'track': [
                    {
                        'artist': {'#text': 'Current Artist'},
                        'name': 'Now Playing',
                        # No 'date' field for currently playing tracks
                    },
                    {
                        'artist': {'#text': 'Past Artist'},
                        'name': 'Past Track',
                        'date': {'uts': '1577836800'}
                    }
                ]
            }
        }
        
        mock_response = mock.Mock()
        mock_response.json.return_value = track_data
        mock_get.return_value = mock_response
        
        class TestLastFMScraper(GenericLastFMScraper):
            username = 'testuser'
        
        scraper = TestLastFMScraper(date(2020, 1, 1))
        scraper.scrape()
        
        # Only the track with date should be included
        assert len(scraper.tracks) == 1
        assert scraper.tracks[0][0] == 'Past Artist'
