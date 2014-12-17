#!/usr/bin/env python
from datetime import datetime
import logbook
import HTMLParser

from django.core.management.base import BaseCommand
import gevent.monkey
gevent.monkey.patch_socket()
import gevent

from scraper.lib import create_date_range
from scraper.models import Station, Song, Play
from scraper.scrapers import SCRAPERS


class Command(BaseCommand):
    help = 'Scrapes radio stations for new tracks'

    def handle(self, *args, **options):
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
        self.htmlparser = HTMLParser.HTMLParser()
        self.log = logbook.Logger()

    def run(self):
        with self.log.catch_exceptions():
            for date in self.date_range:
                scraper = SCRAPERS[self.station_name]['cls'](date)
                self.log.info('Scraping {0} for date {1}...'.format(
                    self.station_name, date.strftime('%Y-%m-%d')))
                try:
                    scraper.scrape()
                except LookupError:
                    msg = 'No data found for date {0} on {1}.'
                    self.log.error(msg.format(date.strftime('%Y%m%d'), self.station_name))
                    continue
                added_already = 0
                # Add all unique tracks: we need to make a set as sometimes
                # tracks are duplicated on the website by accident
                for track in list(set(scraper.tracks)):
                    song, _ = Song.objects.get_or_create(
                        artist=self.htmlparser.unescape(track[0]),
                        title=self.htmlparser.unescape(track[1]))
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
                    self.log.info('End reached for {0} at {1}. Stopping...'.format(
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
