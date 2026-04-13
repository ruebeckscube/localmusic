function modal_form_data() {
  return {
    show_modal: false,
    success_text: "",

    open_modal() {
      this.show_modal = true;
      this.success_text = "";
    },

    close_modal() {
      this.show_modal = false;
    },

    on_successful_create(event) {
      this.success_text = event.detail.success_text || "";
      this.close_modal();
    }
  }
}
