import random

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

    return render(request, "core/exercise_detail.html", {
        "ex": ex,
        "prog": prog,
        "stage2_study_rows": stage2_study_rows,
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
        round_len = ROUND_SIZE
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
    last_feedback_key = f"stage2_last_feedback_{ex.id}"

    round_state = request.session.get(round_key)  # dict or None
    pending = request.session.get(pending_key)    # dict or None (word correct, waiting pitch)

    configured_ids = {v.id for v in configured}

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
            request.session.modified = True

            expected_display = expected
            if expected_romaji:
                expected_display = f"{expected} / {expected_romaji}"

            feedback = {"step": "word", "correct": False, "expected": expected_display}
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
                "expected_span": (vocab.pitch_start, vocab.pitch_end),
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
    # Kana segments are strongly recommended, but we can fall back to JP segments if missing.
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
    progress_by_sentence = {p.sentence_item_id: p for p in progress_qs}

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
    last_feedback_key = _stage3_last_feedback_key(ex.id)

    round_state = request.session.get(round_key)

    # Start round
    if request.method == "POST" and request.POST.get("action") == "start":
        chosen = random.choice(configured)
        request.session[round_key] = {
            "remaining": STAGE3_ROUND_SIZE,
            "total": STAGE3_ROUND_SIZE,
            "correct": 0,
        }
        request.session[current_key] = chosen.id
        request.session.pop(last_feedback_key, None)
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

    # Round finished: completion page
    if round_state["remaining"] <= 0:
        completed = round_state
        last_feedback = request.session.pop(last_feedback_key, None)

        request.session.pop(round_key, None)
        request.session.pop(current_key, None)
        request.session.modified = True

        return render(request, "core/stage3_complete.html", {
            "ex": ex,
            "completed": completed,
            "last_feedback": last_feedback,
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

    feedback = None
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

        # Use kana display if the user was in kana mode and kana segments exist.
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

        feedback = {
            "correct": correct,
            "user_sentence": " ".join(user_segments),
            "correct_sentence": " ".join(display_segments),
            "correct_sentence_natural": correct_natural,
        }

        request.session[last_feedback_key] = feedback

        # Refresh stats after update
        total_points = sum(
            UserSentenceProgress.objects.get(user=request.user, sentence_item=s).confidence
            for s in configured
        )
        stage_percent = round((total_points / max_points) * 100) if max_points else 0
        ex_prog.stage3_confidence = stage_percent
        ex_prog.save()

        if round_state["remaining"] <= 0:
            request.session.modified = True
            return redirect("stage3_sentences", exercise_id=ex.id)

        # Pick the next sentence for the next question
        next_sentence = random.choice(configured)
        request.session[current_key] = next_sentence.id
        request.session.modified = True
        current_sentence = next_sentence

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

    rows = [
        {"en": s.en, "confidence": progress_by_sentence[s.id].confidence}
        for s in configured
    ]

    return render(request, "core/stage3_sentences.html", {
        "ex": ex,
        "sentence": current_sentence,
        "round_state": round_state,
        "shuffled_segments": shuffled_segments,
        "rows": rows,
        "total_points": total_points,
        "max_points": max_points,
        "stage_percent": stage_percent,
        "feedback": feedback,
        "before_conf": before_conf,
        "after_conf": after_conf,
        "delta_points": delta_points,
    })