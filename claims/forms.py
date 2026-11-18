from django import forms
from .models import Claim
from institutions.models import Institution
from listings.models import FoodListing
from accounts.models import User

class ClaimListingForm(forms.Form):
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.filter(user__verification_status=User.STATUS_APPROVED, user__is_active=True),
        required=False,
        empty_label="-- Select Intended Beneficiary Institution (Or leave blank for Homeless / Direct) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    recipient_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional claim notes or vehicle/volunteer details'})
    )


class DeliveryStatusUpdateForm(forms.Form):
    STATUS_CHOICES = (
        (FoodListing.STATUS_COLLECTED, '1. Mark Collected (Food picked up from donor)'),
        (FoodListing.STATUS_IN_TRANSIT, '2. Mark In Transit (En route to distribution point)'),
        (FoodListing.STATUS_DELIVERED, '3. Mark Delivered (Successfully handed over / served)'),
    )

    RECIPIENT_TYPE_CHOICES = (
        ('institution', 'Registered Beneficiary Institution (Orphanage, Shelter, Old-Age Home)'),
        ('homeless', 'Direct Distribution to Homeless Individuals / Communities (BR7)'),
    )

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_status_select'})
    )
    recipient_type = forms.ChoiceField(
        choices=RECIPIENT_TYPE_CHOICES,
        initial='institution',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    institution = forms.ModelChoiceField(
        queryset=Institution.objects.filter(user__verification_status=User.STATUS_APPROVED, user__is_active=True),
        required=False,
        empty_label="-- Select Registered Beneficiary Institution --",
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_institution_select'})
    )
    recipient_note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Provide details of distribution (e.g. 50 individuals at Railway Road shelter, names/locations)',
            'id': 'id_recipient_note'
        })
    )
    meals_delivered = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Total number of people / meals served',
            'id': 'id_meals_delivered'
        })
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional log remarks (e.g. On-time handover, temperature check OK)'})
    )

    def clean(self):
        cleaned_data = super().clean()
        new_status = cleaned_data.get('status')
        rtype = cleaned_data.get('recipient_type')
        inst = cleaned_data.get('institution')
        note = cleaned_data.get('recipient_note')
        meals = cleaned_data.get('meals_delivered')

        if new_status == FoodListing.STATUS_DELIVERED:
            if rtype == 'institution' and not inst:
                self.add_error('institution', "Please select a registered beneficiary institution as recipient.")
            if rtype == 'homeless' and not note:
                self.add_error('recipient_note', "Please record recipient details and distribution location for homeless delivery (Rule BR7).")
            if not meals:
                self.add_error('meals_delivered', "Please record the number of meals served upon delivery completion.")

        return cleaned_data
