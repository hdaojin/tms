from pathlib import Path

from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.http import  Http404

from libs.md2html import markdown_to_html, extract_soup_from_html

# Create your views here.

# Path to the markdown notes directory
NOTES_DIR = Path(settings.MEDIA_ROOT) / 'notes'
NOTES_DIR.mkdir(parents=True, exist_ok=True)  # Create the directory if it doesn't exist

# Validate the notes directory
def _validate_notes_directory(path: Path):
    if not path or not path.is_dir():
        raise Http404("Invalid notes directory")
    
# Convert markdown file to HTML  
def _convert_markdown_file_to_html(file_path: Path):
    if not file_path.exists() or not file_path.is_file() or not file_path.suffix == ".md":
        raise Http404("Note file not found")
    return markdown_to_html(file_path.read_text(encoding='utf-8'))

def list_notes_directories(request):
    """
    List all notes directories in the notes directory
    """
    try:
        subdirectories = [d.name for d in NOTES_DIR.iterdir() if d.is_dir()]
        return render(request, 'notes/directory_list.html', {
            'subdirectories': subdirectories,
            'title': 'Notes Directories'
        })
    except Exception as e:
        return render(request, 'notes/error.html', {
            'error_message': f"An error occurred while fetching notes directories: {str(e)}.",
            'title': 'Error'
        }, status=500)

def get_readme(request, subdirectory):
    """
    Get content of README.md file in the notes directory and convert to HTML
    """
    base_path = NOTES_DIR / subdirectory
    try:
        _validate_notes_directory(base_path)
        readme_files = list((base_path).glob("README.md"))
        if readme_files:
            readme_path = readme_files[0]
            html_content = _convert_markdown_file_to_html(readme_path)
            return render(request, 'notes/note_content.html', {
                'title': f'README - {subdirectory}',
                'html_content': html_content,
                'subdirectory': subdirectory
            })
        else:
            raise Http404("README file not found")

    except Http404 as http_exc:
        raise http_exc

    except Exception as e:
        return render(request, 'notes/error.html', {
            'error_message': f"An error occurred while fetching README file.{str(e)}",
            'title': 'Error'
        }, status=500)
            
def get_note(request, subdirectory, note_file):
    """
    Get content of specified markdown file and convert to HTML
    """
    try:
        note_path = NOTES_DIR.joinpath(subdirectory, f"{note_file}")

        if not note_path.exists() or not note_path.is_file() or not note_path.suffix == ".md":
            raise Http404("Note file not found")

        html_content = markdown_to_html(note_path.read_text(encoding='utf-8'))
        return render(request, 'notes/note_content.html', {
            'title': f'{note_file} - {subdirectory}',
            'html_content': html_content,
            'subdirectory': subdirectory,
            'note_file': note_file
        })

    except Http404 as http_exc:
        raise http_exc

    except Exception as e:
        return render(request, 'notes/error.html', {
            'error_message': f"Failed to get note: {str(e)}",
            'title': 'Error'
        }, status=500)



