from django import forms
from django.core.exceptions import ValidationError

WORLDS_DEFAULTS = {'min': 1, 'max': 10000, 'limit': 20, 'page': 1}


class WorldsForm(forms.Form):
    """The query string of GET /worlds; absent parameters take their defaults."""

    min = forms.IntegerField(required=False, min_value=1, max_value=10000)
    max = forms.IntegerField(required=False, min_value=1, max_value=10000)
    limit = forms.IntegerField(required=False, min_value=1, max_value=100)
    page = forms.IntegerField(required=False, min_value=1, max_value=1000)

    def clean(self):
        data = super().clean()
        for name, default in WORLDS_DEFAULTS.items():
            if name not in self.errors and data.get(name) is None:
                data[name] = default
        if not self.errors and data['min'] > data['max']:
            raise ValidationError('min must not be greater than max')
        return data


class WorldUpdateForm(forms.Form):
    """The JSON body of PUT /world/{id}, as a dict parsed with json.loads.

    IntegerField also accepts the string "5"; the body's value must be a JSON
    integer, so the raw value's type is checked too.
    """

    randomNumber = forms.IntegerField(min_value=1, max_value=10000)

    def clean_randomNumber(self):
        if type(self.data.get('randomNumber')) is not int:
            raise ValidationError('randomNumber must be a JSON integer')
        return self.cleaned_data['randomNumber']


class GreetingForm(forms.Form):
    """The fields of POST /form."""

    name = forms.CharField(min_length=1, max_length=64)
    randomNumber = forms.IntegerField(min_value=1, max_value=10000)
