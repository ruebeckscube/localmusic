function musicbrainz_artist_search_data(selected_musicbrainz_artists, max_artists) {
  return {
    show_search: false,
    search_text: '',
    selected_musicbrainz_artists: selected_musicbrainz_artists,

    open_dropdown() {
      if (this.show_search) return;
      this.show_search = true;
    },

    close_dropdown(focusAfter) {
      if (! this.show_search) return;
      focusAfter && focusAfter.focus();  // Must come before show_search=false so we don't trigger menu opening via focus
      this.show_search = false;
    },

    add_artist(mbid, name) {
      if (this.selected_musicbrainz_artists.length < max_artists && !this.selected_musicbrainz_artists.some(a => a.mbid === mbid)) {
        this.selected_musicbrainz_artists.push({'mbid':mbid, 'name':name});
        this.search_text = '';
        this.$dispatch('widget-update');
        this.$dispatch('add-musicbrainz-card', { id: mbid });
        this.close_dropdown(this.$refs.mb_search);
      }
    },

    remove_artist(index) {
      this.selected_musicbrainz_artists.splice(index, 1);
      this.$dispatch('widget-update');
      this.close_dropdown(this.$refs.mb_search);
    }
  }
}
