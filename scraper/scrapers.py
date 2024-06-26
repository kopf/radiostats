import calendar
from datetime import datetime
import json
import time

from BeautifulSoup import BeautifulSoup
from dateutil import parser as dateutil_parser
from django.conf import settings
import logbook
import requests

from scraper.lib import http_get, http_post


class ScraperBase(object):
    def __init__(self, date):
        self.date = date
        self.tracks = []
        self.log = logbook.Logger(type(self).__name__)


class GenericScraper(ScraperBase):
    cookies = {}
    terminate_early = False
    utc_datetimes = False

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


class GenericLastFMScraper(ScraperBase):
    terminate_early = False
    base_url = ('http://ws.audioscrobbler.com/2.0/?method=user.getrecenttracks'
                '&user={user}&api_key={api_key}&from={start}&to={end}&format=json&limit=200')
    utc_datetimes = True

    def __init__(self, date):
        super(GenericLastFMScraper, self).__init__(date)
        self.start = datetime.combine(date, datetime.min.time())
        self.end = datetime.combine(date, datetime.max.time())

    def _get_tracks(self, url, page):
        try:
            time.sleep(1)
            return requests.get(url + '&page=%s' % page).json()['recenttracks']['track']
        except LookupError:
            self.log.error('Error getting tracks, retrying...')
            time.sleep(5)
            return self._get_tracks(url, page)

    def scrape(self):
        url = self.base_url.format(
            user=self.username, api_key=settings.LASTFM_API_KEY,
            start=calendar.timegm(self.start.timetuple()),
            end=calendar.timegm(self.end.timetuple()))

        # Last.fm will respond with the first tracks played by an account
        # when we request pages that are out of bounds.
        # So, keep track of what was the first track on the last page,
        # and compare it with the first track on the current page. If identical,
        # break.
        first_track = {}
        for page in range(1, 99999):
            self.log.info('Scraping page %s...' % page)
            tracks = self._get_tracks(url, page)
            if not tracks:
                break
            if isinstance(tracks, dict):
                tracks = [tracks]
            if tracks[0] == first_track:
                break
            first_track = tracks[0]
            for track in tracks:
                if 'date' not in track:
                    # currently playing
                    continue
                artist = track['artist']['#text']
                title = track['name']
                utc_time = datetime.utcfromtimestamp(int(track['date']['uts']))
                self.tracks.append((artist, title, utc_time))


class SWR1Scraper(GenericScraper):
    base_url = ('https://www.swr.de/swr1/bw/playlist/index.html'
                '?swx_time={hour:02}%3A00&swx_date={date}')

    @property
    def tracklist_urls(self):
        return [self.base_url.format(hour=i, date=self.date.strftime('%Y-%m-%d')) for i in range(24)]

    def extract_tracks(self):
        """Parse HTML of a tracklist page and return a list of
        (artist, title, time played) tuples
        """
        tracks = self.soup.findAll('div', {'class': 'list-playlist-item'})
        if not tracks:
            self.log.error('No tracks found for date {0}'.format(
                self.date.strftime('%Y-%m-%d %H:00')))
        for el in tracks:
            time_played = dateutil_parser.parse(el.find('time')['datetime'])
            container = el.find('dl')
            title = container.findAll('dd', {'class': 'playlist-item-song'})[0].text
            artist = container.findAll('dd', {'class': 'playlist-item-artist'})[0].text
            self.tracks.append((artist, title, time_played))
        return len(tracks) > 0


class SWR3Scraper(GenericScraper):

    def scrape(self):
        """General scrape workflow. Can be overridden if necessary."""
        for hour in range(24):
            form_data = {'time':'{0:02d}:00'.format(hour), 'date': self.date.strftime('%Y-%m-%d')}
            resp = http_post('https://www.swr3.de/playlisten/index.html', data=form_data)
            self.soup = BeautifulSoup(resp.text)
            result = self.extract_tracks()
            if not result:
                self.log.warn('No tracks found in url {0}'.format(url))

    def extract_tracks(self):
        """Parse HTML of a tracklist page and return a list of
        (artist, title, time played) tuples
        """
        for track in self.soup.findAll('div', {'class': 'list-playlist-item'}):
            try:
                title = track.findAll('dd')[0].text
                artist = track.findAll('dd')[1].text
            except AttributeError:
                continue
            dt = datetime.strptime(
                track.find('time')['datetime'], '%Y-%m-%dT%H:%M')
            self.tracks.append((artist, title, dt))
        return True


class KEXPScraper(ScraperBase):
    cookies = {}
    terminate_early = False
    utc_datetimes = False # The responses make it look like UTC time, but it's actually local

    def __init__(self, date):
        super(KEXPScraper, self).__init__(date)
        self.url = 'https://legacy-api.kexp.org/play/?end_time={date}T23:59:59Z&limit=1000'.format(
            date=self.date.strftime('%Y-%m-%d')
        )

    def scrape(self):
        r = requests.get(self.url)
        data = r.json()
        extracted = []

        for result in data.get('results', []):
            if (result['playtype']['name'] == 'Media play' and
                    result['track'] and result['artist']):
                artist = result['artist']['name']
                title = result['track']['name']
                dt = datetime.fromtimestamp(result['epoch_airdate']/1000)
                extracted.append((artist, title, dt))
        if not extracted:
            self.log.warn('No tracks found in url {0}'.format(self.url))
        self.tracks.extend(extracted)


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
                self.log.error(u'Failed to extract track from: {0}'.format(row))
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


class ByteFMScraper(GenericLastFMScraper):
    username = 'ByteFM'


class BBC1XtraScraper(GenericLastFMScraper):
    username = 'bbc1xtra'


class BBC6MusicScraper(GenericLastFMScraper):
    username = 'bbc6music'


class BBCRadio1Scraper(GenericLastFMScraper):
    username = 'bbcradio1'


class BBCRadio2Scraper(GenericLastFMScraper):
    username = 'bbcradio2'


class BBCRadio3Scraper(GenericLastFMScraper):
    username = 'bbcradio3'


class Beats1Scraper(GenericLastFMScraper):
    username = 'beats1radio'


class RadioNovaScraper(GenericLastFMScraper):
    username = 'RadioNovaFR'


class Spin1038Scraper(GenericLastFMScraper):
    username = 'spin1038'


class XFMUKScraper(GenericLastFMScraper):
    username = 'XFMUK'


class Antenne1Scraper(GenericScraper):
    base_url = ('http://www.antenne1.de/musik/on-air/playlist-was-lief-gerade/'
                'ajax-skript.html?playstunde={hour}&playdatum={date}')

    @property
    def tracklist_urls(self):
        return [self.base_url.format(hour=hour, date=self.date.strftime('%d.%m.%Y')) for hour in range(24)]

    def scrape(self):
        for url in self.tracklist_urls:
            resp = requests.get(url)
            html = resp.text.replace('\\/', '/').replace('\\"', '"').strip('"')
            self.soup = BeautifulSoup(html)
            self.extract_tracks()

    def extract_tracks(self):
        track_divs = self.soup.findAll('div', {'class': 'track'})
        if not track_divs:
            return False
        for track in track_divs:
            dt = self.time_to_datetime(
                track.find('p', {'class': 'playtime'}).text.replace('Uhr', '').strip(),
                ':')
            artist = track.find('p', {'class': 'artist'}).text
            title = track.find('p', {'class': 'title'}).text
            track = (artist, title, dt)
            self.tracks.append(track)
        return True


class SunshineLiveScraper(GenericScraper):
    base_url = ('http://www.sunshine-live.de/playlist?filterTime={date}%20{time}'
                '&filterStream=studio&format=html'
                '&zcmlimitstart={start_from}&ax=ok')
    page_size = 25

    def scrape(self):
        page = 0
        date_string = self.date.strftime('%d.%m.%Y')
        while True:
            tracks_found = False
            url = self.base_url.format(date=date_string, time='00:00', start_from=page * self.page_size)
            resp = http_get(url)
            soup = BeautifulSoup(resp.text)
            for entry in soup.findAll('article'):
                if not entry.find('div', {'class': 'date'}).text == date_string:
                    # next day reached, but list is not necessarily ordered - see 30.07.2016 for example
                    continue
                tracks_found = True
                title = entry.find('h4').text.replace('Titel:', '')
                artist = entry.find('h5').text.replace('Artist:', '')
                time = entry.find('div', {'class': 'time'}).text.replace('UHR', '').strip()
                date_time = datetime.strptime('{} {}'.format(date_string, time), '%d.%m.%Y %H:%M')

                # filter dummy entries from lazy moderators/technical studio issues
                if artist.lower() == 'sunshine live' and title.lower() == 'electronic music radio':
                    continue
                else:
                    self.tracks.append((artist, title, date_time))

            if not tracks_found:
                self.log.info('No more tracks for {} on page {}'.format(date_string, page))
                break
            page += 1
        if not self.tracks:
            self.log.error('No tracks found for {}'.format(date_string))
        else:
            self.log.info('Collected {} tracks for {}'.format(len(self.tracks), date_string))
