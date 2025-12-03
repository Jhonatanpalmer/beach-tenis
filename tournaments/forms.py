"""Forms that power the Beach Tennis management UI."""

from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.db import models as dj_models
from django.forms import inlineformset_factory

from .models import (
    Category,
    DailyGuide,
    DailyMatch,
    DailyTeam,
    Match,
    Participant,
    SetScore,
    Team,
    Tournament,
)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]
        labels = {"name": "Nome", "description": "Descrição"}


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["full_name", "birth_date", "gender", "category", "notes"]
        labels = {
            "full_name": "Nome completo",
            "birth_date": "Data de nascimento",
            "gender": "Gênero",
            "category": "Categoria",
            "notes": "Observações",
        }
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name", "division", "category", "player_one", "player_two"]
        labels = {
            "name": "Nome da dupla",
            "division": "Divisão",
            "category": "Categoria",
            "player_one": "Jogador(a) 1",
            "player_two": "Jogador(a) 2",
        }

    def __init__(self, *args, **kwargs):
        self.division_filter = kwargs.pop("division_filter", None)
        self.category_filter = kwargs.pop("category_filter", None)
        super().__init__(*args, **kwargs)
        self._filter_players_by_division()

    def _filter_players_by_division(self) -> None:
        division_field = self.add_prefix("division")
        category_field = self.add_prefix("category")
        division_value = (
            self.division_filter
            or self.data.get(division_field)
            or self.initial.get("division")
            or getattr(self.instance, "division", None)
        )
        category_value = (
            self.category_filter
            or self.data.get(category_field)
            or self.initial.get("category")
            or getattr(self.instance, "category_id", None)
        )
        try:
            category_value = int(category_value) if category_value not in (None, "") else None
        except (TypeError, ValueError):
            category_value = None

        queryset = Participant.objects.select_related("category").order_by("full_name")
        if division_value == Team.Division.MALE:
            queryset = queryset.filter(gender=Participant.Gender.MALE)
        elif division_value == Team.Division.FEMALE:
            queryset = queryset.filter(gender=Participant.Gender.FEMALE)
        else:
            queryset = queryset.filter(gender__in=[
                Participant.Gender.MALE,
                Participant.Gender.FEMALE,
                Participant.Gender.MIXED,
            ])

        if category_value:
            queryset = queryset.filter(category_id=category_value)

        self.fields["player_one"].queryset = queryset
        self.fields["player_two"].queryset = queryset

    def clean(self):
        cleaned = super().clean()
        player_one = cleaned.get("player_one")
        player_two = cleaned.get("player_two")
        category = cleaned.get("category")
        if player_one and player_two and player_one == player_two:
            raise ValidationError("Escolha dois atletas diferentes para montar a dupla.")
        if player_one and player_two and category:
            if player_one.category_id != category.id or player_two.category_id != category.id:
                raise ValidationError("Os atletas precisam pertencer à categoria selecionada.")
        return cleaned


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = [
            "name",
            "category",
            "division",
            "location",
            "start_date",
            "end_date",
            "max_sets",
            "tie_break_enabled",
            "tie_break_points",
            "tie_break_margin",
            "notes",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "name": "Nome do torneio",
            "tie_break_enabled": "Habilitar tie-break?",
            "tie_break_points": "Pontos do tie-break",
            "tie_break_margin": "+2 Obrigatório",
        }


class MatchForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ["tournament", "round_name", "scheduled_at", "team_one", "team_two", "notes"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        labels = {
            "round_name": "Fase/Etapa",
            "scheduled_at": "Data/hora",
            "team_one": "Dupla A",
            "team_two": "Dupla B",
        }

    def clean(self):
        cleaned = super().clean()
        tournament: Tournament | None = cleaned.get("tournament")
        team_one: Team | None = cleaned.get("team_one")
        team_two: Team | None = cleaned.get("team_two")
        if tournament and team_one and team_two:
            if team_one.category_id != team_two.category_id:
                raise ValidationError("As duas duplas precisam estar na mesma categoria.")
            if tournament.category_id and tournament.category_id != team_one.category_id:
                raise ValidationError("Categoria da dupla não coincide com a do torneio.")
            if team_one.division != team_two.division:
                raise ValidationError("As duas duplas precisam estar na mesma divisão (M/F/Mista).")
            if tournament.division and tournament.division != team_one.division:
                raise ValidationError("A divisão da partida precisa respeitar a divisão do torneio.")
        return cleaned


class MatchPointsForm(forms.Form):
    team_one_points = forms.CharField(
        required=False,
        label="Sequência de pontos da Dupla A",
        help_text="Separe por vírgula seguindo o padrão 15,30,40,GAME. Esses valores são usados em critérios de desempate.",
    )
    team_two_points = forms.CharField(
        required=False,
        label="Sequência de pontos da Dupla B",
        help_text="Separe por vírgula seguindo o padrão 15,30,40,GAME.",
    )

    def _parse(self, raw: str) -> list[str]:
        if not raw:
            return []
        try:
            return Match._normalize_point_sequence(raw.split(","))
        except ValidationError as exc:  # pragma: no cover - simple validation branch
            raise forms.ValidationError(exc.message)

    def clean_team_one_points(self):
        return self._parse(self.cleaned_data.get("team_one_points", ""))

    def clean_team_two_points(self):
        return self._parse(self.cleaned_data.get("team_two_points", ""))


SetScoreFormSet = inlineformset_factory(
    parent_model=Match,
    model=SetScore,
    fields=[
        "set_number",
        "team_one_games",
        "team_two_games",
        "tie_break_played",
        "team_one_tie_break_points",
        "team_two_tie_break_points",
    ],
    extra=3,
    can_delete=True,
    validate_min=False,
)


class DailyGuideSetupForm(forms.Form):
    guide_name = forms.CharField(label="Nome do torneio", max_length=120)
    participant_names = forms.CharField(
        label="Participantes",
        widget=forms.Textarea,
        help_text="Informe um nome por linha.",
    )

    def clean_participant_names(self) -> list[str]:
        raw = self.cleaned_data["participant_names"]
        names = [line.strip() for line in raw.splitlines() if line.strip()]
        if len(names) < 2:
            raise ValidationError("Cadastre pelo menos dois participantes.")
        return names


class DailyPairForm(forms.ModelForm):
    class Meta:
        model = DailyTeam
        fields = ["player_one", "player_two"]
        labels = {
            "player_one": "Jogador(a) 1",
            "player_two": "Jogador(a) 2",
        }

    def __init__(self, guide: DailyGuide, *args, **kwargs):
        self.guide = guide
        super().__init__(*args, **kwargs)
        available = guide.participants.exclude(
            dj_models.Q(primary_daily_teams__isnull=False)
            | dj_models.Q(secondary_daily_teams__isnull=False)
        ).order_by("name")
        self.fields["player_one"].queryset = available
        self.fields["player_two"].queryset = available

    def save(self, commit=True):  # type: ignore[override]
        instance = super().save(commit=False)
        instance.guide = self.guide
        if commit:
            instance.save()
        return instance


class DailyMatchForm(forms.ModelForm):
    class Meta:
        model = DailyMatch
        fields = ["team_one", "team_two", "team_one_score", "team_two_score"]
        labels = {
            "team_one": "Dupla A",
            "team_two": "Dupla B",
            "team_one_score": "Games da dupla A",
            "team_two_score": "Games da dupla B",
        }

    def __init__(self, guide: DailyGuide, *args, **kwargs):
        self.guide = guide
        super().__init__(*args, **kwargs)
        teams = guide.daily_teams.order_by("name")
        self.fields["team_one"].queryset = teams
        self.fields["team_two"].queryset = teams

    def clean(self):
        cleaned = super().clean()
        team_one = cleaned.get("team_one")
        team_two = cleaned.get("team_two")
        if team_one and team_two and team_one == team_two:
            raise ValidationError("Escolha duplas diferentes.")
        return cleaned

    def save(self, commit=True):  # type: ignore[override]
        match = super().save(commit=False)
        match.guide = self.guide
        if commit:
            match.save()
        return match
