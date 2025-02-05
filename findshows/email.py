import datetime
from django.conf import settings
from django.core.mail import BadHeaderError, EmailMultiAlternatives, get_connection, send_mail, send_mass_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode

from findshows.forms import ContactForm
from findshows.models import Artist, Concert, UserProfile


def invite_artist(temp_artist: Artist):
    subject = "Make your profile on ChicagoLocalMusic.com"
    message = "This will include instructions and a code or link to create an account & link it to the specific artist provided as an argument."
    return send_mail(subject, message, None, [temp_artist.temp_email])


def send_artist_setup_info(user_email: str):
    send_mail(
        "Make an Artist page on Chicago Local Music",
        "this will be a link to create an artist account linked to user",
        "admin@chicagolocalmusic.com",
        [user_email],
        fail_silently=False,
    )


def contact_email(cf: ContactForm): # Assumes the form has already run is_valid()
    match cf.cleaned_data['type']:
        case cf.Types.REPORT_BUG:
            recipient_list = [admin[1] for admin in settings.ADMINS] # Tuples (Name, email)
        case cf.Types.OTHER:
            recipient_list = [mod[1] for mod in settings.MODERATORS]
        case _:
            recipient_list = []

    try:
        success = send_mail(cf.cleaned_data['subject'],
                            cf.cleaned_data['message'],
                            cf.cleaned_data['email'],
                            recipient_list)
        if not success:
            cf.add_error(None, f"Unable to send email. Please try again later, or email site admins directly at {settings.ADMINS} if this issue persists.")
    except BadHeaderError:
        cf.add_error(None, "Bad header. Make sure there are no newlines in your email or subject.")
        success = 0

    return success


# from https://stackoverflow.com/questions/7583801/send-mass-emails-with-emailmultialternatives/10215091#10215091
def send_mass_html_mail(datatuple, fail_silently=False, user=None, password=None,
                        connection=None):
    """
    Given a datatuple of (subject, text_content, html_content, from_email,
    recipient_list), sends each message to each recipient list. Returns the
    number of emails sent.

    If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
    If auth_user and auth_password are set, they're used to log in.
    If auth_user is None, the EMAIL_HOST_USER setting is used.
    If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.

    """
    connection = connection or get_connection(
        username=user, password=password, fail_silently=fail_silently)
    messages = []
    for subject, text, html, from_email, recipient in datatuple:
        message = EmailMultiAlternatives(subject, text, from_email, recipient)
        message.attach_alternative(html, 'text/html')
        messages.append(message)
    return connection.send_messages(messages)


def rec_email_generator(header_message):
    user_profiles = UserProfile.objects.filter(weekly_email=True)
    today = datetime.date.today()
    week_later = today + datetime.timedelta(6)
    search_params = {'date': today,
                      'end_date': week_later,
                      'is_date_range': True}

    for user_profile in user_profiles:
        concerts = sorted(Concert.objects.filter(date__gte=today, date__lte=week_later),
                          key=lambda c: c.relevance_score(user_profile.favorite_spotify_artists_and_relateds),
                          reverse=True)
        search_params['concert_tags'] = user_profile.preferred_concert_tags
        search_params['spotify_artists'] = [a['id'] for a in user_profile.favorite_spotify_artists]
        search_url = settings.HOST_NAME + reverse('findshows:concert_search') + '?' + urlencode(search_params, doseq=True)

        html_message = render_to_string("findshows/emails/rec_email.html",
                                        context={'header_message': header_message,
                                                 'user_profile': user_profile,
                                                 'concerts': concerts,
                                                 'host_name': settings.HOST_NAME,
                                                 'search_url': search_url})
        text_message = f'{header_message}\n\nGo to {search_url} to see your weekly concert recommendations.'

        yield text_message, html_message, user_profile.user.email



def send_rec_email(subject, header_message):
    datatuple = ( (subject, text_message, html_message, None, [email])
                  for text_message, html_message, email in rec_email_generator(header_message) )
    return send_mass_html_mail(datatuple)
