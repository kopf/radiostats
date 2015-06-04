from django.contrib import admin
from django.db import models

from .models import Tag, Station, NormalizedSong, Song, Play


class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'timezone', 'start_date', 'last_scraped', 'enabled')


class SongAdmin(admin.ModelAdmin):
    list_display = ('artist', 'title', 'normalized', 'last_scraped', 'play_count')
    exclude = ('normalized',)

    def queryset(self, request):
        return Song.objects.annotate(play_ct=models.Count('play'))

    def play_count(self, inst):
        return inst.play_ct

    play_count.admin_order_field = 'play_ct'


class NormalizedSongAdmin(admin.ModelAdmin):
    list_display = ('mbid', 'artist', 'title')


class PlayAdmin(admin.ModelAdmin):
    list_display = ('local_time', 'time', 'song', 'station')
    exclude = ('song', )


admin.site.register(Station, StationAdmin)
admin.site.register(Tag)
admin.site.register(NormalizedSong, NormalizedSongAdmin)
admin.site.register(Song, SongAdmin)
admin.site.register(Play, PlayAdmin)
