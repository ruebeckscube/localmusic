import datetime

from django import template
from django.template.loader import render_to_string
from django.urls import reverse

from findshows.email import local_url_to_email
from findshows.models import CustomText

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
def similar_artist_name_with_relevancy(similar_musicbrainz_artist, is_last, searched_musicbrainz_artists=None, always_inline=False, user=None):
    if not searched_musicbrainz_artists:
        if user is None or user.is_anonymous:
            searched_musicbrainz_artists = []
        else:
            searched_musicbrainz_artists = user.userprofile.favorite_musicbrainz_artists.all()

    relevant_names = ", ".join(searched_artist.name
                               for searched_artist in searched_musicbrainz_artists
                               if similar_musicbrainz_artist.similarity_score(searched_artist.mbid))
    return {
        'name': similar_musicbrainz_artist.name,
        'relevant_names': relevant_names,
        'is_last': is_last,
        'always_inline': always_inline,
    }


@register.simple_tag
def custom_text(type: str):
    return CustomText.get_text(type)

@register.simple_tag
def email_url(url_name: str, *args, **kwargs):
    return local_url_to_email(reverse(url_name, args=args, query=kwargs))

@register.simple_tag
def email_raw_url(raw_url: str):
    return local_url_to_email(raw_url)

@register.simple_tag
def num_true_args(*args):
    return sum(1 for arg in args if arg)

@register.simple_block_tag
def accordion_element(content, title):
    return render_to_string('findshows/partials/accordion_element.html', context={
        'content': content,
        'title': title,
    })
