from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Exercise, SiteSetting, UserExerciseAccess


class ExerciseAccessTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username="student",
			password="test-password",
		)
		self.exercise = Exercise.objects.create(
			title="Exercise 2",
			order=2,
		)
		self.detail_url = reverse("exercise_detail", args=[self.exercise.id])

	def test_locked_exercise_shows_modal_and_rejects_wrong_code(self):
		self.client.force_login(self.user)

		response = self.client.get(self.detail_url)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Access code required")

		response = self.client.post(
			self.detail_url,
			{"action": "unlock_exercise", "access_code": "wrong-code"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "That access code was not correct")
		self.assertFalse(
			UserExerciseAccess.objects.filter(
				user=self.user,
				exercise=self.exercise,
			).exists()
		)

	def test_correct_code_grants_access_for_stage_routes(self):
		self.client.force_login(self.user)

		response = self.client.post(
			self.detail_url,
			{"action": "unlock_exercise", "access_code": "akigakita123"},
		)

		self.assertRedirects(response, self.detail_url)
		self.assertTrue(
			UserExerciseAccess.objects.get(
				user=self.user,
				exercise=self.exercise,
			).is_current()
		)

		stage1_url = reverse("stage1_flashcards", args=[self.exercise.id])
		self.assertEqual(self.client.get(stage1_url).status_code, 200)

	def test_expired_access_redirects_from_stage_routes(self):
		UserExerciseAccess.objects.create(
			user=self.user,
			exercise=self.exercise,
			granted_at=timezone.now() - timedelta(days=15),
		)
		self.client.force_login(self.user)

		for route_name in (
			"stage1_flashcards",
			"stage2_flashcards",
			"stage3_sentences",
		):
			response = self.client.get(reverse(route_name, args=[self.exercise.id]))
			self.assertRedirects(response, self.detail_url)

	def test_admin_can_change_current_access_code(self):
		setting = SiteSetting.objects.create(access_code="monthly-code")
		self.client.force_login(self.user)

		response = self.client.post(
			self.detail_url,
			{"action": "unlock_exercise", "access_code": "monthly-code"},
		)

		self.assertRedirects(response, self.detail_url)
		self.assertTrue(
			UserExerciseAccess.objects.filter(
				user=self.user,
				exercise=self.exercise,
			).exists()
		)


class Stage1MultipleChoiceTests(TestCase):
	def test_build_stage1_choices_includes_correct_answer_and_three_total_options(self):
		from .views import build_stage1_choices
		from .models import VocabItem

		correct = VocabItem(en="apple")
		vocab_items = [
			VocabItem(id=1, en="banana"),
			VocabItem(id=2, en="orange"),
			VocabItem(id=3, en="grape"),
			VocabItem(id=4, en="apple"),
		]

		choices = build_stage1_choices(correct, vocab_items)

		self.assertEqual(len(choices), 3)
		self.assertIn("apple", choices)
		self.assertTrue(all(choice in ["banana", "orange", "grape", "apple"] for choice in choices))


class Stage3SentenceOrderTests(TestCase):
	def test_duplicate_segment_values_are_accepted_when_sentence_text_matches(self):
		display_segments = ["この", "人", "は", "優しい", "人", "です"]
		selected_indices = [0, 4, 2, 3, 1, 5]
		expected_indices = list(range(len(display_segments)))
		valid_indices = sorted(selected_indices) == expected_indices
		user_segments = [
			display_segments[index]
			for index in selected_indices
		] if valid_indices else []
		correct = valid_indices and user_segments == display_segments

		self.assertTrue(correct)
		self.assertEqual(user_segments, display_segments)
