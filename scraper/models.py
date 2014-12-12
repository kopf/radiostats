from django.db import models
from django_countries.fields import CountryField


class Tag(models.Model):
    name = models.CharField(max_length=32)


class Station(models.Model):
    name = models.CharField(max_length=32)
    country = CountryField()


class NormalizedSong(models.Model):
    mbid = models.CharField(max_length=36)
    artist = models.TextField()
    title = models.TextField()
    tags = models.ManyToManyField(Tag, null=True)


class Song(models.Model):
    artist = models.TextField()
    title = models.TextField()
    normalized = models.ForeignKey(NormalizedSong, null=True)


class Play(models.Model):
    song = models.ForeignKey(Song)
    time = models.DateTimeField()
