from django.contrib import admin
from .models import Exercise, VocabItem, SentenceItem, UserExerciseProgress


class VocabInline(admin.TabularInline):
    model = VocabItem
    extra = 0


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
    list_display = ("user", "exercise", "stage1_confidence", "stage2_confidence", "stage3_confidence", "stage4_listens", "updated_at")
    search_fields = ("user__username", "exercise__title")
    list_filter = ("updated_at",)


# Optional: register these too (you can still edit them inline inside Exercise)
@admin.register(VocabItem)
class VocabItemAdmin(admin.ModelAdmin):
    list_display = ("exercise", "order", "jp", "en", "pitch")
    search_fields = ("jp", "en", "exercise__title")
    list_filter = ("exercise",)


@admin.register(SentenceItem)
class SentenceItemAdmin(admin.ModelAdmin):
    list_display = ("exercise", "order", "en")
    search_fields = ("en", "jp", "exercise__title")
    list_filter = ("exercise",)