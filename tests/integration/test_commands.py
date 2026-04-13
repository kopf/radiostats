# -*- coding: utf-8 -*-
"""
Integration tests for Django management commands.
Compatible with Python 2.7 and 3.x
"""
import pytest
from datetime import datetime, date, timedelta
try:
    from unittest import mock
except ImportError:
    # Python 2.7
    import mock

from django.core.management import call_command
from io import StringIO

from scraper.models import Station, Song, Play, NormalizedSong, Tag


@pytest.mark.django_db
class TestRemoveDuplicatePlaysCommand(object):
    """Integration tests for remove_duplicate_plays management command."""

    def test_command_removes_duplicate_plays(self):
        """Test that duplicate plays within 10 minutes are removed."""
        station = Station.objects.create(
            name='Test Station',
            country='GB',
            timezone='Europe/London',
            class_name='TestScraper',
            start_date=date(2020, 1, 1)
        )
        song = Song.objects.create(artist='Artist', title='Title')
        
        base_time = datetime(2020, 1, 1, 12, 0, 0)
        
        # Create original play
        original_play = Play.objects.create(
            local_time=base_time,
            time=base_time,
            song=song,
            station=station
        )
        
        # Create duplicate play within 10 minutes
        duplicate_time = base_time + timedelta(minutes=5)
        duplicate_play = Play.objects.create(
            local_time=duplicate_time,
            time=duplicate_time,
            song=song,
            station=station
        )
        
        # Verify both plays exist
        assert Play.objects.filter(station=station).count() == 2
        
        # Run the command
        call_command('remove_duplicate_plays')
        
        # Original should exist, duplicate should be removed
        assert Play.objects.filter(id=original_play.id).exists()
        assert not Play.objects.filter(id=duplicate_play.id).exists()

    def test_command_keeps_plays_outside_10_minute_window(self):
        """Test that plays outside 10 minute window are kept."""
        station = Station.objects.create(
            name='Test Station',
            country='GB',
            timezone='Europe/London',
            class_name='TestScraper',
            start_date=date(2020, 1, 1)
        )
        song = Song.objects.create(artist='Artist', title='Title')
        
        base_time = datetime(2020, 1, 1, 12, 0, 0)
        
        # Create first play
        play1 = Play.objects.create(
            local_time=base_time,
            time=base_time,
            song=song,
            station=station
        )
        
        # Create same song play outside 10 minute window
        play2_time = base_time + timedelta(minutes=15)
        play2 = Play.objects.create(
            local_time=play2_time,
            time=play2_time,
            song=song,
            station=station
        )
        
        # Run command
        call_command('remove_duplicate_plays')
        
        # Both should exist
        assert Play.objects.filter(id=play1.id).exists()
        assert Play.objects.filter(id=play2.id).exists()

    def test_command_handles_multiple_stations(self):
        """Test command works correctly with multiple stations."""
        station1 = Station.objects.create(
            name='Station 1',
            country='GB',
            timezone='Europe/London',
            class_name='TestScraper1',
            start_date=date(2020, 1, 1)
        )
        station2 = Station.objects.create(
            name='Station 2',
            country='US',
            timezone='America/New_York',
            class_name='TestScraper2',
            start_date=date(2020, 1, 1)
        )
        
        song = Song.objects.create(artist='Artist', title='Title')
        
        base_time = datetime(2020, 1, 1, 12, 0, 0)
        
        # Create plays for station 1
        play1_s1 = Play.objects.create(
            local_time=base_time,
            time=base_time,
            song=song,
            station=station1
        )
        play2_s1 = Play.objects.create(
            local_time=base_time + timedelta(minutes=5),
            time=base_time + timedelta(minutes=5),
            song=song,
            station=station1
        )
        
        # Create plays for station 2 (different times, no duplicates)
        play1_s2 = Play.objects.create(
            local_time=base_time,
            time=base_time,
            song=song,
            station=station2
        )
        
        call_command('remove_duplicate_plays')
        
        # Station 1 should have one play removed
        assert not Play.objects.filter(id=play2_s1.id).exists()
        assert Play.objects.filter(id=play1_s1.id).exists()
        # Station 2 play should remain
        assert Play.objects.filter(id=play1_s2.id).exists()


@pytest.mark.django_db
class TestIntegrationPlayCreation(object):
    """Integration tests for Play model creation and relationships."""

    def test_create_complete_play_hierarchy(self):
        """Test creating a complete hierarchy: Station -> Song -> Play."""
        station = Station.objects.create(
            name='Complete Station',
            country='GB',
            timezone='Europe/London',
            class_name='CompleteScraper',
            start_date=date(2020, 1, 1)
        )
        
        normalized = NormalizedSong.objects.create(
            mbid='12345678-1234-1234-1234-123456789012',
            artist='The Beatles',
            title='Let It Be'
        )
        
        tag = Tag.objects.create(name='classic-rock')
        normalized.tags.add(tag)
        
        song = Song.objects.create(
            artist='Beatles, The',
            title='Let It Be',
            normalized=normalized
        )
        
        play = Play.objects.create(
            local_time=datetime(2020, 1, 1, 12, 0, 0),
            time=datetime(2020, 1, 1, 12, 0, 0),
            song=song,
            station=station,
            synced=False
        )
        
        # Verify all relationships
        assert play.song == song
        assert play.song.normalized == normalized
        assert tag in play.song.normalized.tags.all()
        assert play.station == station

    def test_bulk_play_creation(self):
        """Test creating multiple plays in bulk."""
        station = Station.objects.create(
            name='Bulk Station',
            country='GB',
            timezone='Europe/London',
            class_name='BulkScraper',
            start_date=date(2020, 1, 1)
        )
        
        songs = []
        for i in range(5):
            song = Song.objects.create(
                artist='Artist {0}'.format(i),
                title='Title {0}'.format(i)
            )
            songs.append(song)
        
        plays = []
        base_time = datetime(2020, 1, 1, 12, 0, 0)
        for idx, song in enumerate(songs):
            play = Play.objects.create(
                local_time=base_time + timedelta(hours=idx),
                time=base_time + timedelta(hours=idx),
                song=song,
                station=station
            )
            plays.append(play)
        
        assert Play.objects.filter(station=station).count() == 5
        
        # Verify all plays can be retrieved
        for idx, play in enumerate(Play.objects.filter(station=station)):
            assert play.song.title == 'Title {0}'.format(idx)


@pytest.mark.django_db
class TestPlayDocumentGeneration(object):
    """Integration tests for Play document generation (for Elasticsearch)."""

    def test_elasticsearch_document_structure(self):
        """Test that Play generates correct Elasticsearch document."""
        station = Station.objects.create(
            name='ES Station',
            country='FR',
            timezone='Europe/Paris',
            class_name='ESScraper',
            start_date=date(2020, 1, 1)
        )
        
        song = Song.objects.create(
            artist='Daft Punk',
            title='One More Time'
        )
        
        play = Play.objects.create(
            local_time=datetime(2020, 1, 1, 14, 30, 0),
            time=datetime(2020, 1, 1, 13, 30, 0),
            song=song,
            station=station
        )
        
        es_doc = play.as_elasticsearch_insert()
        
        # Verify document structure
        assert es_doc['_index'] == 'radiostats'
        assert es_doc['_type'] == 'play'
        assert '_source' in es_doc
        
        source = es_doc['_source']
        assert source['station']['name'] == 'ES Station'
        assert source['song']['artist'] == 'Daft Punk'

    def test_synced_flag_toggling(self):
        """Test toggling the synced flag on plays."""
        station = Station.objects.create(
            name='Sync Station',
            country='GB',
            timezone='Europe/London',
            class_name='SyncScraper',
            start_date=date(2020, 1, 1)
        )
        
        song = Song.objects.create(artist='Test', title='Test')
        
        play = Play.objects.create(
            local_time=datetime(2020, 1, 1, 12, 0, 0),
            time=datetime(2020, 1, 1, 12, 0, 0),
            song=song,
            station=station,
            synced=False
        )
        
        assert not play.synced
        
        play.synced = True
        play.save()
        
        reloaded = Play.objects.get(id=play.id)
        assert reloaded.synced
