from datetime import timedelta
from operator import and_, or_
from functools import reduce
import json
from random import random, shuffle

from django.contrib.auth import login
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.urls import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.utils import timezone
from django.views.generic.dates import timezone_today
from django.conf import settings

from findshows.email import contact_email, invite_artist, invite_user_to_artist, send_artist_setup_info
from findshows.widgets import ArtistAccessWidget

from .models import Artist, ArtistLinkingInfo, Concert, ConcertTags, InviteDelayError, MusicBrainzArtist, Venue
from .forms import ArtistAccessForm, ArtistEditForm, ConcertForm, ContactForm, ModDailyDigestForm, RequestArtistForm, ShowFinderForm, TempArtistForm, UserCreationFormE, UserProfileForm, VenueForm


#################
## User Views ###
#################

def contact(request):
    success = False
    if request.POST:
        form = ContactForm(request.POST)
        if form.is_valid() and contact_email(form):
            success = True
            form = ContactForm()
    else:
        form = ContactForm()

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
        "is_local_artist_account": is_local_artist_account(request.user)
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
            if "sendartistinfo" in request.POST:
                send_artist_setup_info(user.email)
            login(request, user)
            if next:
                return redirect(next)
            else:
                return redirect('findshows:home')

    context = {'user_form': user_form,
               'profile_form': profile_form,
               'next': next,
               }

    return render(request, 'registration/create_account.html', context)

###################
## Artist Views ###
###################

def is_artist_account(user):
    return (not user.is_anonymous
            and len(user.userprofile.managed_artists.all()) > 0)


def is_local_artist_account(user):
    return (not user.is_anonymous
            and any(a.local for a in user.userprofile.managed_artists.all()) > 0)


@user_passes_test(is_artist_account)
def managed_artist_list(request):
    artists=request.user.userprofile.managed_artists.all()
    if len(artists)==1:
        return redirect(reverse('findshows:view_artist', args=[artists[0].pk]))
    return render(request, "findshows/pages/managed_artist_list.html", context = {
        "artists": artists,
    })


def view_artist(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    can_edit = (not request.user.is_anonymous
                and artist in request.user.userprofile.managed_artists.all())

    if artist.is_temp_artist and not can_edit:
        raise PermissionDenied

    upcoming_concerts = artist.concert_set.filter(date__gte=timezone.now())
    upcoming_concerts = upcoming_concerts.exclude(artists__is_temp_artist=True)

    return render(request, "findshows/pages/view_artist.html", context={
        'artist': artist,
        'can_edit': can_edit,
        'upcoming_concerts': upcoming_concerts
    })


@login_required
def edit_artist(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    if artist not in request.user.userprofile.managed_artists.all():
        raise PermissionDenied

    if request.method != 'POST':
        form = ArtistEditForm(instance=artist)
    else:
        form = ArtistEditForm(request.POST, instance=artist)
        if form.is_valid():
            form.save()
            return redirect(reverse('findshows:view_artist', args=[pk]))

    context = {'form': form,
               'pk': pk,
               'is_temp_artist': artist.is_temp_artist}

    return render(request, 'findshows/pages/edit_artist.html', context)


def artist_search_results(request):
    if not (request.GET and request.GET["artist-search"] and request.GET["idx"]):
        return HttpResponse("")

    keywords = request.GET["artist-search"].split()
    idx = int(request.GET["idx"])

    search_results = Artist.objects.filter(
        reduce(and_, (Q(name__icontains=k) for k in keywords))
    )[:5]
    return render(request, "findshows/htmx/artist_search_results.html", {
        "artists": search_results,
        "idx": idx
    })


def create_temp_artist(request):
    if not is_local_artist_account(request.user):
        return HttpResponse('')

    if records_created_today(ArtistLinkingInfo, request.user.userprofile) >= settings.MAX_DAILY_INVITES:
        return render(request, 'findshows/htmx/cant_create_artist.html')

    if (not request.user.userprofile.given_artist_access_datetime or
        request.user.userprofile.given_artist_access_datetime > timezone.now() - timedelta(settings.INVITE_BUFFER_DAYS)):
        return render(request, 'findshows/htmx/cant_create_artist.html', context={'new_account_delay': settings.INVITE_BUFFER_DAYS})

    # The latter condition is a slightly hacky way of telling whether this HTMX
    # request is being triggered by page load (we should provide blank form) or
    # click (we should process form and display errors if they exist)
    if request.POST and 'temp_artist-name' in request.POST:
        form = TempArtistForm(request.POST)
    else:
        form = TempArtistForm()

    valid = form.is_valid()
    if valid:
        artist = form.save(commit=False)
        artist.created_by = request.user.userprofile
        artist.save()
        link_info, invite_code = ArtistLinkingInfo.create_and_get_invite_code(artist, form.cleaned_data['email'], request.user.userprofile)

        if invite_artist(link_info, invite_code, form):
            form = TempArtistForm()
        else:
            link_info.delete()
            artist.delete()
            valid = False

    if records_created_today(ArtistLinkingInfo, request.user.userprofile) >= settings.MAX_DAILY_INVITES:
        response = render(request, 'findshows/htmx/cant_create_artist.html')
    else:
        response = render(request, "findshows/htmx/temp_artist_form.html", {
            "temp_artist_form": form,
        })

    if valid:
        response.headers['HX-Trigger'] = json.dumps({
            "modal-form-success": {
                "created_record_name": artist.name,
                "created_record_id": artist.id}})

    return response


def request_artist_access(request):
    if request.user.is_anonymous:
        raise PermissionDenied
    if is_local_artist_account(request.user):
        return HttpResponse('Something went wrong; you already have local artist access.')

    has_requested = Artist.objects.filter(created_by=request.user.userprofile).count()
    if has_requested:
        return render(request, 'findshows/htmx/cant_request_artist.html')

    # The latter condition is a slightly hacky way of telling whether this HTMX
    # request is being triggered by page load (we should provide blank form) or
    # click (we should process form and display errors if they exist)
    if request.POST and 'request_artist-name' in request.POST:
        form = RequestArtistForm(request.POST)
    else:
        form = RequestArtistForm()

    if form.is_valid():
        artist = form.save(commit=False)
        artist.created_by = request.user.userprofile
        artist.save()
        response = render(request, 'findshows/htmx/cant_request_artist.html')
        response.headers['HX-Trigger'] = json.dumps({
            "modal-form-success": {
                "created_record_name": artist.name,
                "created_record_id": artist.id}})
    else:
        response = render(request, "findshows/htmx/request_artist_form.html", {
            "request_artist_form": form,
        })

    return response


def manage_artist_access(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    if artist not in request.user.userprofile.managed_artists.all():
        raise PermissionDenied

    # TODO: check for number of permission-giving actions

    # The latter condition is a slightly hacky way of telling whether this HTMX
    # request is being triggered by page load (we should provide blank form) or
    # click (we should process form and display errors if they exist)
    if request.POST and 'artist_access-users' in request.POST:
        form = ArtistAccessForm(request.POST)
    else:
        form = ArtistAccessForm.populate_intial(request.user.userprofile, artist)

    if form.is_valid():
        for user_json in form.cleaned_data['users']:
            match user_json['type']:
                case ArtistAccessWidget.Types.NEW.value:
                    if user_json['email'] in [up.user.email for up in artist.managing_users.all()]:
                        form.add_error(None, f"The user {user_json['email']} already has edit access to this artist.")
                        continue
                    if records_created_today(ArtistLinkingInfo, request.user.userprofile) >= settings.MAX_DAILY_INVITES:
                        form.add_error(None, "You have hit your max invites for the day; please try again tomorrow")
                        continue
                    try:
                        link_info, invite_code = ArtistLinkingInfo.create_and_get_invite_code(artist, user_json['email'], request.user.userprofile)
                    except IntegrityError:
                        form.add_error(None, f"The user {user_json['email']} already has an invite to this artist; please use the re-send button instead.")
                        continue
                    except InviteDelayError as e:
                        form.add_error(None, e.message)
                        continue
                    if not invite_user_to_artist(link_info, invite_code, form):
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
                    link_info = ArtistLinkingInfo.objects.get(invited_email=user_json['email'], artist=artist)
                    invite_code = link_info.regenerate_invite_code()
                    invite_user_to_artist(link_info, invite_code, form)
                    # NOT deleting it on email failure even though it's now out of date

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
        response.headers['HX-Trigger'] = json.dumps({"modal-form-success": {}})

    return response


@login_required
def link_artist(request):
    error_template = "findshows/pages/artist_link_failure.html"

    invite_id = request.GET.get('invite_id')
    invite_code = request.GET.get('invite_code')

    if not (invite_id and invite_code):
        return render(request, error_template,
                      {'error': 'Bad invite URL. Make sure you clicked the link in your email or copied it correctly; if this error persists, please contact site admins.'})
    try:
        artist_linking_info = ArtistLinkingInfo.objects.get(id=invite_id)
    except ArtistLinkingInfo.DoesNotExist:
        return render(request, error_template,
                      {'error': 'Could not find invite in the database. Please reach out to the artist or mod who invited you and request they re-send it.'})
    if request.user.email != artist_linking_info.invited_email:
        return render(request, error_template,
                      {'error': "User's email does not match the invited email. Please log back in with an account associated with the email that the invite was sent to, or request a new invite with the correct email."})
    if artist_linking_info.generated_datetime + timedelta(settings.INVITE_CODE_EXPIRATION_DAYS) < timezone.now():
        return render(request, error_template,
                      {'error': "Invite code expired. Please reach out to the artist or mod who invited you and request they re-send it."})
    if not artist_linking_info.check_invite_code(invite_code):
        return render(request, error_template,
                      {'error': "Invite code invalid. Make sure you clicked the link in your email or copied it correctly; if this error persists, please contact site admins."})

    artist = artist_linking_info.artist
    up = request.user.userprofile
    if not up.given_artist_access_by:
        up.given_artist_access_by = artist_linking_info.created_by
        up.given_artist_access_datetime = timezone.now()
        up.save()
    up.managed_artists.add(artist)
    artist_linking_info.delete()

    if artist.is_temp_artist:
        return redirect(reverse('findshows:edit_artist', args=(artist.pk,)))
    else:
        return redirect(reverse('findshows:view_artist', args=(artist.pk,)))


#####################
## Concert Views ####
#####################

def view_concert(request, pk=None):
    concert = get_object_or_404(Concert, pk=pk)

    artists = concert.artists.all()
    if any(a.is_temp_artist for a in artists):
        if request.user.is_anonymous:
            raise PermissionDenied
        if not set(artists) & set(request.user.userprofile.managed_artists.all()):
            raise PermissionDenied

    return render(request, 'findshows/pages/view_concert.html', {'concert': concert})


# Model should subclass CreationTrackingMixin
def records_created_today(model, userprofile):
    records = model.objects.filter(created_by=userprofile, created_at=timezone_today())
    return records.count()


@user_passes_test(is_local_artist_account)
def edit_concert(request, pk=None):
    if pk is None:
        if records_created_today(Concert, request.user.userprofile) >= settings.MAX_DAILY_CONCERT_CREATES:
            return render(request, 'findshows/pages/cant_create_concert.html')
        concert = Concert()
        concert.created_by = request.user.userprofile
    else:
        concert = get_object_or_404(Concert, pk=pk)
        if not concert.created_by == request.user.userprofile:
            raise PermissionDenied

    if request.method != 'POST':
        form = ConcertForm(instance=concert)
    else:
        form = ConcertForm(request.POST, request.FILES, instance=concert)
        form.set_editing_user(request.user)
        if form.is_valid():
            form.save()
            return redirect(reverse('findshows:my_concert_list'))

    context = {'form': form,
               'pk': pk}

    return render(request, 'findshows/pages/edit_concert.html', context)


@user_passes_test(is_artist_account)
def my_concert_list(request):
    artists=request.user.userprofile.managed_artists.all()
    # Remove duplicates in case user manages multiple artists on same bill
    concerts = set(c for a in artists for c in a.concert_set.filter(date__gte=timezone_today()))
    concerts = sorted(concerts, key = lambda c: c.date)

    return render(request, "findshows/pages/concert_list_for_artist.html", context = {
        "concerts": concerts,
        "userprofile": request.user.userprofile,
        "is_local_artist": is_local_artist_account(request.user)
    })


#################
## Venue views ##
#################

def venue_search_results(request):
    if not (request.GET and request.GET["venue-search"]):
        return HttpResponse("")

    keywords = request.GET['venue-search'].split()
    search_results = Venue.objects.filter(
        reduce(and_, (Q(name__icontains=k) for k in keywords))
    )[:5]
    return render(request, "findshows/htmx/venue_search_results.html", {
        "venues": search_results
    })


def create_venue(request):
    if not is_local_artist_account(request.user):
        return HttpResponse('')

    if records_created_today(Venue, request.user.userprofile) >= settings.MAX_DAILY_VENUE_CREATES:
        return render(request, 'findshows/htmx/cant_create_venue.html')

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
                "created_record_name": venue.name,
                "created_record_id": venue.id}})

    return response


#############################
## MusicBrainz search tool ##
#############################


def musicbrainz_artist_search_results(request):
    if not (request.GET and request.GET["mb-search"]):
        return HttpResponse("")

    keywords = request.GET['mb-search'].split()
    mb_artists = MusicBrainzArtist.objects.defer('similar_artists', 'similar_artists_cache_datetime')
    mb_artists = mb_artists.filter(reduce(and_, (Q(name__icontains=k) for k in keywords)))[:10]

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


def concert_search(request):
    if request.GET:
        search_form = ShowFinderForm(request.GET)
    else:
        search_form = ShowFinderForm(initial=get_concert_search_defaults(request))
    return render(request, "findshows/pages/concert_search.html", context = {
        "search_form": search_form,
    })


def concert_search_results(request):
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

    else:
        concerts = []
        searched_musicbrainz_artists = []

    return render(request, "findshows/htmx/concert_search_results.html", context={
        "concerts": concerts,
        "search_form": search_form,
        "searched_musicbrainz_artists": searched_musicbrainz_artists,
    })


#######################
## Moderator views  ###
#######################

def is_mod(user):
    return ((not user.is_anonymous) and user.userprofile.is_mod)


@user_passes_test(is_mod)
def mod_dashboard(request):
    return render(request, "findshows/pages/mod_dashboard.html")


@user_passes_test(is_mod)
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
        'is_admin': request.user.is_staff,
    })


@user_passes_test(is_mod)
def mod_queue(request):
    return render(request, "findshows/htmx/mod_queue.html", context={
        'artists': Artist.objects.filter(is_active_request=True),
        'venues': Venue.objects.filter(is_verified=False),
        'is_admin': request.user.is_staff,
    })


@user_passes_test(is_mod)
def mod_outstanding_invites(request):
    return render(request, "findshows/htmx/mod_outstanding_invites.html", context={
        'artist_linking_infos': ArtistLinkingInfo.objects.all(),
        'is_admin': request.user.is_staff,
    })


@user_passes_test(is_mod)
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


@user_passes_test(is_mod)
def resend_invite(request, pk):
    ali = get_object_or_404(ArtistLinkingInfo, pk=pk)
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


@user_passes_test(is_mod)
def approve_artist_request(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    if not artist.is_active_request:
        success = False
        errorlist = ["This request has already been approved."]
    else:
        errorlist = []
        try:
            ali, invite_code = ArtistLinkingInfo.create_and_get_invite_code(artist, artist.created_by.user.email, request.user.userprofile)
            success = invite_artist(ali, invite_code, errorlist=errorlist)
            if not success:
                ali.delete()
        except IntegrityError:
            errorlist.append(f"The user {artist.created_by.user.email} already has an invite to this artist; please use the re-send button instead.")
            success = False

    if success:
        artist.is_active_request = False
        artist.save()

    return render(request, "findshows/htmx/mod_artist_buttons.html", context={
        'artist': artist,
        'success': success,
        'errors': " ".join(errorlist),
    })
