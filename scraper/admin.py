from django.contrib import admin

from .models import Tag, Station, NormalizedSong, Song, Play

class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'timezone', 'start_date', 'last_scraped', 'enabled')

class SongAdmin(admin.ModelAdmin):
    list_display = ('artist', 'title', 'normalized', 'last_scraped')

class NormalizedSongAdmin(admin.ModelAdmin):
    list_display = ('mbid', 'artist', 'title')

class PlayAdmin(admin.ModelAdmin):
    list_display = ('local_time', 'time', 'song', 'station')



admin.site.register(Station, StationAdmin)
admin.site.register(Tag)
admin.site.register(NormalizedSong, NormalizedSongAdmin)
admin.site.register(Song, SongAdmin)
admin.site.register(Play, PlayAdmin)
