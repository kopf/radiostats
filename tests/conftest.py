# -*- coding: utf-8 -*-
"""
Shared test configuration and fixtures for radiostats tests.
Compatible with Python 2.7 and 3.x
"""
import os
import sys
import django
from datetime import datetime, date
from django.conf import settings

import pytest


# Configure Django settings
def pytest_configure():
    """Configure Django settings before running tests."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "radiostats.settings.dev")
    
    # Add project root to path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Setup Django
    if hasattr(django, 'setup'):
        django.setup()
    
    # Configure database for tests
    if not settings.configured:
        settings.configure(
            DEBUG=True,
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=(
                'django.contrib.admin',
                'django.contrib.auth',
                'django.contrib.contenttypes',
                'django.contrib.sessions',
                'django.contrib.messages',
                'django.contrib.staticfiles',
                'django_countries',
                'scraper',
            ),
            MIDDLEWARE_CLASSES=(
                'django.contrib.sessions.middleware.SessionMiddleware',
                'django.middleware.common.CommonMiddleware',
                'django.middleware.csrf.CsrfViewMiddleware',
                'django.contrib.auth.middleware.AuthenticationMiddleware',
                'django.contrib.messages.middleware.MessageMiddleware',
            ),
            SECRET_KEY='test-secret-key',
        )


@pytest.fixture
def sample_station():
    """Fixture providing a sample station model instance."""
    from scraper.models import Station
    return Station(
        name='Test Station',
        country='GB',
        timezone='Europe/London',
        class_name='TestScraper',
        start_date=date(2020, 1, 1),
        enabled=True
    )


@pytest.fixture
def sample_tag():
    """Fixture providing a sample tag model instance."""
    from scraper.models import Tag
    return Tag(name='test-genre')


@pytest.fixture
def sample_song():
    """Fixture providing a sample song model instance."""
    from scraper.models import Song
    return Song(
        artist='Test Artist',
        title='Test Title'
    )


@pytest.fixture
def sample_normalized_song():
    """Fixture providing a sample normalized song model instance."""
    from scraper.models import NormalizedSong
    return NormalizedSong(
        mbid='12345678-1234-1234-1234-123456789012',
        artist='Test Artist',
        title='Test Title'
    )


@pytest.fixture
def sample_play(sample_station, sample_song):
    """Fixture providing a sample play model instance."""
    from scraper.models import Play
    return Play(
        local_time=datetime(2020, 1, 1, 12, 0, 0),
        time=datetime(2020, 1, 1, 12, 0, 0),
        song=sample_song,
        station=sample_station,
        synced=False
    )


@pytest.fixture
def db_session(db):
    """Fixture providing pytest-django's database session."""
    return db
