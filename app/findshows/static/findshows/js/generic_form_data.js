// form needs:
//   x-data="generic_form_data()"
//   x-bind="props"

// submit button needs:
//   :disabled="submitDisabled"
// cancel buttons etc need (only if you pass blockUnload=true):
//   @click=unblockUnload()
function generic_form_data(blockUnload = false) {
    return {
        blockUnload: blockUnload,
        submitDisabled: false,
        maybeEdited: false,

        props: {
            ['x-on:submit']() {
                this.submitDisabled = true;
                this.unblockUnload();
            },
            ['@pageshow.window'](event) {
                if (event.persisted) {
                    this.submitDisabled = false;
                }
            },
            ...(blockUnload && { // improves performance (don't add beforeunload listener if we don't need it)
                ['@beforeunload.window'](event) {
                    if (this.maybeEdited && this.blockUnload) {
                        event.preventDefault();
                        event.returnValue = true;
                    }
                },
                ['@keyup']() {
                    this.maybeEdited = true;
                }
            }),
        },

        unblockUnload() {
            this.blockUnload = false;
        },
    }
}
