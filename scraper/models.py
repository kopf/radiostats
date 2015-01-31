from django.db import models
from django_countries.fields import CountryField


class Tag(models.Model):
    name = models.CharField(max_length=32)


class Station(models.Model):
    name = models.CharField(max_length=32)
    country = CountryField()
    timezone = models.CharField(max_length=64)
    class_name = models.CharField(max_length=32)
    start_date = models.DateField()
    last_scraped = models.DateTimeField(null=True)
    enabled = models.BooleanField(default=True)


class NormalizedSong(models.Model):
    mbid = models.CharField(max_length=36)
    artist = models.CharField(max_length=256)
    title = models.CharField(max_length=256)
    tags = models.ManyToManyField(Tag, null=True)


class Song(models.Model):
    artist = models.CharField(max_length=256)
    title = models.CharField(max_length=256)
    normalized = models.ForeignKey(NormalizedSong, null=True)
    last_scraped = models.DateTimeField(null=True)


class Play(models.Model):
    local_time = models.DateTimeField()
    time = models.DateTimeField()
    song = models.ForeignKey(Song)
    station = models.ForeignKey(Station)

