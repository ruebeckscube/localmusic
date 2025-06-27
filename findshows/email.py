import datetime
from functools import reduce
from operator import or_
from random import shuffle
import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse
from django.db.models import Q

from findshows.forms import ContactForm
from findshows.models import Artist, ArtistLinkingInfo, Concert, CustomText, EmailVerification, UserProfile, Venue


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
    logger.error(log_error)
    return 0


def send_verify_email(email_verification: EmailVerification, invite_code, form=None, errorlist=None):
    subject = "Confirm your email address"
    message = f"Please click the following link to verify your email address:\n\n{local_url_to_email(email_verification.get_url(invite_code))}"
    return send_mail_helper(subject, message, [email_verification.invited_email], form, errorlist=errorlist)


def invite_artist(link_info: ArtistLinkingInfo, invite_code, form=None, errorlist=None):
    subject = "Artist profile invite"
    message = f"You've been invited to create an artist profile on {settings.HOST_NAME}. Click the link to claim it and fill out your profile!\n\n{local_url_to_email(link_info.get_url(invite_code))}"
    return send_mail_helper(subject, message, [link_info.invited_email], form, errorlist=errorlist)


def invite_user_to_artist(link_info: ArtistLinkingInfo, invite_code, form):
    subject = "Artist profile invite"
    message = f"You've been invited to manage an artist profile on {settings.HOST_NAME}. Click the link to claim access:\n\n{local_url_to_email(link_info.get_url(invite_code))}"
    return send_mail_helper(subject, message, [link_info.invited_email], form)


def send_artist_setup_info(user_email: str):
    return send_mail_helper(
        f"Make an Artist page on {settings.HOST_NAME}",
        f"""To request an artist page, go to your user settings page
        ({local_url_to_email(reverse('findshows:user_settings'))}) and click
        'Request local artist access.' You will need to provide your artist
        name, as well as a website or social media account where we can contact
        you to verify your identity. A mod will review the request and reach out
        as soon as possible.""",
        [user_email]
    )


def contact_email(cf: ContactForm):
    match cf.cleaned_data['type']:
        case cf.Types.REPORT_BUG:
            recipient_list = [admin[1] for admin in settings.ADMINS] # Tuples (Name, email)
            type = cf.Types.REPORT_BUG.label
        case cf.Types.OTHER:
            mods = UserProfile.objects.filter(is_mod=True)
            recipient_list = [mod.user.email for mod in mods]
            type = cf.Types.OTHER.label
        case _:
            recipient_list = []
            type = ""

    return send_mail_helper(f"[Contact|{type}] {cf.cleaned_data['subject']}",
                            cf.cleaned_data['message'],
                            recipient_list,
                            cf,
                            reply_to_list=[cf.cleaned_data['email']],
                            cc_reply_to=False,
                            )

def daily_mod_email(date):
    query_labels = ("NEW ARTISTS", "ACTIONABLE ARTISTS", "NEW VENUES", "ACTIONABLE VENUES", "NEW CONCERTS")
    queries = (
        Artist.objects.filter(created_at=date),
        Artist.objects.filter(is_active_request=True),
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
    recipient_list = [mod.user.email for mod in UserProfile.objects.filter(is_mod=True)]
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
                logger.error(f"Email failure: {str(e)}")
    return sent


def rec_email_generator():
    user_profiles = UserProfile.objects.filter(weekly_email=True, email_is_verified=True)
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
        search_url = local_url_to_email(reverse('findshows:home', query=search_params))

        tag_filtered_concerts = next_week_concerts.all()
        if search_params['concert_tags']:
            tag_filtered_concerts = next_week_concerts.filter(reduce(or_, (Q(tags__icontains=t) for t in search_params['concert_tags'])))

        scored_concerts = ((c.relevance_score(search_params['musicbrainz_artists']), c) for c in tag_filtered_concerts)

        top_scored_concerts = sorted((s_c for s_c in scored_concerts if s_c[0] != 0), reverse=True)

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
                                        context={'user_profile': user_profile,
                                                 'concerts': rec_concerts,
                                                 'search_url': search_url,
                                                 'has_recs': has_recs})
        text_message = f'{CustomText.get_text(CustomText.WEEKLY_EMAIL_HEADER)}\n\nGo to {search_url} to see your weekly concert recommendations.'

        yield text_message, html_message, user_profile.user.email



def send_rec_email():
    datatuple = ( (CustomText.get_text(CustomText.WEEKLY_EMAIL_SUBJECT), text_message, html_message, None, [email])
                  for text_message, html_message, email in rec_email_generator() )
    return send_mass_html_mail(datatuple)
