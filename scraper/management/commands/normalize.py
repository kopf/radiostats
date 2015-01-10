#!/usr/bin/env python
import logbook
from simplejson.decoder import JSONDecodeError
from urllib import quote_plus
import os

from django.core.exceptions import ObjectDoesNotExist
from django.db import DataError
from django.conf import settings
from django.core.management.base import BaseCommand

from radiostats.settings import LOG_DIR
from scraper.lib import http_get
from scraper.models import Song, NormalizedSong, Tag

log = logbook.Logger()
FILE_LOGGER = logbook.FileHandler(
    os.path.join(LOG_DIR, 'normalize.log'), bubble=True)


class Command(BaseCommand):
    help = 'Normalizes tracks with canonical song information from Last.fm'

    def handle(self, *args, **options):
        FILE_LOGGER.push_thread()
        i = 0
        for track in Song.objects.filter(normalized=None):
            self.normalize(track)
            i += 1
            if i % 10 == 0:
                log.info('Done {0}...'.format(i))

    def get_info(self, artist, title):
        url = (u'http://ws.audioscrobbler.com/2.0/?method=track.getinfo&autocorrect=1'
               u'&artist={artist}&track={title}&api_key={api_key}&format=json')
        url = url.format(artist=quote_plus(artist.encode('utf-8')),
                         title=quote_plus(title.encode('utf-8')),
                         api_key=settings.LASTFM_API_KEY)
        try:
            resp = http_get(url).json()
        except JSONDecodeError:
            try:
                resp = http_get(url).json()
            except JSONDecodeError as e:
                log.error('Error occurred twice trying to parse response from {0}'.format(url))
                return None
        if isinstance(resp, dict) and not 'error' in resp and 'track' in resp:
            return resp['track']
        else:
            log.error('Invalid Last.fm response: {0}'.format(url))
            return None

    def normalize(self, track):
        """Using last.fm's API, normalise the artist and track title"""
        track_info = self.get_info(track.artist, track.title)
        if not track_info:
            return
        artist = track_info['artist']['name']
        title = track_info['name']
        mbid = track_info['mbid']
        toptags = track_info.get('toptags', [])
        if isinstance(toptags, dict):
            if isinstance(toptags.get('tag', []), dict):
                # only one tag
                toptags = [toptags['tag']['name']]
            else:
                toptags = [tag['name'] for tag in toptags.get('tag', [])]
        try:
            normalized = NormalizedSong.objects.get(
                mbid=mbid, artist=artist, title=title)
        except ObjectDoesNotExist:
            tag_objects = []
            for text_tag in toptags:
                try:
                    tag, _ = Tag.objects.get_or_create(name=text_tag)
                except DataError:
                    # Tag longer than 32 chars, probs bullshit
                    log.error(u'Failed creating tag: {0}'.format(text_tag))
                    continue
                tag_objects.append(tag)
            normalized, _= NormalizedSong.objects.get_or_create(
                mbid=mbid,
                artist=artist[:256],
                title=title[:256])
            normalized.tags.add(*tag_objects)
            normalized.save()
        track.normalized = normalized
        track.save()
