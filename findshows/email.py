import datetime
from django.conf import settings
from django.core.mail import BadHeaderError, EmailMultiAlternatives, get_connection, send_mail, send_mass_mail
from django.shortcuts import render
from django.template.loader import render_to_string

from findshows.forms import ContactForm
from findshows.models import Artist, Concert, UserProfile


def invite_artist(temp_artist: Artist):
    subject = "Make your profile on ChicagoLocalMusic.com"
    message = "This will include instructions and a code or link to create an account & link it to the specific artist provided as an argument."
    return send_mail(subject, message, None, [temp_artist.temp_email])


def contact_email(cf: ContactForm): # Assumes the form has already run is_valid()
    match cf.cleaned_data['type']:
        case cf.Types.REPORT_BUG:
            recipient_list = settings.ADMINS
        case cf.Types.OTHER:
            recipient_list = settings.MODERATORS

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


def send_rec_email(subject, header_message):
    user_profiles = UserProfile.objects.filter(weekly_email=True)
    today = datetime.date.today()
    concertss = (sorted(Concert.objects.filter(date__gte=today, date__lt=today + datetime.timedelta(7)),
                        key=lambda c: c.relevance_score(user_profile.favorite_spotify_artists_and_relateds),
                        reverse=True)
                 for user_profile in user_profiles)

    html_messages = (render_to_string("findshows/emails/rec_email.html", context={'header_message': header_message,
                                                                                  'user_profile': user_profile,
                                                                                  'concerts': concerts,
                                                                                  'host_name': settings.HOST_NAME})
                     for user_profile, concerts in zip(user_profiles, concertss))
    text_message = f'{header_message}\n\nGo to liiiink to see your weekly recommendations'
    datatuple = ( (subject, text_message, html_message, None, [user_profile.user.email])
                  for html_message, user_profile in zip(html_messages, user_profiles) )
    return send_mass_html_mail(datatuple)
