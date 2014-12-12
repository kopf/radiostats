from datetime import datetime
from runner import GenericRunner

from scraper.models import *

def main():
    r = GenericRunner('')
    sql = u'select artist, title, station_name, time_played from songs;'
    r.db.execute(sql)
    rows = []
    while True:
        xyz = r.db.fetchone()
        if not xyz:
            break
        rows.append([row for row in xyz])

    kexp = Station(name='KEXP', country='US')
    swr1 = Station(name='SWR1', country='DE')
    swr2 = Station(name='SWR2', country='DE')
    for station in [kexp, swr1, swr2]:
        station.save()

    for row in rows:
        artist, title, radio_station, time_played = row
        if radio_station == 'SWR1':
            station = swr1
        elif radio_station == 'SWR2':
            station = swr2
        elif radio_station == 'KEXP':
            station = kexp
        song, _ = Song.objects.get_or_create(artist=artist, title=title)
        play = Play(time=time_played, song=song, station=station)
        play.save()

if __name__ == '__main__':
    import django
    django.setup()
    main()
