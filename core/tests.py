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
