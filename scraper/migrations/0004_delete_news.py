import re
from django.db import migrations

def is_news(artist, title):
    if artist == 'SWR3 Nachrichten':
        return True
    if artist == 'ByteFM' and title == 'Nachrichten':
        return True
    if re.match(r'^\d+ Uhr$', artist) and 'Nachrichten' in title:
        return True
    return False

def delete_news_songs(apps, schema_editor):
    Song = apps.get_model('scraper', 'Song')
    Play = apps.get_model('scraper', 'Play')
    
    plays_before = Play.objects.count()
    
    songs_to_delete = []
    # Broad filter to narrow down candidates
    for song in Song.objects.filter(title__icontains='Nachrichten'):
        if is_news(song.artist, song.title):
            songs_to_delete.append(song.id)
            
    # Also check for specific artist-only news
    for song in Song.objects.filter(artist='SWR3 Nachrichten'):
        if song.id not in songs_to_delete:
            songs_to_delete.append(song.id)

    songs_count = len(songs_to_delete)
    Song.objects.filter(id__in=songs_to_delete).delete()
    
    plays_after = Play.objects.count()
    
    print(f"\n[Migration] Deleted {songs_count} news songs.")
    print(f"[Migration] Plays before: {plays_before}")
    print(f"[Migration] Plays after:  {plays_after}")
    print(f"[Migration] Plays deleted: {plays_before - plays_after}")

class Migration(migrations.Migration):
    dependencies = [
        ('scraper', '0003_play_synced'),
    ]
    operations = [
        migrations.RunPython(delete_news_songs),
    ]
