#!/usr/bin/env python
import logbook
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from elasticsearch import Elasticsearch, helpers

from radiostats.settings import LOG_DIR
from scraper.models import Play

log = logbook.Logger()
FILE_LOGGER = logbook.FileHandler(
    os.path.join(LOG_DIR, 'sync.log'), bubble=True)
BULK_SIZE = 5000


class Command(BaseCommand):
    help = 'Syncs db data with elasticsearch'

    def handle(self, *args, **options):
        FILE_LOGGER.push_thread()
        self.es = Elasticsearch([settings.ELASTICSEARCH])
        total_count = Play.objects.filter(synced=False).count()
        log.info('Found {} plays to be synced...'.format(total_count))
        processed = 0
        while True:
            plays = Play.objects.filter(synced=False)[:BULK_SIZE]
            helpers.bulk(self.es, [play.as_elasticsearch_insert() for play in plays])
            for play in plays:
                play.synced = True
                play.save()
            processed += BULK_SIZE
            log.info('Done {} of {}'.format(processed, total_count))
