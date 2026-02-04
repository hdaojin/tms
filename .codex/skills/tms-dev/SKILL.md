---
name: tms-dev
description: TMS 项目开发规范与流程。用于在该仓库中新增或修改 Django 模型、视图、表单、模板、菜单、权限、文件上传与 HTMX 交互，并遵循 TitleMixin / StyledFormMixin / BaseTable 等项目约定。
---

# TMS Development

## Required Reading
- Open `.github/copilot-instructions.md` first to get stack, conventions, and commands.

## References
- Open `references/project-overview.md` when you need a quick map of apps, key entry points, and URL/menu notes.
- Open `references/feature-checklist.md` when you want a step-by-step checklist for adding or updating a feature.

## Core Conventions
- Use `TitleMixin` for class-based views; set `title` and optional `title_icon`.
- Use `StyledFormMixin` for forms.
- Use `BaseTable` + `ActionsColumn` and `BaseDateColumn` for list pages.
- Use constants from `core/constants.py`; avoid hard-coded group names, upload limits, or paths.
- Validate file uploads with `validate_file_size` and type validators; register cleanup with `register_file_cleanup_signals`.
- Use `upload_to` helpers with stable, date-based paths; prefer `*_UPLOAD_DIR` and `*_ALLOWED_EXTENSIONS` from settings or constants.
- Keep LoginRequired as the default; open pages with `login_not_required` only when intended.
- Use `CrossGroupAccessMixin` for coach/competitor cross-group access.
- For HTMX, check `request.htmx` and return partial templates for fragment updates.
- Extend `templates/base.html`; hide sidebars via `left_sidebar` / `right_sidebar` blocks.
- Use Iconify class format `icon-[tabler--...]` for icons.

## Feature Workflow
- Identify the target app and reuse its patterns by reading `models.py`, `views.py`, `forms.py`, `tables.py`, `urls.py`, and templates.
- Add or update URLs in `tmsproject/urls.py` and the app `urls.py`.
- Update menus in `core/config/menus/*.yml` or the app `menus.yml`.
- Add permissions to models or views as needed and reflect them in templates.
- Add or update tests in `<app>/tests.py` for new behavior.

## Common Commands
- `uv sync`
- `uv run manage.py migrate`
- `uv run manage.py test <app>`
- `npm install`
- `npm run watch:css`
- `npm run build:css`

## Notes
- For HTML/CSS edits, include `https://daisyui.com/llms.txt` in the prompt to reference DaisyUI docs.
- The `demo` app only loads in `DEBUG`.
- `competitions` routes may be disabled in `tmsproject/urls.py`; verify before adding links.
