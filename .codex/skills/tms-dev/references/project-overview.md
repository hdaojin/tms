# TMS Project Overview

## Entry Points
- `tmsproject/settings.py`: installed apps, middleware, i18n, static/media.
- `tmsproject/urls.py`: app routes; `competitions` is commented; `demo` only loads in `DEBUG`.
- `templates/base.html` and `templates/partials/*`: shared layout and UI.
- `core/config/menus/*.yml`: sidebar menus; some apps also have `menus.yml`.

## Apps (purpose + key files)
- `core`: utilities, constants, menus. Key: `core/constants.py`, `core/utils/*`.
- `accounts`: user profiles and group metadata. Key: `accounts/models.py`.
- `traininglogs`: training log upload and listing. Key: `traininglogs/models.py`, `traininglogs/forms.py`, `traininglogs/tables.py`.
- `meeting`: meeting records upload. Key: `meeting/models.py`, `meeting/forms.py`, `meeting/tables.py`.
- `notices`: notices + attachments + visibility. Key: `notices/models.py`, `notices/forms.py`.
- `notes`: note repositories and asset access. Key: `notes/models.py`, `notes/views.py`, `notes/utils.py`.
- `assessment`: assessments, modules, attachments, scores. Key: `assessment/models.py`, `assessment/forms.py`.
- `competitions`: competition taxonomy, participants, results. Key: `competitions/models.py`, `competitions/fixtures/competitions/default.yaml`.
- `articles`: categories, tags, articles. Key: `articles/models.py`.
- `samba`: samba integration. Key: `samba/models.py`, `samba/samba_sync.py`.
- `demo`: component demos, only in `DEBUG`.

## Files & Uploads
- Public uploads: `media/`.
- Private uploads: `media-private/` (served via views).
- Use `core.utils.signals.register_file_cleanup_signals` for file fields.

## When Exploring a Feature
- Start with the app `models.py`, `views.py`, `forms.py`, `tables.py`, `urls.py`, and templates.
- Then check menus in `core/config/menus/*.yml` or the app `menus.yml`.
- Verify permissions and URL wiring in `tmsproject/urls.py`.
