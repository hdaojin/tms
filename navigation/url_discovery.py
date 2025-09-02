"""
URL Discovery Module for TMS Navigation

This module provides functionality to automatically discover all named URLs
from Django applications (excluding admin) and provide them as choices for
the MenuItem model's named_url field.
"""

import logging
from typing import List, Tuple, Dict, Set
from django.apps import apps
from django.urls import get_resolver
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def discover_urls() -> Dict[str, List[Tuple[str, str]]]:
    """
    Discover all named URLs from installed Django applications.
    
    Returns:
        Dict mapping app names to lists of (url_name, display_name) tuples.
        Excludes admin URLs by default.
    """
    url_patterns = {}
    
    try:
        resolver = get_resolver()
        
        # Get all URL patterns from the root resolver
        all_patterns = _extract_url_patterns(resolver, '', set())
        
        # Group by app name
        for url_name, url_path in all_patterns:
            # Skip admin URLs
            if url_name.startswith('admin:'):
                continue
                
            # Determine app name from URL name
            app_name = 'root'  # Default for URLs without namespace
            if ':' in url_name:
                app_name = url_name.split(':')[0]
            
            if app_name not in url_patterns:
                url_patterns[app_name] = []
            
            # Create display name (prettier version of URL name)
            display_name = _create_display_name(url_name, url_path)
            url_patterns[app_name].append((url_name, display_name))
        
        # Sort within each app
        for app_name in url_patterns:
            url_patterns[app_name].sort(key=lambda x: x[0])
            
    except Exception as e:
        logger.error(f"Error discovering URLs: {e}")
        url_patterns = {}
    
    return url_patterns


def _extract_url_patterns(resolver, prefix: str, visited: Set[str]) -> List[Tuple[str, str]]:
    """
    Recursively extract URL patterns from a resolver.
    
    Args:
        resolver: Django URL resolver
        prefix: URL prefix for current level
        visited: Set of visited patterns to avoid infinite recursion
        
    Returns:
        List of (url_name, url_path) tuples
    """
    patterns = []
    
    # Avoid infinite recursion
    resolver_id = id(resolver)
    if resolver_id in visited:
        return patterns
    visited.add(resolver_id)
    
    try:
        for pattern in resolver.url_patterns:
            if hasattr(pattern, 'name') and pattern.name:
                # This is a named URL pattern
                url_name = pattern.name
                if hasattr(resolver, 'namespace') and resolver.namespace:
                    url_name = f"{resolver.namespace}:{pattern.name}"
                
                url_path = prefix + str(pattern.pattern)
                patterns.append((url_name, url_path))
                
            elif hasattr(pattern, 'url_patterns'):
                # This is an included URL pattern
                new_prefix = prefix + str(pattern.pattern).rstrip('^$')
                namespace = getattr(pattern, 'namespace', None)
                if namespace and hasattr(pattern, 'app_name'):
                    # Create a pseudo-resolver for namespaced patterns
                    sub_patterns = _extract_url_patterns(pattern, new_prefix, visited)
                    for sub_name, sub_path in sub_patterns:
                        if ':' not in sub_name:  # Add namespace if not already present
                            sub_name = f"{namespace}:{sub_name}"
                        patterns.append((sub_name, sub_path))
                else:
                    patterns.extend(_extract_url_patterns(pattern, new_prefix, visited))
                    
    except (AttributeError, ImportError) as e:
        logger.debug(f"Skipping resolver pattern due to error: {e}")
    
    return patterns


def _create_display_name(url_name: str, url_path: str) -> str:
    """
    Create a human-readable display name for a URL.
    
    Args:
        url_name: The URL name (e.g., 'meeting:upload_meeting')
        url_path: The URL path pattern (e.g., 'meeting/upload/')
        
    Returns:
        Human-readable display name
    """
    # Start with the URL name
    display = url_name
    
    # Add URL path info if it helps clarify
    if url_path and url_path != '/':
        # Clean up the path for display
        clean_path = url_path.strip('^$/')
        if clean_path and len(clean_path) < 50:  # Don't show very long paths
            display = f"{url_name} ({clean_path})"
    
    return display


def get_named_url_choices() -> List[Tuple[str, str]]:
    """
    Get all named URL choices for use in Django model choice fields.
    
    Returns:
        List of (value, display_name) tuples for use in Django choices.
    """
    choices = [('', '-- 选择命名路由 --')]  # Empty choice
    
    try:
        url_patterns = discover_urls()
        
        # Group choices by app
        for app_name in sorted(url_patterns.keys()):
            app_urls = url_patterns[app_name]
            if app_urls:
                # Add app header (disabled choice)
                app_display = _get_app_display_name(app_name)
                choices.append((f'--- {app_display} ---', f'--- {app_display} ---'))
                
                # Add URLs for this app
                for url_name, display_name in app_urls:
                    choices.append((url_name, f"  {display_name}"))
                    
    except Exception as e:
        logger.error(f"Error getting URL choices: {e}")
        # Return minimal choices on error
        choices = [
            ('', '-- 选择命名路由 --'),
            ('home', 'home (首页)'),
        ]
    
    return choices


def _get_app_display_name(app_name: str) -> str:
    """
    Get a display name for an app.
    
    Args:
        app_name: The app name
        
    Returns:
        Human-readable app display name
    """
    if app_name == 'root':
        return '根路由'
    
    # Try to get app config for a better name
    try:
        app_config = apps.get_app_config(app_name)
        if hasattr(app_config, 'verbose_name'):
            return app_config.verbose_name
    except LookupError:
        pass
    
    # Fallback to app name with some beautification
    return app_name.replace('_', ' ').title()


def get_all_urls_for_app(app_name: str) -> List[Tuple[str, str]]:
    """
    Get all URLs for a specific app.
    
    Args:
        app_name: Name of the Django app
        
    Returns:
        List of (url_name, display_name) tuples for the app
    """
    all_urls = discover_urls()
    return all_urls.get(app_name, [])


def validate_named_url(url_name: str) -> bool:
    """
    Validate that a named URL exists and can be resolved.
    
    Args:
        url_name: The named URL to validate
        
    Returns:
        True if the URL exists and can be resolved, False otherwise
    """
    if not url_name:
        return False
        
    try:
        from django.urls import reverse
        reverse(url_name)
        return True
    except Exception:
        return False