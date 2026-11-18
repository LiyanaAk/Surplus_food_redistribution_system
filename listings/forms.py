from django import forms
from django.utils import timezone
from .models import FoodListing, FoodCategory

class FoodListingForm(forms.ModelForm):
    prepared_at = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        help_text="When the food was cooked or packed"
    )
    usable_until = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        help_text="Safe consumption deadline"
    )

    class Meta:
        model = FoodListing
        fields = [
            'food_type',
            'category',
            'quantity',
            'quantity_unit',
            'prepared_at',
            'usable_until',
            'pickup_address',
            'latitude',
            'longitude',
            'description',
            'food_safety_accepted',
        ]
        widgets = {
            'food_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Vegetable Pulao, Dal & Chapati, Bakery Assortment'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0.1', 'placeholder': 'Amount'}),
            'quantity_unit': forms.Select(attrs={'class': 'form-select'}),
            'pickup_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Enter pickup address (street, area, landmark)'}),
            'latitude': forms.HiddenInput(attrs={'id': 'id_latitude'}),
            'longitude': forms.HiddenInput(attrs={'id': 'id_longitude'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Allergens, packaging type, storage advice (optional)'}),
            'food_safety_accepted': forms.CheckboxInput(attrs={'class': 'form-check-input', 'required': 'required'}),
        }

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return qty

    def clean_usable_until(self):
        usable_until = self.cleaned_data.get('usable_until')
        if usable_until:
            now = timezone.now()
            if usable_until <= now:
                raise forms.ValidationError("Usable until time must be in the future.")
        return usable_until

    def clean(self):
        cleaned_data = super().clean()
        prep = cleaned_data.get('prepared_at')
        usable = cleaned_data.get('usable_until')
        declaration = cleaned_data.get('food_safety_accepted')

        if prep and usable and usable <= prep:
            self.add_error('usable_until', "Safe usable-until time must be after the preparation time.")

        if not declaration:
            self.add_error('food_safety_accepted', "You must accept the food safety declaration before posting surplus food.")

        return cleaned_data


class FoodCategoryForm(forms.ModelForm):
    class Meta:
        model = FoodCategory
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name (e.g., Bakery, Dairy, Prepared Meals)'})
        }
