from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from multiselectfield import MultiSelectFormField
from findshows import email

from findshows.models import Artist, Concert, ConcertTags, UserProfile, Venue
from findshows.widgets import BillWidget, DatePickerField, SocialsLinksWidget, SpotifyArtistSearchWidget, TimePickerField, VenuePickerWidget


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


class UserProfileForm(forms.ModelForm):
    class Meta:
        model=UserProfile
        fields=("favorite_spotify_artists", "weekly_email", "preferred_concert_tags")
        widgets={"favorite_spotify_artists": SpotifyArtistSearchWidget}


class ArtistEditForm(forms.ModelForm):
    class Meta:
        model=Artist
        fields=("name", "profile_picture", "bio", "youtube_links", "socials_links", "listen_links", "similar_spotify_artists")
        widgets={"similar_spotify_artists": SpotifyArtistSearchWidget,
                 "socials_links": SocialsLinksWidget}


class ConcertForm(forms.ModelForm):
    date = DatePickerField()
    doors_time = TimePickerField(required=False)
    start_time = TimePickerField()
    end_time = TimePickerField(required=False)
    bill = forms.JSONField(widget=BillWidget) # NOT a model field, we parse this and save to the artists field through the SetOrder through-model

    class Meta:
        model=Concert
        fields=("poster", "date", "doors_time", "start_time", "end_time", "venue", "ages", "ticket_link", "ticket_description", "tags")
        widgets={"venue": VenuePickerWidget}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.id:
            self.fields['bill'].initial = [{'id': a.pk, 'name': a.name}
                                           for a in self.instance.sorted_artists]
        else:
            self.fields['bill'].initial = []

    def clean(self):
        cleaned_data = super().clean() or {}
        venue = cleaned_data.get("venue")
        date = cleaned_data.get("date")

        if venue and date:
            conflict_concerts = Concert.objects.filter(venue=venue, date=date)
            if self.instance:
                conflict_concerts = conflict_concerts.exclude(pk=self.instance.pk)
            if conflict_concerts:
                raise ValidationError(
                    "There is already a show in the database for the specified venue and date.\
                    If you think this is in error, or there are in fact two events on the same\
                    date, please contact site admins for an override."
                )
        return cleaned_data

    def save(self, commit = True): # saving this without a commit is gonna be weird, hope it doesn't happen
        concert = super().save(commit=False)

        if commit and not concert.id:
            concert.save()

        if concert.id:
            concert.artists.clear()
            for idx, artist_dict in enumerate(self.cleaned_data['bill']):  # Assuming all new artist records have been saved
                concert.artists.add(artist_dict['id'], through_defaults = {'order_number': idx})

        if commit:
            concert.save()

        return concert


class VenueForm(forms.ModelForm):
    prefix = "venue"
    use_required_attribute = False

    class Meta:
        model=Venue
        fields=("name", "address", "ages", "website")


class TempArtistForm(forms.ModelForm):
    prefix = "temp_artist"
    use_required_attribute = False

    class Meta:
        model=Artist
        fields=("name", "local", "temp_email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['temp_email'].required = True

    def save(self, commit = True):
        artist = super().save(commit=False)
        email.invite_artist(artist)

        if commit:
            artist.save()
        return artist


class ShowFinderForm(forms.Form):
    date = DatePickerField()
    spotify_artists = forms.JSONField(widget=SpotifyArtistSearchWidget(is_ids_only=True), initial=list)
    concert_tags = forms.MultipleChoiceField(choices=ConcertTags, widget=forms.CheckboxSelectMultiple)


class ContactForm(forms.Form):
    class Types(models.TextChoices):
        REPORT_BUG = "bug", "Bug report"
        OTHER = "oth", "Other"

    email = forms.EmailField()
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)
    type = forms.ChoiceField(choices=Types)

