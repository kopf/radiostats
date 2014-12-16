#!/usr/bin/env python
import logbook
from simplejson.decoder import JSONDecodeError
from urllib import quote_plus

from django.core.exceptions import ObjectDoesNotExist
from django.db import DataError
from django.conf import settings
from django.core.management.base import BaseCommand

from scraper.lib import http_get
from scraper.models import Song, NormalizedSong, Tag

log = logbook.Logger()
FILE_LOGGER = logbook.FileHandler('runner.log', bubble=True)
FILE_LOGGER.push_application()


class Command(BaseCommand):
    help = 'Normalizes tracks with canonical song information from Last.fm'

    def handle(self, *args, **options):
        i = 0
        for track in Song.objects.filter(normalized=None):
            self.normalize(track)
            i += 1
            if i % 10 == 0:
                log.info('Done {0}...'.format(i))

    def search_track(self, artist, title):
        url = (u'http://ws.audioscrobbler.com/2.0/?method=track.search'
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
                raise e
        if isinstance(resp, dict):
            if (resp.get('results', {}).get('trackmatches')
                    and not isinstance(resp['results']['trackmatches'], basestring)):
                result = resp['results']['trackmatches']['track']
                if isinstance(result, list):
                    result = result[0]
            else:
                # Track not found by last.fm
                result = None
        else:
            log.error('Invalid Last.fm response: {0}'.format(url))
            result = None
        return result

    def get_tags(self, mbid, artist, title):
        if mbid:
            url = (u'http://ws.audioscrobbler.com/2.0/?method=track.getInfo'
                   u'&mbid={mbid}&api_key={api_key}&format=json')
            url = url.format(mbid=mbid, api_key=settings.LASTFM_API_KEY)
        else:
            url = (u'http://ws.audioscrobbler.com/2.0/?method=track.getInfo'
                   u'&artist={artist}&title={title}&api_key={api_key}&format=json')
            url = url.format(
                artist=quote_plus(artist.encode('utf-8')),
                title=quote_plus(title.encode('utf-8')),
                api_key=settings.LASTFM_API_KEY)
        resp = http_get(url).json()
        if isinstance(resp, dict):
            toptags = resp.get('track', {}).get('toptags')
            if isinstance(toptags, dict):
                if isinstance(toptags.get('tag', []), dict):
                    return [toptags['tag']['name']]
                else:
                    return [tag['name'] for tag in toptags.get('tag', [])]
        return []

    def normalize(self, track):
        """Using last.fm's API, normalise the artist and track title"""
        track_info = self.search_track(track.artist, track.title)
        if not track_info:
            return
        try:
            normalized = NormalizedSong.objects.get(
                artist=track_info['artist'], title=track_info['name'])
        except ObjectDoesNotExist:
            tags = self.get_tags(
                track_info['mbid'].strip(), track_info['artist'],
                track_info['name'])
            tag_objects = []
            for text_tag in tags:
                try:
                    tag, _ = Tag.objects.get_or_create(name=text_tag)
                except DataError:
                    # Tag longer than 32 chars, probs bullshit
                    log.error(u'Failed creating tag: {0}'.format(text_tag))
                    continue
                tag_objects.append(tag)
            normalized, _= NormalizedSong.objects.get_or_create(
                mbid=track_info['mbid'],
                artist=track_info['artist'],
                title=track_info['name'])
            for tag in tag_objects:
                normalized.tags.add(tag)
            normalized.save()
        track.normalized = normalized
        track.save()
