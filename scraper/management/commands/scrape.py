#!/usr/bin/env python
from datetime import datetime
import HTMLParser
import logbook
import os

from django.core.management.base import BaseCommand
import gevent.monkey
gevent.monkey.patch_socket()
import gevent

from radiostats.settings import LOG_DIR
from scraper import scrapers
from scraper.lib import create_date_range, utc_datetime
from scraper.models import Station, Song, Play

log = logbook.Logger()


class Command(BaseCommand):
    help = 'Scrapes radio stations for new tracks'

    def handle(self, *args, **options):
        threads = []
        for station in Station.objects.all():
            runner = GenericRunner(station)
            threads.append(gevent.spawn(runner.run))
        gevent.joinall(threads)


class GenericRunner(object):
    def __init__(self, station):
        self.station = station
        self.htmlparser = HTMLParser.HTMLParser()

    def run(self):
        log_handler = logbook.FileHandler(
            os.path.join(LOG_DIR, u'{0}.log'.format(self.station.name)))
        log_handler.push_thread()
        for date in self.date_range:
            scraper = getattr(scrapers, self.scraper.class_name)(date)
            log.info(u'Scraping {0} for date {1}...'.format(
                self.station.name, date.strftime('%Y-%m-%d')))
            try:
                scraper.scrape()
            except LookupError:
                msg = u'No data found for date {0} on {1}.'
                log.error(msg.format(date.strftime('%Y%m%d'), self.station.name))
                continue
            except Exception as e:
                msg = u'Uncaught exception occurred scraping {0} on {1}:\n{2}'
                msg = msg.format(
                    self.station.name, date.strftime('%Y%m%d'), e.message)
                log.error(msg)
                continue
            added_already = 0
            # Add all unique tracks: we need to make a set as sometimes
            # tracks are duplicated on the website by accident
            for track in list(set(scraper.tracks)):
                artist = self.htmlparser.unescape(track[0])[:256].strip()
                title = self.htmlparser.unescape(track[1])[:256].strip()
                if not (artist and title):
                    continue
                song, _ = Song.objects.get_or_create(
                    artist=artist, title=title)
                _, created = Play.objects.get_or_create(
                    local_time=track[2],
                    time=utc_datetime(track[2], self.station),
                    song=song, station=self.station)
                if not created:
                    # We're encountering tracks we've already added.
                    # Keep trying to add tracks for this date, but
                    # don't proceed with processing further dates if
                    # all tracks for this date were already added.
                    added_already += 1
                    continue
            if scraper.tracks and added_already == len(scraper.tracks):
                log.info(u'End reached for {0} at {1}. Stopping...'.format(
                    self.station.name, date))
                self.station.last_scraped = datetime.utcnow()
                self.station.save()
                return

    @property
    def date_range(self):
        """A list of dates to be processed"""
        try:
            latest = Play.objects.filter(
                station=self.station).order_by('-time').first().time
        except AttributeError:
            latest = self.station.start_date
        return create_date_range(latest)
