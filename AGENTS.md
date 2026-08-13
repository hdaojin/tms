# AGENTS.md

## Project Overview
TMS is a Django 6 monolith for training logs, assessments, meetings, notices, notes, behaviors, competitions, skills, Samba integration, articles, and account management. Use Chinese (`zh-hans`) for user-facing model names, form labels, validation errors, messages, and documentation. The default timezone is `Asia/Shanghai`.

## First Reads
- Treat this `AGENTS.md` as the authoritative project instruction file.
- Read `README.md` for setup, deployment, and command conventions.
- For user-visible feature changes, inspect and update `docs/user-manual/`.
- Check the target app's `models.py`, `forms.py`, `views.py`, `tables.py`, `urls.py`, templates, `core/config/navigation.yml`, tests, and migrations before editing.

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `hdaojin/tms`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default five-label triage vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repo. See `docs/agents/domain.md`.

## 指导文件边界

- `AGENTS.md` 是唯一的项目级开发指导文件，维护长期工程规范、架构边界和默认开发流程。
- `CONTEXT.md` 维护领域术语、业务语义和领域不变量。
- `docs/adr/` 记录已经作出的重要架构决策。
- `.github/copilot-instructions.md` 只作为 Copilot 入口，指向上述权威文件，不维护第二套详细规范。
- 当前仓库不维护通用的 TMS 开发 Skill；只有出现明确、专项且可重复的工作流时才新增 Skill，且不得复制项目通用规范。

## 默认开发闭环

需求/权限/入口 → 追踪实际纵向链路 → 明确 model、form、service、selector、view、template 职责 → 实现最小完整切片 → 检查事务、幂等、并发、N+1 和文件副作用 → 测试、migration check、Ruff、CSS build → 行为变化时同步用户文档或 README。

## Commands
Run all Django commands from the repository root because `.env` may use a relative SQLite URL.

- Install/sync Python deps: `uv sync`
- Add Python deps: `uv add <package>`
- Run checks: `uv run manage.py check`
- Run lint: `uv run ruff check .`
- Make migrations: `uv run manage.py makemigrations`
- Apply migrations: `uv run manage.py migrate`
- Run tests: `uv run pytest`
- Run focused tests: `uv run pytest <app-or-test-path>`
- Build CSS: `npm run build:css`
- Watch CSS: `npm run watch:css`
- Copy mermaid bundle to `static/js/`: `npm run copy:mermaid`
- Copy Alpine.js bundle to `static/js/`: `npm run copy:alpine`
- Copy both at once: `npm run copy:static`

The project-level uv cache is configured as `.uv-cache/` in `pyproject.toml` to avoid Windows global-cache permission issues; run uv commands normally from the repository root.

Prefer focused app tests over the full suite unless the change crosses app boundaries.

## Pre-Push Requirement

- Before every `git push`, run `npm run build:css` from the repository root.
- Do not push if the CSS build fails. After a successful build, check `static/css/output.css` and include the generated change in the intended commit when it differs.

## Static JS Bundle Maintenance

`static/js/mermaid.min.js` and `static/js/alpinejs.min.js` are vendored from npm packages and committed to the repository. After upgrading either package in `package.json`, immediately run the corresponding copy script to sync the bundle:

- Upgraded `mermaid` → run `npm run copy:mermaid`
- Upgraded `@alpinejs/csp` → run `npm run copy:alpine`
- Upgraded both → run `npm run copy:static`

Include the updated `static/js/*.min.js` file in the same commit as the `package.json` and `package-lock.json` changes. Never upgrade the npm version without also running the copy script.

`static/css/prism.css` and `static/js/prism.js` are a custom Prism build downloaded from the Prism website builder. The exact build URL (with all selected languages and plugins) is preserved in the first-line comment of `prism.js`. To upgrade: open that URL, change the version number, download the new JS and CSS files, and replace the existing ones. There is no npm automation for this.

`static/js/htmx.js` is a project-authored script (CSRF token injection for HTMX requests), not the HTMX library itself. Do not replace or auto-update it. The HTMX runtime is provided by the `django-htmx` Python package via its template tag and collected by `collectstatic`; upgrade HTMX by upgrading `django-htmx` with `uv add django-htmx@<version>`.

## Architecture Rules
- Use Django's default `auth.User`; do not introduce a custom User model.
- Keep role/group names, upload limits, paths, and shared constants in `core/constants.py`; keep reusable upload behavior, upload specs, and private storage helpers in `core/uploads.py`.
- Global login is enforced by `LoginRequiredMiddleware`; public views must explicitly use `login_not_required`.
- Preserve middleware ordering in `tmsproject/settings.py`.
- App URLs must be included from `tmsproject/urls.py` with `app_name` namespaces.
- Navigation lives in `core/config/navigation.yml`; templates render the parsed navigation from `core.navigation`.

## Code Patterns
- Use `TitleMixin` for class-based views and set `title` plus `title_icon`.
- Use `StyledFormMixin` for forms.
- Use `BaseTable`, `BaseDateColumn`, `BaseDateTimeColumn`, and `ActionsColumn` from `core.tables` for list/table pages.
- Use `OwnerRequiredMixin`, `CrossGroupAccessMixin`, `PermissionRequiredMixin`, or `SuperuserRequiredMixin` for access control.
- Templates and compatibility layers may display users as `user.display_name` or `user.full_info`; new Python logic should prefer `accounts.services.users.get_user_display_name()` or `get_user_full_info()`.
- For file fields, use `core.uploads.UploadSpec`, `UploadSizeValidator`, `PrivateMediaStorage`, project upload constants, and cleanup signals.
- For multiple file form inputs, use `core.forms.fields.MultipleFileField` and `MultipleFileInput`.
- Keep edits scoped; do not refactor unrelated modules.

## Templates And Frontend
- Extend `layouts/app.html`, `layouts/minimal.html`, `layouts/auth.html`, `layouts/print.html`, or `layouts/htmx.html`; `templates/base.html` is only a thin base entry.
- Reuse components from `templates/components/`, especially `components/form.html`, `components/field.html`, and `components/table_wrapper.html`.
- Use DaisyUI/Tailwind classes consistent with existing templates.
- Use Iconify classes like `icon-[tabler--calendar]`.
- Do not dynamically concatenate Tailwind/Iconify classes in templates.
- Do not add inline scripts, inline event handlers, or `javascript:` links.
- If templates introduce new Tailwind/Iconify classes, rebuild and commit `static/css/output.css`.
- Do not put secrets or raw credentials into templates, context debug output, tests, logs, or docs.

## Security And Sensitive Data
- Never read, print, or commit `.env` secrets unless explicitly required and safe.
- `.env` is ignored; `.env.example` documents required variables.
- Public uploads live in `media/`; private/sensitive uploads live under `settings.PRIVATE_MEDIA_ROOT` (default `media-private/`) and must not be served directly.
- AI API keys are encrypted through `accounts.services.ai_crypto`.
- `UserAIModelCredential` must not be registered in Django admin.
- Shared AI credentials may be callable through backend helpers but must never reveal raw API keys.
- Production must set `AI_API_KEY_ENCRYPTION_KEY`.

## Documentation
When changing user-visible behavior, update the matching user manual under `docs/user-manual/`. Include entry paths, roles, permissions, field meanings, workflows, and important limitations.

## Git And Workspace Safety
- The working tree may contain user changes. Do not revert or overwrite changes you did not make.
- Avoid destructive commands such as `git reset --hard` or `git checkout --` unless explicitly requested.
- Treat generated files such as migrations, `uv.lock`, `package-lock.json`, and `static/css/output.css` as intentional when the related source change requires them.
