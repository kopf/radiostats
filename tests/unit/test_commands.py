from unittest import mock
from datetime import date, datetime

import pytz
from django.test import TestCase
from django.core.exceptions import ObjectDoesNotExist

from scraper.management.commands import scrape, normalize
from scraper.lib import create_date_range


class ScrapeTests(TestCase):
    @mock.patch('scraper.management.commands.scrape.GenericRunner')
    def test_handle_with_station(self, mock_runner):
        """Test that handle calls the runner for the specified station."""
        mock_station = mock.MagicMock()
        mock_station.name = "test_station"

        with mock.patch('scraper.models.Station.objects.filter') as mock_filter:
            mock_filter.return_value = [mock_station]
            command = scrape.Command()
            command.handle(station_name="test_station", dry_run=False, sequential=False)

        mock_runner.assert_called_once_with(mock_station, dry_run=False)
        self.assertTrue(mock_runner.return_value.run.called)

    @mock.patch('subprocess.Popen')
    def test_handle_all_stations(self, mock_popen):
        """Test that handle spawns processes for all enabled stations."""
        mock_station1 = mock.MagicMock()
        mock_station1.name = "station1"
        mock_station2 = mock.MagicMock()
        mock_station2.name = "station2"

        with mock.patch('scraper.models.Station.objects.filter') as mock_filter:
            mock_filter.return_value = [mock_station1, mock_station2]
            command = scrape.Command()
            command.handle(station_name=None, dry_run=True, sequential=False)

        self.assertEqual(mock_popen.call_count, 2)
        mock_popen.assert_any_call(['python', mock.ANY, 'scrape', '-s', 'station1', '-d'])
        mock_popen.assert_any_call(['python', mock.ANY, 'scrape', '-s', 'station2', '-d'])


class GenericRunnerTests(TestCase):
    def setUp(self):
        self.mock_station = mock.MagicMock()
        self.mock_station.name = "test_station"
        self.mock_station.class_name = "TestScraper"
        self.mock_station.timezone = "UTC"
        self.mock_station.start_date = date(2020, 1, 1)

    @mock.patch('scraper.lib.datetime')
    @mock.patch('scraper.models.Play.objects.filter')
    def test_date_range_with_plays(self, mock_filter, mock_datetime):
        """Test date_range property when plays exist."""
        mock_datetime.now.return_value.date.return_value = date(2020, 1, 10)
        mock_play = mock.MagicMock()
        mock_play.local_time.date.return_value = date(2020, 1, 5)
        mock_filter.return_value.order_by.return_value.first.return_value = mock_play

        runner = scrape.GenericRunner(self.mock_station)
        # create_date_range will create a list of dates from the start date up to today.
        # So we just check the first date.
        self.assertEqual(runner.date_range[0], date(2020, 1, 9))

    @mock.patch('scraper.lib.datetime')
    @mock.patch('scraper.models.Play.objects.filter')
    def test_date_range_no_plays(self, mock_filter, mock_datetime):
        """Test date_range property when no plays exist."""
        mock_datetime.now.return_value.date.return_value = date(2020, 1, 10)
        mock_filter.return_value.order_by.return_value.first.return_value = None
        runner = scrape.GenericRunner(self.mock_station)
        self.assertEqual(runner.date_range[0], date(2020, 1, 9))

    @mock.patch('scraper.management.commands.scrape.logbook')
    @mock.patch('scraper.management.commands.scrape.scrapers')
    @mock.patch('scraper.models.Song.objects.get_or_create')
    @mock.patch('scraper.models.Play.objects.get_or_create')
    def test_run_normal(self, mock_play_get_or_create, mock_song_get_or_create, mock_scrapers, mock_logbook):
        """Test the normal run case."""
        mock_scraper_instance = mock.MagicMock()
        mock_scraper_instance.tracks = [('Artist', 'Title', datetime(2020, 1, 1, 12, 0))]
        mock_scraper_instance.utc_datetimes = False
        mock_scraper_instance.terminate_early = False
        mock_scrapers.TestScraper.return_value = mock_scraper_instance

        mock_song_get_or_create.return_value = (mock.MagicMock(), True)
        mock_play_get_or_create.return_value = (mock.MagicMock(), True)

        runner = scrape.GenericRunner(self.mock_station)
        type(runner).date_range = mock.PropertyMock(return_value=[date(2020, 1, 1)])
        runner.run()

        mock_scrapers.TestScraper.assert_called_once_with(date(2020, 1, 1))
        mock_scraper_instance.scrape.assert_called_once()
        mock_song_get_or_create.assert_called_once_with(artist='Artist', title='Title')

        # Check that the play was created with the correct time
        first_call_args = mock_play_get_or_create.call_args[1]
        self.assertEqual(first_call_args['station'], self.mock_station)
        self.assertEqual(first_call_args['local_time'], datetime(2020, 1, 1, 12, 0))
        self.assertEqual(first_call_args['time'].year, 2020)
        self.assertEqual(first_call_args['time'].month, 1)
        self.assertEqual(first_call_args['time'].day, 1)

    @mock.patch('scraper.management.commands.scrape.logbook')
    @mock.patch('scraper.management.commands.scrape.scrapers')
    def test_run_dry_run(self, mock_scrapers, mock_logbook):
        """Test the dry_run functionality."""
        mock_scraper_instance = mock.MagicMock()
        mock_scraper_instance.tracks = [('Artist', 'Title', datetime(2020, 1, 1, 12, 0))]
        mock_scrapers.TestScraper.return_value = mock_scraper_instance

        runner = scrape.GenericRunner(self.mock_station, dry_run=True)
        type(runner).date_range = mock.PropertyMock(return_value=[date(2020, 1, 1)])

        with mock.patch('builtins.print') as mock_print:
            runner.run()
        
        mock_print.assert_called_once_with([('Artist', 'Title', datetime(2020, 1, 1, 12, 0))])
        self.assertFalse(self.mock_station.save.called)

    @mock.patch('scraper.management.commands.scrape.logbook')
    @mock.patch('scraper.management.commands.scrape.scrapers')
    @mock.patch('scraper.models.Play.objects.get_or_create')
    def test_run_stops_on_duplicate(self, mock_play_get_or_create, mock_scrapers, mock_logbook):
        """Test that the runner terminates early if all tracks are duplicates."""
        mock_scraper_instance = mock.MagicMock()
        mock_scraper_instance.tracks = [('Artist', 'Title', datetime(2020, 1, 1, 12, 0))]
        mock_scraper_instance.terminate_early = False
        mock_scrapers.TestScraper.return_value = mock_scraper_instance

        mock_play_get_or_create.return_value = (mock.MagicMock(), False) # Not created (duplicate)

        runner = scrape.GenericRunner(self.mock_station)
        type(runner).date_range = mock.PropertyMock(return_value=[date(2020, 1, 1), date(2020, 1, 2)])
        runner.run()

        # Scraper should only be called for the first date
        mock_scrapers.TestScraper.assert_called_once_with(date(2020, 1, 1))
        self.assertTrue(self.mock_station.save.called)


class NormalizeTests(TestCase):
    def setUp(self):
        self.command = normalize.Command()

    @mock.patch('scraper.management.commands.normalize.Command.normalize')
    @mock.patch('scraper.models.Song.objects.filter')
    def test_handle(self, mock_filter, mock_normalize):
        """Test that handle calls normalize for each un-scraped track."""
        mock_track1 = mock.MagicMock()
        mock_track2 = mock.MagicMock()
        mock_filter.return_value = [mock_track1, mock_track2]

        self.command.handle()

        self.assertEqual(mock_normalize.call_count, 2)
        mock_normalize.assert_any_call(mock_track1)
        mock_normalize.assert_any_call(mock_track2)
        self.assertTrue(mock_track1.save.called)
        self.assertTrue(mock_track2.save.called)
        self.assertIsNotNone(mock_track1.last_scraped)
        self.assertIsNotNone(mock_track2.last_scraped)

    @mock.patch('scraper.models.NormalizedSong.objects.get')
    @mock.patch('scraper.management.commands.normalize.tag_item')
    @mock.patch('scraper.management.commands.normalize.Command.query_lastfm')
    @mock.patch('scraper.models.NormalizedSong.objects.get_or_create')
    def test_normalize_beets_success(self, mock_get_or_create, mock_query_lastfm, mock_tag_item, mock_get):
        """Test normalize when beets finds a confident match."""
        mock_track = mock.MagicMock()
        mock_track.artist = "Artist"
        mock_track.title = "Title"

        mock_match_info = mock.MagicMock()
        mock_match_info.artist = "Normalized Artist"
        mock_match_info.title = "Normalized Title"
        mock_match_info.track_id = "test_mbid"
        
        mock_match = mock.MagicMock()
        mock_match.distance.distance = 0.1
        mock_match.info = mock_match_info
        
        mock_tag_item.return_value = [[mock_match]]
        mock_get.side_effect = ObjectDoesNotExist
        mock_get_or_create.return_value = (mock.MagicMock(), True)

        with mock.patch.object(self.command, 'get_tags', return_value=[]):
            with mock.patch.object(self.command, 'extract_tags', return_value=[]):
                self.command.normalize(mock_track)

        self.assertFalse(mock_query_lastfm.called)
        mock_get_or_create.assert_called_once_with(
            mbid='test_mbid',
            artist='Normalized Artist',
            title='Normalized Title'
        )
        self.assertTrue(mock_track.save.called)

    @mock.patch('scraper.management.commands.normalize.tag_item')
    @mock.patch('scraper.management.commands.normalize.Command.query_lastfm')
    @mock.patch('scraper.models.NormalizedSong.objects.get_or_create')
    def test_normalize_lastfm_success(self, mock_get_or_create, mock_query_lastfm, mock_tag_item):
        """Test normalize when beets fails and lastfm finds a match."""
        mock_track = mock.MagicMock()
        mock_track.artist = "Artist"
        mock_track.title = "Title"

        mock_tag_item.return_value = None # beets fails
        mock_query_lastfm.return_value = {
            'artist': 'Normalized Artist',
            'title': 'Normalized Title',
            'mbid': 'test_mbid',
            'tags': ['rock', 'pop']
        }

        mock_normalized_song = mock.MagicMock()
        mock_get_or_create.return_value = (mock_normalized_song, True)
        
        with mock.patch('scraper.models.Tag.objects.get_or_create', return_value=(mock.MagicMock(), True)):
             self.command.normalize(mock_track)

        mock_query_lastfm.assert_called_once_with("Artist", "Title")
        mock_get_or_create.assert_called_once_with(
            mbid='test_mbid',
            artist='Normalized Artist',
            title='Normalized Title'
        )
        self.assertEqual(mock_normalized_song.tags.add.call_count, 1)
        self.assertTrue(mock_track.save.called)

    @mock.patch('scraper.management.commands.normalize.tag_item')
    @mock.patch('scraper.management.commands.normalize.Command.query_lastfm')
    def test_normalize_no_match(self, mock_query_lastfm, mock_tag_item):
        """Test normalize when no match is found."""
        mock_track = mock.MagicMock()
        mock_track.artist = "Artist"
        mock_track.title = "Title"

        mock_tag_item.return_value = None
        mock_query_lastfm.return_value = None

        self.command.normalize(mock_track)

        self.assertFalse(mock_track.save.called)

    def test_extract_tags(self):
        """Test the extract_tags method."""
        self.assertEqual(self.command.extract_tags({}), [])
        self.assertEqual(self.command.extract_tags({'tag': {'name': 'rock'}}), ['rock'])
        self.assertEqual(self.command.extract_tags({'tag': [{'name': 'rock'}, {'name': 'pop'}]}), ['rock', 'pop'])
        self.assertEqual(self.command.extract_tags([]), [])
