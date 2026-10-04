# Zehnify

A Django-based ECAT / MDCAT test-prep platform, built for the CSC Back-to-School Hackathon.

Students sign up, choose their stream (Pre-Engineering or Pre-Medical), and work through subjects chapter by chapter, with lectures, subtopic-level practice, exams and progress tracking.

## Features

- **Stream-aware content:** subjects and chapters shown depend on the stream chosen at signup
- **Subtopic-based learning:** each chapter is split into subtopics, each with embedded YouTube lectures and its own practice questions
- **Mixed practice:** pick several subtopics and practice them together
- **Chapter exams** with a full answer review afterwards
- **My Mistakes:** revisit the questions you got wrong
- **Chapter notes** saved per student
- **Progress tracking:** chapter mastery and subject progress weighted by chapter weightage

## Quick start

Developed and tested on Python 3.14, which is the version the pinned packages in `requirements.txt` were installed on. Using Python 3.14 is the safest choice.

```
git clone https://github.com/haiderrjarar91-afk/Zehnify.git
cd Zehnify
python -m venv .venv
```

Activate the virtual environment:

```
# Windows (cmd)
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Then install and run:

```
pip install -r requirements.txt
python manage.py runserver
```

Open http://127.0.0.1:8000/ and **sign up** (choose Pre-Engineering or Pre-Medical). There are no pre-made accounts. No `migrate` step is needed, because the demo database is already up to date.

## Demo data

The repo ships with `db_demo.sqlite3`, a sanitized copy of the project database containing the subjects, chapters, questions and lectures, with **no user accounts or personal data**.

`settings.py` uses `db.sqlite3` if it exists, and otherwise falls back to `db_demo.sqlite3`, so a fresh clone works without any setup. Accounts you create are saved in `db_demo.sqlite3` on your own machine.

Only a few chapters are published in the demo. The remaining chapters are hidden with an `is_published` flag while their questions and lectures are still being tagged, so you will see a small, finished set of chapters rather than half-finished ones.

## Admin (optional)

```
python manage.py createsuperuser
```

Then open http://127.0.0.1:8000/admin/ to browse chapters, questions and lectures.

## Project layout

- `myproject/`: Django project settings and URLs
- `ZehnifyApp/`: the main app (models, views, templates, migrations)
- `ZehnifyApp/fixtures/`: question banks as JSON
- `import_mcqs.py`: imports MCQ JSON files into the database
- `db_demo.sqlite3`: sanitized demo database

## Tech

Python, Django, SQLite, HTML, CSS. Lectures are embedded YouTube videos.