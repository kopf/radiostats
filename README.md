# Radiostats

## Overview

Radiostats is a platform for the analysis of music played on radio stations.
It is in the preliminary phases, with most work focused on amassing a large
amount of data from as many sources as possible. This will be followed by
the development of a flexible web application which enables users to perform
their own analyses on the collected data.

# Contributing

Are you interested in the project? Would you like to be able to analyse data from
your local radio stations on radiostats.org? All help is greatly appreciated.
Simply fork the repository, read the following sections, and submit a pull request.

## Code a scraper

If you want to help, the best way would be to contribute a scraper for a radio
station website.

Scrapers can be viewed as plugins defined by individual classes. In order to
code a scraper, you'll need to make modifications to the
[scrapers.py](https://github.com/kopf/radiostats/blob/master/scraper/scrapers.py)
file, namely:

* Creating a scraper class that scrapes data from the new radio station's website.
* Adding an entry to the module-level `SCRAPERS` dict for this new scraper.

Each scraper class must have the following attributes:

* `date`: A `datetime.datetime` object representing the date being scraped. One
scraper instance will be created per date by the `scrape` django-admin job.
* `tracks`: A list of tuples, each of the form: `("artist name", "track title", <datetime object of time track was played>)`
* `scrape()`: The function called from the `scrape` job which populates the `tracks` list.

It's a good idea to have a quick read of `scrapers.py` to see examples of
how other scrapers work. In order to simplify the task of creating a scraper,
a `GenericScraper` class is provided. This class provides a typical `scrape()`
function which is sufficient for many cases. It behaves as follows:

* Iterates over `self.tracklist_urls` - a list of URLs, each containing a playlist
to be parsed and stored. This is necessary as many radio stations separate
tracklists on an hour-by-hour basis, meaning that there are 24 URLs to be scraped for one day. If the radio station in question puts all tracks for the entire day on one webpage, this can simply be a list containing one string (see, for example, the `FluxFMScraper`).
* For each URL, GET the HTML content and store its BeautifulSoup representation in `self.soup`.
* Call `self.extract_tracks()`, a function that will find all tracks in `self.soup` and append them to `self.tracks`

Occasionally, it is necessary to override the `scrape` function (see the `SWR1Scraper`),
but for the most part it should be necessary to just create a class that inherits from `GenericScraper`
and defines `self.name`, `self.tracklist_urls` and `self.extract_tracks`.

Scrapers do **not** need to take care of the following:

* Decoding HTML entities
* Timezone conversion
* Determining a canonical artist name and song title for entries (the [normalize job](https://github.com/kopf/radiostats/blob/master/scraper/management/commands/normalize.py) takes care of this, querying Last.fm for metadata, so that the application doesn't record "Beatles, The - Taxman" and "The Beatles - Taxman" as two different songs by different artists)
* Deduplication of mistakenly duplicated tracks on radio websites (the [remove_duplicates job](https://github.com/kopf/radiostats/blob/master/scraper/management/commands/remove_duplicates.py) takes care of this)
* Retrying GET requests (as long as the `http_get` helper is used)

Once the scraper is written, an entry needs to be added to the `SCRAPERS` dict in the following form:

````
{
    "station_name": {
        "cls": MyStationScraper, # class that should be used
        "start_date": "20010101", # the earliest date for which playlists are available (YYYYMMDD)
        "country": "DE", # Two-letter ISO Country code
        "timezone": "Europe/Berlin" # Timezone of scraped play times. This should be an entry in pytz.all_timezones
    }
}
````
