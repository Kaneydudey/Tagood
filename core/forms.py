import re

from django import forms
from .models import VocabItem


def split_mora_text(text: str) -> list[str]:
    """
    Split mora entered by the admin.

    Supports:
    - spaces: そ る
    - commas: そ,る
    - Japanese commas: そ、る
    - mixed spacing: そ, る
    """
    text = text.strip()
    if not text:
        return []

    parts = re.split(r"[\s,、，]+", text)
    return [part for part in parts if part]


class VocabItemAdminForm(forms.ModelForm):
    mora_text = forms.CharField(
        required=False,
        label="Mora breakdown",
        help_text="Space-separated mora, e.g. か え る or ゆ う び ん きょ く. Use きょ / ちゅ as a single mora.",
    )

    class Meta:
        model = VocabItem
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.mora:
            self.fields["mora_text"].initial = " ".join(self.instance.mora)

    def clean(self):
        cleaned = super().clean()

        mora_text = cleaned.get("mora_text", "")
        mora_list = split_mora_text(mora_text)

        cleaned["mora_list_cleaned"] = mora_list

        pitch_start = cleaned.get("pitch_start")
        pitch_end = cleaned.get("pitch_end")

        if (pitch_start is None) != (pitch_end is None):
            raise forms.ValidationError("Pitch start and pitch end must both be set, or both be empty.")

        if mora_list and pitch_start is not None and pitch_end is not None:
            if pitch_start < 0 or pitch_end < 0:
                raise forms.ValidationError("Pitch start/end cannot be negative.")

            if pitch_start >= len(mora_list) or pitch_end >= len(mora_list):
                raise forms.ValidationError("Pitch start/end must be within the mora list range.")

            if pitch_start > pitch_end:
                raise forms.ValidationError("Pitch start must be less than or equal to pitch end.")

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)

        instance.mora = self.cleaned_data.get("mora_list_cleaned", [])

        if commit:
            instance.save()
            self.save_m2m()

        return instance