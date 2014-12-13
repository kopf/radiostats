#!/usr/bin/env python
from datetime import datetime
import logbook
from simplejson.decoder import JSONDecodeError
from urllib import quote_plus

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
import gevent.monkey
gevent.monkey.patch_socket()
import gevent

from scraper.lib import http_get, create_date_range
from scraper.models import Station, Song, Play
from scraper.scrapers import SCRAPERS

log = logbook.Logger()
FILE_LOGGER = logbook.FileHandler('runner.log', bubble=True)
FILE_LOGGER.push_application()


class Command(BaseCommand):
    help = 'Scrapes radio stations for new tracks'

    def add_arguments(self, parser):
        parser.add_argument('--station',
            action='store',
            dest='station',
            default=False,
            help='Specify a certain radio station to scrape')

    def handle(self, *args, **options):
        if options['station']:
            if options['station'] not in SCRAPERS:
                raise CommandError('Invalid radio station: {0}'.format(
                    options['station']))
            runner = GenericRunner(options['station'])
            runner.run()
        else:
            threads = []
            for station_name in SCRAPERS:
                runner = GenericRunner(station_name)
                threads.append(gevent.spawn(runner.run))
            gevent.joinall(threads)


class GenericRunner(object):
    def __init__(self, station_name):
        self.station_name = station_name
        self.station, _ = Station.objects.get_or_create(
            name=station_name,
            country=SCRAPERS[station_name]['country'])

    def run(self):
        with log.catch_exceptions():
            for date in self.date_range:
                scraper = SCRAPERS[self.station_name]['cls'](date)
                log.info('Scraping {0} for date {1}...'.format(
                    self.station_name, date.strftime('%Y-%m-%d')))
                try:
                    scraper.scrape()
                except LookupError:
                    msg = 'No data found for date {0} on {1}.'
                    log.error(msg.format(date.strftime('%Y%m%d'), self.station_name))
                    continue
                added_already = 0
                # Add all unique tracks: we need to make a set as sometimes
                # tracks are duplicated on the website by accident
                for track in list(set(scraper.tracks)):
                    song, _ = Song.objects.get_or_create(
                        artist=track[0], title=track[1])
                    _, created = Play.objects.get_or_create(
                        time=track[2], song=song, station=self.station)
                    if not created:
                        # We're encountering tracks we've already added.
                        # Keep trying to add tracks for this date, but
                        # don't proceed with processing further dates if
                        # all tracks for this date were already added.
                        added_already += 1
                        continue
                if scraper.tracks and added_already == len(scraper.tracks):
                    log.info('End reached for {0} at {1}. Stopping...'.format(
                        self.station_name, date))
                    return

    @property
    def date_range(self):
        """A list of dates to be processed"""
        try:
            latest = Play.objects.filter(
                station=self.station).order_by('-time').first().time
        except AttributeError:
            latest = datetime.strptime(
                SCRAPERS[self.station_name]['start_date'], '%Y%m%d')
        return create_date_range(latest)
