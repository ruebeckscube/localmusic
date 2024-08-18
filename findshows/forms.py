from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from findshows.models import Artist, Concert, UserProfile
from findshows.widgets import DatePickerField, DatePickerWidget, SocialsLinksWidget, SpotifyArtistSearchWidget, TimePickerField


class UserCreationFormE(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')

        if User.objects.filter(email=email).exists():
            msg = 'A user with that email already exists.'
            self.add_error('email', msg)

        return self.cleaned_data

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class UserProfileCreationForm(forms.ModelForm):
    class Meta:
        model=UserProfile
        fields=("favorite_spotify_artists", "weekly_email")
        widgets={"favorite_spotify_artists": SpotifyArtistSearchWidget}


class ArtistEditForm(forms.ModelForm):
    class Meta:
        # TODO: should bands be able to edit their local status? if not how is it set?
        model=Artist
        fields=("name", "profile_picture", "bio", "youtube_links", "socials_links", "listen_links", "similar_spotify_artists")
        widgets={"similar_spotify_artists": SpotifyArtistSearchWidget,
                 "socials_links": SocialsLinksWidget}


class ConcertForm(forms.ModelForm):
    date = DatePickerField()
    doors_time = TimePickerField(required=False)
    start_time = TimePickerField()
    end_time = TimePickerField(required=False)

    class Meta:
        model=Concert
        fields=("poster", "date", "doors_time", "start_time", "end_time", "venue", "ages", "artists", "ticket_link")


class ShowFinderForm(forms.Form):
    date = DatePickerField()
    spotify_artists = forms.fields.JSONField(widget=SpotifyArtistSearchWidget, initial=list)
