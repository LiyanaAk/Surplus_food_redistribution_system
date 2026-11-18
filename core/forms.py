from django import forms
from .models import SystemSetting

class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ['urgent_threshold_minutes', 'high_threshold_minutes', 'default_search_radius_km']
        widgets = {
            'urgent_threshold_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 10, 'max': 300}),
            'high_threshold_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 30, 'max': 720}),
            'default_search_radius_km': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 200}),
        }

    def clean(self):
        cleaned_data = super().clean()
        urgent = cleaned_data.get('urgent_threshold_minutes')
        high = cleaned_data.get('high_threshold_minutes')
        if urgent and high and urgent >= high:
            self.add_error('urgent_threshold_minutes', "Urgent threshold must be less than High priority threshold.")
        return cleaned_data


class ContactForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your Full Name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your.email@example.com'}))
    subject = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Inquiry Subject'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'How can we help you?'}))
