from django.urls import path

from . import views


app_name = "events"

urlpatterns = [
    path("", views.EventListView.as_view(), name="event_list"),
    path("create/", views.EventCreateView.as_view(), name="event_create"),
    path("<int:pk>/", views.EventDetailView.as_view(), name="event_detail"),
    path("<int:pk>/edit/", views.EventUpdateView.as_view(), name="event_edit"),
    path("series/", views.CompetitionSeriesListView.as_view(), name="series_list"),
    path("series/create/", views.CompetitionSeriesCreateView.as_view(), name="series_create"),
    path("series/<int:pk>/", views.CompetitionSeriesDetailView.as_view(), name="series_detail"),
    path("series/<int:pk>/edit/", views.CompetitionSeriesUpdateView.as_view(), name="series_edit"),
    path("levels/", views.CompetitionLevelListView.as_view(), name="level_list"),
    path("levels/create/", views.CompetitionLevelCreateView.as_view(), name="level_create"),
    path("levels/<int:pk>/", views.CompetitionLevelDetailView.as_view(), name="level_detail"),
    path("levels/<int:pk>/edit/", views.CompetitionLevelUpdateView.as_view(), name="level_edit"),
    path("modules/", views.EventModuleListView.as_view(), name="module_list"),
    path("modules/create/", views.EventModuleCreateView.as_view(), name="module_create"),
    path("modules/<int:pk>/", views.EventModuleDetailView.as_view(), name="module_detail"),
    path("modules/<int:pk>/edit/", views.EventModuleUpdateView.as_view(), name="module_edit"),
    path(
        "modules/<int:module_pk>/domains/create/",
        views.EventModuleCapabilityDomainMapCreateView.as_view(),
        name="module_domain_map_create",
    ),
    path(
        "module-domain-maps/<int:pk>/edit/",
        views.EventModuleCapabilityDomainMapUpdateView.as_view(),
        name="module_domain_map_edit",
    ),
    path(
        "module-domain-maps/<int:pk>/delete/",
        views.EventModuleCapabilityDomainMapDeleteView.as_view(),
        name="module_domain_map_delete",
    ),
    path("participants/", views.EventParticipantListView.as_view(), name="participant_list"),
    path("participants/create/", views.EventParticipantCreateView.as_view(), name="participant_create"),
    path("participants/<int:pk>/", views.EventParticipantDetailView.as_view(), name="participant_detail"),
    path("participants/<int:pk>/edit/", views.EventParticipantUpdateView.as_view(), name="participant_edit"),
]
