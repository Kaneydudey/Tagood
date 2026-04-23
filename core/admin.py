from django.contrib import admin
from .models import Exercise, VocabItem, SentenceItem, UserExerciseProgress
from .forms import VocabItemAdminForm


class VocabInline(admin.TabularInline):
    model = VocabItem
    extra = 0
    show_change_link = True
    fields = ("order", "jp", "en", "reading_hira")


class SentenceInline(admin.TabularInline):
    model = SentenceItem
    extra = 0


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
        "pitch",  # optional legacy field
    )

    class Media:
        js = ("core/pitch_admin.js",)
        css = {"all": ("core/pitch_admin.css",)}


@admin.register(SentenceItem)
class SentenceItemAdmin(admin.ModelAdmin):
    list_display = ("exercise", "order", "en")
    search_fields = ("en", "jp", "exercise__title")
    list_filter = ("exercise",)