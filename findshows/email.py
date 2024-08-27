from django.core.mail import send_mail

from findshows.models import Artist


def _send_mail_helper(recipient_list, subject, message, html_message=None):
    return send_mail(
        subject,
        message,
        "admin@chicagolocalmusic.com",
        recipient_list,
        fail_silently=False,
        html_message=html_message
    )


def invite_artist(temp_artist: Artist):
    subject = "Make your profile on ChicagoLocalMusic.com"
    message = "This will include instructions and a code or link to create an account & link it to the specific artist provided as an argument."
    return _send_mail_helper([temp_artist.temp_email], subject, message)
