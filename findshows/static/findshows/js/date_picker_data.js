function datePickerData(allowPastOrFuture) {
  return {
    MONTH_NAMES: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
    DAYS: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    TODAY: new Date(),

    showDatepicker: false,
    apf: allowPastOrFuture, // -1 to allow only past, 1 to allow only future, 0 to allow both

    selectedDate: '',
    selectedMonth: '',
    selectedYear: '',

    // We're using month indexed from 1, javascript Date stuff expects it indexed from 0
    calMonth: '',
    calYear: '',
    numDaysInMonth: 0,
    NumSpacesBeforeDays: 0,
    days: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],

    initDate(initialWidgetVal) {
      if (initialWidgetVal) {
        [this.selectedYear, this.selectedMonth, this.selectedDate] = initialWidgetVal.split('-').map((x) => parseInt(x))

        this.calMonth = this.selectedMonth;
        this.calYear = this.selectedYear;
      }
      else {
        let today = new Date();
        this.calMonth = today.getMonth() + 1;
        this.calYear = today.getFullYear();
      }

    },

    getDisplayDate() {
      if (this.selectedYear==='' || this.selectedMonth==='' || this.selectedDate==='') {
        return ''
      }
      d = new Date(this.selectedYear, this.selectedMonth - 1, this.selectedDate);
      return d.toDateString()
    },

    getWidgetReturnVal() {
      if (this.selectedYear==='' || this.selectedMonth==='' || this.selectedDate==='') {
        return ''
      }
      return [this.selectedYear, this.selectedMonth, this.selectedDate].join('-')
    },

    isToday(date) {
      return (date === this.TODAY.getDate() &&
              this.calMonth === this.TODAY.getMonth() + 1 &&
              this.calYear === this.TODAY.getFullYear())
    },

    isSelectable(date) {
      // Assuming the year/month are bounded correctly by increment function
      if (this.calYear != this.TODAY.getFullYear()) return true;
      if (this.calMonth != this.TODAY.getMonth() + 1) return true;
      if (this.apf * date < this.apf * this.TODAY.getDate()) return false;
      return true;
    },

    isSelected(date) {
      return (date === this.selectedDate &&
              this.calMonth === this.selectedMonth &&
              this.calYear === this.selectedYear)
    },

    onDateClick(date) {
      if (!this.isSelectable(date)) return;

      this.showDatepicker = false;

      if (this.selectedYear === this.calYear &&
          this.selectedMonth === this.calMonth &&
          this.selectedDate === date) return;

      this.selectedYear = this.calYear;
      this.selectedMonth = this.calMonth;
      this.selectedDate = date;

      this.$dispatch('widget-update');
    },

    incrementCalDisplay(incr) {
      newMonthIndexedZero = this.calMonth - 1 + incr;
      newYear = this.calYear + Math.floor(newMonthIndexedZero / 12);
      newMonthIndexedZero = ((newMonthIndexedZero % 12) + 12) % 12; // get true modulo from Javascript's remainder operator

      if (this.apf * newYear < this. apf * this.TODAY.getFullYear()) return;
      if (newYear === this.TODAY.getFullYear() &&
          this.apf * newMonthIndexedZero < this.apf * this.TODAY.getMonth()) return;

      this.calYear = newYear;
      this.calMonth = newMonthIndexedZero + 1;

      this.numDaysInMonth = new Date(this.calYear, this.calMonth, 0).getDate();
      this.NumSpacesBeforeDays = new Date(this.calYear, this.calMonth - 1).getDay();
    }

  }
}
