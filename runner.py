#!/usr/bin/env python
from datetime import datetime
import logbook
from urllib import quote_plus

import gevent.monkey
gevent.monkey.patch_socket()
import gevent
import MySQLdb

from lib import http_get, create_date_range
from scrapers import SWR1Scraper, SWR3Scraper, KEXPScraper
from settings import LASTFM_API_KEY

SCRAPERS = {
    'SWR1': {
        'cls': SWR1Scraper,
        'start_date': '20140213'
    },
    'SWR3': {
        'cls': SWR3Scraper,
        'start_date': '20130301'
    },
    'KEXP': {
        'cls': KEXPScraper,
        'start_date': '20010412'
    }
}

log = logbook.Logger()
FILE_LOGGER = logbook.FileHandler('runner.log', bubble=True)
FILE_LOGGER.push_application()


class GenericRunner(object):
    def __init__(self, station_name):
        self.station_name = station_name
        self.db_conn = MySQLdb.connect(
            '192.168.92.20', 'radiostats', 'r4diostats', 'radiostats',
            use_unicode=True, charset='utf8')
        self.db = self.db_conn.cursor()
        self.lastfm_cache = {}

    def normalize(self, track):
        """Using last.fm's API, normalise the artist and track title"""
        if self.lastfm_cache.get(track[0], {}).get(track[1]):
            artist, title = self.lastfm_cache[track[0]][track[1]]
            return (artist, title, track[2])
        url = (u'http://ws.audioscrobbler.com/2.0/?method=track.search'
               u'&artist={artist}&track={track}&api_key={api_key}&format=json')
        url = url.format(artist=quote_plus(track[0].encode('utf-8')),
                         track=quote_plus(track[1].encode('utf-8')),
                         api_key=LASTFM_API_KEY)
        resp = http_get(url).json()
        if resp.get('results', {}).get('trackmatches') and not isinstance(resp['results']['trackmatches'], basestring):
            result = resp['results']['trackmatches']['track']
            if isinstance(result, list):
                result = result[0]

            # update cache
            self.lastfm_cache.setdefault(track[0], {})[track[1]] = (result['artist'], result['name'])

            new_track = (result['artist'], result['name'], track[2])
            #log.info(u'Mapping: {0} to {1}'.format(track, new_track))
            track = new_track
        else:
            log.error('Invalid Last.fm response: {0}'.format(url))
        return track

    def run(self):
        with log.catch_exceptions():
            for date in self.date_range:
                self.scraper = SCRAPERS[self.station_name]['cls'](date)
                log.info('Scraping {0} for date {1}...'.format(
                    self.station_name, date.strftime('%Y-%m-%d')))
                try:
                    self.scraper.scrape()
                except LookupError:
                    msg = 'No data found for date {0} on {1}.'
                    log.error(msg.format(date.strftime('%Y%m%d'), self.station_name))
                    continue

                added_already = 0
                # Add all unique tracks: we need to make a set as sometimes
                # tracks are duplicated on the website by accident
                for track in list(set(self.scraper.tracks)):
                    track = self.normalize(track)
                    try:
                        self.add_to_db(track)
                    except Exception as e:
                        if e[0] == 1062:
                            # We're encountering tracks we've already added.
                            # Keep trying to add tracks for this date, but
                            # don't proceed with processing further dates if
                            # all tracks for this date were already added.
                            added_already += 1
                            continue
                        else:
                            raise e
                self.db_conn.commit()
                if self.scraper.tracks and added_already == len(self.scraper.tracks):
                    log.info('End reached for {0} at {1}. Stopping...'.format(
                        self.station_name, date))
                    return

    def add_to_db(self, track):
        sql = u'insert into songs (time_played, station_name, artist, title) values (%s, %s, %s, %s);'
        self.db.execute(sql, (track[2], self.station_name, track[0], track[1]))

    def get_latest_date_from_db(self):
        sql = u'select time_played from songs where station_name=%s order by time_played desc limit 1;'
        self.db.execute(sql, (self.station_name))
        try:
            row = self.db.fetchone()[0]
        except TypeError:
            row = None
        return row

    @property
    def date_range(self):
        """A list of dates to be processed"""
        #latest = self.get_latest_date_from_db()
        #if not latest:
        #    latest = datetime.strptime(SCRAPERS[self.station_name]['start_date'], '%Y%m%d')
        latest = datetime.strptime('20141125', '%Y%m%d')
        return create_date_range(latest)


if __name__ == '__main__':
    threads = []
    for station_name in SCRAPERS:
        runner = GenericRunner(station_name)
        threads.append(gevent.spawn(runner.run))
    gevent.joinall(threads)
