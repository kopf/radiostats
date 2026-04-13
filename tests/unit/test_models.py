# -*- coding: utf-8 -*-
"""
Unit tests for scraper models.
Compatible with Python 2.7 and 3.x
"""
import pytest
from datetime import datetime, date
from django.db import IntegrityError

from scraper.models import Station, Tag, Song, NormalizedSong, Play


@pytest.mark.django_db
class TestStationModel(object):
    """Test cases for Station model."""

    def test_station_creation(self):
        """Test creating a Station instance."""
        station = Station.objects.create(
            name='BBC Radio 1',
            country='GB',
            timezone='Europe/London',
            class_name='BBCRadio1Scraper',
            start_date=date(2020, 1, 1),
            enabled=True
        )
        assert station.id is not None
        assert station.name == 'BBC Radio 1'
        assert station.country == 'GB'

    def test_station_unicode(self):
        """Test Station unicode representation."""
        station = Station.objects.create(
            name='Test Station',
            country='GB',
            timezone='Europe/London',
            class_name='TestScraper',
            start_date=date(2020, 1, 1)
        )
        # Python 2/3 compatible unicode test
        assert str(station) == 'Test Station'

    def test_station_disabled(self):
        """Test creating a disabled station."""
        station = Station.objects.create(
            name='Old Station',
            country='GB',
            timezone='Europe/London',
            class_name='OldScraper',
            start_date=date(2020, 1, 1),
            enabled=False
        )
        assert station.enabled is False

    def test_station_last_scraped(self):
        """Test updating last_scraped timestamp."""
        station = Station.objects.create(
            name='Updated Station',
            country='GB',
            timezone='Europe/London',
            class_name='UpdatedScraper',
            start_date=date(2020, 1, 1)
        )
        assert station.last_scraped is None
        
        test_time = datetime(2020, 1, 15, 10, 30, 0)
        station.last_scraped = test_time
        station.save()
        
        reloaded = Station.objects.get(id=station.id)
        assert reloaded.last_scraped is not None


@pytest.mark.django_db
class TestTagModel(object):
    """Test cases for Tag model."""

    def test_tag_creation(self):
        """Test creating a Tag instance."""
        tag = Tag.objects.create(name='rock')
        assert tag.id is not None
        assert tag.name == 'rock'

    def test_tag_unique(self):
        """Test that tag names are unique."""
        Tag.objects.create(name='unique-tag')
        with pytest.raises(IntegrityError):
            Tag.objects.create(name='unique-tag')

    def test_tag_unicode(self):
        """Test Tag unicode representation."""
        tag = Tag.objects.create(name='pop')
        assert str(tag) == 'pop'


@pytest.mark.django_db
class TestSongModel(object):
    """Test cases for Song model."""

    def test_song_creation(self):
        """Test creating a Song instance."""
        song = Song.objects.create(
            artist='The Beatles',
            title='Let It Be'
        )
        assert song.id is not None
        assert song.artist == 'The Beatles'
        assert song.title == 'Let It Be'
        assert song.normalized is None

    def test_song_unicode(self):
        """Test Song unicode representation."""
        song = Song.objects.create(
            artist='David Bowie',
            title='Space Oddity'
        )
        assert str(song) == 'David Bowie - Space Oddity'

    def test_song_unique(self):
        """Test that artist-title combination is unique."""
        Song.objects.create(artist='Artist', title='Title')
        with pytest.raises(IntegrityError):
            Song.objects.create(artist='Artist', title='Title')

    def test_song_with_same_artist_different_title(self):
        """Test that same artist with different titles is allowed."""
        song1 = Song.objects.create(artist='Artist', title='Title 1')
        song2 = Song.objects.create(artist='Artist', title='Title 2')
        assert song1.id != song2.id


@pytest.mark.django_db
class TestNormalizedSongModel(object):
    """Test cases for NormalizedSong model."""

    def test_normalized_song_creation(self):
        """Test creating a NormalizedSong instance."""
        norm_song = NormalizedSong.objects.create(
            mbid='12345678-1234-1234-1234-123456789012',
            artist='The Beatles',
            title='Let It Be'
        )
        assert norm_song.id is not None
        assert norm_song.mbid == '12345678-1234-1234-1234-123456789012'

    def test_normalized_song_unicode(self):
        """Test NormalizedSong unicode representation."""
        norm_song = NormalizedSong.objects.create(
            mbid='87654321-4321-4321-4321-210987654321',
            artist='Pink Floyd',
            title='Comfortably Numb'
        )
        assert str(norm_song) == 'Pink Floyd - Comfortably Numb'

    def test_normalized_song_unique(self):
        """Test that mbid-artist-title combination is unique."""
        NormalizedSong.objects.create(
            mbid='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            artist='Artist',
            title='Title'
        )
        with pytest.raises(IntegrityError):
            NormalizedSong.objects.create(
                mbid='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
                artist='Artist',
                title='Title'
            )

    def test_normalized_song_with_tags(self):
        """Test adding tags to a normalized song."""
        norm_song = NormalizedSong.objects.create(
            mbid='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
            artist='Test Artist',
            title='Test Title'
        )
        tag1 = Tag.objects.create(name='rock')
        tag2 = Tag.objects.create(name='classic')
        
        norm_song.tags.add(tag1, tag2)
        
        reloaded = NormalizedSong.objects.get(id=norm_song.id)
        assert reloaded.tags.count() == 2
        assert tag1 in reloaded.tags.all()
        assert tag2 in reloaded.tags.all()


@pytest.mark.django_db
class TestPlayModel(object):
    """Test cases for Play model."""

    def test_play_creation(self):
        """Test creating a Play instance."""
        station = Station.objects.create(
            name='Test Station',
            country='GB',
            timezone='Europe/London',
            class_name='TestScraper',
            start_date=date(2020, 1, 1)
        )
        song = Song.objects.create(
            artist='Test Artist',
            title='Test Title'
        )
        play = Play.objects.create(
            local_time=datetime(2020, 1, 1, 12, 0, 0),
            time=datetime(2020, 1, 1, 12, 0, 0),
            song=song,
            station=station,
            synced=False
        )
        assert play.id is not None
        assert play.song == song
        assert play.station == station

    def test_play_unique(self):
        """Test that time-station combination is unique."""
        station = Station.objects.create(
            name='Station',
            country='GB',
            timezone='Europe/London',
            class_name='Scraper',
            start_date=date(2020, 1, 1)
        )
        song = Song.objects.create(artist='Artist', title='Title')
        play_time = datetime(2020, 1, 1, 12, 0, 0)
        
        Play.objects.create(
            local_time=play_time,
            time=play_time,
            song=song,
            station=station
        )
        
        # Same time and station should fail
        with pytest.raises(IntegrityError):
            Play.objects.create(
                local_time=play_time,
                time=play_time,
                song=song,
                station=station
            )

    def test_play_as_document(self):
        """Test Play.as_document() method."""
        station = Station.objects.create(
            name='Test Station',
            country='US',
            timezone='America/New_York',
            class_name='TestScraper',
            start_date=date(2020, 1, 1)
        )
        song = Song.objects.create(
            artist='The Beatles',
            title='Yellow Submarine'
        )
        play = Play.objects.create(
            local_time=datetime(2020, 1, 1, 12, 0, 0),
            time=datetime(2020, 1, 1, 17, 0, 0),
            song=song,
            station=station
        )
        
        doc = play.as_document()
        
        assert doc['local_time'] == '2020-01-01 12:00:00'
        assert doc['utc_time'] == '2020-01-01 17:00:00'
        assert doc['station']['name'] == 'Test Station'
        assert doc['station']['country'] == 'US'
        assert doc['song']['title'] == 'Yellow Submarine'
        assert doc['song']['artist'] == 'The Beatles'
        assert doc['song']['normalized'] is False
        assert doc['song']['tags'] == []

    def test_play_as_document_with_normalized_song(self):
        """Test Play.as_document() with normalized song and tags."""
        station = Station.objects.create(
            name='Test Station',
            country='GB',
            timezone='Europe/London',
            class_name='TestScraper',
            start_date=date(2020, 1, 1)
        )
        
        norm_song = NormalizedSong.objects.create(
            mbid='12345678-1234-1234-1234-123456789012',
            artist='Pink Floyd',
            title='Wish You Were Here'
        )
        tag = Tag.objects.create(name='psychedelic')
        norm_song.tags.add(tag)
        
        song = Song.objects.create(
            artist='Pink Floyd',
            title='Wish You Were Here',
            normalized=norm_song
        )
        
        play = Play.objects.create(
            local_time=datetime(2020, 1, 1, 15, 30, 0),
            time=datetime(2020, 1, 1, 15, 30, 0),
            song=song,
            station=station
        )
        
        doc = play.as_document()
        
        assert doc['song']['normalized'] is True
        assert len(doc['song']['tags']) == 1
        assert 'psychedelic' in doc['song']['tags']

    def test_play_as_elasticsearch_insert(self):
        """Test Play.as_elasticsearch_insert() method."""
        station = Station.objects.create(
            name='Test',
            country='GB',
            timezone='Europe/London',
            class_name='TestScraper',
            start_date=date(2020, 1, 1)
        )
        song = Song.objects.create(artist='Artist', title='Title')
        play = Play.objects.create(
            local_time=datetime(2020, 1, 1, 12, 0, 0),
            time=datetime(2020, 1, 1, 12, 0, 0),
            song=song,
            station=station
        )
        
        insert_doc = play.as_elasticsearch_insert()
        
        assert insert_doc['_index'] == 'radiostats'
        assert insert_doc['_type'] == 'play'
        assert '_source' in insert_doc
        assert insert_doc['_source']['station']['name'] == 'Test'
