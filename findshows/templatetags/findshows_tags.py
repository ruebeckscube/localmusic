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
