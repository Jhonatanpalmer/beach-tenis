"""URL mappings for the tournaments app."""

from django.urls import path

from . import views

app_name = "tournaments"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("categorias/", views.category_list_create, name="category_list"),
    path("participantes/", views.participant_list_create, name="participant_list"),
    path("duplas/", views.team_list_create, name="team_list"),
    path("torneio-rapido/", views.daily_guide_setup, name="daily_guide_setup"),
    path("torneio-rapido/<int:pk>/", views.daily_guide_detail, name="daily_guide_detail"),
    path("torneios/", views.tournament_list_create, name="tournament_list"),
    path("torneios/<int:pk>/", views.tournament_detail, name="tournament_detail"),
    path("partidas/<int:pk>/resultado/", views.match_result_update, name="match_result"),
]
