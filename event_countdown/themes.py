DEFAULT_THEME_KEY = 'network'


COUNTDOWN_THEMES = {
    DEFAULT_THEME_KEY: {
        'label': 'ITNSA of WorldSkills Competition',
        'choice_label': '世赛网络系统管理项目倒计时大屏',
        'body_class': 'countdown-theme-network',
        'background_image': 'images/countdown/network-command-center-bg.png',
        'default_project_name': '网络系统管理项目',
        'default_subtitle': '竞赛训练倒计时',
        'default_description': (
            '聚焦 Linux、Windows、Network、Security、Automation 与 Troubleshooting，'
            '以世界标准推进训练过程管理。'
        ),
        'font_tokens': {
            'title': '"Microsoft YaHei UI", "Microsoft YaHei", "DengXian", "Segoe UI", Arial, sans-serif',
            'number': '"DSEG7Classic", "Bahnschrift", "Arial Black", "Impact", "Cascadia Mono", "Consolas", sans-serif',
            'mono': '"Cascadia Mono", "Consolas", "SFMono-Regular", monospace',
        },
        'keywords': [
            {'label': 'Linux', 'icon_class': 'icon-[mdi--linux]'},
            {'label': 'Windows Server', 'icon_class': 'icon-[mdi--microsoft-windows]'},
            {'label': 'Network', 'icon_class': 'icon-[tabler--network]'},
            {'label': 'Security', 'icon_class': 'icon-[tabler--shield-lock]'},
            {'label': 'Automation', 'icon_class': 'icon-[tabler--automation]'},
            {'label': 'Troubleshooting', 'icon_class': 'icon-[tabler--tools]'},
        ],
    },
}

THEME_CHOICES = tuple((key, theme.get('choice_label', theme['label'])) for key, theme in COUNTDOWN_THEMES.items())


def get_countdown_theme(theme_key):
    return COUNTDOWN_THEMES.get(theme_key or DEFAULT_THEME_KEY, COUNTDOWN_THEMES[DEFAULT_THEME_KEY])
