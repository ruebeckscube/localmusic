function bill_data() {
  return {
    show_search: false,
    search_text: '',
    bill_order: [],

    bill_init(initial_widget_val) {
      this.bill_order = initial_widget_val;
      for (artist of this.bill_order) {
        artist.show_search = false;
        artist.search_text = artist.name;
      }
      if (!this.bill_order.length) this.add_artist();
    },

    open_dropdown(artist) {
      if (artist.show_search) return;
      artist.show_search = true;
    },

    close_dropdown(artist, focusAfter) {
      if (! artist.show_search) return;
      artist.show_search = false;
      if (artist.name) {
        artist.search_text = artist.name;
      }
      focusAfter && focusAfter.focus();
    },

    select_artist(idx, selected_name, selected_id) {
      this.bill_order[idx].search_text = selected_name;
      this.bill_order[idx].name = selected_name;
      this.bill_order[idx].id = selected_id;
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
    },

    on_temp_artist_create(event) {
      new_artist = this.artist_from_args(event.detail.created_record_name,
                                         event.detail.created_record_id)

      empty_idx = this.bill_order.findIndex(artist => artist.id === "");
      if (empty_idx === -1) {
        this.add_artist(new_artist);
      }
      else {
        this.bill_order[empty_idx] = new_artist
      }

    },
  }
}
