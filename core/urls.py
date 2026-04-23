from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("exercise/<int:exercise_id>/", views.exercise_detail, name="exercise_detail"),
    path("exercise/<int:exercise_id>/stage/<int:stage>/complete/", views.complete_stage, name="complete_stage"),
    path("exercise/<int:exercise_id>/stage4/listen/", views.stage4_listen, name="stage4_listen"),
    path("exercise/<int:exercise_id>/stage1/confirm-video/", views.confirm_stage1_video, name="confirm_stage1_video"),
    path("exercise/<int:exercise_id>/stage1/flashcards/", views.stage1_flashcards, name="stage1_flashcards"),
]
