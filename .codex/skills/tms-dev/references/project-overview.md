# TMS Project Overview

## Entry Points
- `tmsproject/settings.py`: installed apps, middleware, i18n, static/media.
- `tmsproject/urls.py`: app routes; `demo` only loads in `DEBUG`.
- `templates/base.html` and `templates/partials/*`: shared layout and UI.
- `core/config/menus/*.yml`: sidebar menu items.
- `core/config/menus.yml`: sidebar menu grouping and layout.

## Apps (purpose + key files)
- `core`: utilities, constants, menus, upload specs. Key: `core/constants.py`, `core/uploads.py`, `core/utils/*`.
- `accounts`: user profiles and group metadata. Key: `accounts/models.py`.
- `traininglogs`: training log upload and listing. Key: `traininglogs/models.py`, `traininglogs/forms.py`, `traininglogs/tables.py`.
- `meetings`: meeting records upload. Key: `meetings/models.py`, `meetings/forms.py`, `meetings/tables.py`.
- `notices`: notices + attachments + visibility. Key: `notices/models.py`, `notices/forms.py`.
- `notes`: note repositories and asset access. Key: `notes/models.py`, `notes/views.py`, `notes/utils.py`.
- `assessments`: assessments, modules, attachments, scores. Key: `assessments/models.py`, `assessments/forms.py`.
- `behaviors`: behavior reward/penalty records. Key: `behaviors/models.py`, `behaviors/forms.py`.
- `competitions`: competition taxonomy, participants, results. Key: `competitions/models.py`, `competitions/fixtures/competitions/default.yaml`.
- `skills`: skill/resource pages. Key: `skills/models.py`, `skills/views.py`.
- `articles`: categories, tags, articles. Key: `articles/models.py`.
- `samba`: samba integration. Key: `samba/models.py`, `samba/samba_sync.py`.
- `demo`: component demos, only in `DEBUG`.

## Files & Uploads
- Public uploads: `media/`.
- Private uploads: `settings.PRIVATE_MEDIA_ROOT` (default `media-private/`, served via views).
- Upload rules and reusable storage helpers: `core/uploads.py`.
- Multiple-file form fields: `core/forms/fields.py`.
- Use `core.utils.signals.register_file_cleanup_signals` for file fields.

## When Exploring a Feature
- Start with the app `models.py`, `views.py`, `forms.py`, `tables.py`, `urls.py`, and templates.
- Then check menus in `core/config/menus/*.yml` and group placement in `core/config/menus.yml`.
- Verify permissions and URL wiring in `tmsproject/urls.py`.
