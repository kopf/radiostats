from datetime import datetime, timedelta
import logbook

import _mysql

from scrapers import SWR1BWScraper, SWR3Scraper


##
# NOTES
#
# * Don't forget to HTMLDecode text
# * 
# * Runner: object that runs through individual dates
# * Scraper: Scrapes hours from a date, tracks from an hour
# * Split artists by ';' ?

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
        self.db=_mysql.connect(host='192.168.92.20', user='radiostats',
                               passwd='r4diostats', db='radiostats')

    def run(self):
        for date in self.date_range:
            self.scraper = SCRAPERS[self.station_name]['cls'](date)
            log.info('Scraping {0} for date {1}...'.format(
                self.station_name, date))
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
            if end_reached:
                return

    def add_to_db(self, track):
        artist = track[0]
        title = track[1]
        time_played = track[2]
        sql = 'insert into songs (time_played, station_name, artist, title) values ("{0}", "{1}", "{2}", "{3}");'
        self.db.query(sql.format(time_played.strftime('%Y-%m-%d %H:%M:%S'),
                                 self.station_name, artist, title))
        return self.db.store_result()

    def get_latest_date_from_db(self):
        sql = 'select time_played from songs where station_name="{0}" order by time_played desc limit 1;'
        self.db.query(sql.format(self.station_name))
        r = self.db.store_result()
        return [x[0] for x in r.fetch_row(maxrows=0)]

    @property
    def date_range(self):
        """A list of dates to be processed"""
        latest = self.get_latest_date_from_db()
        if latest:
            latest = datetime.strptime(latest[0], '%Y-%m-%d %H:%M:%S')
        else:
            latest = datetime.strptime(SCRAPERS[self.station_name]['start_date'], '%Y%m%d')
        return create_date_range(latest)


if __name__ == '__main__':
    runner = GenericRunner('SWR1-BW')
    runner.run()