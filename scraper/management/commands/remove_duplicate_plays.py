#!/usr/bin/env python
from datetime import timedelta
import logbook

from django.core.management.base import BaseCommand

from scraper.models import Station, Play


log = logbook.Logger()


class Command(BaseCommand):
    """Sometimes, especially when one show ends and another begins, a track
    will be displayed twice on the radio station's website, even though it was
    just played once. This script removes all duplicates within 10 minutes of
    eachother, leaving just the first Play object."""

    help = 'Remove mistakenly duplicated plays of tracks'
    deleted = {}
    to_delete_ids = []

    def handle(self, *args, **options):
        for station in Station.objects.all():
            log.info(u'Scanning {0}'.format(station.name))
            self.deleted[station.name] = 0
            for play in Play.objects.filter(station=station):
                duplicates = Play.objects.filter(
                    song=play.song, station=play.station,
                    time__gt=play.time,
                    time__lte=play.time+timedelta(minutes=10))
                duplicates = duplicates.exclude(id=play.id)
                if duplicates:
                    log.info(u'Duplicate found on {0} for {1}'.format(
                        station.name, ' '.join([play.song.title, play.time.strftime('%Y-%m-%d %H:%M:%S')])))
                    for duplicate in duplicates:
                        log.info(u'Duplicate: {0}'.format(
                            ' '.join([duplicate.song.title, duplicate.time.strftime('%Y-%m-%d %H:%M:%S')])))
                        self.to_delete_ids.append(duplicate.id)
                        self.deleted[station.name] += 1
        log.info('Deleting...')
        Play.objects.filter(id__in=self.to_delete_ids).delete()
        log.info('==============')
        log.info('Report:')
        for station_name, deleted_count in self.deleted.iteritems():
            log.info('{0}: {1} deleted'.format(station_name, deleted_count))
        log.info('==============')
