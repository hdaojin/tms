# TMS Feature Checklist

## Before Coding
- Confirm the target app and read its `models.py`, `views.py`, `forms.py`, `tables.py`, `urls.py`, and templates.
- Read `.github/copilot-instructions.md` for required patterns and commands.

## Models & Files
- Prefer constants from `core/constants.py`.
- For file fields:
  - Validate with `validate_file_size` and type validators.
  - Use a stable `upload_to` path with date-based folders.
  - Register cleanup via `register_file_cleanup_signals`.

## Views & Permissions
- Use `TitleMixin` in class-based views; set `title` and `title_icon` when needed.
- Enforce access with `PermissionRequiredMixin`, `OwnerRequiredMixin`, or `CrossGroupAccessMixin`.
- Remember global `LoginRequiredMiddleware`; only open routes with `login_not_required`.

## Forms & Tables
- Use `StyledFormMixin` for forms.
- Use `BaseTable`, `BaseDateColumn`, and `ActionsColumn` for list pages.

## Templates & UI
- Extend `templates/base.html`.
- Use Iconify syntax `icon-[tabler--...]`.
- Ensure sidebar menus are updated in `core/config/menus/*.yml` or app `menus.yml`.

## URLs & Menus
- Wire routes in `tmsproject/urls.py` and app `urls.py`.
- Check if `competitions` routes are enabled before linking to them.

## HTMX
- Check `request.htmx` and return partial templates for fragment updates.
- Ensure CSRF headers are present (base template already sets them).

## Tests
- Add/adjust tests in `<app>/tests.py` for new behavior.

## Run
- `uv run manage.py test <app>`
- `npm run watch:css` for UI changes
