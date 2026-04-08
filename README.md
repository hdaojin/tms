# Training Management System (TMS)

## Introduction

Training Management System (TMS) is a web application that helps organizations manage their competition training programs.

It is built using Django, Tailwind CSS, DaisyUI, ~~FlyonUI~~, iconify, HTMX, and more.

## Requirements

- Python 3.13+
- Django 6.0+
- Tailwind CSS 4.0+
- DaisyUI 5.0+
- django-htmx 1.27+

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
uv run manage.py loaddata conduct/default
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
Copy-Item "node_modules\alpinejs\dist\cdn.min.js" "static\js\alpinejs.min.js"
```




