from django import forms
from django.contrib import admin
from .models import VocabItem


class VocabItemAdminForm(forms.ModelForm):
    mora_text = forms.CharField(
        required=False,
        help_text="Comma-separated mora (e.g. か,え,る). Will be saved as JSON.",
    )

    class Meta:
        model = VocabItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.mora:
            self.fields["mora_text"].initial = ",".join(self.instance.mora)

    def save(self, commit=True):
        instance = super().save(commit=False)
        mora_text = self.cleaned_data.get("mora_text", "").strip()
        if mora_text:
            instance.mora = [m.strip() for m in mora_text.split(",") if m.strip()]
        else:
            instance.mora = []
        if commit:
            instance.save()
        return instance