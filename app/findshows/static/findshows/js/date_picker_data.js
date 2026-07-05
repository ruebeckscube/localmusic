function datePickerData(allowPastOrFuture) {
  return {
    MONTH_NAMES: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    DAYS: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    TODAY: justDateToday(),

    showDatePicker: false,
    apf: allowPastOrFuture, // -1 to allow only past, 1 to allow only future, 0 to allow both

    focusedDate: justDateToday(), // the date the calendar is displaying as ready to select
    selectedDate: null, // the value of the widget once the user selects a date

    initDate(initialWidgetVal) {
        this.selectedDate = initialWidgetVal ? justDateISO(initialWidgetVal) : null;
        this.focusedDate = initialWidgetVal ? justDateISO(initialWidgetVal) : justDateToday();
    },

    openDatePicker() {
        this.showDatePicker = true;
        if (this.selectedDate) {
            this.focusedDate = new Date(this.selectedDate.getTime())
        }
    },

    buttonAriaDescription() {
        if (this.showDatePicker) return "Navigate with arrow keys";
        return this.selectedDate ? this.selectedDate.toDateString() : 'No date selected';
    },

    closeDatePicker(focusAfter) {
        this.showDatePicker = false;
        focusAfter && focusAfter.focus();
    },

    currentMonthName() {
        return this.MONTH_NAMES[this.focusedDate.getMonth()];
    },

    displayDayToDate(day) {
        return justDate(this.focusedDate.getFullYear(), this.focusedDate.getMonth(), day);
    },

    isToday(day) {
        return datesAreEqual(this.displayDayToDate(day), this.TODAY);
    },

    isAllowedDate(date) {
        return this.apf * date.getTime() >= this.apf * this.TODAY.getTime();
    },

    isSelectable(day) {
        return this.isAllowedDate(this.displayDayToDate(day));
    },

    isSelected(day) {
        return datesAreEqual(this.displayDayToDate(day), this.selectedDate);
    },

    numDaysInMonth() {
        return justDate(this.focusedDate.getFullYear(), this.focusedDate.getMonth() + 1, 0).getDate();
    },

    numSpacesBeforeDays() {
        return justDate(this.focusedDate.getFullYear(), this.focusedDate.getMonth(), 1).getDay();
    },

    focusFocusedDate() {
        document.getElementById(this.$id('date', this.focusedDate.getDate())).focus();
    },

    onArrowPress(event) {
        let incr = 0;
        switch (event.key) {
          case "ArrowUp": incr = -7; break;
          case "ArrowDown": incr = 7; break;
          case "ArrowLeft": incr = -1; break;
          case "ArrowRight": incr = 1; break;
        }
        this.incrementFocusedDate(incr);
        this.focusFocusedDate();
    },

    incrementFocusedDate(incrDays) {
        let newDate = justDate(this.focusedDate.getFullYear(), this.focusedDate.getMonth(), this.focusedDate.getDate() + incrDays);
        if (this.isAllowedDate(newDate)) {
            this.focusedDate = newDate;
        }
    },

    incrementDisplayMonth(incrMonths) {
        newMonth = this.focusedDate.getMonth() + incrMonths
        newDay = incrMonths >= 0 ? 1 : justDate(this.focusedDate.getFullYear(), newMonth + 1, 0).getDate();
        let newDate = justDate(this.focusedDate.getFullYear(), newMonth, newDay);
        if (!this.isAllowedDate(newDate)) return;

        this.focusedDate = newDate;
    },

    onDateClick(day) {
        if (!this.isSelectable(day)) return;

        this.closeDatePicker(this.$refs.datepicker);
        clickedDate = this.displayDayToDate(day);

        if (datesAreEqual(clickedDate, this.selectedDate)) return;

        this.selectedDate = clickedDate;
        this.$dispatch('widget-update');
    }

  }
}
