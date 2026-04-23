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
    pitch = models.CharField(max_length=50, blank=True)  # keep this for now if you still use it
    order = models.PositiveIntegerField(default=0)

    # --- Stage 2 (pitch) fields ---
    reading_hira = models.CharField(
        max_length=100,
        blank=True,
        help_text="Hiragana reading used for Stage 2 typing + pitch UI (e.g. かえる).",
    )
    mora = models.JSONField(
        default=list,
        blank=True,
        help_text="List of mora, stored as JSON (e.g. ['か', 'え', 'る']).",
    )
    pitch_start = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="0-based index where HIGH starts (inclusive).",
    )
    pitch_end = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="0-based index where HIGH ends (inclusive). Can equal start.",
    )


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
    stage1_video_confirmed = models.BooleanField(default=False)
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
    
class UserVocabProgress(models.Model):
    STAGE_CHOICES = [
        (1, "Stage 1"),
        (2, "Stage 2"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    vocab_item = models.ForeignKey(VocabItem, on_delete=models.CASCADE)
    stage = models.PositiveSmallIntegerField(choices=STAGE_CHOICES)
    confidence = models.PositiveSmallIntegerField(default=2)  # 1..6
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "vocab_item", "stage"], name="unique_user_vocab_stage")
        ]

    def __str__(self):
        return f"{self.user} / {self.vocab_item} / S{self.stage} = {self.confidence}"