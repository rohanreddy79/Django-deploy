# Django Polls on Vercel

**A Django 4.0 + Django REST Framework polling app (register, create polls, vote, see percentages) packaged for serverless deployment on Vercel.**

## Overview

This is a small server-rendered polling application. Users register and log in with an email address, create a poll with a free-form list of answers, share a per-question link, and watch vote percentages update live. Votes are recorded through a JSON endpoint built with Django REST Framework's `@api_view`, and the question page updates its progress bars from the response without reloading. The project is `poll`, the single app is `questions`, and the UI is Materialize CSS 1.0 (via CDN) for the authenticated pages plus a hand-written stylesheet for the public vote page. `vercel.json` and `build_files.sh` wire the WSGI app and static files into Vercel's Python runtime. The initial migration is dated June 2022 and the code was uploaded to GitHub in one commit in February 2023.

## What it does

- **Accounts**: `register_view` creates a `django.contrib.auth` `User` whose username is the submitted email; `login_view` is meant to authenticate and redirect to `/dashboard/` (see Limitations for its current state).
- **Poll creation** (`/create_poll/`): a POST with `question` and a repeated `answers` field creates one `Question` and one `Answers` row per option; the template adds extra answer inputs with a small jQuery snippet.
- **Results** (`/see_answers/`): lists the current user's questions with a Materialize modal per question showing each answer's percentage (`Answers.calculate_percentage`) and an "Open" link to the public vote page.
- **Voting** (`/question/<uuid>/`): renders the question's answers as selectable options; clicking one `fetch`es `POST /api/save_question_result/` with `{question_uid, answer_uid}`, which increments `Answers.counter` and returns `Question.calculate_percentage()` (a list of integer percentages) that the page writes into the `.percent` labels and the `--w` CSS variable driving each progress bar.
- **Admin**: `QuestionAdmin` (question text, owner) and `AnswerAdmin` (answer text, parent question, counter) are registered at `/admin/`.

## How it works

| Path | Role |
|---|---|
| `poll/settings.py` | Django 4.0.4 settings; `ALLOWED_HOSTS = ['.vercel.app', '.now.sh']`, `STATIC_ROOT = staticfiles_build/static`, `rest_framework` installed |
| `poll/urls.py` | Routes: `/` login, `/register/`, `/dashboard/`, `/create_poll/`, `/see_answers/`, `/question/<question_uid>/`, `/api/save_question_result/`, `/admin/` |
| `poll/wsgi.py` | WSGI entry point; also exports `app = application` for `@vercel/python` |
| `questions/models.py` | `BaseModel` (abstract: UUID primary key, `created_at`, `updated_at`), `Question` (FK to `User`, `question_text`), `Answers` (FK to `Question`, `answer_text`, `counter`) |
| `questions/views.py` | The seven views listed above; `save_question_result` is `@api_view(['POST'])` and `@csrf_exempt` |
| `questions/templates/` | `login`, `register`, `dashboard`, `create_poll`, `see_ansswers` (Materialize), `question` + `css` (custom vote page) |
| `questions/migrations/0001_initial.py` | Creates the two tables (generated 2022-06-05) |
| `html/` | Three static design mock-ups (`index`, `create_polls`, `see_answers`) with placeholder links; not served by Django |
| `vercel.json`, `build_files.sh` | Builds `poll/wsgi.py` with `@vercel/python` (python3.9, 15 MB lambda) and runs `pip install` + `collectstatic` as a `@vercel/static-build` step; routes `/static/*` to the built files and everything else to WSGI |
| `requirements.txt` | `Django==4.0.4`, `djangorestframework==3.13.1`, `asgiref`, `pytz`, `sqlparse`, `tzdata` |
| `db.sqlite3` | A committed SQLite database with the auth, sessions and `questions` migrations already applied |

Key design points: every model row has a UUID primary key, so poll links are unguessable; percentages are computed on the fly from `counter` rather than stored; the vote endpoint is stateless JSON so the public page needs no session.

## Running it

Django 4.0 supports Python 3.8–3.10. The system check was run on this machine:

```bash
uv run --python 3.10 --with 'django==4.0.4' --with 'djangorestframework==3.13.1' python manage.py check
# -> "System check identified 1 issue (0 silenced)."  (staticfiles.W004: the static/ directory does not exist)
```

To actually serve it locally you must first add a database to `poll/settings.py` (the `DATABASES` block is absent; the committed `db.sqlite3` is not referenced anywhere) and allow localhost:

```python
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}}
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.vercel.app', '.now.sh']
```

then (not verified on this machine):

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Deploying: `vercel` from the repo root uses `vercel.json` as-is. Not verified here; note that SQLite on Vercel's read-only filesystem would not persist writes, which is presumably why the database setting was removed.

## Limitations / Notes

- `login_view` begins with `return HttpResponse("<h1> Hey This is Rohan Reddy </h1>")`, so the login form and `authenticate()`/`login()` code below it never run; `/` currently shows that placeholder.
- No view is protected by `login_required`; `create_poll` and `see_answers` use `request.user` and will fail for anonymous visitors. `save_question_result` is unauthenticated and CSRF-exempt, so anyone with a question's UUID can vote repeatedly.
- `Question.calculate_percentage` divides by `total_votes` without guarding zero, so the API raises on the first vote of a poll if no answer has a count; `Answers.calculate_percentage` catches the same case and returns 0.
- `DEBUG = True` and the `SECRET_KEY` are committed; `STATICFILES_DIRS` points at a `static/` directory that does not exist; the results template is named `see_ansswers.html`; sidebar name/email in the templates are hard-coded placeholders.
