from datetime import timedelta
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator, FileExtensionValidator
from django.db import models
from django.views.generic.dates import timezone_today
from django.conf import settings
from multiselectfield.forms.fields import MultiSelectFormField
from captcha.fields import CaptchaField

from findshows.models import Artist, Concert, ConcertTags, LabeledURLsValidator, MusicBrainzArtist, UserProfile, Venue
from findshows.widgets import ArtistAccessWidget, BillWidget, DatePickerField, DatePickerWidget, ImageInput, SocialsLinksWidget, MusicBrainzArtistSearchWidget, StyledSelect, TimePickerField, VenuePickerWidget


def add_default_styling_to_fields(fields):
    field_type_to_css_class = {
        forms.CharField: 'textinput',
        forms.URLField: 'textinput',
        forms.EmailField: 'textinput',
        MultiSelectFormField: 'accent-clickable',
        forms.BooleanField: 'accent-clickable mr-auto',
        CaptchaField: 'textinput',
    }
    for field in fields:
        field.widget.attrs.update({
            'class': field_type_to_css_class.get(type(field))
        })


# Have to duplicate this because of how the base classes are written
# (they don't call super in init, so a mixin version of this wouldn't get init called)
class DefaultStylingForm(forms.Form):
    required_css_class = "required"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_default_styling_to_fields(self.fields.values())


class DefaultStylingModelForm(forms.ModelForm):
    required_css_class = "required"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_default_styling_to_fields(self.fields.values())


class UserCreationFormE(UserCreationForm):
    required_css_class = "required"
    captcha = CaptchaField()

    class Meta:
        model = User
        fields = ("username", "password1", "password2")
        labels = {
            "username": "Email"
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_default_styling_to_fields(self.fields.values())


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


class UserProfileForm(DefaultStylingModelForm):
    class Meta:
        model=UserProfile
        fields=("favorite_musicbrainz_artists", "preferred_concert_tags", "weekly_email")
        widgets={"favorite_musicbrainz_artists": MusicBrainzArtistSearchWidget(max_artists=settings.MAX_USER_ARTISTS)}


def validate_image(image):
    FileExtensionValidator(allowed_extensions=('jpg', 'jpeg'))(image)
    if image.size > settings.MAX_IMAGE_SIZE_IN_MB*1024*1024:
        raise ValidationError("Image file too large")
    return image


class ArtistEditForm(DefaultStylingModelForm):
    class Meta:
        model=Artist
        fields=("name", "profile_picture", "bio", "youtube_links", "socials_links", "listen_links", "similar_musicbrainz_artists")
        widgets={
            "similar_musicbrainz_artists": MusicBrainzArtistSearchWidget,
            "socials_links": SocialsLinksWidget,
            "youtube_links": forms.Textarea(attrs={'rows': 5}),
            "listen_links": forms.Textarea(attrs={'rows': 7}),
            "profile_picture": ImageInput(),
        }

    def clean_socials_links(self):
        socials_links = self.cleaned_data['socials_links']
        LabeledURLsValidator()(socials_links)
        return socials_links


    def clean_profile_picture(self):
        return validate_image(self.cleaned_data['profile_picture'])


    def clean_similar_musicbrainz_artists(self):
        mb_artists = self.cleaned_data['similar_musicbrainz_artists']
        no_similar_artists = [mba.name
                              for mba in mb_artists
                              if not mba.get_similar_artists()]
        if no_similar_artists:
            raise ValidationError(f"We do not currently have any similarity data on the following artists: {','.join(no_similar_artists)}. Please select another to make sure you show up in search results!")
        return mb_artists


    def save(self, commit = True):
        artist = super().save(commit=False)
        artist.is_temp_artist = False
        if commit:
            artist.save()
            self.save_m2m()
        return artist


class ConcertForm(DefaultStylingModelForm):
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
        fields=("poster", "date", "doors_time", "start_time", "end_time", "venue", "ages", "ticket_link", "ticket_description", "tags", "description")
        widgets={
            "venue": VenuePickerWidget,
            "poster": ImageInput,
            "ages": StyledSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].widget.attrs['placeholder'] = 'Emojis encouraged ✌️'
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


    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone_today() + timedelta(settings.MAX_FUTURE_CONCERT_WEEKS * 7):
            self.add_error('date', f'Date cannot be more than {settings.MAX_FUTURE_CONCERT_WEEKS} weeks in the future.')
        return date


    def clean_poster(self):
        return validate_image(self.cleaned_data['poster'])


    def clean(self):
        cleaned_data = super().clean() or {}

        local_user_artists = set(str(a.id)
                                 for a in self.editing_user.userprofile.managed_artists.all()
                                 if a.local)
        if not local_user_artists.intersection(str(a['id']) for a in cleaned_data['bill']):
            self.add_error('bill', """The bill must include one of the local
            artists that your account manages.""")

        venue = cleaned_data.get("venue")
        date = cleaned_data.get("date")
        if venue and date:
            conflict_concerts = Concert.objects.filter(venue=venue, date=date).exclude(cancelled=True)
            if self.instance:
                conflict_concerts = conflict_concerts.exclude(pk=self.instance.pk)
            if conflict_concerts.count():
                self.add_error(None, """There is already a show in the database
                               for the specified venue and date. If you think
                               this is in error, or there are in fact two events
                               on the same date, please contact site admins for
                               an override.""")
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


class VenueForm(DefaultStylingModelForm):
    prefix = "venue"
    use_required_attribute = False

    class Meta:
        model=Venue
        fields=("name", "address", "ages", "website")
        widgets={"ages": StyledSelect}


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
                           f"Invalid email addresses: {invalid_emails}.")
        return self.cleaned_data['users']


class TempArtistForm(DefaultStylingModelForm):
    prefix = "temp_artist"
    use_required_attribute = False
    email=forms.EmailField(required=True, help_text="""Please check with the
    artist you're inviting and and use a personal email rather than a band
    email. This address must match the one on their account.""")

    class Meta:
        model=Artist
        fields=("name", "local")

    def save(self, commit = True):
        artist = super().save(commit=False)
        artist.is_temp_artist = True
        if commit:
            artist.save()
        return artist


class RequestArtistForm(DefaultStylingModelForm):
    prefix = "request_artist"
    use_required_attribute = False

    class Meta:
        model=Artist
        fields=("name", "socials_links")
        widgets={"socials_links": SocialsLinksWidget(num_links=1)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['socials_links'].required = True

    def clean_socials_links(self):
        socials_links = self.cleaned_data['socials_links']
        LabeledURLsValidator()(socials_links)
        return socials_links

    def save(self, commit = True):
        artist = super().save(commit=False)
        artist.is_temp_artist = True
        artist.is_active_request = True
        artist.local = True
        if commit:
            artist.save()
        return artist


class ShowFinderForm(forms.Form):
    date = DatePickerField(required=False)
    end_date = DatePickerField(required=False)
    is_date_range = forms.BooleanField(required=False)
    musicbrainz_artists = forms.ModelMultipleChoiceField(
        queryset=MusicBrainzArtist.objects.all(),
        widget=MusicBrainzArtistSearchWidget(max_artists=settings.MAX_USER_ARTISTS),
        required=False,
        label="Sounds like",
        help_text="""We'll recommend some concerts based on the artists you
        select here. Leave blank to get a randomly sorted list.""",
    )
    concert_tags = forms.MultipleChoiceField(
        choices=ConcertTags,
        widget=forms.CheckboxSelectMultiple(attrs={
            "@click": "$dispatch('widget-update')",
            "class": "accent-clickable",
        }),
        required=False,
        label="Categories",
        help_text="Leave blank to include all show categories.",
    )

    def clean(self):
        cleaned_data = super().clean() or {}
        today = timezone_today()

        date = cleaned_data.get("date")
        if (not date) or date < today:
            cleaned_data['date'] = today

        if cleaned_data.get('is_date_range'):
            end_date = cleaned_data.get("end_date")
            if (not end_date) or end_date < cleaned_data['date']:
                cleaned_data['end_date'] = cleaned_data['date']
            elif cleaned_data['end_date'] - cleaned_data['date'] > timedelta(settings.MAX_DATE_RANGE):
                self.add_error(None,
                    "Max date range is " + str(settings.MAX_DATE_RANGE) + " days."
                )

        return cleaned_data


class ContactForm(DefaultStylingForm):
    class Types(models.TextChoices):
        HELP = "hlp", "Tech support/help"
        CONTACT_MOD = "mod", "Moderator question"
        FEATURE_REQUEST = "ftr", "Feature request"
        REPORT_BUG = "bug", "Bug report"
        OTHER = "oth", "Other"

    email = forms.EmailField(max_length=100, label="Your email")
    type = forms.ChoiceField(choices=Types, widget=StyledSelect)
    subject = forms.CharField()
    message = forms.CharField(widget=forms.Textarea,
                              help_text="Please include as much detail as possible for the quickest help.")
    captcha = CaptchaField()

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
