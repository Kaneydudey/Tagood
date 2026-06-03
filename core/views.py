from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from .models import Exercise, UserExerciseProgress, UserVocabProgress, VocabItem
from .flashcards import is_correct_english, choose_next_vocab, is_correct_japanese


# -----------------------------
# Stage 1 settings
# -----------------------------
ROUND_SIZE = 10  # Stage 1 round size


def _round_key(exercise_id: int) -> str:
    return f"stage1_round_{exercise_id}"


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


@login_required
def dashboard(request):
    exercises = Exercise.objects.filter(is_published=True)
    progress_qs = UserExerciseProgress.objects.filter(user=request.user)
    progress_by_ex = {p.exercise_id: p for p in progress_qs}

    rows = []
    for ex in exercises:
        prog = progress_by_ex.get(ex.id)
        if prog is None:
            prog = UserExerciseProgress.objects.create(user=request.user, exercise=ex)
        rows.append((ex, prog))

    return render(request, "core/dashboard.html", {"rows": rows})


@login_required
def exercise_detail(request, exercise_id):
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)
    prog, _ = UserExerciseProgress.objects.get_or_create(user=request.user, exercise=ex)
    return render(request, "core/exercise_detail.html", {"ex": ex, "prog": prog})


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
    ex_prog, _ = UserExerciseProgress.objects.get_or_create(user=request.user, exercise=ex)

    # Optional gate (safe even if older DB rows exist)
    if not getattr(ex_prog, "stage1_video_confirmed", False):
        return redirect("exercise_detail", exercise_id=ex.id)

    vocab_items = list(ex.vocab.all())
    if not vocab_items:
        return render(
            request,
            "core/stage1_overview.html",
            {"ex": ex, "vocab_rows": [], "can_start": False},
        )

    # Load/create per-user vocab progress (stage 1)
    progress_qs = UserVocabProgress.objects.filter(
        user=request.user,
        stage=1,
        vocab_item__exercise=ex,
    )
    progress_by_vocab = {p.vocab_item_id: p for p in progress_qs}

    for v in vocab_items:
        if v.id not in progress_by_vocab:
            progress_by_vocab[v.id] = UserVocabProgress.objects.create(
                user=request.user,
                vocab_item=v,
                stage=1,
                confidence=2,
            )

    # Stats (points-based)
    max_points = 6 * len(vocab_items)
    total_points = sum(progress_by_vocab[v.id].confidence for v in vocab_items)
    stage_percent = round((total_points / max_points) * 100) if max_points else 0
    ex_prog.stage1_confidence = stage_percent
    ex_prog.save()

    # Session round state
    key = _round_key(ex.id)
    round_state = request.session.get(key)  # dict or None

    # Start a round
    if request.method == "POST" and request.POST.get("action") == "start":
        round_len = min(ROUND_SIZE, len(vocab_items))
        request.session[key] = {"remaining": round_len, "total": round_len, "correct": 0}
        request.session.modified = True
        return redirect("stage1_flashcards", exercise_id=ex.id)

    # No active round: show overview (answers visible here)
    if not round_state:
        vocab_rows = [
            {
                "jp": v.jp,
                "en": v.en,
                "pitch": v.pitch,
                "confidence": progress_by_vocab[v.id].confidence,
            }
            for v in vocab_items
        ]
        return render(
            request,
            "core/stage1_overview.html",
            {
                "ex": ex,
                "vocab_rows": vocab_rows,
                "can_start": True,
                "total_points": total_points,
                "max_points": max_points,
                "stage_percent": stage_percent,
            },
        )

    # Round finished: show completion screen
    if round_state["remaining"] <= 0:
        completed = round_state
        request.session.pop(key, None)
        request.session.modified = True
        return render(
            request,
            "core/stage1_complete.html",
            {
                "ex": ex,
                "completed": completed,
                "total_points": total_points,
                "max_points": max_points,
                "stage_percent": stage_percent,
            },
        )

    feedback = None
    before_conf = after_conf = delta_points = None

    # Answer submission (typed)
    if request.method == "POST" and request.POST.get("action") == "answer":
        vocab_id = int(request.POST["vocab_id"])
        answer = request.POST.get("answer", "")

        vocab = get_object_or_404(VocabItem, id=vocab_id, exercise=ex)
        vp = progress_by_vocab[vocab.id]
        before_conf = vp.confidence

        correct = is_correct_english(answer, vocab.en)
        if correct and vp.confidence < 6:
            vp.confidence += 1
        elif (not correct) and vp.confidence > 1:
            vp.confidence -= 1
        vp.save()

        after_conf = vp.confidence
        delta_points = after_conf - before_conf

        if correct:
            round_state["correct"] += 1
        round_state["remaining"] -= 1
        request.session[key] = round_state
        request.session.modified = True

        feedback = {"correct": correct, "expected": vocab.en}

        # refresh stats after update
        total_points = sum(progress_by_vocab[v.id].confidence for v in vocab_items)
        stage_percent = round((total_points / max_points) * 100) if max_points else 0
        ex_prog.stage1_confidence = stage_percent
        ex_prog.save()

        # If that was the last question, redirect to completion page cleanly
        if round_state["remaining"] <= 0:
            return redirect("stage1_flashcards", exercise_id=ex.id)

    # Choose next card (weighted)
    next_card = choose_next_vocab([(v, progress_by_vocab[v.id].confidence) for v in vocab_items])

    # While studying: JP + confidence only (no EN answers)
    vocab_rows = [
        {"jp": v.jp, "pitch": v.pitch, "confidence": progress_by_vocab[v.id].confidence}
        for v in vocab_items
    ]

    return render(
        request,
        "core/stage1_flashcards.html",
        {
            "ex": ex,
            "next_card": next_card,
            "vocab_rows": vocab_rows,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
            "feedback": feedback,
            "before_conf": before_conf,
            "after_conf": after_conf,
            "delta_points": delta_points,
            "round_state": round_state,
        },
    )


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
    progress_qs = UserVocabProgress.objects.filter(user=request.user, stage=2, vocab_item__in=configured)
    progress_by_vocab = {p.vocab_item_id: p for p in progress_qs}

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

    round_state = request.session.get(round_key)  # dict or None
    pending = request.session.get(pending_key)    # dict or None (word correct, waiting pitch)

    # Start round
    if request.method == "POST" and request.POST.get("action") == "start":
        round_len = min(STAGE2_ROUND_SIZE, len(configured))
        request.session[round_key] = {"remaining": round_len, "total": round_len, "perfect": 0}
        request.session.pop(pending_key, None)
        request.session.modified = True
        return redirect("stage2_flashcards", exercise_id=ex.id)

    # No round yet => Overview
    if not round_state:
        rows = [{"en": v.en, "confidence": progress_by_vocab[v.id].confidence} for v in configured]
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

    # Finished round => Complete page
    if round_state["remaining"] <= 0:
        completed = round_state
        request.session.pop(round_key, None)
        request.session.pop(pending_key, None)
        request.session.modified = True
        return render(request, "core/stage2_complete.html", {
            "ex": ex,
            "completed": completed,
            "total_points": total_points,
            "max_points": max_points,
            "stage_percent": stage_percent,
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

        if not is_correct_japanese(answer_jp, expected):
            # Wrong word => confidence down, consume 1 question
            before_conf = vp.confidence
            vp.confidence = max(1, vp.confidence + DELTA_WORD_WRONG)
            vp.save()

            after_conf = vp.confidence
            delta_points = after_conf - before_conf

            round_state["remaining"] -= 1
            request.session[round_key] = round_state
            request.session.pop(pending_key, None)
            request.session.modified = True

            feedback = {"step": "word", "correct": False, "expected": expected}
        else:
            # Word correct => go to pitch step (do NOT consume question yet)
            request.session[pending_key] = {"vocab_id": vocab.id}
            request.session.modified = True
            feedback = {"step": "word", "correct": True}

    elif request.method == "POST" and request.POST.get("action") == "submit_pitch":
        # Must have pending vocab
        if not pending or "vocab_id" not in pending:
            request.session.pop(pending_key, None)
            request.session.modified = True
            return redirect("stage2_flashcards", exercise_id=ex.id)

        vocab = get_object_or_404(VocabItem, id=int(pending["vocab_id"]), exercise=ex)
        vp = progress_by_vocab[vocab.id]

        try:
            user_start = int(request.POST.get("pitch_start", ""))
            user_end = int(request.POST.get("pitch_end", ""))
        except ValueError:
            user_start = user_end = None

        if user_start is None or user_end is None:
            feedback = {"step": "pitch", "correct": False, "error": "Please select a start and end mora."}
        else:
            correct_pitch = (user_start == vocab.pitch_start) and (user_end == vocab.pitch_end)

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
            request.session.modified = True

            feedback = {
                "step": "pitch",
                "correct": correct_pitch,
                "expected_span": (vocab.pitch_start, vocab.pitch_end),
            }

            if round_state["remaining"] <= 0:
                return redirect("stage2_flashcards", exercise_id=ex.id)

    # Refresh stats after update
    total_points = sum(progress_by_vocab[v.id].confidence for v in configured)
    stage_percent = round((total_points / max_points) * 100) if max_points else 0
    ex_prog.stage2_confidence = stage_percent
    ex_prog.save()

    # Choose current prompt:
    pending = request.session.get(pending_key)
    if pending:
        current_vocab = get_object_or_404(VocabItem, id=int(pending["vocab_id"]), exercise=ex)
        show_pitch = True
    else:
        current_vocab = choose_next_vocab([(v, progress_by_vocab[v.id].confidence) for v in configured])
        show_pitch = False

    rows = [{"en": v.en, "confidence": progress_by_vocab[v.id].confidence} for v in configured]

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