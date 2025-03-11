import datetime
from random import shuffle
import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection, send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode

from findshows.forms import ContactForm, TempArtistForm
from findshows.models import Concert, UserProfile


logger = logging.getLogger(__name__)


def send_mail_helper(subject, message, recipient_list, form=None, from_email=None):
    """
    Sends a single email.

    If form is provided, we will add an error to it if email fails. Assumes is_valid() has been called.
    If from_email is not provided, it will be from DEFAULT_FROM_EMAIL
    """
    try:
        return send_mail(subject, message, from_email, recipient_list, fail_silently=False)
    except SMTPException as e:
        if form:
            form.add_error(None, f"Unable to send email. Please try again later.")
        logger.error(f"Email failure: {str(e)}")
        return 0


def invite_artist(taf: TempArtistForm):
    subject = "Make your profile on ChicagoLocalMusic.com"
    message = "This will include instructions and a code or link to create an account & link it to the specific artist provided as an argument."
    return send_mail_helper(subject, message, [taf.cleaned_data['temp_email']], taf)


def send_artist_setup_info(user_email: str):
    return send_mail_helper(
        "Make an Artist page on Chicago Local Music",
        "this will be a link to create an artist account linked to user",
        [user_email]
    )


def contact_email(cf: ContactForm):
    match cf.cleaned_data['type']:
        case cf.Types.REPORT_BUG:
            recipient_list = [admin[1] for admin in settings.ADMINS] # Tuples (Name, email)
        case cf.Types.OTHER:
            recipient_list = [mod[1] for mod in settings.MODERATORS]
        case _:
            recipient_list = []

    return send_mail_helper(cf.cleaned_data['subject'],
                            cf.cleaned_data['message'],
                            recipient_list,
                            cf,
                            cf.cleaned_data['email'])


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


def artist_invite_url(artist_linking_info, invite_code):
    qs = {'invite_id': artist_linking_info.id,
          'invite_code': invite_code}
    return settings.HOST_NAME + reverse("findshows:link_artist") + '?' + urlencode(qs, doseq=True)


def rec_email_generator(header_message):
    user_profiles = UserProfile.objects.filter(weekly_email=True)
    today = datetime.date.today()
    week_later = today + datetime.timedelta(6)
    search_params = {'date': today,
                      'end_date': week_later,
                      'is_date_range': True}

    next_week_concerts = Concert.objects.filter(date__gte=today, date__lte=week_later)
    next_week_concerts = next_week_concerts.exclude(artists__is_temp_artist=True)
    for user_profile in user_profiles:
        search_params['musicbrainz_artists'] = [mb_artist.mbid
                                                for mb_artist in user_profile.favorite_musicbrainz_artists.all()]
        search_params['concert_tags'] = user_profile.preferred_concert_tags
        search_url = settings.HOST_NAME + reverse('findshows:concert_search') + '?' + urlencode(search_params, doseq=True)

        scored_concerts = ((c.relevance_score(search_params['musicbrainz_artists']), c) for c in next_week_concerts)
        top_scored_concerts = sorted(s_c for s_c in scored_concerts if s_c[0] != 0)
        has_recs = len(top_scored_concerts) > 0
        if has_recs:
            rec_concerts = [s_c[1] for s_c in top_scored_concerts]
        else:
            rec_concerts = list(next_week_concerts)
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
