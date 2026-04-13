from django.db import models
from django_countries.fields import CountryField


class Tag(models.Model):
    name = models.CharField(max_length=32, unique=True)

    def __str__(self):
        return self.name


class Station(models.Model):
    name = models.CharField(max_length=32)
    country = CountryField()
    timezone = models.CharField(max_length=64)
    class_name = models.CharField(max_length=32)
    start_date = models.DateField()
    last_scraped = models.DateTimeField(null=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class NormalizedSong(models.Model):
    mbid = models.CharField(max_length=36)
    artist = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    tags = models.ManyToManyField(Tag)

    class Meta:
        unique_together = (("mbid", "artist", "title"),)

    def __str__(self):
        return f'{self.artist} - {self.title}'


class Song(models.Model):
    artist = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    normalized = models.ForeignKey(NormalizedSong, null=True, on_delete=models.SET_NULL)
    last_scraped = models.DateTimeField(null=True)

    class Meta:
        unique_together = (("artist", "title"),)

    def __str__(self):
        return f'{self.artist} - {self.title}'


class Play(models.Model):
    local_time = models.DateTimeField()
    time = models.DateTimeField()
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    station = models.ForeignKey(Station, on_delete=models.CASCADE)
    synced = models.BooleanField(default=False)

    def as_document(self):
        doc = {
            'local_time': self.local_time.strftime('%Y-%m-%d %H:%M:%S'),
            'utc_time': self.time.strftime('%Y-%m-%d %H:%M:%S'),
            'station': {
                'name': self.station.name,
                'country': str(self.station.country)
            }
        }
        if self.song.normalized:
            song = self.song.normalized
            normalized = True
        else:
            song = self.song
            normalized = False
        doc['song'] = {
            'title': song.title,
            'artist': song.artist,
            'normalized': normalized,
            'tags': [tag.name for tag in song.tags.all()] if normalized else []
        }
        return doc

    def as_elasticsearch_insert(self):
        return {
            '_index': 'radiostats',
            '_type': 'play',
            '_source': self.as_document()
        }

    class Meta:
        unique_together = (("time", "station"),)
