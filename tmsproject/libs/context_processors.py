from django.conf import settings


def custom_context(request):
    return {
        'my_site_name': settings.MY_SITE_NAME,
    }