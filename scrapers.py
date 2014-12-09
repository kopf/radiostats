import HTMLParser
import time

from BeautifulSoup import BeautifulSoup
import logbook
import requests

log = logbook.Logger()

USER_AGENT = ('Mozilla/5.0 (Windows NT 6.2; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/32.0.1667.0 Safari/537.36')

BING_CACHE = {}


class GenericScraper(object):
    def __init__(self, date):
        self.date = date
        self.tracks = []
        self.htmlparser = HTMLParser.HTMLParser()

    def scrape(self):
        """Scrape tracks for a single date"""
        raise NotImplementedError

    def http_get(self, url, retries=10, user_agent=USER_AGENT):
        """Wrapper for requests.get for retries"""
        if retries:
            try:
                retval = requests.get(url, headers={'User-Agent': user_agent})
            except Exception as e:
                time.sleep(1)
                return self.http_get(url, retries=retries-1)
            else:
                return retval
        else:
            log.error('Exceeded number of retries getting {0}'.format(url))
            return requests.get(url)

    def time_to_datetime(self, text_time, split_char):
        """Transform a text time into a datetime using appropriate date"""
        text_time = text_time.split(split_char)
        hour = int(text_time[0])
        minute = int(text_time[1])
        try:
            second = int(text_time[2])
        except IndexError:
            second = 0
        return self.date.replace(hour=hour, minute=minute, second=second)


class SWR1Scraper(GenericScraper):
    base_url = ('http://www.swr.de/swr1/bw/musik/musikrecherche/-/id=446260'
                '/8biejp/index.html')

    @property
    def tracklist_urls(self):
        tags = self.soup.find('ul', {'class': 'progTimeList'}).findAll('a')
        return [a['href'] for a in tags]

    def extract_tracks(self):
        """Parse HTML of a tracklist page and return a list of
        (artist, title, time played) tuples
        """
        main_div = self.soup.find('ul', {'class': 'musicList'})
        elements = main_div.findAll('li')
        for el in elements:
            time_played = el.find('div', {'class': 'musicItemTime'}).p.text
            time_played = self.time_to_datetime(time_played, '.')
            artist = self.htmlparser.unescape(el.find('div', {'class': 'musicItemText'}).p.text)[:128]
            title = self.htmlparser.unescape(el.find('div', {'class': 'musicItemText'}).a.text)[:256]
            self.tracks.append((artist, title, time_played))

    def scrape(self):
        resp = self.http_get(self.base_url)
        soup = BeautifulSoup(resp.text)
        date_links = [a['href'] for a in soup.find('ul', {'class': 'progDays'}).findAll('a')]
        for url in date_links:
            if 'date={0}'.format(self.date.strftime('%Y%m%d')) in url:
                resp = self.http_get(url)
                self.soup = BeautifulSoup(resp.text)
                for tracklist_url in self.tracklist_urls:
                    resp = self.http_get(tracklist_url)
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
                artist = self.htmlparser.unescape(elements[0].text)[:128]
                title = self.htmlparser.unescape(elements[1].text)[:256]
                self.tracks.append(
                    (artist, title, self.time_to_datetime(elements[2].text, ':')))
            except ValueError:
                log.error('Error occurred on {0} - skipping...'.format(elements))
        return True

    def scrape(self):
        for url in self.tracklist_urls:
            resp = self.http_get(url)
            self.soup = BeautifulSoup(resp.text)
            result = self.extract_tracks()
            if not result:
                log.info('No tracks found in url {0}'.format(url))

