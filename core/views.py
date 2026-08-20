import random
from django.db.models import Sum
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .models import Exercise, UserExerciseProgress, UserVocabProgress, VocabItem, SentenceItem, UserSentenceProgress
from .flashcards import is_correct_english, choose_next_vocab, is_correct_stage2_reading


# -----------------------------
# Stage 1 settings
# -----------------------------
ROUND_SIZE = 10


def _round_key(exercise_id):
    return f"stage1_round_{exercise_id}"


def _stage1_feedback_key(exercise_id):
    return f"stage1_feedback_{exercise_id}"


# -----------------------------
# Stage 2 settings
# -----------------------------
STAGE2_ROUND_SIZE = 10

# Confidence deltas (tweak later if you want)
DELTA_WORD_WRONG = -1
DELTA_WORD_RIGHT_PITCH_RIGHT = +1
DELTA_WORD_RIGHT_PITCH_WRONG = -1


def _stage2_round_key(exercise_id: int) -> str:
    return f"stage2_round_{exercise_id}"


def _stage2_pending_key(exercise_id: int) -> str:
    return f"stage2_pending_{exercise_id}"


# -----------------------------
# Basic pages / auth
# -----------------------------
def home(request):
    return render(request, "core/home.html")


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard")
    else:
        form = UserCreationForm()

    return render(request, "registration/signup.html", {"form": form})


def dashboard(request):
    exercises = Exercise.objects.filter(is_published=True).order_by("order", "id")

    exercise_cards = []

    if request.user.is_authenticated:
        progress_qs = UserExerciseProgress.objects.filter(
            user=request.user,
            exercise__in=exercises,
        ).select_related("exercise")

        progress_by_exercise_id = {
            progress.exercise_id: progress
            for progress in progress_qs
        }

        for exercise in exercises:
            progress = progress_by_exercise_id.get(exercise.id)

            if progress:
                overall_progress = round(
                    (
                        progress.stage1_confidence
                        + progress.stage2_confidence
                        + progress.stage3_confidence
                    ) / 3
                )
            else:
                overall_progress = 0

            exercise_cards.append({
                "exercise": exercise,
                "progress": progress,
                "overall_progress": overall_progress,
            })

    else:
        for exercise in exercises:
            exercise_cards.append({
                "exercise": exercise,
                "progress": None,
                "overall_progress": 0,
            })

    return render(request, "core/dashboard.html", {
        "exercise_cards": exercise_cards,
    })

@login_required
def profile_stats(request):
    user = request.user

    stage1_qs = UserVocabProgress.objects.filter(user=user, stage=1)
    stage2_qs = UserVocabProgress.objects.filter(user=user, stage=2)
    stage3_qs = UserSentenceProgress.objects.filter(user=user)

    stage1_points = stage1_qs.aggregate(total=Sum("confidence"))["total"] or 0
    stage2_points = stage2_qs.aggregate(total=Sum("confidence"))["total"] or 0
    stage3_points = stage3_qs.aggregate(total=Sum("confidence"))["total"] or 0

    total_confidence_points = stage1_points + stage2_points + stage3_points

    stage1_items_seen = stage1_qs.count()
    stage2_items_seen = stage2_qs.count()
    stage3_items_seen = stage3_qs.count()

    max_confidence_points = 6 * (
        stage1_items_seen + stage2_items_seen + stage3_items_seen
    )

    if max_confidence_points:
        overall_confidence_percent = round(
            (total_confidence_points / max_confidence_points) * 100
        )
    else:
        overall_confidence_percent = 0

    progress_items = list(
        UserExerciseProgress.objects.filter(user=user)
        .select_related("exercise")
        .order_by("exercise__order", "exercise__title")
    )

    exercises_started = len(progress_items)
    exercises_completed_stage3 = sum(
        1 for progress in progress_items if progress.stage3_complete()
    )

    exercise_rows = []

    for progress in progress_items:
        if progress.stage3_complete():
            status = "Stage 3 complete"
        elif progress.unlocked_stage3():
            status = "Stage 3 unlocked"
        elif progress.unlocked_stage2():
            status = "Stage 2 unlocked"
        else:
            status = "Stage 1 in progress"

        exercise_rows.append({
            "exercise": progress.exercise,
            "stage1_confidence": progress.stage1_confidence,
            "stage2_confidence": progress.stage2_confidence,
            "stage3_confidence": progress.stage3_confidence,
            "status": status,
        })

    return render(request, "core/profile_stats.html", {
        "stage1_points": stage1_points,
        "stage2_points": stage2_points,
        "stage3_points": stage3_points,
        "total_confidence_points": total_confidence_points,
        "max_confidence_points": max_confidence_points,
        "overall_confidence_percent": overall_confidence_percent,
        "stage1_items_seen": stage1_items_seen,
        "stage2_items_seen": stage2_items_seen,
        "stage3_items_seen": stage3_items_seen,
        "exercises_started": exercises_started,
        "exercises_completed_stage3": exercises_completed_stage3,
        "exercise_rows": exercise_rows,
    })

@login_required
def global_ranking(request):
    ranking_rows = []

    users = User.objects.filter(
        is_active=True,
        is_staff=False,
        is_superuser=False,
    ).order_by("username")

    for user in users:
        stage1_qs = UserVocabProgress.objects.filter(user=user, stage=1)
        stage2_qs = UserVocabProgress.objects.filter(user=user, stage=2)
        stage3_qs = UserSentenceProgress.objects.filter(user=user)

        stage1_points = stage1_qs.aggregate(total=Sum("confidence"))["total"] or 0
        stage2_points = stage2_qs.aggregate(total=Sum("confidence"))["total"] or 0
        stage3_points = stage3_qs.aggregate(total=Sum("confidence"))["total"] or 0

        total_points = stage1_points + stage2_points + stage3_points

        items_seen = stage1_qs.count() + stage2_qs.count() + stage3_qs.count()
        max_points = 6 * items_seen

        if max_points:
            overall_percent = round((total_points / max_points) * 100)
        else:
            overall_percent = 0

        progress_items = list(UserExerciseProgress.objects.filter(user=user))
        exercises_started = len(progress_items)
        exercises_completed_stage3 = sum(
            1 for progress in progress_items if progress.stage3_complete()
        )

        if total_points == 0 and exercises_started == 0:
            continue

        ranking_rows.append({
            "user": user,
            "total_points": total_points,
            "overall_percent": overall_percent,
            "exercises_started": exercises_started,
            "exercises_completed_stage3": exercises_completed_stage3,
        })

    ranking_rows.sort(
        key=lambda row: (
            row["total_points"],
            row["overall_percent"],
            row["exercises_completed_stage3"],
        ),
        reverse=True,
    )

    for index, row in enumerate(ranking_rows, start=1):
        row["rank"] = index

    current_user_rank = None

    for row in ranking_rows:
        if row["user"].id == request.user.id:
            current_user_rank = row["rank"]
            break

    return render(request, "core/global_ranking.html", {
        "ranking_rows": ranking_rows,
        "current_user_rank": current_user_rank,
    })

def exercise_detail(request, exercise_id):
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)

    prog = None
    stage1_unlocked = True
    stage2_unlocked = False
    stage3_unlocked = False
    stage4_unlocked = False

    if request.user.is_authenticated:
        prog, _ = UserExerciseProgress.objects.get_or_create(
            user=request.user,
            exercise=ex,
        )

        stage2_unlocked = prog.unlocked_stage2()
        stage3_unlocked = prog.unlocked_stage3()
        stage4_unlocked = prog.unlocked_stage4()

    # Stage 1 study list
    stage1_study_rows = []

    for vocab in ex.vocab.all():
        stage1_study_rows.append({
            "jp": vocab.jp,
            "en": vocab.en,
            "pitch": vocab.pitch,
        })

    # Stage 2 pitch study list
    stage2_study_rows = []

    for vocab in ex.vocab.all():
        if not vocab.mora:
            continue

        if vocab.pitch_start is None or vocab.pitch_end is None:
            continue

        pitch_mora = []

        for index, mora in enumerate(vocab.mora):
            pitch_mora.append({
                "text": mora,
                "is_high": vocab.pitch_start <= index <= vocab.pitch_end,
            })

        stage2_study_rows.append({
            "en": vocab.en,
            "reading_hira": vocab.reading_hira,
            "romaji": vocab.romaji,
            "pitch_mora": pitch_mora,
        })

    # Stage 3 sentence study list
    stage3_study_rows = []

    for sentence in ex.sentences.all():
        stage3_study_rows.append({
            "en": sentence.en,
            "jp": sentence.jp,
            "jp_kana": sentence.jp_kana,
        })

    return render(request, "core/exercise_detail.html", {
        "ex": ex,
        "prog": prog,
        "stage1_unlocked": stage1_unlocked,
        "stage2_unlocked": stage2_unlocked,
        "stage3_unlocked": stage3_unlocked,
        "stage4_unlocked": stage4_unlocked,
        "stage1_study_rows": stage1_study_rows,
        "stage2_study_rows": stage2_study_rows,
        "stage3_study_rows": stage3_study_rows,
    })


@require_POST
@login_required
def complete_stage(request, exercise_id, stage):
    """
    Optional: keep for stages 2–4 demo/testing.
    IMPORTANT: We block stage 1 manual completion so users can't bypass typing.
    """
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)
    prog, _ = UserExerciseProgress.objects.get_or_create(user=request.user, exercise=ex)

    if stage == 1:
        # Don't allow skipping Stage 1 typing system
        return redirect("exercise_detail", exercise_id=ex.id)

    if stage == 2 and prog.unlocked_stage2():
        prog.stage2_confidence = 100
    elif stage == 3 and prog.unlocked_stage3():
        prog.stage3_confidence = 100

    prog.save()
    return redirect("exercise_detail", exercise_id=ex.id)


@require_POST
@login_required
def stage4_listen(request, exercise_id):
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)
    prog, _ = UserExerciseProgress.objects.get_or_create(user=request.user, exercise=ex)

    if prog.unlocked_stage4():
        prog.stage4_listens += 10  # demo increments; refine later
        prog.save()

    return redirect("exercise_detail", exercise_id=ex.id)


# -----------------------------
# Stage 1: video confirm + rounds
# -----------------------------
@require_POST
@login_required
def confirm_stage1_video(request, exercise_id):
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)
    prog, _ = UserExerciseProgress.objects.get_or_create(user=request.user, exercise=ex)
    prog.stage1_video_confirmed = True
    prog.save()
    return redirect("stage1_flashcards", exercise_id=ex.id)


@login_required
def stage1_flashcards(request, exercise_id):
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)
    vocab_items = list(ex.vocab.all())

    if not vocab_items:
        return render(request, "core/stage1_overview.html", {
            "ex": ex,
            "can_start": False,
            "rows": [],
        })

    ex_prog, _ = UserExerciseProgress.objects.get_or_create(
        user=request.user,
        exercise=ex,
    )

    # Make sure every vocab item has a progress row for Stage 1
    progress_qs = UserVocabProgress.objects.filter(
        user=request.user,
        vocab_item__in=vocab_items,
        stage=1,
    )

    progress_by_vocab = {
        progress.vocab_item_id: progress
        for progress in progress_qs
    }

    for vocab in vocab_items:
        if vocab.id not in progress_by_vocab:
            progress_by_vocab[vocab.id] = UserVocabProgress.objects.create(
                user=request.user,
                vocab_item=vocab,
                stage=1,
                confidence=2,
            )

    # Stats
    max_points = 6 * len(vocab_items)
    total_points = sum(progress_by_vocab[v.id].confidence for v in vocab_items)
    stage_percent = round((total_points / max_points) * 100) if max_points else 0

    ex_prog.stage1_confidence = stage_percent
    ex_prog.save()

    round_key = _round_key(ex.id)
    feedback_key = _stage1_feedback_key(ex.id)

    round_state = request.session.get(round_key)
    feedback = request.session.get(feedback_key)

    # Start/restart a round
    if request.method == "POST" and request.POST.get("action") == "start":
        request.session[round_key] = {
            "remaining": ROUND_SIZE,
            "total": ROUND_SIZE,
            "correct": 0,
        }
        request.session.pop(feedback_key, None)
        request.session.modified = True
        return redirect("stage1_flashcards", exercise_id=ex.id)

    # Move from feedback state to next question
    if request.method == "POST" and request.POST.get("action") == "next":
        request.session.pop(feedback_key, None)
        request.session.modified = True
        return redirect("stage1_flashcards", exercise_id=ex.id)

    # No active round: show study/start page
    if not round_state:
        rows = [
            {
                "jp": vocab.jp,
                "en": vocab.en,
                "confidence": progress_by_vocab[vocab.id].confidence,
            }
            for vocab in vocab_items
        ]

        return render(request, "core/stage1_overview.html", {
            "ex": ex,
            "can_start": True,
            "rows": rows,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
        })

    # Round finished, but only after feedback has been cleared
    if round_state["remaining"] <= 0 and not feedback:
        completed = round_state

        request.session.pop(round_key, None)
        request.session.modified = True

        return render(request, "core/stage1_complete.html", {
            "ex": ex,
            "completed": completed,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
        })

    # Check answer
    if request.method == "POST" and request.POST.get("action") == "check_answer":
        vocab_id = request.POST.get("vocab_id")
        submitted_answer = request.POST.get("answer", "")

        vocab = get_object_or_404(VocabItem, id=vocab_id, exercise=ex)
        progress = progress_by_vocab[vocab.id]

        before_conf = progress.confidence
        correct = is_correct_english(submitted_answer, vocab.en)

        if correct:
            progress.confidence = min(6, progress.confidence + 1)
            round_state["correct"] += 1
        else:
            progress.confidence = max(1, progress.confidence - 1)

        progress.save()

        after_conf = progress.confidence
        delta_points = after_conf - before_conf

        round_state["remaining"] -= 1
        request.session[round_key] = round_state

        # Refresh total stats after the confidence update
        total_points = sum(
            UserVocabProgress.objects.get(
                user=request.user,
                vocab_item=vocab,
                stage=1,
            ).confidence
            for vocab in vocab_items
        )
        stage_percent = round((total_points / max_points) * 100) if max_points else 0

        ex_prog.stage1_confidence = stage_percent
        ex_prog.save()

        request.session[feedback_key] = {
            "correct": correct,
            "jp": vocab.jp,
            "correct_answer": vocab.en,
            "submitted_answer": submitted_answer,
            "before_conf": before_conf,
            "after_conf": after_conf,
            "delta_points": delta_points,
            "is_round_finished": round_state["remaining"] <= 0,
        }

        request.session.modified = True
        return redirect("stage1_flashcards", exercise_id=ex.id)

    # If feedback exists, show feedback card and do not choose a new question yet
    if feedback:
        rows = [
            {
                "jp": vocab.jp,
                "confidence": progress_by_vocab[vocab.id].confidence,
            }
            for vocab in vocab_items
        ]

        return render(request, "core/stage1_flashcards.html", {
            "ex": ex,
            "vocab": None,
            "round_state": round_state,
            "feedback": feedback,
            "rows": rows,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
        })

    # Choose next question, weighted toward lower-confidence items
    weights = [
        7 - progress_by_vocab[vocab.id].confidence
        for vocab in vocab_items
    ]
    vocab = random.choices(vocab_items, weights=weights, k=1)[0]

    rows = [
        {
            "jp": item.jp,
            "confidence": progress_by_vocab[item.id].confidence,
        }
        for item in vocab_items
    ]

    return render(request, "core/stage1_flashcards.html", {
        "ex": ex,
        "vocab": vocab,
        "round_state": round_state,
        "feedback": None,
        "rows": rows,
        "total_points": total_points,
        "max_points": max_points,
        "stage_percent": stage_percent,
    })


# -----------------------------
# Stage 2: rounds + word then pitch span
# -----------------------------
@login_required
def stage2_flashcards(request, exercise_id):
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)
    ex_prog, _ = UserExerciseProgress.objects.get_or_create(user=request.user, exercise=ex)

    # Gate: Stage 2 only after Stage 1 complete
    if not ex_prog.unlocked_stage2():
        return redirect("exercise_detail", exercise_id=ex.id)

    # Only vocab items configured for Stage 2
    all_vocab = list(ex.vocab.all())
    configured = []

    for v in all_vocab:
        if not v.reading_hira:
            continue
        if not v.mora or v.pitch_start is None or v.pitch_end is None:
            continue
        if v.pitch_start < 0 or v.pitch_end < 0:
            continue
        if v.pitch_end >= len(v.mora):
            continue

        configured.append(v)

    if not configured:
        return render(request, "core/stage2_overview.html", {
            "ex": ex,
            "can_start": False,
            "configured_count": 0,
            "total_count": len(all_vocab),
        })

    # Ensure per-user progress rows exist for Stage 2
    progress_qs = UserVocabProgress.objects.filter(
        user=request.user,
        stage=2,
        vocab_item__in=configured,
    )

    progress_by_vocab = {
        p.vocab_item_id: p
        for p in progress_qs
    }

    for v in configured:
        if v.id not in progress_by_vocab:
            progress_by_vocab[v.id] = UserVocabProgress.objects.create(
                user=request.user,
                vocab_item=v,
                stage=2,
                confidence=2,
            )

    # Points/progress for Stage 2
    max_points = 6 * len(configured)
    total_points = sum(progress_by_vocab[v.id].confidence for v in configured)
    stage_percent = round((total_points / max_points) * 100) if max_points else 0

    ex_prog.stage2_confidence = stage_percent
    ex_prog.save()

    round_key = _stage2_round_key(ex.id)
    pending_key = _stage2_pending_key(ex.id)
    last_feedback_key = f"stage2_last_feedback_{ex.id}"

    round_state = request.session.get(round_key)
    pending = request.session.get(pending_key)

    configured_ids = {v.id for v in configured}

    # Clear stale pending vocab if admin deleted/changed vocab during a session
    if pending:
        try:
            pending_vocab_id = int(pending.get("vocab_id"))
        except (TypeError, ValueError):
            pending_vocab_id = None

        if pending_vocab_id not in configured_ids:
            request.session.pop(pending_key, None)
            request.session.modified = True
            pending = None

    # Start round
    if request.method == "POST" and request.POST.get("action") == "start":
        round_len = STAGE2_ROUND_SIZE

        request.session[round_key] = {
            "remaining": round_len,
            "total": round_len,
            "perfect": 0,
        }

        request.session.pop(pending_key, None)
        request.session.pop(last_feedback_key, None)
        request.session.modified = True

        return redirect("stage2_flashcards", exercise_id=ex.id)

    # No round yet => Overview
    if not round_state:
        rows = []

        for v in configured:
            pitch_mora = []

            for index, mora in enumerate(v.mora):
                pitch_mora.append({
                    "text": mora,
                    "is_high": v.pitch_start <= index <= v.pitch_end,
                })

            rows.append({
                "en": v.en,
                "reading_hira": v.reading_hira,
                "romaji": v.romaji,
                "pitch_mora": pitch_mora,
                "confidence": progress_by_vocab[v.id].confidence,
            })

        return render(request, "core/stage2_overview.html", {
            "ex": ex,
            "can_start": True,
            "configured_count": len(configured),
            "total_count": len(all_vocab),
            "rows": rows,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
        })

    # Finished round => complete page
    if round_state["remaining"] <= 0:
        completed = round_state
        last_feedback = request.session.pop(last_feedback_key, None)

        request.session.pop(round_key, None)
        request.session.pop(pending_key, None)
        request.session.modified = True

        return render(request, "core/stage2_complete.html", {
            "ex": ex,
            "completed": completed,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
            "last_feedback": last_feedback,
        })

    feedback = None
    before_conf = after_conf = delta_points = None

    # Submissions
    if request.method == "POST" and request.POST.get("action") == "check_word":
        vocab_id = int(request.POST["vocab_id"])
        answer_jp = request.POST.get("answer_jp", "")

        vocab = get_object_or_404(VocabItem, id=vocab_id, exercise=ex)
        vp = progress_by_vocab[vocab.id]

        expected = vocab.reading_hira
        expected_romaji = vocab.romaji

        expected_display = expected
        if expected_romaji:
            expected_display = f"{expected} / {expected_romaji}"

        if not is_correct_stage2_reading(answer_jp, expected, expected_romaji):
            # Wrong word => confidence down, consume 1 question
            before_conf = vp.confidence
            vp.confidence = max(1, vp.confidence + DELTA_WORD_WRONG)
            vp.save()

            after_conf = vp.confidence
            delta_points = after_conf - before_conf

            round_state["remaining"] -= 1
            request.session[round_key] = round_state
            request.session.pop(pending_key, None)

            feedback = {
                "step": "word",
                "correct": False,
                "expected": expected_display,
            }

            request.session[last_feedback_key] = feedback
            request.session.modified = True

            if round_state["remaining"] <= 0:
                return redirect("stage2_flashcards", exercise_id=ex.id)

        else:
            # Word correct => go to pitch step. Do NOT consume question yet.
            request.session[pending_key] = {
                "vocab_id": vocab.id,
            }

            request.session.modified = True

            feedback = {
                "step": "word",
                "correct": True,
            }

    elif request.method == "POST" and request.POST.get("action") == "submit_pitch":
        # Must have pending vocab
        if not pending or "vocab_id" not in pending:
            request.session.pop(pending_key, None)
            request.session.modified = True
            return redirect("stage2_flashcards", exercise_id=ex.id)

        vocab = get_object_or_404(
            VocabItem,
            id=int(pending["vocab_id"]),
            exercise=ex,
        )

        vp = progress_by_vocab[vocab.id]

        try:
            user_start = int(request.POST.get("pitch_start", ""))
            user_end = int(request.POST.get("pitch_end", ""))
        except ValueError:
            user_start = user_end = None

        # This is the important new display string.
        # Example: え [い] [ご]
        expected_pitch_display = " ".join(
            f"[{mora}]" if vocab.pitch_start <= index <= vocab.pitch_end else mora
            for index, mora in enumerate(vocab.mora)
        )

        if user_start is None or user_end is None:
            feedback = {
                "step": "pitch",
                "correct": False,
                "error": "Please select a start and end mora.",
                "expected": expected_pitch_display,
            }

        else:
            correct_pitch = (
                user_start == vocab.pitch_start
                and user_end == vocab.pitch_end
            )

            before_conf = vp.confidence

            if correct_pitch:
                vp.confidence = min(6, vp.confidence + DELTA_WORD_RIGHT_PITCH_RIGHT)
                round_state["perfect"] += 1
            else:
                vp.confidence = max(1, vp.confidence + DELTA_WORD_RIGHT_PITCH_WRONG)

            vp.save()

            after_conf = vp.confidence
            delta_points = after_conf - before_conf

            # Consume 1 question after pitch attempt
            round_state["remaining"] -= 1
            request.session[round_key] = round_state
            request.session.pop(pending_key, None)

            expected_mora = [
                {
                    "text": mora,
                    "is_high": vocab.pitch_start <= index <= vocab.pitch_end,
                }
                for index, mora in enumerate(vocab.mora)
            ]

            selected_mora = [
                {
                    "text": mora,
                    "is_high": user_start <= index <= user_end,
                }
                for index, mora in enumerate(vocab.mora)
            ]

            feedback = {
                "step": "pitch",
                "correct": correct_pitch,
                "expected": expected_pitch_display,
                "expected_span": [vocab.pitch_start, vocab.pitch_end],
                "expected_mora": expected_mora,
                "selected_mora": selected_mora,
            }

            request.session[last_feedback_key] = feedback
            request.session.modified = True

            if round_state["remaining"] <= 0:
                return redirect("stage2_flashcards", exercise_id=ex.id)

    # Refresh stats after update
    total_points = sum(progress_by_vocab[v.id].confidence for v in configured)
    stage_percent = round((total_points / max_points) * 100) if max_points else 0

    ex_prog.stage2_confidence = stage_percent
    ex_prog.save()

    # Choose current prompt
    pending = request.session.get(pending_key)

    if pending:
        current_vocab = get_object_or_404(
            VocabItem,
            id=int(pending["vocab_id"]),
            exercise=ex,
        )
        show_pitch = True
    else:
        current_vocab = choose_next_vocab([
            (v, progress_by_vocab[v.id].confidence)
            for v in configured
        ])
        show_pitch = False

    rows = []
    for v in configured:
        rows.append({
            "en": v.en,
            "reading_hira": v.reading_hira,
            "romaji": getattr(v, "romaji", ""),
            "confidence": progress_by_vocab[v.id].confidence,
            "pitch_mora": [
                {
                    "text": mora,
                    "is_high": v.pitch_start <= i <= v.pitch_end,
                }
                for i, mora in enumerate(v.mora or [])
            ],
        })

    return render(request, "core/stage2_flashcards.html", {
        "ex": ex,
        "round_state": round_state,
        "vocab": current_vocab,
        "show_pitch": show_pitch,
        "rows": rows,
        "total_points": total_points,
        "max_points": max_points,
        "stage_percent": stage_percent,
        "feedback": feedback,
        "before_conf": before_conf,
        "after_conf": after_conf,
        "delta_points": delta_points,
    })


def _stage3_current_key(exercise_id: int) -> str:
    return f"stage3_current_sentence_{exercise_id}"


STAGE3_ROUND_SIZE = 5


def _stage3_round_key(exercise_id: int) -> str:
    return f"stage3_round_{exercise_id}"


def _stage3_current_key(exercise_id: int) -> str:
    return f"stage3_current_sentence_{exercise_id}"


def _stage3_last_feedback_key(exercise_id: int) -> str:
    return f"stage3_last_feedback_{exercise_id}"


@login_required
def stage3_sentences(request, exercise_id):
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)
    ex_prog, _ = UserExerciseProgress.objects.get_or_create(user=request.user, exercise=ex)

    # Gate: Stage 3 only after Stage 2 complete
    if not ex_prog.unlocked_stage3():
        return redirect("exercise_detail", exercise_id=ex.id)

    # A sentence is configured if it has JP segments.
    configured = [s for s in ex.sentences.all() if s.jp_segments]

    if not configured:
        return render(request, "core/stage3_overview.html", {
            "ex": ex,
            "can_start": False,
            "rows": [],
        })

    # Ensure progress rows exist
    progress_qs = UserSentenceProgress.objects.filter(
        user=request.user,
        sentence_item__in=configured,
    )

    progress_by_sentence = {
        progress.sentence_item_id: progress
        for progress in progress_qs
    }

    for sentence in configured:
        if sentence.id not in progress_by_sentence:
            progress_by_sentence[sentence.id] = UserSentenceProgress.objects.create(
                user=request.user,
                sentence_item=sentence,
                confidence=2,
            )

    # Stats
    max_points = 6 * len(configured)
    total_points = sum(progress_by_sentence[s.id].confidence for s in configured)
    stage_percent = round((total_points / max_points) * 100) if max_points else 0

    ex_prog.stage3_confidence = stage_percent
    ex_prog.save()

    round_key = _stage3_round_key(ex.id)
    current_key = _stage3_current_key(ex.id)
    feedback_key = _stage3_last_feedback_key(ex.id)

    round_state = request.session.get(round_key)
    feedback = request.session.get(feedback_key)

    # Start round
    if request.method == "POST" and request.POST.get("action") == "start":
        chosen = random.choice(configured)

        request.session[round_key] = {
            "remaining": STAGE3_ROUND_SIZE,
            "total": STAGE3_ROUND_SIZE,
            "correct": 0,
        }

        request.session[current_key] = chosen.id
        request.session.pop(feedback_key, None)
        request.session.modified = True

        return redirect("stage3_sentences", exercise_id=ex.id)

    # Next card after feedback
    if request.method == "POST" and request.POST.get("action") == "next":
        request.session.pop(feedback_key, None)
        request.session.modified = True

        round_state = request.session.get(round_key)

        if round_state and round_state["remaining"] <= 0:
            return redirect("stage3_sentences", exercise_id=ex.id)

        chosen = random.choice(configured)
        request.session[current_key] = chosen.id
        request.session.modified = True

        return redirect("stage3_sentences", exercise_id=ex.id)

    # No active round: overview/study page
    if not round_state:
        rows = [
            {
                "en": s.en,
                "jp": s.jp,
                "jp_kana": s.jp_kana,
                "confidence": progress_by_sentence[s.id].confidence,
            }
            for s in configured
        ]

        return render(request, "core/stage3_overview.html", {
            "ex": ex,
            "can_start": True,
            "rows": rows,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
        })

    # Finished round, but only after feedback has been cleared
    if round_state["remaining"] <= 0 and not feedback:
        completed = round_state

        request.session.pop(round_key, None)
        request.session.pop(current_key, None)
        request.session.modified = True

        return render(request, "core/stage3_complete.html", {
            "ex": ex,
            "completed": completed,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
        })

    current_id = request.session.get(current_key)
    current_sentence = next((s for s in configured if s.id == current_id), None)

    if current_sentence is None:
        current_sentence = random.choice(configured)
        request.session[current_key] = current_sentence.id
        request.session.modified = True

    before_conf = after_conf = delta_points = None

    # Submit sentence order
    if request.method == "POST" and request.POST.get("action") == "submit_order":
        selected_raw = request.POST.get("selected_order", "")
        selected_mode = request.POST.get("selected_mode", "kanji")

        try:
            selected_indices = [int(x) for x in selected_raw.split(",") if x != ""]
        except ValueError:
            selected_indices = []

        correct_indices = list(range(len(current_sentence.jp_segments)))
        correct = selected_indices == correct_indices

        # Use kana display if user was in kana mode and kana segments exist
        if selected_mode == "kana" and current_sentence.jp_kana_segments:
            display_segments = current_sentence.jp_kana_segments
            correct_natural = current_sentence.jp_kana
        else:
            display_segments = current_sentence.jp_segments
            correct_natural = current_sentence.jp

        user_segments = [
            display_segments[i]
            for i in selected_indices
            if 0 <= i < len(display_segments)
        ]

        progress = progress_by_sentence[current_sentence.id]
        before_conf = progress.confidence

        if correct:
            progress.confidence = min(6, progress.confidence + 1)
            round_state["correct"] += 1
        else:
            progress.confidence = max(1, progress.confidence - 1)

        progress.save()

        after_conf = progress.confidence
        delta_points = after_conf - before_conf

        round_state["remaining"] -= 1
        request.session[round_key] = round_state

        # Refresh stats after update
        total_points = sum(
            UserSentenceProgress.objects.get(
                user=request.user,
                sentence_item=s,
            ).confidence
            for s in configured
        )

        stage_percent = round((total_points / max_points) * 100) if max_points else 0
        ex_prog.stage3_confidence = stage_percent
        ex_prog.save()

        feedback = {
            "correct": correct,
            "english": current_sentence.en,
            "user_sentence": " ".join(user_segments),
            "correct_sentence": " ".join(display_segments),
            "correct_sentence_natural": correct_natural,
            "before_conf": before_conf,
            "after_conf": after_conf,
            "delta_points": delta_points,
            "is_round_finished": round_state["remaining"] <= 0,
        }

        request.session[feedback_key] = feedback
        request.session.modified = True

        return redirect("stage3_sentences", exercise_id=ex.id)

    rows = [
        {
            "en": s.en,
            "confidence": progress_by_sentence[s.id].confidence,
        }
        for s in configured
    ]

    # Feedback state: show feedback card, not a new question
    if feedback:
        return render(request, "core/stage3_sentences.html", {
            "ex": ex,
            "sentence": current_sentence,
            "round_state": round_state,
            "shuffled_segments": [],
            "rows": rows,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
            "feedback": feedback,
            "before_conf": feedback.get("before_conf"),
            "after_conf": feedback.get("after_conf"),
            "delta_points": feedback.get("delta_points"),
        })

    # Prepare shuffled snippets for current question
    shuffled_segments = []

    for index, kanji_text in enumerate(current_sentence.jp_segments):
        kana_text = kanji_text

        if current_sentence.jp_kana_segments and index < len(current_sentence.jp_kana_segments):
            kana_text = current_sentence.jp_kana_segments[index]

        shuffled_segments.append({
            "index": index,
            "kanji": kanji_text,
            "kana": kana_text,
        })

    random.shuffle(shuffled_segments)

    return render(request, "core/stage3_sentences.html", {
        "ex": ex,
        "sentence": current_sentence,
        "round_state": round_state,
        "shuffled_segments": shuffled_segments,
        "rows": rows,
        "total_points": total_points,
        "max_points": max_points,
        "stage_percent": stage_percent,
        "feedback": None,
        "before_conf": None,
        "after_conf": None,
        "delta_points": None,
    })