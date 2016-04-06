#!/usr/bin/env python
from datetime import timedelta
import logbook

from django.core.management.base import BaseCommand

from scraper.models import Song, Play


log = logbook.Logger()


RAW_SQL = '''SELECT
    id,
    artist,
    title,
    MAX(id) as max_id,
    COUNT(id) as count_id
FROM
    scraper_song
GROUP BY
    artist, title
HAVING
    count_id > 1'''


class Command(BaseCommand):
    help = 'Remove duplicated scraper_song table rows'
    deleted = {}
    to_delete_ids = []

    def handle(self, *args, **options):
        while True:
            duplicates = [song for song in Song.objects.raw(RAW_SQL)]
            if not duplicates:
                break
            log.info('{} duplicates found, removing...'.format(len(duplicates)))
            self.clean(duplicates)

    def clean(self, duplicates):
        for result in duplicates:
            original_song = Song.objects.filter(id=result.id).first()
            duplicate = Song.objects.filter(id=result.max_id).first()
            plays = Play.objects.filter(song=duplicate).all()
            for play in plays:
                play.song = original_song
                play.save()
            duplicate.delete()
