import datetime

from django import forms
from django.contrib.auth.models import User


class DateInput(forms.DateInput):
    input_type = "date"


class UsernameForm(forms.Form):
    username = forms.CharField(max_length=150)

    def clean_username(self):
        username = self.cleaned_data["username"]
        try:
            self.user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise forms.ValidationError("No such username. Register the student first.")
        return username


class DateForm(forms.Form):
    date = forms.DateField(widget=DateInput, initial=datetime.date.today)


class DateRangeForm(forms.Form):
    date_from = forms.DateField(widget=DateInput)
    date_to = forms.DateField(widget=DateInput, initial=datetime.date.today)

    def clean(self):
        cleaned = super().clean()
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise forms.ValidationError("The end date must be on or after the start date.")
        return cleaned


class UsernameAndDateRangeForm(UsernameForm, DateRangeForm):
    field_order = ["username", "date_from", "date_to"]
