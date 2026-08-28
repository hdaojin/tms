from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from .models import CountdownEvent
from .themes import DEFAULT_THEME_KEY, get_countdown_theme


def _event_context(event):
    now = timezone.localtime(timezone.now())
    target_at_iso = None
    event_year = ''
    event_type_display = ''
    theme_key = DEFAULT_THEME_KEY

    if event is not None:
        target_at = timezone.localtime(event.target_at)
        target_at_iso = target_at.isoformat()
        event_year = str(target_at.year)
        event_type_display = event.event_type.name
        theme_key = event.theme

    theme = get_countdown_theme(theme_key)
    countdown_prefix = getattr(event, 'countdown_prefix', '') or '距离开始还有'
    finished_message = getattr(event, 'finished_message', '') or '活动已经开始'
    location_display = getattr(event, 'location', '') or '地点待定'
    project_name_display = getattr(event, 'project_name', '') or theme['default_project_name']
    project_english_name_display = getattr(event, 'project_english_name', '') or ''
    subtitle_display = getattr(event, 'subtitle', '') or theme['default_subtitle']
    event_name_display = getattr(event, 'name', '') or '竞赛倒计时'
    description_display = getattr(event, 'description', '') or theme['default_description']
    event_type_display = event_type_display or '竞赛倒计时'
    hero_badge_parts = [location_display]
    if event_year:
        hero_badge_parts.append(event_year)
    hero_badge_text = ' · '.join(hero_badge_parts + [event_type_display])

    return {
        'event': event,
        'has_event': event is not None,
        'target_at_iso': target_at_iso,
        'server_now': now,
        'active_theme': theme,
        'event_type_display': event_type_display,
        'event_year': event_year,
        'location_display': location_display,
        'project_name_display': project_name_display,
        'project_english_name_display': project_english_name_display,
        'subtitle_display': subtitle_display,
        'event_name_display': event_name_display,
        'description_display': description_display,
        'hero_badge_text': hero_badge_text,
        'countdown_prefix': countdown_prefix,
        'finished_message': finished_message,
        'theme_keywords': theme['keywords'],
        'default_keywords': [keyword['label'] for keyword in theme['keywords']],
        'countdown_config': {
            'targetAt': target_at_iso,
            'serverNow': now.isoformat(),
            'countdownPrefix': countdown_prefix,
            'finishedMessage': finished_message,
        },
        'title': '竞赛倒计时',
        'show_header': False,
        'show_left_sidebar': False,
        'show_right_sidebar': False,
        'show_footer': False,
    }


def countdown_screen(request):
    event = (
        CountdownEvent.objects.select_related('event_type')
        .filter(is_active=True)
        .order_by('display_order', 'target_at')
        .first()
    )
    return render(request, 'event_countdown/countdown_screen.html', _event_context(event))


def countdown_screen_by_slug(request, slug):
    try:
        event = CountdownEvent.objects.select_related('event_type').get(slug=slug, is_active=True)
    except CountdownEvent.DoesNotExist as exc:
        raise Http404('倒计时事件不存在或未启用') from exc

    return render(request, 'event_countdown/countdown_screen.html', _event_context(event))
