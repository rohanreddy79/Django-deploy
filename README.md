# Django Polls on Vercel

[![CI](https://github.com/rohanreddy79/Django-deploy/actions/workflows/ci.yml/badge.svg)](https://github.com/rohanreddy79/Django-deploy/actions/workflows/ci.yml)

**A Django 4.0 + Django REST Framework polling app (register, create polls, vote, see percentages) packaged for serverless deployment on Vercel.**

## Overview

This is a small server-rendered polling application. Users register and log in with an email address, create a poll with a free-form list of answers, share a per-question link, and watch vote percentages update live. Votes are recorded through a JSON endpoint built with Django REST Framework's `@api_view`, and the question page updates its progress bars from the response without reloading. The project is `poll`, the single app is `questions`, and the UI is Materialize CSS 1.0 (via CDN) for the authenticated pages plus a hand-written stylesheet for the public vote page. `vercel.json` and `build_files.sh` wire the WSGI app and static files into Vercel's Python runtime. The initial migration is dated June 2022 and the code was uploaded to GitHub in one commit in February 2023; the October 2026 pass fixed the defects listed in the Changelog and added tests, a license and CI.

## What it does

- **Accounts**: `register_view` creates a `django.contrib.auth` `User` whose username is the submitted email; `login_view` (served at `/`) authenticates and redirects to `/dashboard/`. An unknown email redirects to `/register/`, a wrong password back to `/`, each with a Materialize toast.
- **Poll creation** (`/create_poll/`, login required): a POST with `question` and a repeated `answers` field creates one `Question` and one `Answers` row per option; the template adds extra answer inputs with a small jQuery snippet.
- **Results** (`/see_answers/`, login required): lists the current user's questions with a Materialize modal per question showing each answer's percentage (`Answers.calculate_percentage`) and an "Open" link to the public vote page.
- **Voting** (`/question/<uuid>/`, public): renders the question's answers as selectable options; clicking one `fetch`es `POST /api/save_question_result/` with `{question_uid, answer_uid}` and the page's CSRF token in the `X-CSRFToken` header. The endpoint validates that token for every caller (anonymous voters included), increments `Answers.counter` and returns `Question.calculate_percentage()` (a list of integer percentages, all `0` until the first vote) that the page writes into the `.percent` labels and the `--w` CSS variable driving each progress bar. A request without a valid token gets `403`.
- **Admin**: `QuestionAdmin` (question text, owner) and `AnswerAdmin` (answer text, parent question, counter) are registered at `/admin/`.

## How it works

| Path | Role |
|---|---|
| `poll/settings.py` | Django 4.0.4 settings. `SECRET_KEY`, `DEBUG` and the SQLite path come from `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_DB_PATH` with local-dev defaults; `ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.vercel.app', '.now.sh']`; `LOGIN_URL = '/'`; `STATICFILES_DIRS = [static/]`, `STATIC_ROOT = staticfiles_build/static`; `rest_framework` installed |
| `poll/urls.py` | Routes: `/` login, `/register/`, `/dashboard/`, `/create_poll/`, `/see_answers/`, `/question/<question_uid>/`, `/api/save_question_result/`, `/admin/` |
| `poll/wsgi.py` | WSGI entry point; also exports `app = application` for `@vercel/python` |
| `questions/models.py` | `BaseModel` (abstract: UUID primary key, `created_at`, `updated_at`), `Question` (FK to `User`, `question_text`), `Answers` (FK to `Question`, `answer_text`, `counter`) |
| `questions/views.py` | The seven views listed above; `dashboard`, `create_poll` and `see_answers` are `@login_required`; `save_question_result` is `@api_view(['POST'])` with `CsrfSessionAuthentication`, a `SessionAuthentication` subclass that runs Django's CSRF check unconditionally (DRF only checks it for logged-in users by default) |
| `questions/templates/` | `login`, `register`, `dashboard`, `create_poll`, `see_answers` (Materialize), `question` + `css` (custom vote page) |
| `questions/tests.py` | Ten Django test-client tests: register → login → create poll → vote through the API → results page, CSRF rejection/acceptance under `enforce_csrf_checks=True`, zero-vote percentages, `login_required` redirects, bad poll links |
| `questions/migrations/0001_initial.py` | Creates the two tables (generated 2022-06-05) |
| `static/` | Empty (a `.gitkeep`); the directory `STATICFILES_DIRS` points at, for project-level assets |
| `html/` | Three static design mock-ups (`index`, `create_polls`, `see_answers`) with placeholder links; not served by Django |
| `vercel.json`, `build_files.sh` | Builds `poll/wsgi.py` with `@vercel/python` (python3.9, 15 MB lambda) and runs `pip install` + `collectstatic` as a `@vercel/static-build` step; routes `/static/*` to the built files and everything else to WSGI |
| `requirements.txt` | `Django==4.0.4`, `djangorestframework==3.13.1`, `asgiref`, `pytz`, `sqlparse`, `tzdata` (all pinned) |
| `.github/workflows/ci.yml` | GitHub Actions: Python 3.10, `pip install -r requirements.txt`, `python -m compileall -q .`, `manage.py check`, `manage.py test` |
| `db.sqlite3` | A committed SQLite database with the auth, sessions and `questions` migrations applied and a few sample rows; it is the default database file |

Key design points: every model row has a UUID primary key, so poll links are unguessable; percentages are computed on the fly from `counter` rather than stored; the vote endpoint is JSON and needs no login, only the CSRF token the vote page hands to its own JavaScript.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | the `django-insecure-…` development key | Set a real secret in production |
| `DJANGO_DEBUG` | `1` | Set to `0` in production |
| `DJANGO_DB_PATH` | `<repo>/db.sqlite3` | Location of the SQLite file, e.g. `/tmp/db.sqlite3` on Vercel |

## Running it

Django 4.0 supports Python 3.8–3.10. Everything below was run on this machine (macOS, uv 0.9, CPython 3.10.19, 2026-10):

```bash
uv run --python 3.10 --with-requirements requirements.txt python manage.py check
# -> System check identified no issues (0 silenced).

uv run --python 3.10 --with-requirements requirements.txt python manage.py test --verbosity 2
# -> Ran 10 tests in 0.412s
# -> OK

DJANGO_DB_PATH=/tmp/polls.sqlite3 uv run --python 3.10 --with-requirements requirements.txt python manage.py migrate
# -> Applying questions.0001_initial... OK  /  Applying sessions.0001_initial... OK
DJANGO_DB_PATH=/tmp/polls.sqlite3 uv run --python 3.10 --with-requirements requirements.txt python manage.py runserver
# curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/                        -> 200 (login form)
# curl -s -o /dev/null -w '%{http_code} %{redirect_url}' http://127.0.0.1:8000/dashboard/ -> 302 http://127.0.0.1:8000/?next=/dashboard/
# curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8000/api/save_question_result/ -> 403
```

With a plain virtualenv the equivalent is `pip install -r requirements.txt`, `python manage.py migrate`, `python manage.py runserver`, then open <http://127.0.0.1:8000/>, register, log in, create a poll and open its link from `/see_answers/`. Leaving `DJANGO_DB_PATH` unset writes to the committed `db.sqlite3`.

Deploying: `vercel` from the repo root uses `vercel.json` as-is (not verified here). Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` and `DJANGO_DB_PATH=/tmp/db.sqlite3` in the project's environment variables; the bundle's filesystem is read-only and `/tmp` does not persist between invocations, so votes would not survive a cold start without an external database.

## Limitations / Notes

- Anyone with a question's UUID can vote any number of times: the API checks the CSRF token, not a per-voter session, and the page does not remember a previous vote.
- The vote page renders at most four selectable options (the template hard-codes `opt-1` … `opt-4` inputs), and `Answers` rows are returned in insertion order rather than an explicit ordering.
- No logout view exists; the sidebar's "Logout" link is a placeholder, as are the sidebar name/email in the templates.
- The committed `db.sqlite3` is the default database, so running locally without `DJANGO_DB_PATH` modifies a tracked file.
- SQLite on Vercel's read-only filesystem does not persist writes (see Deploying).

## Changelog

- 2026-10: fixed `login_view` (a placeholder `return` short-circuited authentication), added `login_required` to `dashboard`/`create_poll`/`see_answers` with `LOGIN_URL = '/'`, replaced `csrf_exempt` on the vote API with an always-on CSRF check (the page already sent the token), guarded the zero-vote division in `Question.calculate_percentage`, required both UUIDs in the API (`or` instead of `and`), made bad poll links redirect home instead of crashing, restored `DATABASES` (SQLite, path from `DJANGO_DB_PATH`), moved `SECRET_KEY`/`DEBUG` to environment variables, allowed `localhost`/`127.0.0.1`, renamed `see_ansswers.html` → `see_answers.html`, created the `static/` directory `STATICFILES_DIRS` expects; added ten tests, an MIT license, a complete `.gitignore` (and untracked `__pycache__`) and GitHub Actions CI.
