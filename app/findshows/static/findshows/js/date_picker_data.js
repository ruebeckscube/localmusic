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

    buttonAriaLabel() {
        if (this.showDatePicker) {
            var detail = "Navigate with arrow keys"
        } else {
            var detail = this.selectedDate ? this.selectedDate.toDateString() : 'No date selected'
        }
        return `Select date. ${detail}`;
    },

    closeDatePicker() {
        this.showDatePicker = false;
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

    onArrowPress(event) {
        let incr = 0;
        switch (event.key) {
          case "ArrowUp": incr = -7; break;
          case "ArrowDown": incr = 7; break;
          case "ArrowLeft": incr = -1; break;
          case "ArrowRight": incr = 1; break;
        }
        this.incrementFocusedDate(incr);
        document.getElementById(this.$id('date', this.focusedDate.getDate())).focus();
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

        this.closeDatePicker();
        clickedDate = this.displayDayToDate(day);

        if (datesAreEqual(clickedDate, this.selectedDate)) return;

        this.selectedDate = clickedDate;
        this.$refs.datepicker.focus();
        this.$dispatch('widget-update');
    }

  }
}
