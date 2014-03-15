from BeautifulSoup import BeautifulSoup
import logbook
import requests

log = logbook.Logger()


class GenericScraper(object):
    def __init__(self, date):
        self.date = date
        self.tracks = []

    def scrape(self):
        """Scrape tracks for a single date"""
        raise NotImplementedError

    def time_to_datetime(self, text_time, split_char):
        """Transform a text representation of time into a datetime"""
        text_time = text_time.split(split_char)
        hour = int(text_time[0])
        minute = int(text_time[1])
        try:
            second = int(text_time[2])
        except IndexError:
            second = 0
        return self.date.replace(hour=hour, minute=minute, second=second)


class SWR1BWScraper(GenericScraper):
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
            artist = elements[i].span.text
            try:
                title = elements[i].a.text
            except AttributeError:
                title = elements[i].text
            time_played = self.time_to_datetime(time_tag.text, '.')
            tracks.append((artist, title, time_played))
            i += 2

    def scrape(self):
        resp = requests.get(self.base_url)
        soup = BeautifulSoup(resp.text)
        date_links = soup.findAll('a', {'class': 'pgcalendarblue'})
        for url in [tag['href'] for tag in date_links]:
            if 'date={0}'.format(self.date.strftime('%Y%m%d')) in url:
                resp = requests.get(url)
                self.soup = BeautifulSoup(resp.text)
                for tracklist_url in self.tracklist_urls:
                    resp = requests.get(tracklist_url)
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
            self.tracks.append(
                (elements[0].text, elements[1].text,
                    self.time_to_datetime(elements[2].text, ':')))

    def scrape(self):
        for url in self.tracklist_urls:
            resp = requests.get(url)
            self.soup = BeautifulSoup(resp.text)
            self.extract_tracks()

