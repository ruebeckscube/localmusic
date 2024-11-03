from operator import and_, or_
from functools import reduce
import json

from django.contrib.auth import login
from django.core.mail import send_mail
from django.urls import reverse
from django.views import generic
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.utils import timezone
from django.views.generic.dates import timezone_today

from findshows.email import contact_email

from .models import Artist, Concert, ConcertTags, Venue
from .forms import ArtistEditForm, ConcertForm, ContactForm, ShowFinderForm, TempArtistForm, UserCreationFormE, UserProfileForm, VenueForm
from .spotify import search_spotify_artists
from findshows import spotify


#################
## User Views ###
#################

def get_concert_search_defaults(request):
    defaults = {'date': timezone_today,
                'end_date': timezone_today,
                'is_date_range': False,
                'concert_tags': [t.value for t in ConcertTags]}
    if request.user and hasattr(request.user, 'userprofile'):
        defaults['spotify_artists'] = [a['id'] for a in request.user.userprofile.favorite_spotify_artists]
        defaults['concert_tags'] = request.user.userprofile.preferred_concert_tags
    return defaults


def home(request):
    return render(request, "findshows/pages/home.html", context={
        "search_form": ShowFinderForm(initial=get_concert_search_defaults(request))
    })


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
    user_profile = request.user.userprofile
    if request.POST:
        form = UserProfileForm(request.POST, instance=user_profile)
        if form.is_valid():
            form.save()
            return redirect('findshows:home')
    else:
        form = UserProfileForm(instance=user_profile)

    return render(request, "findshows/pages/user_settings.html", context={
        "form": form
    })


def create_account(request):
    if request.method != 'POST':
        user_form = UserCreationFormE()
        profile_form = UserProfileForm()
    else:
        user_form = UserCreationFormE(request.POST)
        profile_form = UserProfileForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            if "sendartistinfo" in request.POST:
                send_mail(
                    "Make an Artist page on Chicago Local Music",
                    "this will be a link to create an artist account linked to user",
                    "admin@chicagolocalmusic.com",
                    [user.email],
                    fail_silently=False,
                )
            login(request, user)
            return redirect('findshows:home')

    context = {'user_form': user_form,
               'profile_form': profile_form,
               }

    return render(request, 'registration/create_account.html', context)

###################
## Artist Views ###
###################

def is_artist_account(user):
    return (not user.is_anonymous
            and len(user.userprofile.managed_artists.all()) > 0)


@user_passes_test(is_artist_account)
def managed_artist_list(request):
    artists=request.user.userprofile.managed_artists.all()
    if len(artists)==1:
        return redirect(reverse('findshows:view_artist', args=[artists[0].pk]))
    return render(request, "findshows/pages/managed_artist_list.html", context = {
        "artists": artists,
    })


class ArtistView(generic.DetailView):
    model = Artist
    template_name = "findshows/pages/view_artist.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["can_edit"] = (not self.request.user.is_anonymous
                               and self.object in self.request.user.userprofile.managed_artists.all())
        context["spotify_artists"] = self.get_object().similar_spotify_artists
        context["upcoming_concerts"] = self.get_object().concert_set.filter(date__gt=timezone.now())

        return context


@login_required
def edit_artist(request, pk):
    artist = get_object_or_404(Artist, pk=pk)
    if artist not in request.user.userprofile.managed_artists.all():
        return redirect("/accounts/login/?next=%s" % request.path)

    if request.method != 'POST':
        form = ArtistEditForm(instance=artist)
    else:
        form = ArtistEditForm(request.POST, instance=artist)
        if form.is_valid():
            form.save()
            return redirect(reverse('findshows:view_artist', args=[pk]))

    context = {'form': form,
               'pk': pk }

    return render(request, 'findshows/pages/edit_artist.html', context)


#####################
## Concert Views ####
#####################

def view_concert(request, pk=None):
    concert = get_object_or_404(Concert, pk=pk)
    return render(request, 'findshows/pages/view_concert.html', {'concert': concert})


@login_required
def edit_concert(request, pk=None):
    if pk is None:
        concert = Concert()
    else:
        concert = get_object_or_404(Concert, pk=pk)

    if request.method != 'POST':
        form = ConcertForm(instance=concert)
    else:
        form = ConcertForm(request.POST, request.FILES, instance=concert)
        if form.is_valid():
            form.save()
            return redirect(reverse('findshows:my_concert_list'))

    context = {'form': form,
               'pk': pk}

    return render(request, 'findshows/pages/edit_concert.html', context)


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
    venue_form = VenueForm(request.POST)
    valid = venue_form.is_valid()
    if valid:
        venue = venue_form.save()
        venue_form = VenueForm()

    response = render(request, "findshows/htmx/venue_form.html", {
        "venue_form": venue_form,
    })

    if valid:
        response.headers['HX-Trigger'] = json.dumps({
            "successfully-created-venue": {
                "created_venue_name": venue.name,
                "created_venue_id": venue.id}})

    return response


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
    temp_artist_form = TempArtistForm(request.POST)
    valid = temp_artist_form.is_valid()
    if valid:
        artist = temp_artist_form.save()
        temp_artist_form = TempArtistForm()

    response = render(request, "findshows/htmx/temp_artist_form.html", {
        "temp_artist_form": temp_artist_form,
    })

    if valid:
        response.headers['HX-Trigger'] = json.dumps({
            "successfully-created-temp-artist": {
                "created_temp_artist_name": artist.name,
                "created_temp_artist_id": artist.id}})

    return response


@user_passes_test(is_artist_account)
def my_concert_list(request):
    artists=request.user.userprofile.managed_artists.all()
    concerts=set(c for a in artists for c in a.concert_set.all()) # Set removes duplicates
    return render(request, "findshows/pages/concert_list_for_artist.html", context = {
        "concerts": concerts,
    })


#########################
## Spotify search tool ##
#########################


def spotify_artist_search_results(request):
    query = request.GET['spotify-search']
    if not query:
        return HttpResponse(b'')

    search_results = search_spotify_artists(query)

    return render(request, "findshows/htmx/spotify_artist_search_results.html", {
        "spotify_artists": search_results
    })



#######################
## Main Search page ###
#######################

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
        artists_and_relateds = { id: spotify.get_related_spotify_artists(id)
                                 for id in search_form.cleaned_data['spotify_artists']}
        concerts = Concert.objects.filter(reduce(or_, (Q(tags__icontains=t) for t in search_form.cleaned_data['concert_tags'])))
        if search_form.cleaned_data['is_date_range']:
            concerts = concerts.filter(date__gte=search_form.cleaned_data['date'])
            concerts = concerts.filter(date__lte=search_form.cleaned_data['end_date'])
        else:
            concerts = concerts.filter(date=search_form.cleaned_data['date'])
        concerts = sorted(concerts,
                          key=lambda c: c.relevance_score(artists_and_relateds),
                          reverse=True)
    else:
        concerts = []

    return render(request, "findshows/htmx/concert_search_results.html", context = {
        "concerts": concerts,
    })
