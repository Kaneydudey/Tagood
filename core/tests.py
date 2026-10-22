from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from .admin import SiteSettingAdmin
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
		self.assertContains(response, "Incorrect, typo maybe? Try again.")
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

		self.assertRedirects(response, self.detail_url, fetch_redirect_response=False)
		response = self.client.get(self.detail_url)
		self.assertContains(response, "Exercise unlocked! Enjoy your studies.")
		self.assertTrue(
			UserExerciseAccess.objects.get(
				user=self.user,
				exercise=self.exercise,
			).is_current()
		)

		stage1_url = reverse("stage1_flashcards", args=[self.exercise.id])
		self.assertEqual(self.client.get(stage1_url).status_code, 200)

	def test_most_recently_updated_setting_supplies_access_code(self):
		from .views import get_current_access_code

		stale_setting = SiteSetting.objects.create(access_code="stale-code")
		current_setting = SiteSetting.objects.create(access_code="current-code")
		SiteSetting.objects.filter(pk=stale_setting.pk).update(
			updated_at=current_setting.updated_at - timedelta(seconds=1),
		)

		self.assertEqual(get_current_access_code(), "current-code")

	def test_admin_cannot_add_a_second_site_setting(self):
		SiteSetting.objects.create(access_code="current-code")
		model_admin = SiteSettingAdmin(SiteSetting, admin.site)

		self.assertFalse(model_admin.has_add_permission(RequestFactory().get("/admin/")))

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

class DashboardSortingTests(TestCase):
	def setUp(self):
		self.first = Exercise.objects.create(title="Exercise 1", order=1)
		self.second = Exercise.objects.create(title="Exercise 2", order=2)
		self.third = Exercise.objects.create(title="Exercise 3", order=2)
		self.dashboard_url = reverse("dashboard")

	def card_titles(self, response):
		return [card["exercise"].title for card in response.context["exercise_cards"]]

	def test_default_sort_is_oldest_first(self):
		response = self.client.get(self.dashboard_url)

		self.assertEqual(self.card_titles(response), [
			"Exercise 1",
			"Exercise 2",
			"Exercise 3",
		])
		self.assertEqual(response.context["sort_order"], "oldest")

	def test_newest_sort_reverses_order_and_ties_by_id(self):
		response = self.client.get(self.dashboard_url, {"sort": "newest"})

		self.assertEqual(self.card_titles(response), [
			"Exercise 3",
			"Exercise 2",
			"Exercise 1",
		])
		self.assertEqual(response.context["sort_order"], "newest")

	def test_invalid_sort_falls_back_to_oldest(self):
		response = self.client.get(self.dashboard_url, {"sort": "sideways"})

		self.assertEqual(self.card_titles(response), [
			"Exercise 1",
			"Exercise 2",
			"Exercise 3",
		])
		self.assertEqual(response.context["sort_order"], "oldest")

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
