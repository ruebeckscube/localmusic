import datetime
from functools import reduce
from operator import or_
from random import shuffle
import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection, send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode
from django.db.models import Q
from django.views.generic.dates import timezone_today

from findshows.forms import ContactForm
from findshows.models import Artist, ArtistLinkingInfo, Concert, UserProfile, Venue


logger = logging.getLogger(__name__)


def send_mail_helper(subject, message, recipient_list, form=None, from_email=None, errorlist=None):
    """
    Sends a single email.

    If form is provided, we will add an error to it if email fails. Assumes is_valid() has been called.
    If from_email is not provided, it will be from DEFAULT_FROM_EMAIL
    If errorlist is provided, we will append errors to it if email fails.
    """
    try:
        return send_mail(subject, message, from_email, recipient_list, fail_silently=False)
    except SMTPException as e:
        if form:
            form.add_error(None, f"Unable to send email to {','.join(recipient_list)}. Please try again later.")
        if errorlist is not None:
            errorlist.append(f"Unable to send email to {','.join(recipient_list)}. Please try again later.")
        logger.error(f"Email failure: {str(e)}")
        return 0


def artist_invite_url(link_info: ArtistLinkingInfo, invite_code):
    qs = {'invite_id': link_info.pk,
          'invite_code': invite_code}
    return settings.HOST_NAME + reverse("findshows:link_artist") + '?' + urlencode(qs, doseq=True)


def invite_artist(link_info: ArtistLinkingInfo, invite_code, form=None, errorlist=None):
    subject = "Artist profile invite"
    message = f"You've been invited to create an artist profile on {settings.HOST_NAME}. Click the link to claim it and fill out your profile!\n\n{artist_invite_url(link_info, invite_code)}"
    return send_mail_helper(subject, message, [link_info.invited_email], form, errorlist=errorlist)


def invite_user_to_artist(link_info: ArtistLinkingInfo, invite_code, form):
    subject = "Artist profile invite"
    message = f"You've been invited to manage an artist profile on {settings.HOST_NAME}. Click the link to claim access:\n\n{artist_invite_url(link_info, invite_code)}"
    return send_mail_helper(subject, message, [link_info.invited_email], form)


def send_artist_setup_info(user_email: str):
    return send_mail_helper(
        f"Make an Artist page on {settings.HOST_NAME}",
        f"To request an artist page, go to your user settings page ({settings.HOST_NAME}{reverse('findshows:user_settings')}) and click 'Request local artist access.'",
        [user_email]
    )


def contact_email(cf: ContactForm):
    match cf.cleaned_data['type']:
        case cf.Types.REPORT_BUG:
            recipient_list = [admin[1] for admin in settings.ADMINS] # Tuples (Name, email)
        case cf.Types.OTHER:
            mods = UserProfile.objects.filter(is_mod=True)
            recipient_list = [mod.user.email for mod in mods]
        case _:
            recipient_list = []

    return send_mail_helper(cf.cleaned_data['subject'],
                            cf.cleaned_data['message'],
                            recipient_list,
                            cf,
                            cf.cleaned_data['email'])

def daily_mod_email():
    today = timezone_today()

    new_artists = Artist.objects.filter(created_at=today)
    new_concerts = Concert.objects.filter(created_at=today)
    new_venues = Venue.objects.filter(created_at=today)

    actionable_artists = Artist.objects.filter(is_active_request=True)
    actionable_venues = Venue.objects.filter(is_verified=False)

    if all(q.count()==0 for q in (new_artists, new_concerts, new_venues, actionable_artists, actionable_venues)):
        return True

    message = f"There are new or actionable listings to moderate.\n\n{settings.HOST_NAME}{reverse('findshows:mod_dashboard')}"
    recipient_list = [mod.user.email for mod in UserProfile.objects.filter(is_mod=True)]
    return send_mail_helper("Moderation reminder", message, recipient_list)


# from https://stackoverflow.com/questions/7583801/send-mass-emails-with-emailmultialternatives/10215091#10215091
def send_mass_html_mail(datatuples):
    """
    Given an list of datatuples of (subject, text_content, html_content, from_email,
    recipient_list), sends each message to each recipient list. Returns the
    number of emails sent.

    If from_email is None for a datatuple, the DEFAULT_FROM_EMAIL setting is used.
    The EMAIL_HOST_USER and EMAIL_HOST_PASSWORD settings are used to log in to the email service.
    """
    with get_connection() as connection:
        sent = 0
        for subject, text, html, from_email, recipient in datatuples:
            try:
                message = EmailMultiAlternatives(subject, text, from_email, recipient,
                                                 connection=connection)
                message.attach_alternative(html, 'text/html')
                message.send()
                sent += 1
            except SMTPException as e:
                logger.error(f"Email failure: {str(e)}")
    return sent


def rec_email_generator(header_message):
    user_profiles = UserProfile.objects.filter(weekly_email=True)
    today = datetime.date.today()
    week_later = today + datetime.timedelta(6)
    search_params = {'date': today,
                      'end_date': week_later,
                      'is_date_range': True}

    next_week_concerts = Concert.publically_visible().filter(date__gte=today, date__lte=week_later)
    for user_profile in user_profiles:
        search_params['musicbrainz_artists'] = [mb_artist.mbid
                                                for mb_artist in user_profile.favorite_musicbrainz_artists.all()]
        search_params['concert_tags'] = user_profile.preferred_concert_tags
        search_url = settings.HOST_NAME + reverse('findshows:concert_search') + '?' + urlencode(search_params, doseq=True)

        tag_filtered_concerts = next_week_concerts.all()
        if search_params['concert_tags']:
            tag_filtered_concerts = next_week_concerts.filter(reduce(or_, (Q(tags__icontains=t) for t in search_params['concert_tags'])))

        scored_concerts = ((c.relevance_score(search_params['musicbrainz_artists']), c) for c in tag_filtered_concerts)

        top_scored_concerts = sorted(s_c for s_c in scored_concerts if s_c[0] != 0)

        has_recs = len(top_scored_concerts) > 0
        if has_recs:
            rec_concerts = [s_c[1] for s_c in top_scored_concerts]
        else:
            if len(tag_filtered_concerts) == 0:
                rec_concerts = list(next_week_concerts)
            else:
                rec_concerts = list(tag_filtered_concerts)
            shuffle(rec_concerts)
        rec_concerts = rec_concerts[:settings.CONCERT_RECS_PER_EMAIL]

        html_message = render_to_string("findshows/emails/rec_email.html",
                                        context={'header_message': header_message,
                                                 'user_profile': user_profile,
                                                 'concerts': rec_concerts,
                                                 'host_name': settings.HOST_NAME,
                                                 'search_url': search_url,
                                                 'has_recs': has_recs})
        text_message = f'{header_message}\n\nGo to {search_url} to see your weekly concert recommendations.'

        yield text_message, html_message, user_profile.user.email



def send_rec_email(subject, header_message):
    datatuple = ( (subject, text_message, html_message, None, [email])
                  for text_message, html_message, email in rec_email_generator(header_message) )
    return send_mass_html_mail(datatuple)
