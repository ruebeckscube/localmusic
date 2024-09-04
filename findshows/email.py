from django.conf import settings
from django.core.mail import BadHeaderError, send_mail
from findshows.forms import ContactForm

from findshows.models import Artist


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
