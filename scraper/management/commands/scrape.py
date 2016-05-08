#!/usr/bin/env python
from datetime import datetime
import HTMLParser
import traceback
import os
from optparse import make_option
import pytz

import logbook
from django.core.exceptions import MultipleObjectsReturned
from django.core.management.base import BaseCommand
from django.db import transaction
import subprocess

from radiostats.settings import LOG_DIR
from scraper import scrapers
from scraper.lib import create_date_range, utc_datetime
from scraper.models import Station, Song, Play

log = logbook.Logger()


class Command(BaseCommand):
    help = 'Scrapes radio stations for new tracks'
    option_list = BaseCommand.option_list + (
        make_option(
            "-s",
            "--station",
            dest = "station_name",
            help = "specify name of station to scrape"
        ),
    )

    def handle(self, *args, **options):
        if options['station_name']:
            station = Station.objects.filter(name=options['station_name'])[0]
            runner = GenericRunner(station)
            runner.run()
        else:
            stations = Station.objects.filter(enabled=True)
            processes = []
            for station in stations:
                processes.append(subprocess.Popen(['python', 'manage.py', 'scrape', '-s', station.name]))
            [p.wait() for p in processes]


class GenericRunner(object):
    def __init__(self, station):
        self.station = station
        self.htmlparser = HTMLParser.HTMLParser()

    def run(self):
        log_handler = logbook.FileHandler(os.path.join(LOG_DIR, 'scraper.log'), bubble=True)
        log_handler.push_thread()
        last_date = None
        for date in self.date_range:
            last_date = date
            scraper = getattr(scrapers, self.station.class_name)(date)
            log.info(u'Scraping {0} for date {1}...'.format(
                self.station.name, date.strftime('%Y-%m-%d')))
            try:
                scraper.scrape()
            except LookupError:
                if not scraper.tracks:
                    msg = u'No data found for date {0} on {1}.'
                    log.error(msg.format(date.strftime('%Y%m%d'), self.station.name))
                    continue
                else:
                    raise
            except Exception as e:
                msg = u'Uncaught exception occurred scraping {0} on {1}:\n{2}'
                msg = msg.format(
                    self.station.name, date.strftime('%Y%m%d'),
                    traceback.format_exc())
                log.error(msg)
                continue
            added_already = 0
            with transaction.atomic():
                # Add all unique tracks: we need to make a set as sometimes
                # tracks are duplicated on the website by accident
                for track in list(set(scraper.tracks)):
                    artist = self.htmlparser.unescape(track[0])[:256].strip()
                    title = self.htmlparser.unescape(track[1])[:256].strip()
                    if not (artist and title):
                        continue
                    song, _ = Song.objects.get_or_create(
                        artist=artist, title=title)
                    if scraper.utc_datetimes:
                        utc_tz = pytz.timezone('UTC')
                        utc_dt = utc_tz.localize(track[2])
                        local_tz = pytz.timezone(self.station.timezone)
                        local_time = local_tz.normalize(utc_dt.astimezone(local_tz))
                        utc_time = pytz.utc.localize(track[2])
                    else:
                        local_time = track[2]
                        utc_time = utc_datetime(track[2], self.station)
                    _, created = Play.objects.get_or_create(
                        local_time=local_time,
                        time=utc_time,
                        song=song, station=self.station)
                    if not created:
                        # We're encountering tracks we've already added.
                        # Keep trying to add tracks for this date, but
                        # don't proceed with processing further dates if
                        # all tracks for this date were already added.
                        added_already += 1
                        continue
            if (scraper.terminate_early
                    or (scraper.tracks and added_already == len(scraper.tracks))):
                break
        log.info(u'End reached for {0} at {1}. Stopping...'.format(
                 self.station.name, last_date))
        self.station.last_scraped = datetime.utcnow()
        self.station.save()
        return

    @property
    def date_range(self):
        """A list of dates to be processed"""
        try:
            latest = Play.objects.filter(
                station=self.station).order_by('-time').first().local_time.date()
        except AttributeError:
            latest = self.station.start_date
        return create_date_range(latest)
