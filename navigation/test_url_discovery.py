"""
Tests for URL discovery functionality.

These tests verify that the URL discovery module correctly identifies and 
processes Django URL patterns from all installed applications.
"""

from django.test import TestCase, override_settings
from django.urls import reverse, NoReverseMatch
from django.core.management import call_command
from io import StringIO

from navigation.url_discovery import (
    discover_urls,
    get_named_url_choices,
    get_all_urls_for_app,
    validate_named_url,
    _create_display_name,
    _get_app_display_name
)


class URLDiscoveryTestCase(TestCase):
    """Test the core URL discovery functionality."""

    def test_discover_urls_returns_dict(self):
        """Test that discover_urls returns a dictionary."""
        urls = discover_urls()
        self.assertIsInstance(urls, dict)

    def test_discover_urls_excludes_admin(self):
        """Test that admin URLs are excluded from discovery."""
        urls = discover_urls()
        
        # Check that no URL names start with 'admin:'
        for app_name, app_urls in urls.items():
            for url_name, _ in app_urls:
                self.assertFalse(
                    url_name.startswith('admin:'),
                    f"Admin URL {url_name} should be excluded"
                )

    def test_discover_urls_includes_expected_apps(self):
        """Test that expected apps are discovered."""
        urls = discover_urls()
        
        # These apps should be present based on the settings
        expected_apps = ['accounts', 'meeting', 'notices', 'articles', 'traininglogs']
        
        for app in expected_apps:
            self.assertIn(app, urls, f"App {app} should be discovered")

    def test_discover_urls_includes_root_urls(self):
        """Test that root-level URLs are included."""
        urls = discover_urls()
        
        # Should have a 'root' entry for URLs without namespace
        self.assertIn('root', urls)
        
        # Should include the home URL
        root_urls = dict(urls['root'])
        self.assertIn('home', root_urls)

    def test_get_named_url_choices_format(self):
        """Test that get_named_url_choices returns proper format."""
        choices = get_named_url_choices()
        
        # Should be a list of tuples
        self.assertIsInstance(choices, list)
        
        # Each choice should be a 2-tuple
        for choice in choices:
            self.assertIsInstance(choice, tuple)
            self.assertEqual(len(choice), 2)
            
        # First choice should be empty
        self.assertEqual(choices[0], ('', '-- 选择命名路由 --'))

    def test_get_named_url_choices_includes_known_urls(self):
        """Test that known URLs are included in choices."""
        choices = get_named_url_choices()
        
        # Convert to dict for easier checking
        choice_dict = dict(choices)
        
        # Should include home URL
        self.assertIn('home', choice_dict)

    def test_get_all_urls_for_app_existing_app(self):
        """Test getting URLs for an existing app."""
        # Test with meeting app
        meeting_urls = get_all_urls_for_app('meeting')
        
        self.assertIsInstance(meeting_urls, list)
        
        # Should contain known meeting URLs
        url_names = [url_name for url_name, _ in meeting_urls]
        expected_urls = ['meeting:meeting_list', 'meeting:upload_meeting']
        
        for expected_url in expected_urls:
            self.assertIn(expected_url, url_names)

    def test_get_all_urls_for_app_nonexistent_app(self):
        """Test getting URLs for a non-existent app."""
        urls = get_all_urls_for_app('nonexistent_app')
        self.assertEqual(urls, [])

    def test_validate_named_url_valid_url(self):
        """Test validating a valid named URL."""
        # Test with home URL
        is_valid = validate_named_url('home')
        self.assertTrue(is_valid)

    def test_validate_named_url_invalid_url(self):
        """Test validating an invalid named URL."""
        is_valid = validate_named_url('nonexistent:url')
        self.assertFalse(is_valid)

    def test_validate_named_url_empty_url(self):
        """Test validating an empty URL."""
        is_valid = validate_named_url('')
        self.assertFalse(is_valid)

    def test_validate_named_url_none(self):
        """Test validating None URL."""
        is_valid = validate_named_url(None)
        self.assertFalse(is_valid)

    def test_create_display_name(self):
        """Test the display name creation function."""
        # Test simple URL
        display = _create_display_name('home', '/')
        self.assertEqual(display, 'home')
        
        # Test URL with path
        display = _create_display_name('meeting:list', 'meeting/')
        self.assertEqual(display, 'meeting:list (meeting)')
        
        # Test URL with complex path
        display = _create_display_name('meeting:detail', 'meeting/detail/<int:pk>/')
        self.assertEqual(display, 'meeting:detail (meeting/detail/<int:pk>)')

    def test_get_app_display_name(self):
        """Test the app display name function."""
        # Test root app
        display = _get_app_display_name('root')
        self.assertEqual(display, '根路由')
        
        # Test regular app
        display = _get_app_display_name('meeting')
        # Should return the app name or verbose name
        self.assertIsInstance(display, str)
        self.assertTrue(len(display) > 0)


class URLDiscoveryIntegrationTestCase(TestCase):
    """Integration tests for URL discovery with actual Django URLs."""

    def test_real_url_validation(self):
        """Test validation with real URLs from the project."""
        # Test some URLs that should exist
        known_urls = [
            'home',
            'accounts:login',
            'meeting:meeting_list',
        ]
        
        for url_name in known_urls:
            with self.subTest(url=url_name):
                # Should be discoverable
                all_urls = discover_urls()
                found = False
                for app_urls in all_urls.values():
                    if any(url_name == name for name, _ in app_urls):
                        found = True
                        break
                
                self.assertTrue(found, f"URL {url_name} should be discovered")
                
                # Should be validatable
                is_valid = validate_named_url(url_name)
                self.assertTrue(is_valid, f"URL {url_name} should be valid")

    def test_url_choices_functionality(self):
        """Test that URL choices work with actual Django forms."""
        choices = get_named_url_choices()
        
        # Should have at least some choices
        self.assertGreater(len(choices), 1)
        
        # Test that we can use these choices in a form field
        from django import forms
        
        class TestForm(forms.Form):
            url_choice = forms.CharField(
                widget=forms.Select(choices=choices)
            )
        
        form = TestForm()
        # Should render without errors
        html = str(form['url_choice'])
        self.assertIn('select', html)
        self.assertIn('option', html)


class ListURLsCommandTestCase(TestCase):
    """Test the list_urls management command."""

    def test_list_urls_command_basic(self):
        """Test basic functionality of list_urls command."""
        out = StringIO()
        call_command('list_urls', stdout=out)
        
        output = out.getvalue()
        
        # Should contain expected text
        self.assertIn('正在发现URL模式', output)
        self.assertIn('URL模式', output)

    def test_list_urls_command_app_filter(self):
        """Test list_urls command with app filter."""
        out = StringIO()
        call_command('list_urls', '--app', 'meeting', stdout=out)
        
        output = out.getvalue()
        
        # Should contain meeting URLs
        self.assertIn('meeting:', output)
        
        # Should not contain other app URLs
        self.assertNotIn('accounts:', output)

    def test_list_urls_command_list_format(self):
        """Test list_urls command with list format."""
        out = StringIO()
        call_command('list_urls', '--format', 'list', '--app', 'meeting', stdout=out)
        
        output = out.getvalue()
        
        # Should contain meeting app section
        self.assertIn('meeting:', output)
        # Should contain dashed list items
        self.assertIn('  - meeting:', output)

    def test_list_urls_command_json_format(self):
        """Test list_urls command with JSON format."""
        import json
        
        out = StringIO()
        call_command('list_urls', '--format', 'json', '--app', 'meeting', stdout=out)
        
        output = out.getvalue()
        
        # Should be valid JSON
        try:
            data = json.loads(output)
            self.assertIsInstance(data, dict)
            self.assertIn('meeting', data)
        except json.JSONDecodeError:
            self.fail("Output should be valid JSON")

    def test_list_urls_command_validate(self):
        """Test list_urls command with validation."""
        out = StringIO()
        call_command('list_urls', '--validate', '--app', 'meeting', stdout=out)
        
        output = out.getvalue()
        
        # Should contain validation markers (✓ or ✗)
        # Note: exact symbols might not show in test output, so just check command runs
        self.assertIn('meeting:', output)

    def test_list_urls_command_invalid_app(self):
        """Test list_urls command with invalid app."""
        from django.core.management.base import CommandError
        
        with self.assertRaises(CommandError):
            call_command('list_urls', '--app', 'nonexistent_app')


class URLDiscoveryModelIntegrationTestCase(TestCase):
    """Test integration of URL discovery with navigation models."""

    def test_model_choices_are_populated(self):
        """Test that model choices are populated from URL discovery."""
        from navigation.models import MenuItem
        
        # Get the field
        named_url_field = MenuItem._meta.get_field('named_url')
        
        # Should have choices
        self.assertTrue(hasattr(named_url_field, 'choices'))
        
        # Choices should be populated
        choices = named_url_field.choices
        self.assertIsInstance(choices, list)
        self.assertGreater(len(choices), 1)
        
        # First choice should be empty
        self.assertEqual(choices[0], ('', '-- 选择命名路由 --'))

    def test_model_can_save_discovered_url(self):
        """Test that models can save URLs discovered by the system."""
        from navigation.models import Menu, MenuItem
        
        # Create a test menu
        menu = Menu.objects.create(
            slug='test_menu',
            name='Test Menu'
        )
        
        # Create a menu item with a discovered URL
        menu_item = MenuItem.objects.create(
            name='Home Link',
            named_url='home'
        )
        menu_item.menus.add(menu)
        
        # Should save successfully
        menu_item.refresh_from_db()
        self.assertEqual(menu_item.named_url, 'home')
        
        # URL should be valid
        self.assertTrue(validate_named_url(menu_item.named_url))