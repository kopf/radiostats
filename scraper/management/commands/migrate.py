#!/usr/bin/env python
from datetime import timedelta
import logbook
import pytz

from django.core.management.base import BaseCommand

from scraper.models import Station, Play


log = logbook.Logger()


class Command(BaseCommand):

    help = ''

    def handle(self, *args, **options):
        i = 0
        for station in Station.objects.all():
            for play in Play.objects.filter(station=station):
                play.time = play.local_time.astimezone(pytz.timezone(station.timezone)).astimezone(pytz.utc)
                play.save()
                i += 1
                if i % 100 == 0:
                    print '{0} done'.format(i)
