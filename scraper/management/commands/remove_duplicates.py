#!/usr/bin/env python
from datetime import datetime, timedelta
import logbook
import HTMLParser

from django.core.management.base import BaseCommand

from scraper.lib import create_date_range
from scraper.models import Station, Song, Play
from scraper.scrapers import SCRAPERS


log = logbook.Logger()


class Command(BaseCommand):
    help = 'Remove mistakenly duplicated plays of tracks'

    def handle(self, *args, **options):
        for station in Station.objects.all():
            log.info(u'Scanning {0}'.format(station.name))
            for play in Play.objects.filter(station=station):
                duplicates = Play.objects.filter(
                    song=play.song, station=play.station,
                    time__gte=play.time-timedelta(minutes=10),
                    time__lte=play.time+timedelta(minutes=10))
                duplicates = duplicates.exclude(id=play.id)
                if duplicates:
                    log.info(u'Duplicate found on {0} for {1}'.format(
                        station.name, ' '.join([play.song.name, play.time])))
                    for duplicate in duplicates:
                        log.info(u'Duplicate: {0}'.format(
                            ' '.join([duplicate.song.name, duplicate.time])))
