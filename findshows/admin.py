from django.contrib import admin

from .models import Artist, MusicBrainzArtist, UserProfile, Venue, Concert, SetOrder

class SetOrderInline(admin.TabularInline):
    model = SetOrder
    extra = 1 # how many rows to show

class ConcertAdmin(admin.ModelAdmin):
    inlines = (SetOrderInline,)

class UserProfileAdmin(admin.ModelAdmin):
    readonly_fields=('favorite_musicbrainz_artists',)

class ArtistAdmin(admin.ModelAdmin):
    readonly_fields=('similar_musicbrainz_artists',)

class MusicBrainzArtistAdmin(admin.ModelAdmin):
    readonly_fields=('mbid', 'name')

admin.site.register(Concert, ConcertAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Artist, ArtistAdmin)
admin.site.register(Venue)
admin.site.register(MusicBrainzArtist, MusicBrainzArtistAdmin)

# Register your models here.
