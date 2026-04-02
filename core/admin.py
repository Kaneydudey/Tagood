from django.contrib import admin

from django.contrib import admin
from .models import Exercise, VocabItem, SentenceItem


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
    inlines = [VocabInline, SentenceInline]# Register your models here.
