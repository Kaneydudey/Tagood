from django.contrib import admin
from .models import Exercise, VocabItem, SentenceItem, UserExerciseProgress, UserSentenceProgress
from .forms import VocabItemAdminForm, SentenceItemAdminForm


class VocabInline(admin.TabularInline):
    model = VocabItem
    extra = 0
    show_change_link = True
    fields = ("order", "jp", "en", "reading_hira", "romaji")


class SentenceInline(admin.TabularInline):
    model = SentenceItem
    extra = 0
    show_change_link = True
    fields = ("order", "en", "jp", "jp_kana")


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_published", "created_at")
    list_filter = ("is_published",)
    search_fields = ("title",)
    inlines = [VocabInline, SentenceInline]


@admin.register(UserExerciseProgress)
class UserExerciseProgressAdmin(admin.ModelAdmin):
    list_display = (
        "user", "exercise",
        "stage1_confidence", "stage2_confidence", "stage3_confidence",
        "stage4_listens", "updated_at"
    )
    search_fields = ("user__username", "exercise__title")
    list_filter = ("updated_at",)


@admin.register(VocabItem)
class VocabItemAdmin(admin.ModelAdmin):
    form = VocabItemAdminForm
    list_display = ("exercise", "order", "jp", "en", "reading_hira", "romaji", "pitch_start", "pitch_end")
    list_filter = ("exercise",)
    search_fields = ("jp", "en", "reading_hira", "exercise__title")

    fields = (
        "exercise",
        "order",
        "jp",
        "en",
        "reading_hira",
        "romaji",
        "mora_text",
        "pitch_start",
        "pitch_end",
        "pitch",
    )

    class Media:
        js = ("core/pitch_admin.js",)
        css = {"all": ("core/pitch_admin.css",)}


@admin.register(SentenceItem)
class SentenceItemAdmin(admin.ModelAdmin):
    form = SentenceItemAdminForm
    list_display = ("exercise", "order", "en", "jp", "jp_kana")
    search_fields = ("en", "jp", "jp_kana", "exercise__title")
    list_filter = ("exercise",)

    fields = (
        "exercise",
        "order",
        "en",
        "jp",
        "segments_text",
        "jp_kana",
        "kana_segments_text",
        "audio_url",
    )

@admin.register(UserSentenceProgress)
class UserSentenceProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "sentence_item", "confidence", "updated_at")
    search_fields = ("user__username", "sentence_item__en", "sentence_item__jp")
    list_filter = ("updated_at",)   