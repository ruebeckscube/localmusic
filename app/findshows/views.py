from datetime import timedelta
from operator import and_, or_
from functools import reduce
import json
from random import random, shuffle
from pymemcache.client.base import Client

from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.urls import NoReverseMatch, reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Q
from django.utils import timezone
from django.views.generic.dates import timezone_today
from django.conf import settings

from findshows.email import contact_email, invite_artist, invite_user_to_artist, notify_artist_verified, send_verify_email
from findshows.widgets import ArtistAccessWidget

from .models import Artist, ArtistLinkingInfo, ArtistVerificationStatus, Concert, ConcertTags, EmailCodeError, EmailVerification, JPEGImageException, MusicBrainzArtist, User, UserProfile, Venue
from .forms import ArtistAccessForm, ArtistEditForm, ConcertForm, ContactForm, CustomTextFormSet, ModDailyDigestForm, ShowFinderForm, TempArtistForm, UserCreationFormE, UserProfileForm, VenueForm


#################
## User Views ###
#################

def contact(request):
    success = False
    if request.POST:
        form = ContactForm(request.POST)

        if form.is_valid():
            memcache_client = Client(settings.MEMCACHE_LOCATION, timeout=3, connect_timeout=3)
            recent_contacts = memcache_client.incr('num_recent_contacts', 1)
            if recent_contacts is None:
                memcache_client.set('num_recent_contacts', 1, 60, True)
                recent_contacts = 1

            if recent_contacts > settings.MAX_CONTACTS_PER_MINUTE:
                form.add_error(None, "High contact volume; please try again in a minute. This is a spam prevention measure, thanks for understanding.")
            elif contact_email(form):
                success = True
                form = ContactForm()
    else:
        form = ContactForm(initial={'email': request.user.email if not request.user.is_anonymous else None})

    return render(request, "findshows/pages/contact.html", context={
        "form": form,
        "success": success
    })


@login_required
def user_settings(request):
    if request.POST:
        form = UserProfileForm(request.POST, instance=request.user.userprofile)
        if form.is_valid():
            form.save()
            return redirect('findshows:home')
    else:
        form = UserProfileForm(instance=request.user.userprofile)

    return render(request, "findshows/pages/user_settings.html", context={
        "form": form,
    })


def create_account(request):
    if request.method != 'POST':
        user_form = UserCreationFormE()
        profile_form = UserProfileForm()
        next = request.GET.get('next')
    else:
        user_form = UserCreationFormE(request.POST)
        profile_form = UserProfileForm(request.POST)
        next = request.POST.get('next')

        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()

            email_verification, invite_code = EmailVerification.create_and_get_invite_code(user.email)
            if not send_verify_email(email_verification, invite_code, profile_form):
                # Info about verification (failure or otherwise) will be shown
                # to the user in a banner on the home search page
                email_verification.delete()

            login(request, user)

            if next:
                return redirect(next)
            elif "create_artist" in request.POST:
                return redirect('findshows:create_artist')
            else:
                return redirect('findshows:home')

    context = {'user_form': user_form,
               'profile_form': profile_form,
               'next': next,
               }

    return render(request, 'registration/create_account.html', context)


@login_required
def verify_email(request):
    try:
        email_verification = EmailVerification.check_url(request.GET, request.user.email)
    except EmailCodeError as e:
        return render(request, "findshows/pages/email_verification.html",
                      {'error': e.message})

    request.user.userprofile.email_is_verified = True
    request.user.userprofile.save()
    email_verification.delete()

    return render(request, "findshows/pages/email_verification.html")


@login_required
def resend_email_verification(request):
    errorlist = []
    if request.user.userprofile.email_is_verified:
        errorlist.append("Email already verified.")
    else:
        try:
            email_verification = EmailVerification.objects.get(invited_email=request.user.email)
            invite_code = email_verification.regenerate_invite_code()
        except EmailVerification.DoesNotExist:
            email_verification, invite_code = EmailVerification.create_and_get_invite_code(request.user.email)

        if not send_verify_email(email_verification, invite_code, errorlist=errorlist):
            email_verification.delete()

    success = not errorlist

    return render(request, "findshows/htmx/email_verification_banner.html", {
        'success': success,
        'errorlist': errorlist,
    })

###################
## Artist Views ###
###################

@user_passes_test(User.can_see_artist_dashboard)
def artist_dashboard(request):
    artists=request.user.userprofile.managed_artists.all()
    # Remove duplicates in case user manages multiple artists on same bill
    concerts = set(c for a in artists for c in a.concert_set.filter(date__gte=timezone_today()))
    concerts = sorted(concerts, key = lambda c: c.date)
    outstanding_invites = ArtistLinkingInfo.objects.filter(created_by=request.user.userprofile)

    return render(request, "findshows/pages/artist_dashboard.html", context = {
        "artists": artists,
        "concerts": concerts,
        "outstanding_invites": outstanding_invites,
    })


def view_artist(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    is_public = artist.created_by.user.listings_are_public() and (not artist.is_temp_artist)
    if request.user.is_anonymous:
        can_edit = False
        if not is_public:
            raise PermissionDenied
    else:
        can_edit = artist in request.user.userprofile.managed_artists.all()
        if not (is_public or can_edit or request.user.is_mod_or_admin()):
            raise PermissionDenied

    upcoming_concerts = Concert.objects.all() if (can_edit or User.is_mod_or_admin(request.user)) else Concert.publically_visible()
    upcoming_concerts = upcoming_concerts.filter(date__gte=timezone.now(), artists=artist)

    return render(request, "findshows/pages/view_artist.html", context={
        'artist': artist,
        'can_edit': can_edit,
        'upcoming_concerts': upcoming_concerts
    })


def from_link(request, pk=None):
    # Very defensive. If there's a pk in the url we use that, otherwise
    # the pk of the current object (passed in by the calling view). If anything
    # isn't hunky dory, we just default to the Artist Dashboard (or home for non-artist users).
    #
    # The upshot: when linking to an edit page, provide a "from". If you are
    # linking from a different type of object (i.e. View Artist page -> Edit
    # Concert), provide a "from_pk" If you are linking to e.g. the view page of
    # the object being edited, you don't need to provide "from_pk".
    view_name = request.GET.get('from')
    pk = request.GET.get('from_pk') or pk
    if view_name in ('view_artist', 'view_concert'):
        if pk:
            try:
                return reverse(f'findshows:{view_name}', args=[pk])
            except NoReverseMatch:
                pass
    elif view_name in ('artist_dashboard', ):
        return reverse(f'findshows:{view_name}')
    # Defaults
    elif request.user.can_see_artist_dashboard():
        return reverse('findshows:artist_dashboard')
    else:
        return reverse('findshows:home')


@login_required
def edit_artist(request, pk=None):
    profile: UserProfile = request.user.userprofile
    if profile.artist_verification_status == ArtistVerificationStatus.DEVERIFIED:
        # Only status that categorically shouldn't see this page
        raise PermissionDenied

    link_infos = None
    if pk is None: # don't modify pk; we're using it later to check we're in the same flow
        # Check for existing invites for this user before creating new record
        link_infos = ArtistLinkingInfo.objects.filter(invited_email=request.user.email)
        if link_infos:
            artist = link_infos[0].artist
        else:
            artist = Artist(local=True)
        artist.created_by = profile # This is also necessary for the invite situation because it was previously set to the person who rceated the invite.
    else:
        artist = get_object_or_404(Artist, pk=pk)
        if artist not in profile.managed_artists.all() and not request.user.is_staff:
            raise PermissionDenied

    if request.method != 'POST':
        form = ArtistEditForm(instance=artist)
    else:
        form = ArtistEditForm(request.POST, request.FILES, instance=artist)
        if not profile.email_is_verified:
            form.add_error(None, "Please verify your email before submitting. Click the link in the email you've received; if it's not in your inbox, please check spam.")
        elif form.is_valid():
            try:
                saved_artist = form.save()
                if not pk:
                    profile.managed_artists.add(saved_artist)
                if not profile.artist_verification_status:
                    if link_infos:
                        profile.given_artist_access_by = link_infos[0].created_by
                        profile.artist_verification_status = ArtistVerificationStatus.INVITED
                    else:
                        profile.artist_verification_status = ArtistVerificationStatus.UNVERIFIED
                    profile.save()
                return redirect(reverse('findshows:view_artist', args=[saved_artist.pk]))
            except JPEGImageException as e:
                form.add_error('profile_picture', e.message)

    context = {'form': form,
               'pk': artist.pk,
               'cancel_link': from_link(request, artist.pk),
               'is_temp_artist': artist.is_temp_artist}

    return render(request, 'findshows/pages/edit_artist.html', context)


def artist_search_results(request):
    # there are multiple artist search fields on the bill widget; idx is the index of the search field
    if not (request.GET and request.GET.get("artist-search") and request.GET.get("idx")):
        return HttpResponse("")

    keywords = request.GET["artist-search"].split()
    try:
        idx = int(request.GET["idx"])
    except ValueError:
        return HttpResponse("")

    search_results = Artist.objects.filter(reduce(and_, (Q(name__icontains=k) for k in keywords))
    ).exclude(created_by__artist_verification_status=ArtistVerificationStatus.DEVERIFIED
    )[:5]
    return render(request, "findshows/htmx/artist_search_results.html", {
        "artists": search_results,
        "idx": idx
    })


@login_required
def create_temp_artist(request):
    permissions_msg = ""
    if not (request.user.is_local_artist_account() or request.user.is_mod):
        permissions_msg = "You must have a local artist account to invite an artist to the platform."
    elif not request.user.userprofile.email_is_verified:
        permissions_msg = "Please verify your email before inviting artists."
    elif request.user.has_exceeded_daily_invites():
        permissions_msg = "You've hit the daily limit for inviting artists; please try again in 24 hours."
    if permissions_msg:
        return render(request, 'findshows/htmx/modal_error_msg.html', {'message': permissions_msg})

    # The latter condition is a slightly hacky way of telling whether this HTMX
    # request is being triggered by page load (we should provide blank form) or
    # click (we should process form and display errors if they exist)
    if request.POST and 'temp_artist-name' in request.POST:
        form = TempArtistForm(request.POST)
    else:
        form = TempArtistForm()

    success_text = "Invite sent successfully!"
    valid = form.is_valid()
    if valid:
        artist = form.save(commit=False)
        artist.created_by = request.user.userprofile
        artist.save()
        link_info, invite_code = ArtistLinkingInfo.create_and_get_invite_code(artist, form.cleaned_data['email'], request.user.userprofile)

        if request.user.userprofile.artist_verification_status == ArtistVerificationStatus.UNVERIFIED:
            success_text = "Invite has been registered and will be sent once your profile is verified by mods."
        elif invite_artist(link_info, invite_code, form): # this sends invite and returns success
            form = TempArtistForm()
        else:
            link_info.delete()
            artist.delete()
            valid = False

    if request.user.has_exceeded_daily_invites():
        response = render(request, 'findshows/htmx/modal_error_msg.html')
    else:
        response = render(request, "findshows/htmx/temp_artist_form.html", {
            "temp_artist_form": form,
        })

    if valid:
        response.headers['HX-Trigger'] = json.dumps({
            "modal-form-success": {
                "success_text": success_text,
                "created_record_name": artist.name,
                "created_record_id": artist.id}})

    return response


@login_required
def manage_artist_access(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    if (artist not in request.user.userprofile.managed_artists.all()) and not request.user.is_staff:
        raise PermissionDenied

    # The latter condition is a slightly hacky way of telling whether this HTMX
    # request is being triggered by page load (we should provide blank form) or
    # click (we should process form and display errors if they exist)
    if request.POST and 'artist_access-users' in request.POST:
        form = ArtistAccessForm(request.POST)
    else:
        form = ArtistAccessForm.populate_intial(request.user.userprofile, artist)

    success_text = "Artist access saved!"
    if form.is_valid():
        for user_json in form.cleaned_data['users']:
            match user_json['type']:
                case ArtistAccessWidget.Types.NEW.value:
                    if user_json['email'] in [up.user.email for up in artist.managing_users.all()]:
                        form.add_error(None, f"The user {user_json['email']} already has edit access to this artist.")
                        continue
                    if request.user.has_exceeded_daily_invites():
                        form.add_error(None, "You have reached your max invites for the day; please try again tomorrow")
                        continue
                    try:
                        link_info, invite_code = ArtistLinkingInfo.create_and_get_invite_code(artist, user_json['email'], request.user.userprofile)
                    except IntegrityError:
                        form.add_error(None, f"The user {user_json['email']} already has an invite to this artist; please use the re-send button instead.")
                        continue
                    if request.user.userprofile.artist_verification_status == ArtistVerificationStatus.UNVERIFIED:
                        success_text = "Artist access saved! Invite emails will be sent once your artist profile is verified by mods."
                    elif not invite_user_to_artist(link_info, invite_code, form):
                        # invite_user_to_artist adds error to form
                        link_info.delete()
                case ArtistAccessWidget.Types.REMOVED.value:
                    user_profiles = artist.managing_users.filter(user__email=user_json['email'])
                    for u in user_profiles: # Should only be one, but may as well
                        u.managed_artists.remove(artist)
                    link_infos = ArtistLinkingInfo.objects.filter(invited_email=user_json['email'], artist=artist)
                    for ali in link_infos:
                        ali.delete()
                case ArtistAccessWidget.Types.RESEND.value:
                    # NOT deleting it on email failure even though it's now out of date
                    if request.user.userprofile.artist_verification_status == ArtistVerificationStatus.UNVERIFIED:
                        success_text = "Artist access saved! Invite emails will be sent once your artist profile is verified by mods."
                    else:
                        link_info = ArtistLinkingInfo.objects.get(invited_email=user_json['email'], artist=artist)
                        invite_code = link_info.regenerate_invite_code()
                        invite_user_to_artist(link_info, invite_code, form)

        partial_errors = form.non_field_errors  # added explicitly here or by the email functions
        all_success = not partial_errors()
        form = ArtistAccessForm.populate_intial(request.user.userprofile, artist)
    else:
        all_success = False
        partial_errors = None


    response = render(request, "findshows/htmx/artist_access_form.html", {
        "artist_access_form": form,
        "partial_errors": partial_errors
    })

    if all_success:
        response.headers['HX-Trigger'] = json.dumps({"modal-form-success": {
            "success_text": success_text,
        }})

    return response


@login_required
def link_artist(request):
    try:
        artist_linking_info = ArtistLinkingInfo.check_url(request.GET, request.user.email)
    except EmailCodeError as e:
        return render(request, "findshows/pages/artist_link_failure.html",
                      {'error': e.message})

    artist = artist_linking_info.artist
    up = request.user.userprofile
    if not up.artist_verification_status:
        if artist_linking_info.created_by.user.is_mod_or_admin():
            up.artist_verification_status = ArtistVerificationStatus.VERIFIED
        else:
            up.artist_verification_status = ArtistVerificationStatus.INVITED
    if not up.given_artist_access_by:
        up.given_artist_access_by = artist_linking_info.created_by
        up.given_artist_access_datetime = timezone.now()
    up.save()
    up.managed_artists.add(artist)
    artist_linking_info.delete()

    if artist.is_temp_artist:
        artist.created_by = up
        artist.save()
        return redirect(reverse('findshows:edit_artist', args=(artist.pk,)))
    else:
        return redirect(reverse('findshows:view_artist', args=(artist.pk,)))


#####################
## Concert Views ####
#####################

def view_concert(request, pk=None):
    concert = get_object_or_404(Concert, pk=pk)

    artists = concert.artists.all()
    if (not concert.created_by.user.listings_are_public()) or any(a.is_temp_artist for a in artists):
        if request.user.is_anonymous:
            raise PermissionDenied
        elif request.user.is_mod_or_admin():
            pass
        elif not set(artists) & set(request.user.userprofile.managed_artists.all()):
            raise PermissionDenied

    return render(request, 'findshows/pages/view_concert.html', {'concert': concert})


@user_passes_test(User.is_local_artist_or_admin)
def edit_concert(request, pk=None):
    if pk is None:
        if request.user.userprofile.records_created_today(Concert) >= settings.MAX_DAILY_CONCERT_CREATES:
            return render(request, 'findshows/pages/cant_create_concert.html')
        concert = Concert()
        concert.created_by = request.user.userprofile
    else:
        concert = get_object_or_404(Concert, pk=pk)
        if not concert.created_by == request.user.userprofile and not request.user.is_staff:
            raise PermissionDenied

    if request.method != 'POST':
        form = ConcertForm(instance=concert)
    else:
        form = ConcertForm(request.POST, request.FILES, instance=concert)
        form.set_editing_user(request.user)
        if not request.user.userprofile.email_is_verified:
            form.add_error(None, "Please verify your email before submitting.")
        elif form.is_valid():
            try:
                concert = form.save()
                return redirect(reverse('findshows:view_concert', args=[concert.pk]))
            except JPEGImageException as e:
                form.add_error('poster', e.message)

    context = {'form': form,
               'cancel_link': from_link(request, pk),
               'pk': pk}

    return render(request, 'findshows/pages/edit_concert.html', context)


@user_passes_test(User.is_local_artist_or_admin)
def cancel_concert(request, pk, uncancel=False):
    concert = get_object_or_404(Concert, pk=pk)
    if (not concert.created_by == request.user.userprofile) and not request.user.is_staff:
        raise PermissionDenied

    error = ""
    if uncancel:
        conflict_concerts = Concert.objects.filter(venue=concert.venue, date=concert.date).exclude(cancelled=True)
        conflict_concerts = conflict_concerts.exclude(pk=pk)
        if conflict_concerts.count():
            error = "Can't uncancel; there is another concert at this venue on this date"

    if not error:
        concert.cancelled = not uncancel
        concert.save()

    return render(request, "findshows/htmx/cancel_concert_button.html", context = {
        "concert": concert,
        "error": error,
    })


#################
## Venue views ##
#################

def venue_search_results(request):
    if not (request.GET and request.GET.get("venue-search")):
        return HttpResponse("")

    keywords = request.GET['venue-search'].split()
    search_results = Venue.objects.filter(
        reduce(and_, (Q(name__icontains=k) for k in keywords))
    )[:5]
    return render(request, "findshows/htmx/venue_search_results.html", {
        "venues": search_results
    })


@user_passes_test(User.is_local_artist_or_admin)
def create_venue(request):
    permissions_msg = ""
    if not request.user.userprofile.email_is_verified:
        permissions_msg = "Please verify your email before creating a venue listing."
    elif request.user.userprofile.records_created_today(Venue) >= settings.MAX_DAILY_VENUE_CREATES:
        permissions_msg = "You've hit the daily limit for creating venues;please try again in 24 hours or contact an admin if it's urgent."
    if permissions_msg:
        return render(request, 'findshows/htmx/modal_error_msg.html', {'message': permissions_msg})

    # The latter condition is a slightly hacky way of telling whether this HTMX
    # request is being triggered by page load (we should provide blank form) or
    # click (we should process form and display errors if they exist)
    if request.POST and 'venue-name' in request.POST:
        venue_form = VenueForm(request.POST)
    else:
        venue_form = VenueForm()

    valid = venue_form.is_valid()
    if valid:
        venue = venue_form.save(commit=False)
        venue.created_by = request.user.userprofile
        venue.save()
        venue_form = VenueForm()

    response = render(request, "findshows/htmx/venue_form.html", {
        "venue_form": venue_form,
    })

    if valid:
        response.headers['HX-Trigger'] = json.dumps({
            "modal-form-success": {
                "success_text": "Venue created successfully!",
                "created_record_name": venue.name,
                "created_record_id": venue.id}})

    return response


#############################
## MusicBrainz search tool ##
#############################


def musicbrainz_artist_search_results(request):
    if not (request.GET and request.GET.get("mb_search")):
        return HttpResponse("")

    q = request.GET['mb_search']
    mb_artists = MusicBrainzArtist.objects.defer('similar_artists', 'similar_artists_cache_datetime')
    mb_artists = mb_artists.annotate(similarity=TrigramSimilarity('name', q)
                                     ).filter(name__fuzzy_index=q).order_by('-similarity')[:10]

    return render(request, "findshows/htmx/musicbrainz_artist_search_results.html", {
        "musicbrainz_artists": mb_artists
    })


#######################
## Main Search page ###
#######################

def get_concert_search_defaults(request):
    defaults = {'date': timezone_today,
                'end_date': timezone_today,
                'is_date_range': False,
                'concert_tags': [t.value for t in ConcertTags]}
    if request.user and hasattr(request.user, 'userprofile'):
        defaults['musicbrainz_artists'] = request.user.userprofile.favorite_musicbrainz_artists.all()
        defaults['concert_tags'] = request.user.userprofile.preferred_concert_tags
    return defaults


def home(request):
    if request.GET:
        search_form = ShowFinderForm(request.GET)
    else:
        search_form = ShowFinderForm(initial=get_concert_search_defaults(request))
    return render(request, "findshows/pages/home.html", context = {
        "search_form": search_form,
    })


def concert_search(request):
    if request.GET:
        search_form = ShowFinderForm(request.GET)
    else:
        search_form = ShowFinderForm()

    if search_form.is_valid():
        concerts = Concert.publically_visible()
        if search_form.cleaned_data['is_date_range']:
            concerts = concerts.filter(date__gte=search_form.cleaned_data['date'],
                                       date__lte=search_form.cleaned_data['end_date'])
        else:
            concerts = concerts.filter(date=search_form.cleaned_data['date'])

        if search_form.cleaned_data['concert_tags']: # no concert tags = all concert tags
            concerts = concerts.filter(reduce(or_, (Q(tags__icontains=t) for t in search_form.cleaned_data['concert_tags'])))

        searched_musicbrainz_artists = search_form.cleaned_data.get('musicbrainz_artists', [])
        concerts = list(concerts)
        searched_mbids = [mb_artist.mbid for mb_artist in search_form.cleaned_data['musicbrainz_artists']]
        if len(searched_mbids) > 0:
            concerts = sorted(concerts,
                              key=lambda c: (c.relevance_score(searched_mbids), random()),
                              reverse=True)
        else:
            shuffle(concerts)

        search_form = ShowFinderForm(initial=search_form.cleaned_data)

    else:
        concerts = []
        searched_musicbrainz_artists = []

    return render(request, "findshows/htmx/concert_search.html", context={
        "concerts": concerts,
        "search_form": search_form,
        "searched_musicbrainz_artists": searched_musicbrainz_artists,
    })


#######################
## Moderator views  ###
#######################

@user_passes_test(User.is_mod_or_admin)
def mod_dashboard(request):
    return render(request, "findshows/pages/mod_dashboard.html", context={
        'query': {
            'date': request.GET.get('date') if request.GET else None,
        },
        'tabs': [
            {'name': 'actionRequired', 'url_name': 'findshows:mod_queue', 'label': 'Action required'},
            {'name': 'dailyDigest', 'url_name': 'findshows:mod_daily_digest', 'label': 'Daily digest'},
            {'name': 'outstandingInvites', 'url_name': 'findshows:mod_outstanding_invites', 'label': 'Outstanding invites'},
            {'name': 'customTexts', 'url_name': 'findshows:mod_text_customization', 'label': 'Text customization'},
        ]
    })


@user_passes_test(User.is_mod_or_admin)
def mod_daily_digest(request):
    if request.GET:
        form = ModDailyDigestForm(request.GET)
    else:
        form = ModDailyDigestForm(initial={'date': timezone_today})

    date = form.cleaned_data['date'] if form.is_valid() else timezone_today()

    return render(request, "findshows/htmx/mod_daily_digest.html", context={
        'form': form,
        'artists': Artist.objects.filter(created_at=date),
        'concerts': Concert.objects.filter(created_at=date),
        'venues': Venue.objects.filter(created_at=date),
    })


@user_passes_test(User.is_mod_or_admin)
def mod_queue(request):
    return render(request, "findshows/htmx/mod_queue.html", context={
        'unverified_user_profiles': UserProfile.objects.filter(artist_verification_status=ArtistVerificationStatus.UNVERIFIED),
        'venues': Venue.objects.filter(is_verified=False),
    })


@user_passes_test(User.is_mod_or_admin)
def mod_outstanding_invites(request):
    return render(request, "findshows/htmx/mod_outstanding_invites.html", context={
        'artist_linking_infos': ArtistLinkingInfo.objects.all(),
    })


@user_passes_test(User.is_mod_or_admin)
def mod_text_customization(request):
    saved = False
    if request.POST:
        formset = CustomTextFormSet(request.POST)
        if formset.is_valid():
            formset.save()
            saved = True
    else:
        formset = CustomTextFormSet()
    return render(request, "findshows/htmx/mod_text_customization.html", context={
        'formset': formset,
        'saved': saved,
    })


@user_passes_test(User.is_mod_or_admin)
def venue_verification(request, pk):
    venue = get_object_or_404(Venue, pk=pk)
    match request.POST.get('action'):
        case 'verify':
            venue.is_verified = True
        case 'decline':
            venue.is_verified = True
            venue.declined_listing = True
    venue.save()
    return render(request, "findshows/htmx/venue_verification.html", context={
        'venue': venue,
    })


@user_passes_test(User.is_mod_or_admin)
def artist_verification_buttons(request, pk):
    userprofile = get_object_or_404(UserProfile, pk=pk)
    invite_errors = {}
    match request.POST.get('action'):
        case 'verify':
            userprofile.artist_verification_status = ArtistVerificationStatus.VERIFIED
            userprofile.given_artist_access_by = request.user.userprofile
            userprofile.given_artist_access_datetime = timezone.now()
            for link_info in ArtistLinkingInfo.objects.filter(created_by=userprofile):
                invite_code = link_info.regenerate_invite_code()
                errors = []
                if not invite_artist(link_info, invite_code, errorlist=errors):
                    invite_errors[link_info.invited_email] = errors
            notify_artist_verified(userprofile)

        case 'deverify':
            userprofile.artist_verification_status = ArtistVerificationStatus.DEVERIFIED
        case 'notlocal':
            userprofile.artist_verification_status = ArtistVerificationStatus.NOT_LOCAL
    userprofile.save()

    return render(request, "findshows/htmx/artist_verification_buttons.html", context={
        'userprofile': userprofile,
        'invite_errors': invite_errors,
    })


@user_passes_test(User.is_local_artist_or_mod_or_admin)
def resend_invite(request, pk):
    ali = get_object_or_404(ArtistLinkingInfo, pk=pk)
    if (not request.user.is_mod_or_admin()) and (ali.created_by != request.user.userprofile):
        raise PermissionDenied
    if ali.generated_datetime > timezone.now() - timedelta(minutes=5):
        success = False
        errorlist = ["Please wait at least five minutes before sending again."]
    else:
        invite_code = ali.regenerate_invite_code()
        errorlist = []
        success = invite_artist(ali, invite_code, errorlist=errorlist)
    return render(request, "findshows/htmx/mod_resend_invite_button.html", context={
        'ali': ali,
        'success': success,
        'errors': " ".join(errorlist),
    })
