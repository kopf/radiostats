#!/usr/bin/env python
from datetime import datetime
import logbook
from simplejson.decoder import JSONDecodeError
from urllib import quote_plus
import os

from beets.autotag.match import tag_item
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


class FakeBeetsItem(object):
    mb_trackid = None
    length = 0
    def __init__(self, artist, title):
        self.artist = artist
        self.title = title


class Command(BaseCommand):
    help = 'Normalizes tracks with canonical song information from Last.fm'
    base_url = (
        u'http://ws.audioscrobbler.com/2.0/?method={method}&autocorrect=1'
        u'&artist={artist}&track={title}&api_key={api_key}&format=json')

    def handle(self, *args, **options):
        FILE_LOGGER.push_thread()
        i = 0
        tracks = Song.objects.filter(last_scraped=None)
        for track in tracks:
            self.normalize(track)
            track.last_scraped = datetime.utcnow()
            track.save()
            i += 1
            if i % 10 == 0:
                log.info('Done {0} of {1}...'.format(i, len(tracks)))

    def _get(self, url):
        """HTTP GET and decode JSON"""
        try:
            resp = http_get(url).json()
        except JSONDecodeError:
            try:
                resp = http_get(url).json()
            except JSONDecodeError:
                log.error('Error occurred twice trying to parse response from {0}'.format(url))
                return None
        return resp

    def getinfo(self, encoded_artist, encoded_title):
        """Get metadata from last.fm using the track.getinfo method"""
        url = self.base_url.format(
            artist=encoded_artist, title=encoded_title,
            api_key=settings.LASTFM_API_KEY, method='track.getinfo')
        resp = self._get(url)
        if not resp:
            return None
        if isinstance(resp, dict):
            if 'error' in resp or ('track' in resp and not resp['track'].get('mbid')):
                # Found an incomplete listing, better to use track.search
                return None
            else:
                return resp['track']
        else:
            log.error('Invalid Last.fm response: {0}'.format(url))
            return None

    def tracksearch(self, encoded_artist, encoded_title):
        """Get metadata from last.fm using the track.search method"""
        url = self.base_url.format(
            artist=encoded_artist, title=encoded_title,
            api_key=settings.LASTFM_API_KEY, method='track.search')
        try:
            resp = http_get(url).json()
        except JSONDecodeError:
            try:
                resp = http_get(url).json()
            except JSONDecodeError as e:
                log.error('Error occurred twice trying to parse response from {0}'.format(url))
                return None
        if isinstance(resp, dict):
            if (resp.get('results', {}).get('trackmatches')
                    and not isinstance(resp['results']['trackmatches'], basestring)):
                result = resp['results']['trackmatches']['track']
                if isinstance(result, list) and result:
                    result = result[0]
            else:
                # Track not found by last.fm
                result = None
        else:
            log.error('Invalid Last.fm response: {0}'.format(url))
            result = None
        return result

    def get_tags(self, mbid):
        """Get tags from last.fm by using mbid of track we found using track.search"""
        url = (u'http://ws.audioscrobbler.com/2.0/?method=track.getInfo'
               u'&mbid={mbid}&api_key={api_key}&format=json')
        url = url.format(mbid=mbid, api_key=settings.LASTFM_API_KEY)
        resp = http_get(url).json()
        if isinstance(resp, dict):
            return resp.get('track', {}).get('toptags')
        return []

    def extract_tags(self, toptags):
        """Extract tags from a 'toptags' value from a last.fm response"""
        if isinstance(toptags, dict):
            if isinstance(toptags.get('tag'), dict):
                return [toptags['tag']['name']]
            else:
                return [tag['name'] for tag in toptags.get('tag', [])]
        return []

    def query_musicbrainz(self, mbid, artist, title):
        """Query musicbrainz, resolving the recording to the root 'work' MBID"""
        url = ('http://musicbrainz.org/ws/2/recording/{0}'
               '?inc=artist-credits+work-rels&fmt=json')
        resp = self._get(url.format(mbid))
        if resp.get('relations'):
            relation = resp['relations'][0]
            if 'cover' not in relation['attributes']:
                mbid = relation['work']['id']
                artist = resp['artist-credit'][0]['name']
                title = relation['work']['title']
        return mbid, artist, title

    def query_lastfm(self, artist, title):
        """Use track.getinfo to get track metadata. If it fails, fall back on
        track.search"""
        encoded_artist = quote_plus(artist.encode('utf-8'))
        encoded_title = quote_plus(title.encode('utf-8'))
        track_info = self.getinfo(encoded_artist, encoded_title)
        if not track_info:
            track_info = self.tracksearch(encoded_artist, encoded_title)
            if not track_info:
                return None
            fixed_artist = track_info['artist'][:256]
            fixed_title = track_info['name'][:256]
            mbid = track_info['mbid']
            toptags = self.get_tags(mbid)
        else:
            fixed_artist = track_info['artist']['name'][:256]
            fixed_title = track_info['name'][:256]
            mbid = track_info['mbid']
            toptags = track_info.get('toptags', [])
        if not mbid:
            if ';' in artist:
                # Try slicing into multiple artists and retry using the first one listed
                return self.query_lastfm(artist.split(';')[0], title)

            # Cannot continue without an MBID.
            return None
        mbid, fixed_artist, fixed_title = self.query_musicbrainz(
            mbid, fixed_artist, fixed_title)
        tags = self.extract_tags(toptags)
        return {'artist': fixed_artist, 'title': fixed_title, 'mbid': mbid,
                'tags': tags}

    def normalize(self, track):
        """Using beets and last.fm's API, normalise the artist and track title"""
        artist = unicode(track.artist)
        title = unicode(track.title)
        res = tag_item(FakeBeetsItem(artist, title),
                       search_artist=artist, search_title=title)
        if res and res[0] and res[0][0].distance.distance < 0.35:
            # 75% confidence
            track_info = {'artist': res[0][0].info.artist,
                          'title': res[0][0].info.title,
                          'mbid': res[0][0].info.track_id}
            track_info['tags'] = self.get_tags(track_info['mbid'])
        else:
            track_info = self.query_lastfm(track.artist, track.title)
        if not track_info:
            return
        try:
            normalized = NormalizedSong.objects.get(mbid=track_info['mbid'])
        except ObjectDoesNotExist:
            tag_objects = []
            for text_tag in track_info['tags']:
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
                title=track_info['title'])
            normalized.tags.add(*tag_objects)
            normalized.save()
        track.normalized = normalized
        track.save()
