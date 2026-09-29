from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile




class StudentRegisterationForm(UserCreationForm):
    stream = forms.ChoiceField(
        choices= UserProfile.STREAM_CHOICES,
        label="Chose your stream:",
        required=True
    )
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')