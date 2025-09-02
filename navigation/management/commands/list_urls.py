"""
Django management command to list all discovered URLs.

Usage:
    python manage.py list_urls [--app APP_NAME] [--validate] [--format FORMAT]
"""

from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from navigation.url_discovery import discover_urls, validate_named_url


class Command(BaseCommand):
    help = '列出所有已发现的命名URL模式，支持按应用过滤和URL验证'

    def add_arguments(self, parser):
        parser.add_argument(
            '--app',
            type=str,
            help='只显示指定应用的URL'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='验证URL是否可以正确解析'
        )
        parser.add_argument(
            '--format',
            choices=['table', 'list', 'json'],
            default='table',
            help='输出格式 (table, list, json)'
        )
        parser.add_argument(
            '--include-admin',
            action='store_true',
            help='包含管理员URL'
        )

    def handle(self, *args, **options):
        app_filter = options['app']
        validate = options['validate']
        output_format = options['format']
        include_admin = options['include_admin']

        # Discover URLs
        if output_format != 'json':
            self.stdout.write(
                self.style.SUCCESS('正在发现URL模式...')
            )
        
        all_urls = discover_urls()
        
        # Filter by app if specified
        if app_filter:
            if app_filter not in all_urls:
                raise CommandError(f'应用 "{app_filter}" 未找到。可用应用: {", ".join(all_urls.keys())}')
            all_urls = {app_filter: all_urls[app_filter]}

        # Count total URLs
        total_urls = sum(len(urls) for urls in all_urls.values())
        
        if output_format != 'json':
            self.stdout.write(
                self.style.SUCCESS(f'发现 {total_urls} 个URL模式，分布在 {len(all_urls)} 个应用中')
            )

        if output_format == 'json':
            self._output_json(all_urls, validate)
        elif output_format == 'list':
            self._output_list(all_urls, validate)
        else:  # table
            self._output_table(all_urls, validate)

    def _output_table(self, all_urls, validate):
        """Output URLs in table format."""
        from django.utils.termcolors import colorize
        
        # Header
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(
            f"{'应用':<15} {'URL名称':<30} {'URL路径':<25} {'状态':<10}"
        )
        self.stdout.write('=' * 80)
        
        for app_name in sorted(all_urls.keys()):
            app_urls = all_urls[app_name]
            
            if not app_urls:
                continue
                
            # App header
            self.stdout.write(
                self.style.HTTP_INFO(f"\n[{app_name.upper()}] ({len(app_urls)} URLs)")
            )
            
            for url_name, display_name in app_urls:
                # Extract URL path from display name
                url_path = ''
                if '(' in display_name and ')' in display_name:
                    url_path = display_name.split('(')[-1].rstrip(')')
                
                # Validate if requested
                status = ''
                if validate:
                    is_valid = validate_named_url(url_name)
                    status = colorize('✓', fg='green') if is_valid else colorize('✗', fg='red')
                
                # Format output
                self.stdout.write(
                    f"{'':15} {url_name:<30} {url_path:<25} {status:<10}"
                )
        
        self.stdout.write('=' * 80)

    def _output_list(self, all_urls, validate):
        """Output URLs in simple list format."""
        for app_name in sorted(all_urls.keys()):
            app_urls = all_urls[app_name]
            
            if not app_urls:
                continue
                
            self.stdout.write(f"\n{app_name}:")
            
            for url_name, display_name in app_urls:
                status_indicator = ''
                if validate:
                    is_valid = validate_named_url(url_name)
                    status_indicator = ' ✓' if is_valid else ' ✗'
                
                self.stdout.write(f"  - {url_name}{status_indicator}")

    def _output_json(self, all_urls, validate):
        """Output URLs in JSON format."""
        import json
        
        output = {}
        for app_name, app_urls in all_urls.items():
            output[app_name] = []
            
            for url_name, display_name in app_urls:
                url_data = {
                    'name': url_name,
                    'display_name': display_name
                }
                
                if validate:
                    url_data['is_valid'] = validate_named_url(url_name)
                
                output[app_name].append(url_data)
        
        self.stdout.write(json.dumps(output, indent=2, ensure_ascii=False))

    def _get_app_display_name(self, app_name):
        """Get a display name for an app."""
        if app_name == 'root':
            return '根路由'
        
        try:
            app_config = apps.get_app_config(app_name)
            if hasattr(app_config, 'verbose_name'):
                return app_config.verbose_name
        except LookupError:
            pass
        
        return app_name.replace('_', ' ').title()