import datetime
from django import template

register = template.Library()

@register.inclusion_tag("findshows/partials/preview_player.html")
def preview_player(artist, mini=False):
    if mini and len(artist.listen_ids) > 0:
        listen_ids = [artist.listen_ids[0]]
    else:
        listen_ids = artist.listen_ids
    return {
        'artist': artist,
        'listen_ids': listen_ids,
        'mini': mini,
    }


@register.filter
def time_short(value: datetime.time):
    ampm = (value.hour//12)*'pm' or 'am'
    hour = value.hour%12 or 12
    return f'{hour}:{value.minute:02}{ampm}'


@register.inclusion_tag("findshows/partials/similar_artist_name_with_relevancy.html")
def similar_artist_name_with_relevancy(similar_musicbrainz_artist, searched_musicbrainz_artists=None):
    if not searched_musicbrainz_artists:
        searched_musicbrainz_artists = []
    relevant_names = ", ".join(searched_artist.name
                               for searched_artist in searched_musicbrainz_artists
                               if similar_musicbrainz_artist.similarity_score(searched_artist.mbid))
    return {
        'name': similar_musicbrainz_artist.name,
        'relevant_names': relevant_names,
    }
