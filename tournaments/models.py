"""Data models for the Beach Tennis management system."""

from __future__ import annotations

from typing import Iterable, List

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Category(models.Model):
	"""Skill/category level (A, B, C, D or custom)."""

	name = models.CharField(max_length=60, unique=True)
	description = models.TextField(blank=True)
	is_default = models.BooleanField(
		default=False,
		help_text="Marca as categorias oficiais (A, B, C, D) criadas pelo sistema.",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("name",)

	def __str__(self) -> str:  # pragma: no cover - readable repr only
		return self.name


class DailyGuide(models.Model):
	"""Ad-hoc daily tournament workflow."""

	class PairingMode(models.TextChoices):
		UNDECIDED = "undecided", "Definir depois"
		MANUAL = "manual", "Manual"
		RANDOM = "random", "Sorteio"

	name = models.CharField(max_length=120)
	pairing_mode = models.CharField(
		max_length=10,
		choices=PairingMode.choices,
		default=PairingMode.UNDECIDED,
	)
	champion = models.ForeignKey(
		"DailyTeam",
		on_delete=models.SET_NULL,
		related_name="champion_guides",
		null=True,
		blank=True,
	)
	runner_up = models.ForeignKey(
		"DailyTeam",
		on_delete=models.SET_NULL,
		related_name="runner_up_guides",
		null=True,
		blank=True,
	)
	third_place = models.ForeignKey(
		"DailyTeam",
		on_delete=models.SET_NULL,
		related_name="third_place_guides",
		null=True,
		blank=True,
	)
	finished_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("-created_at", "name")

	def __str__(self) -> str:  # pragma: no cover
		return self.name


class DailyParticipant(models.Model):
	guide = models.ForeignKey(
		DailyGuide,
		on_delete=models.CASCADE,
		related_name="participants",
	)
	name = models.CharField(max_length=120)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("name",)

	def __str__(self) -> str:  # pragma: no cover
		return self.name

	@property
	def is_assigned(self) -> bool:
		return self.primary_daily_teams.exists() or self.secondary_daily_teams.exists()


class DailyTeam(models.Model):
	guide = models.ForeignKey(
		DailyGuide,
		on_delete=models.CASCADE,
		related_name="daily_teams",
	)
	player_one = models.ForeignKey(
		DailyParticipant,
		on_delete=models.CASCADE,
		related_name="primary_daily_teams",
	)
	player_two = models.ForeignKey(
		DailyParticipant,
		on_delete=models.CASCADE,
		related_name="secondary_daily_teams",
	)
	name = models.CharField(max_length=160, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("name",)
		constraints = [
			models.CheckConstraint(
				check=~Q(player_one=models.F("player_two")),
				name="daily_team_distinct_players",
			),
		]

	def clean(self) -> None:
		if self.player_one.guide_id != self.guide_id or self.player_two.guide_id != self.guide_id:
			raise ValidationError("Os participantes precisam pertencer ao mesmo Torneio Rápido.")
		if self.player_one.is_assigned and not self.pk:
			raise ValidationError(f"{self.player_one.name} já está em uma dupla.")
		if self.player_two.is_assigned and not self.pk:
			raise ValidationError(f"{self.player_two.name} já está em uma dupla.")

	def save(self, *args, **kwargs):  # type: ignore[override]
		if self.player_one_id and self.player_two_id:
			if self.player_one_id > self.player_two_id:
				self.player_one, self.player_two = self.player_two, self.player_one
			self.name = f"{self.player_one.name} / {self.player_two.name}"
		self.full_clean()
		return super().save(*args, **kwargs)

	def __str__(self) -> str:  # pragma: no cover
		return self.name


class DailyMatch(models.Model):
	guide = models.ForeignKey(
		DailyGuide,
		on_delete=models.CASCADE,
		related_name="matches",
	)
	team_one = models.ForeignKey(
		DailyTeam,
		on_delete=models.CASCADE,
		related_name="matches_as_team_one",
	)
	team_two = models.ForeignKey(
		DailyTeam,
		on_delete=models.CASCADE,
		related_name="matches_as_team_two",
	)
	team_one_score = models.PositiveSmallIntegerField("Games Dupla A", default=0)
	team_two_score = models.PositiveSmallIntegerField("Games Dupla B", default=0)
	winner = models.ForeignKey(
		DailyTeam,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="daily_matches_won",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("-created_at",)
		constraints = [
			models.CheckConstraint(
				check=~Q(team_one=models.F("team_two")),
				name="daily_match_distinct_teams",
			)
		]

	def save(self, *args, **kwargs):  # type: ignore[override]
		self.full_clean()
		self._define_winner()
		return super().save(*args, **kwargs)

	def _define_winner(self) -> None:
		if self.team_one_score == self.team_two_score:
			self.winner = None
		elif self.team_one_score > self.team_two_score:
			self.winner = self.team_one
		else:
			self.winner = self.team_two

	@property
	def loser(self) -> DailyTeam | None:
		if not self.winner:
			return None
		return self.team_two if self.winner_id == self.team_one_id else self.team_one


class Participant(models.Model):
	"""Athletes taking part in the tournaments."""

	class Gender(models.TextChoices):
		MALE = "M", "Masculino"
		FEMALE = "F", "Feminino"
		MIXED = "X", "Mista (atua em duplas mistas)"

	full_name = models.CharField(max_length=120)
	birth_date = models.DateField()
	gender = models.CharField(max_length=1, choices=Gender.choices)
	category = models.ForeignKey(
		Category,
		on_delete=models.PROTECT,
		related_name="participants",
	)
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("full_name",)

	def __str__(self) -> str:  # pragma: no cover
		return self.full_name


class Team(models.Model):
	"""Pairs of participants."""

	class Division(models.TextChoices):
		MALE = "M", "Masculino"
		FEMALE = "F", "Feminino"
		MIXED = "X", "Mista"

	name = models.CharField(
		max_length=120,
		blank=True,
		help_text="Se vazio, será montado automaticamente com os nomes dos atletas.",
	)
	player_one = models.ForeignKey(
		Participant,
		on_delete=models.CASCADE,
		related_name="primary_teams",
	)
	player_two = models.ForeignKey(
		Participant,
		on_delete=models.CASCADE,
		related_name="secondary_teams",
	)
	category = models.ForeignKey(
		Category,
		on_delete=models.PROTECT,
		related_name="teams",
	)
	division = models.CharField(max_length=1, choices=Division.choices)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("name",)
		constraints = [
			models.UniqueConstraint(
				fields=("player_one", "player_two", "category", "division"),
				name="unique_team_pair",
			),
			models.CheckConstraint(
				check=~Q(player_one=models.F("player_two")),
				name="team_distinct_players",
			),
		]

	def clean(self) -> None:
		"""Ensure players respect division rules."""

		if self.player_one_id == self.player_two_id:
			raise ValidationError("Os jogadores da mesma dupla precisam ser diferentes.")

		genders = {self.player_one.gender, self.player_two.gender}
		male_allowed = {Participant.Gender.MALE, Participant.Gender.MIXED}
		female_allowed = {Participant.Gender.FEMALE, Participant.Gender.MIXED}
		if self.division == self.Division.MALE and not genders.issubset(male_allowed):
			raise ValidationError("Dupla masculina aceita apenas atletas masculinos ou marcados como mistos.")
		if self.division == self.Division.FEMALE and not genders.issubset(female_allowed):
			raise ValidationError("Dupla feminina aceita apenas atletas femininos ou marcados como mistos.")
		if self.division == self.Division.MIXED:
			if not (Participant.Gender.MALE in genders or Participant.Gender.MIXED in genders):
				raise ValidationError("Dupla mista precisa de ao menos um atleta masculino.")
			if not (Participant.Gender.FEMALE in genders or Participant.Gender.MIXED in genders):
				raise ValidationError("Dupla mista precisa de ao menos uma atleta feminina.")

		if self.player_one.category_id != self.player_two.category_id:
			raise ValidationError("Ambos atletas precisam estar na mesma categoria.")
		if self.category_id and self.category_id != self.player_one.category_id:
			raise ValidationError("A categoria da dupla precisa ser igual à categoria dos atletas.")

	def save(self, *args, **kwargs):  # type: ignore[override]
		if self.player_one_id and self.player_two_id and self.player_one_id > self.player_two_id:
			self.player_one, self.player_two = self.player_two, self.player_one
		if not self.name:
			self.name = f"{self.player_one.full_name} / {self.player_two.full_name}"
		self.full_clean()
		return super().save(*args, **kwargs)

	def __str__(self) -> str:  # pragma: no cover
		return self.name


class Tournament(models.Model):
	"""Tournament configuration, including tie-break rules."""

	name = models.CharField(max_length=120)
	category = models.ForeignKey(
		Category,
		on_delete=models.PROTECT,
		related_name="tournaments",
		null=True,
		blank=True,
	)
	division = models.CharField(
		max_length=1,
		choices=Team.Division.choices,
		default=Team.Division.MIXED,
	)
	location = models.CharField(max_length=120, blank=True)
	start_date = models.DateField()
	end_date = models.DateField(blank=True, null=True)
	max_sets = models.PositiveSmallIntegerField(
		default=3,
		help_text="Quantidade máxima de sets por partida (melhor de 3 por padrão).",
	)
	tie_break_enabled = models.BooleanField(
		default=True,
		help_text="Se verdadeiro, partidas podem encerrar em tie-break.",
	)
	tie_break_points = models.PositiveSmallIntegerField(
		default=7,
		choices=((7, "7 pontos"), (10, "10 pontos")),
		help_text="Escolha se o tie-break será jogado em 7 ou 10 pontos + 2 de diferença.",
	)
	tie_break_margin = models.PositiveSmallIntegerField(
		default=2,
		help_text="Diferença mínima para fechar o tie-break (regra +2).",
	)
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("-start_date", "name")

	def __str__(self) -> str:  # pragma: no cover
		return self.name

	def build_standings(self) -> List[dict]:
		"""Return standings ordered by sets and cumulative points."""

		standings: dict[int, dict] = {}
		for match in self.matches.prefetch_related("set_scores"):
			if not match.team_one_id or not match.team_two_id:
				continue

			for team, sets, points, games_for, games_against in (
				(
					match.team_one,
					match.team_one_sets_won,
					match.accumulated_points(match.team_one_position),
					match.team_one_sets_won,
					match.team_two_sets_won,
				),
				(
					match.team_two,
					match.team_two_sets_won,
					match.accumulated_points(match.team_two_position),
					match.team_two_sets_won,
					match.team_one_sets_won,
				),
			):
				if team is None:
					continue
				entry = standings.setdefault(
					team.id,
					{
						"team": team,
						"matches": 0,
						"wins": 0,
						"losses": 0,
						"sets": 0,
						"points": 0,
						"games_for": 0,
						"games_against": 0,
					},
				)
				entry["matches"] += 1
				entry["sets"] += sets
				entry["points"] += points
				entry["games_for"] += games_for
				entry["games_against"] += games_against
				if match.winner_id == team.id:
					entry["wins"] += 1
				else:
					entry["losses"] += 1

		ordered = []
		for entry in standings.values():
			entry["game_balance"] = entry["games_for"] - entry["games_against"]
			ordered.append(entry)
		return sorted(
			ordered,
			key=lambda item: (item["wins"], item["game_balance"], item["games_for"]),
			reverse=True,
		)


class TournamentParticipant(models.Model):
	"""Participant added to a specific tournament."""

	tournament = models.ForeignKey(
		Tournament,
		on_delete=models.CASCADE,
		related_name="participants",
	)
	participant = models.ForeignKey(
		Participant,
		on_delete=models.CASCADE,
		related_name="tournament_entries",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ("tournament", "participant")
		ordering = ("participant__full_name",)

	def __str__(self) -> str:  # pragma: no cover
		return f"{self.participant.full_name} em {self.tournament.name}"


class TournamentTeam(models.Model):
	"""Team enrolled into a tournament with optional grouping metadata."""

	class Stage(models.TextChoices):
		GROUP = "group", "Fase de grupos"
		KNOCKOUT = "knockout", "Mata-mata"

	tournament = models.ForeignKey(
		Tournament,
		on_delete=models.CASCADE,
		related_name="enrolled_teams",
	)
	team = models.ForeignKey(
		Team,
		on_delete=models.CASCADE,
		related_name="tournament_presences",
	)
	group_label = models.CharField(max_length=5, blank=True)
	stage = models.CharField(
		max_length=15,
		choices=Stage.choices,
		default=Stage.GROUP,
	)
	seed = models.PositiveSmallIntegerField(null=True, blank=True)
	is_eliminated = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ("tournament", "team")
		ordering = ("group_label", "team__name")

	def __str__(self) -> str:  # pragma: no cover
		return f"{self.team.name} em {self.tournament.name}"


class Match(models.Model):
	"""Individual matches inside a tournament."""

	POINT_VALUES = {"15": 15, "30": 30, "40": 40, "45": 45, "GAME": 60}

	tournament = models.ForeignKey(
		Tournament,
		on_delete=models.CASCADE,
		related_name="matches",
	)
	round_name = models.CharField(
		max_length=80,
		default="Fase de grupos",
		help_text="Ex.: Fase de grupos, Quartas, Semi, Final.",
	)
	scheduled_at = models.DateTimeField(null=True, blank=True)
	team_one = models.ForeignKey(
		Team,
		on_delete=models.PROTECT,
		related_name="matches_as_team_one",
	)
	team_two = models.ForeignKey(
		Team,
		on_delete=models.PROTECT,
		related_name="matches_as_team_two",
	)
	winner = models.ForeignKey(
		Team,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="matches_won",
	)
	tie_break_played = models.BooleanField(default=False)
	team_one_sets_won = models.PositiveSmallIntegerField(default=0)
	team_two_sets_won = models.PositiveSmallIntegerField(default=0)
	team_one_point_sequence = models.JSONField(default=list, blank=True)
	team_two_point_sequence = models.JSONField(default=list, blank=True)
	notes = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("tournament", "round_name", "created_at")
		constraints = [
			models.CheckConstraint(
				check=~Q(team_one=models.F("team_two")),
				name="match_distinct_teams",
			)
		]

	team_one_position = 1
	team_two_position = 2

	def __str__(self) -> str:  # pragma: no cover
		return f"{self.team_one} x {self.team_two} ({self.tournament})"

	@staticmethod
	def _normalize_point_sequence(values: Iterable[str]) -> List[str]:
		allowed = {"15", "30", "40", "45", "GAME"}
		normalized: List[str] = []
		for value in values:
			candidate = str(value).strip().upper()
			if not candidate:
				continue
			if candidate not in allowed:
				raise ValidationError(
					"Valores de pontos permitidos: 15, 30, 40, 45 ou GAME (use vírgula para separar)."
				)
			normalized.append(candidate)
		return normalized

	def accumulated_points(self, team_position: int) -> int:
		sequence = (
			self.team_one_point_sequence if team_position == self.team_one_position else self.team_two_point_sequence
		)
		return sum(self.POINT_VALUES.get(str(value).upper(), 0) for value in sequence)

	def set_points_for_team(self, team_position: int, values: Iterable[str]) -> None:
		normalized = self._normalize_point_sequence(values)
		if team_position == self.team_one_position:
			self.team_one_point_sequence = normalized
		else:
			self.team_two_point_sequence = normalized

	def update_totals(self, commit: bool = True) -> None:
		set_scores = list(self.set_scores.all())
		team_one_sets = sum(1 for score in set_scores if score.team_one_games > score.team_two_games)
		team_two_sets = sum(1 for score in set_scores if score.team_two_games > score.team_one_games)
		winner = None
		if team_one_sets != team_two_sets:
			winner = self.team_one if team_one_sets > team_two_sets else self.team_two

		self.team_one_sets_won = team_one_sets
		self.team_two_sets_won = team_two_sets
		self.winner = winner
		if commit:
			self.save(update_fields=["team_one_sets_won", "team_two_sets_won", "winner"])


class Sponsor(models.Model):
	"""Patrocinadores exibidos no portal."""

	name = models.CharField(max_length=120)
	logo = models.ImageField(upload_to="sponsors/")
	website = models.URLField(blank=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("-created_at", "name")

	def __str__(self) -> str:  # pragma: no cover
		return self.name


class LandingStat(models.Model):
	"""Armazena estatísticas simples da landing page."""

	total_views = models.PositiveBigIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:  # pragma: no cover
		return f"Análises da landing ({self.total_views} acessos)"


class LandingAccess(models.Model):
	"""Registro individual de IPs que acessaram a landing."""

	ip_address = models.GenericIPAddressField(unique=True)
	user_agent = models.CharField(max_length=255, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:  # pragma: no cover
		return f"{self.ip_address}"


class SetScore(models.Model):
	"""Scoreboard per set including optional tie-break points."""

	match = models.ForeignKey(
		Match,
		on_delete=models.CASCADE,
		related_name="set_scores",
	)
	set_number = models.PositiveSmallIntegerField(verbose_name="Número do set")
	team_one_games = models.PositiveSmallIntegerField(verbose_name="Games da dupla A")
	team_two_games = models.PositiveSmallIntegerField(verbose_name="Games da dupla B")
	tie_break_played = models.BooleanField(
		default=False,
		verbose_name="Tie-break disputado?",
	)
	team_one_tie_break_points = models.PositiveSmallIntegerField(
		null=True,
		blank=True,
		verbose_name="Pontos tie-break dupla A",
	)
	team_two_tie_break_points = models.PositiveSmallIntegerField(
		null=True,
		blank=True,
		verbose_name="Pontos tie-break dupla B",
	)

	class Meta:
		ordering = ("set_number",)
		constraints = [
			models.UniqueConstraint(
				fields=("match", "set_number"),
				name="unique_set_number_per_match",
			)
		]

	def clean(self) -> None:
		if self.tie_break_played:
			if self.team_one_tie_break_points is None or self.team_two_tie_break_points is None:
				raise ValidationError("Informe os pontos do tie-break para ambos os times.")
		else:
			self.team_one_tie_break_points = None
			self.team_two_tie_break_points = None

	def save(self, *args, **kwargs):  # type: ignore[override]
		self.full_clean()
		saved = super().save(*args, **kwargs)
		self.match.update_totals()
		return saved

	def __str__(self) -> str:  # pragma: no cover
		return f"Set {self.set_number}: {self.team_one_games} x {self.team_two_games}"
