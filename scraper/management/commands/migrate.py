#!/usr/bin/env python
from datetime import timedelta
import logbook
import pytz

from django.core.management.base import BaseCommand

from scraper.models import Station, Play
from scraper.lib import utc_datetime


log = logbook.Logger()


class Command(BaseCommand):

    help = ''

    def handle(self, *args, **options):
        i = 0
        for station in Station.objects.all():
            for play in Play.objects.filter(station=station):
                play.time = utc_datetime(play.local_time, station)
                play.save()
                i += 1
                if i % 100 == 0:
                    print '{0} done'.format(i)
