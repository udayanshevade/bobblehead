# submission_forms
from django import forms
from django.forms import ModelForm
from .models import Submission


class SubmissionForm(ModelForm):

    members_list = forms.CharField(required=False)

    class Meta:
        model = Submission
        exclude = ('project', 'members')
