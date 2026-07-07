import datetime
from random import shuffle
import logging
from smtplib import SMTPException
from django.utils.safestring import mark_safe
from markdown import markdown
import nh3

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.urls import reverse

from findshows.models import Artist, ArtistLinkingInfo, ArtistVerificationStatus, Concert, Contact, CustomText, CustomTextTypes, EmailVerification, UserProfile, Venue

User = get_user_model()
logger = logging.getLogger(__name__)


PROTOCOL = "http" if settings.IS_DEV else "https"
PORT = ":8000" if settings.IS_DEV else ""

def local_url_to_email(local_url, display=""):
    if display:
        return f"[{display}]({PROTOCOL}://{settings.HOST_NAME}{PORT}{local_url})"
    else:
        return f"{PROTOCOL}://{settings.HOST_NAME}{PORT}{local_url}"


def render_email_to_string(template_name, context={}, **kwargs):
    # render_to_string doesn't use default context processors
    email_context = {
        'SITE_TITLE': settings.SITE_TITLE,
        'SITE_LINK': local_url_to_email(''),
        'bg_section': "#ebe7eb",
        **context
    }
    return render_to_string(template_name, email_context, **kwargs)


def send_simple_email(subject, message_blocks, recipient_list, form=None, from_email=None, errorlist=None, reply_to_list=None, cc_list=None):
    """
    Sends a single email. Includes raw <message> in text version of email, and <message> converted
    from markdown to HTML in the HTML version of the message.

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
            html_message = render_email_to_string("findshows/emails/simple_email.html", {
                'message_blocks': [mark_safe(nh3.clean(markdown(block))) for block in message_blocks],
                'homepage_link': local_url_to_email(""),
            })
            email = EmailMultiAlternatives(
                subject,
                ("\n\n".join(block for block in message_blocks)),
                from_email,
                recipient_list,
                reply_to=reply_to_list,
                cc=cc_list,
            )
            email.attach_alternative(html_message, 'text/html')
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
    message_blocks = [f"""
Welcome to {settings.SITE_TITLE}!

Please click the following link to verify your email address:
{local_url_to_email(email_verification.get_url(invite_code))}
    """]
    logger.info("Sending verification email")
    return send_simple_email(subject, message_blocks, [email_verification.invited_email], form, errorlist=errorlist)


def invite_artist(link_info: ArtistLinkingInfo, invite_code, form=None, errorlist=None):
    subject = "Artist profile invite"
    message_blocks = [f"""
{link_info.created_by.user.email} has invited you to create an artist profile for **{link_info.artist.name}**
on {settings.SITE_TITLE}.
{local_url_to_email(link_info.get_url(invite_code), "Make an account and fill out your profile here")}.
\n\nIf they've added you to a show, it will not be publically visible until you make a profile.
    This link expires in {settings.INVITE_CODE_EXPIRATION_DAYS} days.
    """]
    if link_info.artist.local:
        message_blocks.append(CustomText.get_text(CustomTextTypes.ARTIST_INVITE_EMAIL))
    else:
        message_blocks.append(f"""
Hello & welcome! This site is an instance of the [localmusic](https://github.com/ruebeckscube/localmusic)
project, an online media-rich bulletin board for your local music scene. It's a free & open source
project, and if you like the idea you can set it up for your city by
following [these instructions](https://github.com/ruebeckscube/localmusic/blob/master/docs/self-hosting.md).
It's still under development, so you need to have some technical know-how (or know somebody), but we'll
be making it easier & improving documentation in the near future so please
{local_url_to_email(reverse("findshows:contact"), "contact us")} if you'd like to stay up to date
on that front.
        """)

    logger.info("Sending artist invite email")
    return send_simple_email(subject, message_blocks, [link_info.invited_email], form, errorlist=errorlist)


def invite_user_to_artist(link_info: ArtistLinkingInfo, invite_code, form):
    subject = "Artist profile invite"
    message_blocks = [f"""
You've been invited to manage an artist profile on {settings.SITE_TITLE}.
{local_url_to_email(link_info.get_url(invite_code), "Click here")}
to claim access. This link expires in {settings.INVITE_CODE_EXPIRATION_DAYS} days.
    """]
    message_blocks.append(CustomText.get_text(CustomTextTypes.ARTIST_INVITE_EMAIL))
    logger.info("Sending user_to_artist invite email")
    return send_simple_email(subject, message_blocks, [link_info.invited_email], form)


def notify_artist_verified(userprofile):
    subject = "Artist profile verified"
    message_blocks = [f"""
Your artist profile has been verified! Any concerts you've listed will now
be publically visible, and any artist invites have been sent.
    """]
    message_blocks.append(CustomText.get_text(CustomTextTypes.ARTIST_INVITE_EMAIL))
    logger.info("Sending artist verification confirmation email")
    return send_simple_email(subject, message_blocks, [userprofile.user.email])


def daily_mod_email(date):
    queries = {
        "New artists": Artist.objects.filter(created_at=date),
        "Actionable artist accounts": UserProfile.objects.filter(artist_verification_status=ArtistVerificationStatus.UNVERIFIED),
        "New venues": Venue.objects.filter(created_at=date),
        "Actionable venues": Venue.objects.filter(is_verified=False),
        "New concerts": Concert.objects.filter(created_at=date),
        "Contacts": Contact.objects.all(),
    }
    if all(q.count()==0 for q in queries.values()):
        return True

    record_strings = {l: ''.join(f"\n- {str(record)}" for record in q.all())
                      for l, q in queries.items()}

    url = local_url_to_email(reverse('findshows:mod_dashboard', query={'date': date.isoformat()}), "Click here to review")
    message_blocks = [f"There are new or actionable records from {str(date)}. {url}."]
    message_blocks.extend(f"## {label}\n{records}"
                          for label, records in record_strings.items()
                          if records)
    recipient_list = [mod.email for mod in User.objects.filter(is_mod=True)]
    logger.info("Sending daily mod email")
    return send_simple_email(f"{settings.SITE_TITLE} Moderation reminder",
                            message_blocks, recipient_list)


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


def _load_general_recommendation_data():
    subject = CustomText.get_text(CustomTextTypes.WEEKLY_EMAIL_SUBJECT)
    email_header = CustomText.get_text(CustomTextTypes.WEEKLY_EMAIL_HEADER)

    user_profiles = UserProfile.objects.filter(
        weekly_email=True, email_is_verified=True).select_related(
            'user').prefetch_related('favorite_musicbrainz_artists', 'followed_artists').only(
                'preferred_concert_tags',
                'user', 'user__email',
                'favorite_musicbrainz_artists', 'favorite_musicbrainz_artists__mbid',
                'followed_artists',
            )
    today = datetime.date.today()
    week_later = today + datetime.timedelta(6)
    search_params = {'date': today,
                      'end_date': week_later,
                      'is_date_range': True}
    concerts = Concert.publically_visible().select_related('venue').prefetch_related('artists__similar_musicbrainz_artists')
    next_week_concerts = tuple(concerts.filter(date__gte=today, date__lte=week_later))
    unannounced_concerts = tuple(concerts.filter(date__gt=week_later, announced=None))

    return subject, user_profiles, search_params, email_header, next_week_concerts, unannounced_concerts


def _get_concerts_for_email(user_profile, search_params, next_week_concerts, unannounced_concerts):
    followed_artists = set(user_profile.followed_artists.all())
    followed_artist_concerts, not_followed_artist_concerts = [], []
    for c in next_week_concerts:
        if followed_artists.intersection(c.artists.all()):
            followed_artist_concerts.append(c)
        else:
            not_followed_artist_concerts.append(c)
    concerts_to_announce = [c for c in unannounced_concerts
                            if followed_artists.intersection(c.artists.all())]

    tag_filtered_concerts = [c for c in not_followed_artist_concerts
                             if search_params['concert_tags'].intersection(c.tags)
                             ] if search_params['concert_tags'] else list(not_followed_artist_concerts)

    scored_concerts = ((c.relevance_score(search_params['musicbrainz_artists']), c) for c in tag_filtered_concerts)
    rec_concerts = [s_c[1] for s_c in sorted((s_c for s_c in scored_concerts if s_c[0] != 0), reverse=True)][:settings.CONCERT_RECS_PER_EMAIL]

    random_concerts = tag_filtered_concerts or not_followed_artist_concerts
    shuffle(random_concerts)
    random_concerts = random_concerts[:settings.CONCERT_RECS_PER_EMAIL]

    return followed_artist_concerts, rec_concerts, random_concerts, concerts_to_announce


def _one_rec_email(user_profile, search_params, subject, email_header, next_week_concerts, unannounced_concerts):
    search_params = search_params.copy()
    search_params['musicbrainz_artists'] = [mb_artist.mbid
                                            for mb_artist in user_profile.favorite_musicbrainz_artists.all()]
    search_params['concert_tags'] = set(user_profile.preferred_concert_tags)
    search_url = local_url_to_email(reverse('findshows:home', query=search_params))

    followed_artist_concerts, rec_concerts, random_concerts, concerts_to_announce = _get_concerts_for_email(user_profile, search_params, next_week_concerts, unannounced_concerts)

    html_message = render_email_to_string("findshows/emails/rec_email.html", {
        'followed_artist_concerts': followed_artist_concerts,
        'concerts_to_announce': concerts_to_announce,
        'rec_concerts': rec_concerts or random_concerts,
        'search_url': search_url,
        'email_header': mark_safe(nh3.clean(markdown(email_header))),
        'has_recs': len(rec_concerts) > 0,
    })
    text_message = f'{email_header}\n\nGo to {search_url} to see your weekly concert recommendations.'

    # datatuple expected by send_mass_html_mail
    return (subject, text_message, html_message, None, (user_profile.user.email,))


def send_rec_email():
    subject, user_profiles, search_params, email_header, next_week_concerts, unannounced_concerts = _load_general_recommendation_data()
    if not next_week_concerts:
        logger.info(f"There are no concerts listed this week--not sending recommendation emails.")
        return None

    sent = send_mass_html_mail(_one_rec_email(user_profile, search_params, subject, email_header, next_week_concerts, unannounced_concerts)
                               for user_profile in user_profiles.iterator(chunk_size=1000))

    if sent:
        today = datetime.date.today()
        for c in unannounced_concerts:
            c.announced = today
        Concert.objects.bulk_update(unannounced_concerts, ['announced'], 100)

    logger.info(f"Sent {sent} recommendation emails")
    return sent
