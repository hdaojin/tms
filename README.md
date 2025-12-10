# Training Management System (TMS)

## Introduction

Training Management System (TMS) is a web application that helps organizations manage their competition training programs.

It is built using Django, Tailwind CSS, DaisyUI, ~~FlyonUI~~, iconify, HTMX, and more.

## Features

- User management and profile
- Role-based access control (RBAC)
- Notice publishing
- Training log collection
- Meeting record keeping


And more features to come.



## Usage （Development）

### Prerequisites
- Python development environment
- uv (Python virtual environment manager)
- npm (Node.js package manager)

### Clone the repository
```bash
git clone  git@github.com:hdaojin/tms.git
```

### Install dependencies
```bash
cd tms
uv sync
npm install
# Optional: Copy latest JavaScript file to static/js
cp node_modules/htmx.org/dist/htmx.min.js static/js
```

### Migrate database
```bash
cp .env.example .env
uv run manage.py migrate
```

### Load initial data
```bash
uv run manage.py loaddata core/default
uv run manage.py loaddata accounts/default
uv run manage.py loaddata competitions/default
```

### Create superuser
```bash
uv run manage.py createsuperuser
```

### Run the development server
```bash
# In the tmsproject directory
uv run manage.py runserver
```

### Run the tailwindcss

For development, you can use the watch command to automatically compile CSS changes.

```bash
npm run watch:css
```

For production, you can build and optimize with minification at once:

```bash
npm run build:css
```

### Access the development server
```
http://127.0.0.1:8000/
```

### Optional: Update packages
```bash
uv sync -U

# On directory that contains package.json
npm outdated
npm update    
```



