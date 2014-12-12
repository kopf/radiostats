from django.db import models


class Play(models.Model):
    song = models.ForeignKey(Song)
    time = models.DateTimeField()


class Song(models.Model):
    artist = models.TextField(null=False)
    title = models.TextField(null=False)
    normalized = models.ForeignKey(NormalizedSong)


class NormalizedSong(models.Model):
    mbid = models.CharField(max_length=36, null=False)
    artist = models.TextField(null=False)
    title = models.TextField(null=False)
    tags = models.ManyToManyField(Tag)


class Tag(models.Model):
    name = models.CharField(max_length=32)

