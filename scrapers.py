import HTMLParser
import time
import string
import urllib

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
            finally:
                return retval
        else:
            log.error('Exceeded number of retries getting {0}'.format(url))
            return requests.get(url)

    def _find_most_popular(self, *args):
        """Searches bing for certain strings and returns the most popular"""
        winner = (0,)
        url = ('http://www.bing.com/search?q="{term}"&go=&qs=n&form=QBLH&filt=all'
               '&pq="{term}"&sc=0-0&sp=-1&sk=')
        for artist_str in args:
            if artist_str in BING_CACHE:
                return BING_CACHE[artist_str]
            url = url.format(term=urllib.quote_plus(artist_str))
            resp = self.http_get(url, user_agent='')
            soup = BeautifulSoup(resp.text)
            tag = soup.find('span', {'id': 'count'})
            digits = [n for n in soup.find('span', {'id': 'count'}).text if n in string.digits]
            if digits > winner[0]:
                winner = (digits, artist_str)
        for artist_str in args:
            if artist_str != winner[1]:
                BING_CACHE[artist_str] = winner[1]
        return winner[1]

    def _process_artist(self, artist_str):
        """Process artist string, splitting into multiple artists, and correctly
        arranging First Name and Surname.

        Unused and broken for the time being
        """
        retval = []
        if '(feat' in artist_str.lower():
            artist_str = artist_str[:artist_str.lower().index('(feat')].strip()
        artists = artist_str.split('; ')
        for artist in artists:
            if ', ' in artist:
                try:
                    last_name, first_name = [name.strip() for name in artist.split(', ')]
                    new_name = u'{0} {1}'.format(first_name, last_name)
                    retval.append(self._find_most_popular(new_name, artist))
                except ValueError as e:
                    # probably dealing with something like "Pausini, Laura, Blunt, James"
                    if len(names) == 4:
                        names = [name.strip() for name in artist.split(', ')]
                        new_names = [names[1], names[0], names[3], names[2]]
                        retval.append(self._find_most_popular(' '.join(new_names[:2]), names[:2]))
                        retval.append(self._find_most_popular(' '.join(new_names[2:4]), names[2:4]))
                    else:
                        raise e
            else:
                retval.append(artist)
        return u'; '.join([name.strip() for name in retval])

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
        return [x['value'] for x in self.soup.find(
            'select', {'id': 'uhrzeit'}).findAll('option')]

    def extract_tracks(self):
        """Parse HTML of a tracklist page and return a list of 
        (artist, title, time played) tuples
        """
        main_div = self.soup.find('div', {'class': 'recherchelist'})
        elements = main_div.findAll(
            'p', {'class': ['sendezeitrl', 'songtitel']})
        i = 1
        for time_tag in elements[::2]:
            artist = self.htmlparser.unescape(elements[i].span.text)[:128]
            try:
                title = elements[i].a.text
            except AttributeError:
                title = elements[i].text
            title = self.htmlparser.unescape(title)[:256]
            time_played = self.time_to_datetime(time_tag.text, '.')
            self.tracks.append((artist, title, time_played))
            i += 2

    def scrape(self):
        resp = self.http_get(self.base_url)
        soup = BeautifulSoup(resp.text)
        date_links = soup.findAll('a', {'class': 'pgcalendarblue'})
        for url in [tag['href'] for tag in date_links]:
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

    def scrape(self):
        for url in self.tracklist_urls:
            resp = self.http_get(url)
            self.soup = BeautifulSoup(resp.text)
            self.extract_tracks()

