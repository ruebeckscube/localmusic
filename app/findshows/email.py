import datetime
from random import shuffle
import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse

from findshows.forms import ContactForm
from findshows.models import Artist, ArtistLinkingInfo, ArtistVerificationStatus, Concert, CustomText, EmailVerification, UserProfile, Venue

User = get_user_model()
logger = logging.getLogger(__name__)


PROTOCOL = "http" if settings.IS_DEV else "https"
def local_url_to_email(local_url):
    return f"{PROTOCOL}://{settings.HOST_NAME}{local_url}"


def send_mail_helper(subject, message, recipient_list, form=None, from_email=None, errorlist=None, reply_to_list=None, cc_reply_to=False):
    """
    Sends a single email.

    If form is provided, we will add an error to it if email fails. Assumes is_valid() has been called.
    If from_email is not provided, it will be from DEFAULT_FROM_EMAIL. It should always be one from our domain (i.e. mod or admin email).
    If errorlist is provided, we will append errors to it if email fails.
    """
    recipient_list = [r for r in recipient_list if r]
    if not recipient_list:
        display_error = "Internal error; admins have been notified, please try again later."
        log_error = "Email failure: no recipients specified for email."
    else:
        try:
            email = EmailMessage(
                subject,
                message,
                from_email,
                recipient_list,
                reply_to=reply_to_list,
                cc=reply_to_list if cc_reply_to else None,
            )
            return email.send(fail_silently=False)
        except SMTPException as e:
            display_error = f"Unable to send email to {','.join(recipient_list)}. Please try again later."
            log_error = f"Email failure: {str(e)}"

    if form:
        form.add_error(None, display_error)
    if errorlist is not None:
        errorlist.append(display_error)
    logger.warning(log_error)
    return 0


def send_verify_email(email_verification: EmailVerification, invite_code, form=None, errorlist=None):
    subject = "Confirm your email address"
    message = f"Please click the following link to verify your email address:\n\n{local_url_to_email(email_verification.get_url(invite_code))}"
    logger.info("Sending verification email")
    return send_mail_helper(subject, message, [email_verification.invited_email], form, errorlist=errorlist)


def invite_artist(link_info: ArtistLinkingInfo, invite_code, form=None, errorlist=None):
    name = CustomText.get_text(CustomText.SITE_TITLE) or settings.HOST_NAME
    subject = "Artist profile invite"
    message = f"{link_info.created_by.user.email} has invited you to create an artist profile on {name}. Click the link to claim it and fill out your profile!\n\n{local_url_to_email(link_info.get_url(invite_code))}"
    logger.info("Sending artist invite email")
    return send_mail_helper(subject, message, [link_info.invited_email], form, errorlist=errorlist)


def invite_user_to_artist(link_info: ArtistLinkingInfo, invite_code, form):
    name = CustomText.get_text(CustomText.SITE_TITLE) or settings.HOST_NAME
    subject = "Artist profile invite"
    message = f"You've been invited to manage an artist profile on {name}. Click the link to claim access:\n\n{local_url_to_email(link_info.get_url(invite_code))}"
    logger.info("Sending user_to_artist invite email")
    return send_mail_helper(subject, message, [link_info.invited_email], form)


def contact_email(cf: ContactForm):
    try:
        type = cf.Types(cf.cleaned_data['type'])
    except ValueError:
        type = cf.Types.OTHER

    match type:
        case cf.Types.REPORT_BUG | cf.Types.FEATURE_REQUEST:
            recipient_list = [admin[1] for admin in settings.ADMINS] # Tuples (Name, email)
        case cf.Types.CONTACT_MOD | cf.Types.HELP | cf.Types.OTHER:
            mods = User.objects.filter(is_mod=True)
            recipient_list = [mod.email for mod in mods]

    logger.info("Sending contact email")
    return send_mail_helper(f"[Contact|{type.label}] {cf.cleaned_data['subject']}",
                            cf.cleaned_data['message'],
                            recipient_list,
                            cf,
                            reply_to_list=[cf.cleaned_data['email']],
                            cc_reply_to=False,
                            )

def daily_mod_email(date):
    query_labels = ("NEW ARTISTS", "ACTIONABLE ARTIST ACCOUNTS", "NEW VENUES", "ACTIONABLE VENUES", "NEW CONCERTS")
    queries = (
        Artist.objects.filter(created_at=date),
        UserProfile.objects.filter(artist_verification_status=ArtistVerificationStatus.UNVERIFIED),
        Venue.objects.filter(created_at=date),
        Venue.objects.filter(is_verified=False),
        Concert.objects.filter(created_at=date),
    )
    if all(q.count()==0 for q in queries):
        return True

    records_tuple = ('\n'.join(str(record) for record in q.all())
                      for q in queries)
    records_string = '\n\n'.join(f"{label}\n{records}"
                                 for label, records in zip(query_labels, records_tuple)
                                 if records
                                 )
    url = local_url_to_email(reverse('findshows:mod_dashboard', query={'date': date.isoformat()}))
    message = f"There are new or actionable listings to review from {str(date)}.\n\n{url}\n\n{records_string}"
    recipient_list = [mod.email for mod in User.objects.filter(is_mod=True)]
    logger.info("Sending daily mod email")
    return send_mail_helper(f"{CustomText.get_text(CustomText.SITE_TITLE)} Moderation reminder",
                            message, recipient_list)


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
                logger.warning(f"Email failure: {str(e)}")
    return sent


def rec_email_generator():
    user_profiles = UserProfile.objects.filter(
        weekly_email=True, email_is_verified=True).select_related(
            'user').prefetch_related('favorite_musicbrainz_artists').only(
                'preferred_concert_tags', 'user', 'user__email', 'favorite_musicbrainz_artists', 'favorite_musicbrainz_artists__mbid')
    today = datetime.date.today()
    week_later = today + datetime.timedelta(6)
    search_params = {'date': today,
                      'end_date': week_later,
                      'is_date_range': True}
    email_header = CustomText.get_text(CustomText.WEEKLY_EMAIL_HEADER)
    site_title = CustomText.get_text(CustomText.SITE_TITLE)
    next_week_concerts = tuple(Concert.publically_visible().select_related('venue').prefetch_related('artists__similar_musicbrainz_artists').filter(date__gte=today, date__lte=week_later))

    if not next_week_concerts:
        return

    for user_profile in user_profiles.iterator(chunk_size=1000):
        search_params['musicbrainz_artists'] = [mb_artist.mbid
                                                for mb_artist in user_profile.favorite_musicbrainz_artists.all()]
        search_params['concert_tags'] = set(user_profile.preferred_concert_tags)
        search_url = local_url_to_email(reverse('findshows:home', query=search_params))

        tag_filtered_concerts = [
            c for c in next_week_concerts
            if search_params['concert_tags'].intersection(c.tags)
        ] if search_params['concert_tags'] else list(next_week_concerts)
        scored_concerts = ((c.relevance_score(search_params['musicbrainz_artists']), c) for c in tag_filtered_concerts)
        top_scored_concerts = sorted((s_c for s_c in scored_concerts if s_c[0] != 0), reverse=True)

        has_recs = len(top_scored_concerts) > 0
        if has_recs:
            rec_concerts = [s_c[1] for s_c in top_scored_concerts]
        else:
            rec_concerts = tag_filtered_concerts if tag_filtered_concerts else list(next_week_concerts)
            shuffle(rec_concerts)
        rec_concerts = rec_concerts[:settings.CONCERT_RECS_PER_EMAIL]

        html_message = render_to_string("findshows/emails/rec_email.html",
                                        context={'user_profile': user_profile,
                                                 'concerts': rec_concerts,
                                                 'search_url': search_url,
                                                 'email_header': email_header,
                                                 'site_title': site_title,
                                                 'has_recs': has_recs})
        text_message = f'{email_header}\n\nGo to {search_url} to see your weekly concert recommendations.'

        yield text_message, html_message, user_profile.user.email



def send_rec_email():
    subject = CustomText.get_text(CustomText.WEEKLY_EMAIL_SUBJECT)
    datatuple = ( (subject, text_message, html_message, None, [email])
                  for text_message, html_message, email in rec_email_generator() )
    sent = send_mass_html_mail(datatuple)
    logger.info(f"Sent {sent} recommendation emails")
    return sent
