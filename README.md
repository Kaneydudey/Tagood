# Tagood
Website for learners of Japanese
# Tagood Japanese — Learning Platform (MVP)

Tagood Japanese is a web platform for a Japanese language brand and YouTube channel. The goal is to turn each short YouTube lesson into a structured, repeatable learning “exercise” with clear progress tracking.

This repository currently contains the **MVP foundation**: a Django project with a working homepage and the Django Admin enabled for future content management.

---

## Project Vision

Users will be able to create an account and work through exercises based on specific YouTube videos. Each exercise is broken into **4 stages**, and users unlock the next stage by completing the previous one.

### Exercise Stages (planned)

1. **Stage 1 — Core Vocabulary (JP → EN)**
   - 10 key words in flashcard style
   - Users self-rate confidence until reaching **100%**

2. **Stage 2 — Recall + Pitch (EN → JP)**
   - Same 10 words reversed (EN → JP)
   - Focus includes memorizing pitch accent

3. **Stage 3 — Sentence Practice (EN → JP)**
   - 20 sentences using the same 10 words
   - Memorization-focused

4. **Stage 4 — Shadowing (Listening)**
   - Shadowing exercise using the same sentences
   - Completion based on listening repetitions (e.g., **10 listens per sentence**)

---

## Planned Features

- User accounts and profiles
- Progress tracking + stage unlock rules
- Personal lists:
  - all studied sentences
  - all studied vocabulary/phrases
  - ability to favorite/save items
- Weekly leaderboards + achievements
- Subscription tiers (e.g. unlock Stage 4 shadowing, premium requests)
- Admin tools for adding/editing exercises (Django Admin)
- Store section for merch and books

---

## Tech Stack

- **Python / Django**
- **SQLite** for local development (PostgreSQL planned for production)
- Django Admin for content management

---

## Local Setup (Windows)

1. Create and activate a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
