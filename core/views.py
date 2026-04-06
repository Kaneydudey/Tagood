from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Exercise, UserExerciseProgress, UserVocabProgress, VocabItem
from .flashcards import is_correct_english, choose_next_vocab

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
    ex = get_object_or_404(Exercise, id=exercise_id, is_published=True)
    prog, _ = UserExerciseProgress.objects.get_or_create(user=request.user, exercise=ex)

    if stage == 1:
        prog.stage1_confidence = 100
    elif stage == 2 and prog.unlocked_stage2():
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

from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST


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

    # Optional: enforce "watch video first"
    if not ex_prog.stage1_video_confirmed:
        return redirect("exercise_detail", exercise_id=ex.id)

    vocab_items = list(ex.vocab.all())

    # Map vocab_id -> UserVocabProgress (stage 1)
    progress_qs = UserVocabProgress.objects.filter(
        user=request.user,
        stage=1,
        vocab_item__exercise=ex,
    )
    progress_by_vocab = {p.vocab_item_id: p for p in progress_qs}

    # Ensure every vocab item has a progress row
    for v in vocab_items:
        if v.id not in progress_by_vocab:
            progress_by_vocab[v.id] = UserVocabProgress.objects.create(
                user=request.user,
                vocab_item=v,
                stage=1,
                confidence=2,
            )

    vocab_with_conf = [(v, progress_by_vocab[v.id].confidence) for v in vocab_items]

    total_points = sum(conf for _, conf in vocab_with_conf)
    max_points = 6 * len(vocab_items) if vocab_items else 0
    stage_percent = round((total_points / max_points) * 100) if max_points else 0

    # Keep your existing stage unlock logic compatible:
    ex_prog.stage1_confidence = stage_percent
    ex_prog.save()

    feedback = None
    before_conf = after_conf = delta_points = None

    if request.method == "POST":
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

        feedback = {
            "correct": correct,
            "expected": vocab.en,
        }

        # refresh stats after update
        vocab_with_conf = [(v, progress_by_vocab[v.id].confidence) for v in vocab_items]
        total_points = sum(progress_by_vocab[v.id].confidence for v in vocab_items)
        stage_percent = round((total_points / max_points) * 100) if max_points else 0
        ex_prog.stage1_confidence = stage_percent
        ex_prog.save()

    # choose the next card
    next_card = choose_next_vocab([(v, progress_by_vocab[v.id].confidence) for v in vocab_items]) if vocab_items else None

    vocab_rows = [
        {"jp": v.jp, "en": v.en, "pitch": v.pitch, "confidence": progress_by_vocab[v.id].confidence}
        for v in vocab_items
    ]

    return render(request, "core/stage1_flashcards.html", {
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
    })