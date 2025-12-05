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
    TournamentParticipant,
)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]
        labels = {"name": "Nome", "description": "Descrição"}


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["full_name", "birth_date", "gender", "category"]
        labels = {
            "full_name": "Nome completo",
            "birth_date": "Data de nascimento",
            "gender": "Gênero",
            "category": "Categoria",
        }
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }

    #### Definir genero como Masculino e Feminino apenas
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["gender"].choices = [
            (Participant.Gender.MALE, "Masculino"),
            (Participant.Gender.FEMALE, "Feminino"),
        ]
        self.fields["category"].queryset = Category.objects.filter(is_default=True).order_by("name")


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



#### Criação do Formulário de Torneio, onde será definido os dados do torneio
class TournamentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(is_default=True).order_by("name")

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
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "name": "Nome do torneio",
            "category": "Categoria",
            "division": "Divisão",
            "location": "Localização",
            "start_date": "Data de início",
            "end_date": "Data de fim",
            "max_sets": "Quantidade de sets",
        }


class TournamentParticipantForm(forms.Form):
    participants = forms.ModelMultipleChoiceField(
        label="Participantes elegíveis",
        queryset=Participant.objects.none(),
        widget=forms.SelectMultiple(attrs={"size": 12}),
        help_text="Somente atletas dentro da divisão/categoria do torneio.",
    )

    def __init__(self, tournament: Tournament, *args, **kwargs):
        self.tournament = tournament
        super().__init__(*args, **kwargs)
        self.fields["participants"].queryset = self._eligible_participants()

    def _eligible_participants(self):
        queryset = Participant.objects.select_related("category").order_by("full_name")
        if self.tournament.category_id:
            queryset = queryset.filter(category_id=self.tournament.category_id)

        gender_filter = {
            Team.Division.MALE: [Participant.Gender.MALE, Participant.Gender.MIXED],
            Team.Division.FEMALE: [Participant.Gender.FEMALE, Participant.Gender.MIXED],
        }
        allowed_genders = gender_filter.get(self.tournament.division)
        if allowed_genders:
            queryset = queryset.filter(gender__in=allowed_genders)

        existing_ids = TournamentParticipant.objects.filter(tournament=self.tournament).values_list(
            "participant_id", flat=True
        )
        return queryset.exclude(id__in=existing_ids)


class TournamentManualPairForm(forms.Form):
    player_one = forms.ModelChoiceField(
        label="Jogador(a) 1",
        queryset=Participant.objects.none(),
    )
    player_two = forms.ModelChoiceField(
        label="Jogador(a) 2",
        queryset=Participant.objects.none(),
    )
    custom_name = forms.CharField(
        label="Nome da dupla (opcional)",
        max_length=120,
        required=False,
    )

    def __init__(self, tournament: Tournament, *args, **kwargs):
        self.tournament = tournament
        super().__init__(*args, **kwargs)
        available = self._available_participants()
        self.fields["player_one"].queryset = available
        self.fields["player_two"].queryset = available

    def _available_participants(self):
        assigned_ids: set[int] = set()
        for entry in self.tournament.enrolled_teams.select_related("team__player_one", "team__player_two"):
            if entry.team.player_one_id:
                assigned_ids.add(entry.team.player_one_id)
            if entry.team.player_two_id:
                assigned_ids.add(entry.team.player_two_id)
        participant_ids = TournamentParticipant.objects.filter(tournament=self.tournament).values_list(
            "participant_id", flat=True
        )
        queryset = Participant.objects.filter(id__in=participant_ids).order_by("full_name")
        if assigned_ids:
            queryset = queryset.exclude(id__in=assigned_ids)
        return queryset

    def clean(self):
        cleaned = super().clean()
        player_one = cleaned.get("player_one")
        player_two = cleaned.get("player_two")
        if player_one and player_two and player_one == player_two:
            raise ValidationError("Escolha atletas diferentes para formar a dupla.")
        return cleaned


class TournamentAutoPairForm(forms.Form):
    shuffle = forms.BooleanField(
        required=False,
        initial=True,
        label="Sortear automaticamente",
        help_text="Mantém os participantes em ordem aleatória antes de formar as duplas.",
    )


class TournamentGroupingForm(forms.Form):
    create_groups = forms.BooleanField(
        required=False,
        label="Criar grupos automaticamente",
        initial=True,
    )
    group_size = forms.IntegerField(
        label="Duplas por grupo",
        min_value=2,
        initial=3,
        help_text="Define o tamanho-alvo de cada grupo.",
    )
    qualifiers_per_group = forms.IntegerField(
        label="Classificados por grupo",
        min_value=1,
        initial=2,
        help_text="Número padrão de duplas avançando para o mata-mata.",
    )
    small_group_qualifiers = forms.IntegerField(
        label="Classificados em grupos menores",
        min_value=1,
        initial=1,
        help_text="Usado quando um grupo tiver menos duplas que o tamanho-alvo.",
    )
    build_knockout = forms.BooleanField(
        required=False,
        label="Gerar mata-mata",
    )

    def clean(self):
        cleaned = super().clean()
        group_size = cleaned.get("group_size")
        qualifiers = cleaned.get("qualifiers_per_group")
        small_qualifiers = cleaned.get("small_group_qualifiers")
        if group_size and qualifiers and qualifiers > group_size:
            self.add_error("qualifiers_per_group", "Classificados por grupo não pode exceder o tamanho do grupo.")
        if group_size and small_qualifiers and small_qualifiers > group_size:
            self.add_error("small_group_qualifiers", "Classificados em grupos menores não pode exceder o tamanho do grupo.")
        if qualifiers and small_qualifiers and small_qualifiers > qualifiers:
            self.add_error("small_group_qualifiers", "Use um valor menor ou igual ao número padrão de classificados.")
        return cleaned


class TournamentQuickResultForm(forms.Form):
    round_name = forms.CharField(
        label="Fase/Etapa",
        max_length=80,
        initial="Fase de grupos",
        help_text="Ex.: Grupos, Quartas, Semi, Final.",
    )
    team_one = forms.ModelChoiceField(
        label="Dupla A",
        queryset=Team.objects.none(),
    )
    team_two = forms.ModelChoiceField(
        label="Dupla B",
        queryset=Team.objects.none(),
    )
    team_one_sets = forms.IntegerField(label="Game da dupla A", min_value=0, initial=0)
    team_two_sets = forms.IntegerField(label="Game da dupla B", min_value=0, initial=0)

    def __init__(self, tournament: Tournament, *args, **kwargs):
        self.tournament = tournament
        super().__init__(*args, **kwargs)
        teams = Team.objects.filter(tournament_presences__tournament=tournament).order_by("name")
        self.fields["team_one"].queryset = teams
        self.fields["team_two"].queryset = teams

    def clean(self):
        cleaned = super().clean()
        team_one = cleaned.get("team_one")
        team_two = cleaned.get("team_two")
        sets_one = cleaned.get("team_one_sets")
        sets_two = cleaned.get("team_two_sets")
        if team_one and team_two and team_one == team_two:
            raise ValidationError("Escolha duplas diferentes para registrar o resultado.")
        if sets_one is not None and sets_two is not None and sets_one == sets_two:
            raise ValidationError("Defina um vencedor — os sets não podem empatar.")
        return cleaned


class MatchGameEditForm(forms.Form):
    match_id = forms.IntegerField(widget=forms.HiddenInput)
    team_one_sets = forms.IntegerField(label="Game da dupla A", min_value=0)
    team_two_sets = forms.IntegerField(label="Game da dupla B", min_value=0)

    def __init__(self, match: Match | None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if match:
            self.fields["match_id"].initial = match.pk
            self.fields["team_one_sets"].initial = match.team_one_sets_won
            self.fields["team_two_sets"].initial = match.team_two_sets_won

    def clean(self):
        cleaned = super().clean()
        sets_one = cleaned.get("team_one_sets")
        sets_two = cleaned.get("team_two_sets")
        if sets_one is not None and sets_two is not None and sets_one == sets_two:
            raise ValidationError("Os sets não podem empatar. Informe um vencedor.")
        return cleaned


class MatchForm(forms.ModelForm):
    def __init__(self, *args, tournament: Tournament | None = None, **kwargs):
        self._tournament_instance = tournament or kwargs.get("initial", {}).get("tournament")
        super().__init__(*args, **kwargs)
        if self._tournament_instance:
            self._restrict_teams()

    def _restrict_teams(self) -> None:
        if not self._tournament_instance:
            return
        queryset = Team.objects.order_by("name")
        if self._tournament_instance.division:
            queryset = queryset.filter(division=self._tournament_instance.division)
        if self._tournament_instance.category_id:
            queryset = queryset.filter(category_id=self._tournament_instance.category_id)
        enrolled_ids = list(
            self._tournament_instance.enrolled_teams.values_list("team_id", flat=True)
        )
        if enrolled_ids:
            queryset = queryset.filter(pk__in=enrolled_ids)
        self.fields["team_one"].queryset = queryset
        self.fields["team_two"].queryset = queryset

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
