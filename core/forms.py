from django.contrib import admin
from .models import Exercise, VocabItem, SentenceItem, UserExerciseProgress
from .forms import VocabItemAdminForm


@admin.register(VocabItem)
class VocabItemAdmin(admin.ModelAdmin):
    form = VocabItemAdminForm
    list_display = ("exercise", "order", "jp", "en", "reading_hira", "pitch_start", "pitch_end")
    list_filter = ("exercise",)
    search_fields = ("jp", "en", "reading_hira", "exercise__title")

    fields = (
        "exercise",
        "order",
        "jp",
        "en",
        "reading_hira",
        "mora_text",
        "pitch_start",
        "pitch_end",
        "pitch",  # keep if you want
    )

    class Media:
        js = ("core/pitch_admin.js",)
        css = {"all": ("core/pitch_admin.css",)}