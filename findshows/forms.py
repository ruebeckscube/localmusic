from datetime import timedelta
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import models
from django.views.generic.dates import timezone_today
from django.conf import settings

from findshows.models import Artist, Concert, ConcertTags, MusicBrainzArtist, UserProfile, Venue
from findshows.widgets import ArtistAccessWidget, BillWidget, DatePickerField, DatePickerWidget, SocialsLinksWidget, MusicBrainzArtistSearchWidget, TimePickerField, VenuePickerWidget

class UserCreationFormE(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "password1", "password2")
        labels = {
            "username": "Email"
        }

    def clean_username(self):
        # Enforce username-as-email
        username = super().clean_username()
        if not username:
            return username

        EmailValidator()(username)
        if User.objects.filter(email=username).exists(): # This should be redundant, but might as well be careful
            raise ValidationError('A user with that email already exists.')
        return username

    def save(self, commit=True):
        user = super(UserCreationForm, self).save(commit=False)
        user.email = self.cleaned_data["username"]
        if commit:
            user.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model=UserProfile
        fields=("favorite_musicbrainz_artists", "weekly_email", "preferred_concert_tags")
        widgets={"favorite_musicbrainz_artists": MusicBrainzArtistSearchWidget}


class ArtistEditForm(forms.ModelForm):
    class Meta:
        model=Artist
        fields=("name", "profile_picture", "bio", "youtube_links", "socials_links", "listen_links", "similar_musicbrainz_artists")
        widgets={"similar_musicbrainz_artists": MusicBrainzArtistSearchWidget,
                 "socials_links": SocialsLinksWidget}

    def save(self, commit = True):
        artist = super().save(commit=False)
        artist.is_temp_artist = False
        if commit:
            artist.save()
            self.save_m2m()
        return artist


class ConcertForm(forms.ModelForm):
    date = DatePickerField()
    doors_time = TimePickerField(required=False)
    start_time = TimePickerField()
    end_time = TimePickerField(required=False)
    # NOT a model field, we parse this and save to the artists field through the SetOrder through-model
    bill = forms.JSONField(widget=BillWidget, help_text="""The artists will be
    listed in the order they're entered; the artist performing first should be
    at the bottom of the bill and the artist performing last should be at the
    top of the bill. If the artist does not already have a profile, invite them
    to create one with the Invite Artist button.""")

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

    def set_editing_user(self, user):
        self.editing_user = user


    def clean_venue(self):
        venue = self.cleaned_data['venue']
        if venue.declined_listing:
            self.add_error('venue', 'You cannot list a show at a venue that has declined listings.')
        return venue


    def clean(self):
        cleaned_data = super().clean() or {}

        local_user_artists = set(str(a.id)
                                 for a in self.editing_user.userprofile.managed_artists.all()
                                 if a.local)
        if not local_user_artists.intersection(str(a['id']) for a in cleaned_data['bill']):
            self.add_error('bill',
                           "You may only post shows where the bill includes one of the local artists \
                           that your account manages.")

        venue = cleaned_data.get("venue")
        date = cleaned_data.get("date")
        if venue and date:
            conflict_concerts = Concert.objects.filter(venue=venue, date=date)
            if self.instance:
                conflict_concerts = conflict_concerts.exclude(pk=self.instance.pk)
            if conflict_concerts:
                self.add_error(None,
                               "There is already a show in the database for the specified venue and date.\
                               If you think this is in error, or there are in fact two events on the same\
                               date, please contact site admins for an override.")
        return cleaned_data

    def save(self, commit = True): # saving this without a commit is gonna be weird, hope it doesn't happen
        concert = super().save(commit=False)

        if commit and not concert.id:
            concert.save()

        if concert.id:
            concert.artists.clear()
            for idx, artist_dict in enumerate(self.cleaned_data['bill']):  # Assuming all new artist records have been saved
                if artist_dict['id']:
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


class ArtistAccessForm(forms.Form):
    users = forms.JSONField(widget=ArtistAccessWidget, required=False)
    prefix = "artist_access"


    @classmethod
    def populate_intial(cls, current_user_profile, artist):
        form = cls()
        form.fields['users'].initial = [
            {'email': user_profile.user.email, 'type': ArtistAccessWidget.Types.LINKED.value}
            for user_profile in artist.managing_users.all()
            if user_profile != current_user_profile
        ]
        form.fields['users'].initial.extend(
            {'email': ali.invited_email, 'type': ArtistAccessWidget.Types.UNLINKED.value}
            for ali in artist.artistlinkinginfo_set.all()
        )
        return form

    @classmethod
    def user_json_has_valid_email(cls, user_json):
        try:
            EmailValidator()(user_json['email'])
        except ValidationError:
            return False
        return True


    def clean_users(self):
        invalid_emails = ','.join(u['email']
                                  for u in self.cleaned_data['users']
                                  if not self.user_json_has_valid_email(u))
        if invalid_emails:
            self.add_error(None,
                           f"The following email addresses are invalid: {invalid_emails}; please remove them and re-enter.")
        return self.cleaned_data['users']


class TempArtistForm(forms.ModelForm):
    prefix = "temp_artist"
    use_required_attribute = False
    email=forms.EmailField(required=True, help_text="Please check with the artist you're inviting and and use a personal email rather than a band email. This is the address they will need to make an account with.")

    class Meta:
        model=Artist
        fields=("name", "local")

    def save(self, commit = True):
        artist = super().save(commit=False)
        artist.is_temp_artist = True
        if commit:
            artist.save()
        return artist


class RequestArtistForm(forms.ModelForm):
    prefix = "request_artist"
    use_required_attribute = False

    class Meta:
        model=Artist
        fields=("name", "socials_links")
        widgets={"similar_musicbrainz_artists": MusicBrainzArtistSearchWidget,
                 "socials_links": SocialsLinksWidget(num_links=1)}

    def save(self, commit = True):
        artist = super().save(commit=False)
        artist.is_temp_artist = True
        artist.is_active_request = True
        artist.local = True
        if commit:
            artist.save()
        return artist


class ShowFinderForm(forms.Form):
    date = DatePickerField()
    end_date = DatePickerField(required=False)
    is_date_range = forms.BooleanField(required=False)
    musicbrainz_artists = forms.ModelMultipleChoiceField(queryset=MusicBrainzArtist.objects.all(),
                                                         widget=MusicBrainzArtistSearchWidget,
                                                         required=False)
    concert_tags = forms.MultipleChoiceField(choices=ConcertTags,
                                             widget=forms.CheckboxSelectMultiple,
                                             required=False)

    def clean(self):
        cleaned_data = super().clean() or {}
        today = timezone_today()
        if cleaned_data.get('is_date_range'):
            start_date, end_date = cleaned_data.get("date"), cleaned_data.get("end_date")
            if not end_date:
                self.add_error('end_date',
                    "Please enter an end date, or hide date range."
                )
            elif end_date < today:
                self.add_error('end_date',
                    "End date is in the past. Please select a valid date."
                )
            elif start_date and start_date > end_date:
                self.add_error(None,
                    "Please enter a date range with the end date after the start date."
                )
            elif start_date and end_date-start_date > timedelta(settings.MAX_DATE_RANGE):
                self.add_error(None,
                    "Max date range is " + str(settings.MAX_DATE_RANGE) + " days."
                )
            if (not start_date) or start_date < today:
                cleaned_data['date'] = today
        else:
            date = cleaned_data.get('date')
            if date and date < today:
                self.add_error('date',
                    "Date is in the past. Please select a valid date."
                )

        return cleaned_data


class ContactForm(forms.Form):
    class Types(models.TextChoices):
        REPORT_BUG = "bug", "Bug report"
        OTHER = "oth", "Other"

    email = forms.EmailField(max_length=100)
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)
    type = forms.ChoiceField(choices=Types)

    def clean_subject(self):
        data = self.cleaned_data["subject"]
        return ' '.join(data.splitlines()) # Email subjects can't have \n or \r


class ModDailyDigestForm(forms.Form):
    date = DatePickerField(widget=DatePickerWidget(allow_past_or_future=-1))

    def clean_date(self):
        date = self.cleaned_data['date']
        today = timezone_today()
        if date > today:
            self.add_error('date',
                "No data for future dates."
                )
        return date
