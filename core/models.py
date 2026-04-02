from django.conf import settings
from django.db import models


class Exercise(models.Model):
    title = models.CharField(max_length=200)
    youtube_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class VocabItem(models.Model):
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="vocab")
    jp = models.CharField(max_length=100)
    en = models.CharField(max_length=100)
    pitch = models.CharField(max_length=50, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.jp} / {self.en}"


class SentenceItem(models.Model):
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, related_name="sentences")
    en = models.TextField()
    jp = models.TextField()
    audio_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.en[:50]


class UserExerciseProgress(models.Model):
    STAGE4_TARGET_LISTENS = 200  # 20 sentences x 10 listens

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)

    stage1_confidence = models.PositiveSmallIntegerField(default=0)
    stage2_confidence = models.PositiveSmallIntegerField(default=0)
    stage3_confidence = models.PositiveSmallIntegerField(default=0)
    stage4_listens = models.PositiveIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "exercise")]

    def stage1_complete(self) -> bool:
        return self.stage1_confidence >= 100

    def stage2_complete(self) -> bool:
        return self.stage2_confidence >= 100

    def stage3_complete(self) -> bool:
        return self.stage3_confidence >= 100

    def stage4_complete(self) -> bool:
        return self.stage4_listens >= self.STAGE4_TARGET_LISTENS

    def unlocked_stage2(self) -> bool:
        return self.stage1_complete()

    def unlocked_stage3(self) -> bool:
        return self.stage2_complete()

    def unlocked_stage4(self) -> bool:
        return self.stage3_complete()