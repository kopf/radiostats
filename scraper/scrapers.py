from datetime import datetime

from BeautifulSoup import BeautifulSoup
from dateutil import parser as dateutil_parser
import logbook

from scraper.lib import http_get


class GenericScraper(object):
    cookies = {}

    def __init__(self, date):
        self.date = date
        self.tracks = []
        self.log = logbook.Logger()

    def time_to_datetime(self, text_time, split_char):
        """Transform a text time into a datetime using appropriate date"""
        text_time = text_time.split(split_char)
        hour = int(text_time[0])
        minute = int(text_time[1])
        try:
            second = int(text_time[2])
        except IndexError:
            second = 0
        return datetime(self.date.year, self.date.month,self.date.day,
                        hour, minute, second)

    def scrape(self):
        """General scrape workflow. Can be overridden if necessary."""
        for url in self.tracklist_urls:
            resp = http_get(url, cookies=self.cookies)
            self.soup = BeautifulSoup(resp.text)
            result = self.extract_tracks()
            if not result:
                self.log.warn('No tracks found in url {0}'.format(url))


class SWR1Scraper(GenericScraper):
    base_url = ('http://www.swr.de/swr1/bw/musik/musikrecherche/-/id=446260'
                '/8biejp/index.html')

    @property
    def tracklist_urls(self):
        timelist = self.soup.find('ul', {'class': 'progTimeList pulldownlist'})
        return [a['href'] for a in timelist.findAll('a')]

    def extract_tracks(self):
        """Parse HTML of a tracklist page and return a list of
        (artist, title, time played) tuples
        """
        main_div = self.soup.find('ul', {'class': 'musicList'})
        if not main_div:
            self.log.error('No tracks found on SWR1 for date {0}'.format(
                self.date.strftime('%Y-%m-%d %H:00')))
            return
        elements = main_div.findAll('li')
        for el in elements:
            time_played = el.find('div', {'class': 'musicItemTime'}).p.text
            time_played = self.time_to_datetime(time_played, '.')
            artist = el.find('div', {'class': 'musicItemText'}).p.text
            title = el.find('div', {'class': 'musicItemText'}).h3.text
            # They fuck up on SWR1 occasionally, placing the artist
            # at the end of the title too:
            if title.endswith(artist):
                title = title.split(artist)[0]
            self.tracks.append((artist, title, time_played))

    def scrape(self):
        resp = http_get(self.base_url)
        soup = BeautifulSoup(resp.text)
        date_links = []
        for cell in soup.findAll('span', {'class': 'progDayCell'}):
            date_links.extend([a['href'] for a in cell.findAll('a')])
        for url in date_links:
            if 'date={0}'.format(self.date.strftime('%Y%m%d')) in url:
                resp = http_get(url)
                self.soup = BeautifulSoup(resp.text)
                for tracklist_url in self.tracklist_urls:
                    resp = http_get(tracklist_url)
                    self.soup = BeautifulSoup(resp.text)
                    self.extract_tracks()
                return
        raise LookupError


class SWR3Scraper(GenericScraper):
    base_url = ('http://www.swr3.de/musik/playlisten/Musikrecherche-Playlist-Was-lief'
                '-wann-auf-SWR3/-/id=47424/cf=42/did=65794/93avs/index.html'
                '?hour={hour}&date={date}')

    @property
    def tracklist_urls(self):
        return [self.base_url.format(hour=i, date=self.date.strftime('%Y%m%d')) for i in range(24)]

    def extract_tracks(self):
        """Parse HTML of a tracklist page and return a list of
        (artist, title, time played) tuples
        """
        table = self.soup.find('table', {'class': 'richtext'})
        if not table:
            return False
        for row in table.findAll('tr'):
            elements = row.findAll('td')
            if not elements:
                continue
            try:
                artist = elements[0].text
                title = elements[1].text
                self.tracks.append(
                    (artist, title, self.time_to_datetime(elements[2].text, ':')))
            except ValueError:
                self.log.error(
                    'Error occurred on {0} - skipping...'.format(elements))
        return True


class KEXPScraper(GenericScraper):
    base_url = 'http://www.kexp.org/playlist/{year}/{month}/{date}/{hour}'
    cookies = {'newhome2014_splash': '1'}

    @property
    def tracklist_urls(self):
        retval = []
        for cycle in ['am', 'pm']:
            for hour in [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
                retval.append(
                    self.base_url.format(
                        year=self.date.year, month=self.date.month,
                        date=self.date.day, hour='{0}{1}'.format(hour, cycle)
                    )
                )
        return retval

    def extract_tracks(self):
        """Parse HTML of a tracklist page and return a list of
        (artist, title, time played) tuples
        """
        rows = self.soup.findAll('div', {'class': 'Table'})
        if not rows:
            return False
        for row in rows:
            try:
                artist = row.find('div', {'class': 'ArtistName'}).text
                title = row.find('div', {'class': 'TrackName'}).text
                time = row.find('div', {'class': 'AirDate'}).span.text
                time = dateutil_parser.parse(time)
                dt = datetime(self.date.year, self.date.month,self.date.day,
                              time.hour, time.minute, 0)
                track = (artist, title, dt)
                self.tracks.append(track)
            except AttributeError:
                # "Air break"
                pass
        return True


class FluxFMScraper(GenericScraper):
    base_url = 'http://www.fluxfm.de/fluxfm-playlist/?date={0}'

    @property
    def tracklist_urls(self):
        return [self.base_url.format(self.date.strftime('%Y-%m-%d'))]

    def extract_tracks(self):
        """Parse HTML of a tracklist page and return a list of
        (artist, title, time played) tuples
        """
        table = self.soup.find('table', {'id': 'songs'})
        if not table:
            return False
        for row in table.findAll('tr'):
            try:
                time = row.find('td', {'class': 'time'}).div.text
                artist = row.find('span', {'class': 'artist'}).text
                title = row.find('span', {'class': 'song'}).text.strip('- ')
            except AttributeError:
                self.log.error(u'Failed to extract track from FluxFM: {0}'.format(row))
                continue
            time = self.time_to_datetime(time, ':')
            dt = datetime(self.date.year, self.date.month,self.date.day,
                          time.hour, time.minute, 0)
            track = (artist, title, dt)
            self.tracks.append(track)
        return True


class FluxFMBerlinScraper(FluxFMScraper):
    cookies = {'mfmloc': 'berlin'}


class FluxFMBremenScraper(FluxFMScraper):
    cookies = {'mfmloc': 'bremen'}


class FluxFMWorldwideScraper(FluxFMScraper):
    cookies = {'mfmloc': 'world'}


class ByteFMScraper(object):
    """Dummy Scraper class for ByteFM"""
    tracks = []

    def __init__(self, *args, **kwargs):
        pass

    def scrape(self):
        return
