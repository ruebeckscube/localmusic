function bill_data() {
  return {
    bill_order: [],
    creating_artist_idx: -1,

    bill_init(initial_widget_val) {
      this.bill_order = initial_widget_val;
      for (artist of this.bill_order) {
        artist.show_search = false;
        artist.search_text = artist.name;
      }
      if (!this.bill_order.length) {
          this.add_artist()
          this.add_artist()
          this.add_artist()
      };
    },

    open_dropdown(artist) {
      if (artist.show_search) return;
      if (artist.name && artist.search_text === artist.name) return;
      artist.show_search = true;
    },

    close_dropdown(artist, focusAfter) {
      if (artist.name) {
        artist.search_text = artist.name;
      }
      if (! artist.show_search) return;
      focusAfter && focusAfter.focus();
      artist.show_search = false;
    },

    select_artist(idx, selected_name, selected_id, num_users) {
      this.bill_order[idx].search_text = selected_name;
      this.bill_order[idx].name = selected_name;
      this.bill_order[idx].id = selected_id;
      this.bill_order[idx].num_users = num_users;
    },

    move_artist(idx, incr) {
      if (idx + incr > this.bill_order.length - 1 || idx + incr < 0) return;
      [this.bill_order[idx], this.bill_order[idx + incr]] = [this.bill_order[idx + incr], this.bill_order[idx]];
    },

    artist_from_args(name, id) {
      return {
        'search_text': name,
        'name': name,
        'id': id,
        'show_search': false
      }
    },

    add_artist(artist) {
      artist = artist || this.artist_from_args('','')
      this.bill_order.push(artist);
    },

    remove_artist(idx) {
      this.bill_order.splice(idx, 1);
      this.$refs['add-set'].focus();
    },

    open_create_artist_modal(idx) {
        this.creating_artist_idx = idx;
        this.$dispatch('open-modal-popup', {modal_id: 'create-artist-modal'});
    },

    on_temp_artist_create(event) {
      new_artist = this.artist_from_args(event.detail.created_record_name,
                                         event.detail.created_record_id)

      if (this.creating_artist_idx === -1) {
        this.add_artist(new_artist);
      }
      else {
          this.bill_order[this.creating_artist_idx] = new_artist
      }

    },
  }
}
