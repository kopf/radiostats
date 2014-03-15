from datetime import datetime, timedelta
import HTMLParser
import logbook

import MySQLdb

from scrapers import SWR1BWScraper, SWR3Scraper

SCRAPERS = {
    'SWR1-BW': {
        'cls': SWR1BWScraper,
        'start_date': '20140224'
    },
    'SWR3': {
        'cls': SWR3Scraper,
        'start_date': '20130301'
    }
}

log = logbook.Logger()


def create_date_range(from_date):
    now = datetime.now()
    retval = [from_date + timedelta(days=x) for x in range(0,(now-from_date).days)]
    retval.reverse()
    return retval

class GenericRunner(object):
    def __init__(self, station_name):
        self.station_name = station_name
        self.db_conn = MySQLdb.connect(
            '192.168.92.20', 'radiostats', 'r4diostats', 'radiostats',
            use_unicode=True, charset='utf8')
        self.db = self.db_conn.cursor()
        self.htmlparser = HTMLParser.HTMLParser()

    def run(self):
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

            end_reached = False
            for track in self.scraper.tracks:
                try:
                    self.add_to_db(track)
                except Exception as e:
                    if e[0] == 1062:
                        # We're encountering tracks we've already added.
                        # Keep trying to add tracks for this date, but
                        # don't proceed with processing further dates.
                        end_reached = True
                        continue
                    else:
                        raise e
            self.db_conn.commit()
            if end_reached:
                return

    def add_to_db(self, track):
        artist = self.htmlparser.unescape(track[0])
        title = self.htmlparser.unescape(track[1])
        time_played = track[2]
        sql = u'insert into songs (time_played, station_name, artist, title) values ("{0}", "{1}", "{2}", "{3}");'
        sql = sql.format(time_played.strftime('%Y-%m-%d %H:%M:%S'),
                                 self.station_name, artist, title)
        self.db.execute(sql)

    def get_latest_date_from_db(self):
        sql = u'select time_played from songs where station_name="{0}" order by time_played desc limit 1;'
        self.db.execute(sql.format(self.station_name))
        return self.db.fetchone()

    @property
    def date_range(self):
        """A list of dates to be processed"""
        latest = self.get_latest_date_from_db()
        if not latest:
            latest = datetime.strptime(SCRAPERS[self.station_name]['start_date'], '%Y%m%d')
        return create_date_range(latest)


if __name__ == '__main__':
    for station_name in SCRAPERS:
        runner = GenericRunner(station_name)
        runner.run()