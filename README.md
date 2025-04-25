# Training Management System (TMS)

## Introduction

Training Management System (TMS) is a web application that helps organizations manage their competition training programs.

It is built using Django, Tailwind CSS, ~~DaisyUI~~, FlyonUI, HTMX, and more.

## Features

- User management

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
# Optional: Copy flyonui.js to static/js directory
cp node_modules/flyonui/flyonui.js static/js
```

### Migrate database
```bash
cp .env.example .env
uv run manage.py migrate
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
```bash
npm run watch:css
```

### Access the development server
```
http://127.0.0.1:8000/
```



