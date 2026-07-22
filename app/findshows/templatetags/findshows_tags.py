import datetime

from django import template
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.timezone import timedelta
from django.views.generic.dates import timezone_today
from django.conf import settings

from findshows.email import local_url_to_email
from findshows.models import Concert, CustomText

register = template.Library()


@register.inclusion_tag("findshows/partials/preview_player.html")
def preview_player(artist, mini=False):
    links = artist.listenlink_set.order_by('order')
    if mini and len(links) > 0:
        links = [links[0]]
    return {'urls_and_heights': ((l.get_url_for_display(mini), l.get_height(mini)) for l in links)}


@register.inclusion_tag("findshows/partials/youtube_embeds.html")
def youtube_embeds(artist):
    return {'urls': (l.get_url_for_display() for l in artist.youtubelink_set.order_by('order'))}


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
    return mark_safe(CustomText.get_html(type))

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

@register.simple_block_tag(takes_context=True)
def modal_confirmation(context, content, title, initial_show='false'):
    context.push({
        'type': 'confirmation',
        'title': title,
        'content': content,
        'initial_show': initial_show,
    })
    return render_to_string('findshows/partials/modal_popup.html', context.flatten())


@register.simple_block_tag(takes_context=True)
def modal_form(context: template.RequestContext, content, title, htmx_url, htmx_param=None):
    context.push({
        'type': 'form',
        'title': title,
        'content': content,
        'hx_post': reverse(htmx_url, args=(htmx_param,) if htmx_param else None)
    })
    return render_to_string('findshows/partials/modal_popup.html', context.flatten())


@register.filter
def obfuscate_if_email(value):
    if value[:7] != "mailto:": return value

    user, domain = value[7:].split("@")
    return mark_safe(f'#" data-eu="{user}" data-ed="{domain}")')


# Email includes send_date <= concert.date <= send_date + 6
# settings.WEEKLY_EMAIL_DAY = 6 (Sunday)
def _closest_email_date(date, before=False):
    delta = (settings.WEEKLY_EMAIL_DAY - date.weekday()) % 7
    delta = delta or 7 # day-of, assume the email has already gone out
    return date + timedelta(delta - (before * 7))


def _format_share_info(text, date):
    date = date.strftime("%b %d") if date else "n/a"
    return mark_safe(f"<div>{text}</div><div>{date}</div>")


@register.simple_tag
def announce_date(concert: Concert):
    if concert.announced:
        return _format_share_info("Announced", concert.announced)

    email_date = _closest_email_date(timezone_today())
    if concert.date < (email_date + timedelta(7)) or concert.cancelled:
        return _format_share_info("Announced", None)

    return _format_share_info("To announce", email_date)


@register.simple_tag
def share_date(concert):
    if concert.shared:
        return _format_share_info("Shared", concert.shared)

    email_date = _closest_email_date(concert.date, before=True)
    if email_date <= timezone_today() or concert.cancelled:
        return _format_share_info("Shared", None)

    return _format_share_info("To share", email_date)
