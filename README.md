# Training Management System (TMS)

## Introduction

Training Management System (TMS) is a web application that helps organizations manage their competition training programs.

It is built using Django, Tailwind CSS, DaisyUI, HTMX, and more.

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
npm install tailwindcss @tailwindcss/cli
npm install -D daisyui@latest
npm install -D @tailwindcss/typography
```

### Migrate database
```bash
cd tmsproject
cp .env.example .env
uv run manage.py migrate
```

### Create superuser
```bash
uv run manage.py createsuperuser
```

### Run the tailwindcss
```bash
# In the tmsproject directory
npx @tailwindcss/cli -i static/css/input.css -o static/css/output.css --watch
```

### Run the development server
```bash
# In the tmsproject directory
uv run manage.py runserver
```

### Access the development server
```
http://127.0.0.1:8000/
```



