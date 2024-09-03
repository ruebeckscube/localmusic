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
