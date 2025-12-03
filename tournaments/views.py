"""Views that power the Beach Tennis management workflow."""

from __future__ import annotations

import random
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import (
	CategoryForm,
	DailyGuideSetupForm,
	DailyMatchForm,
	DailyPairForm,
	MatchForm,
	MatchPointsForm,
	ParticipantForm,
	SetScoreFormSet,
	TeamForm,
	TournamentForm,
)
from .models import (
	Category,
	DailyGuide,
	DailyMatch,
	DailyParticipant,
	DailyTeam,
	Match,
	Participant,
	Team,
	Tournament,
)


def dashboard(request):
	"""Homepage with quick overview of tournaments and partidas."""

	tournaments = Tournament.objects.order_by("-start_date")[:5]
	latest_participants = Participant.objects.order_by("-created_at")[:5]
	upcoming_matches = (
		Match.objects.select_related("tournament", "team_one", "team_two")
		.order_by("-created_at")
		.prefetch_related("set_scores")[:5]
	)
	standings = {tournament.id: tournament.build_standings() for tournament in tournaments}
	return render(
		request,
		"tournaments/dashboard.html",
		{
			"tournaments": tournaments,
			"latest_participants": latest_participants,
			"upcoming_matches": upcoming_matches,
			"standings": standings,
		},
	)


def category_list_create(request):
	categories = Category.objects.order_by("name")
	form = CategoryForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Categoria salva com sucesso.")
		return redirect("tournaments:category_list")
	return render(
		request,
		"tournaments/category_list.html",
		{"categories": categories, "form": form},
	)


def participant_list_create(request):
	participants = Participant.objects.select_related("category").order_by("full_name")
	search_query = request.GET.get("q", "").strip()
	if search_query:
		participants = participants.filter(full_name__icontains=search_query)
	form = ParticipantForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Participante cadastrado.")
		return redirect("tournaments:participant_list")
	return render(
		request,
		"tournaments/participant_list.html",
		{
			"participants": participants,
			"form": form,
			"search_query": search_query,
		},
	)


def team_list_create(request):
	teams = Team.objects.select_related("category").order_by("name")
	division_filter = request.GET.get("division")
	category_filter = request.GET.get("category")
	form_kwargs = {
		"division_filter": division_filter,
		"category_filter": category_filter,
	}
	if request.method == "POST":
		form = TeamForm(request.POST, **form_kwargs)
	else:
		initial = {}
		if division_filter:
			initial["division"] = division_filter
		if category_filter:
			initial["category"] = category_filter
		form = TeamForm(initial=initial, **form_kwargs)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Dupla criada com sucesso.")
		return redirect("tournaments:team_list")
	return render(
		request,
		"tournaments/team_list.html",
		{
			"teams": teams,
			"form": form,
			"division_filter": division_filter or "",
			"category_filter": category_filter or "",
			"division_choices": Team.Division.choices,
			"categories": Category.objects.order_by("name"),
		},
	)


def tournament_list_create(request):
	tournaments = Tournament.objects.select_related("category").order_by("-start_date")
	form = TournamentForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Torneio cadastrado.")
		return redirect("tournaments:tournament_list")
	return render(
		request,
		"tournaments/tournament_list.html",
		{"tournaments": tournaments, "form": form},
	)


def tournament_detail(request, pk: int):
	tournament = get_object_or_404(
		Tournament.objects.select_related("category"), pk=pk
	)
	matches = (
		tournament.matches.select_related("team_one", "team_two")
		.prefetch_related("set_scores")
		.order_by("created_at")
	)
	match_form = MatchForm(
		request.POST or None,
		initial={"tournament": tournament},
		prefix="match",
	)
	match_form.fields["tournament"].queryset = Tournament.objects.filter(pk=tournament.pk)
	if request.method == "POST" and request.POST.get("action") == "create_match":
		if match_form.is_valid():
			match_form.save()
			messages.success(request, "Partida criada.")
			return redirect("tournaments:tournament_detail", pk=tournament.pk)
	standings = tournament.build_standings()
	return render(
		request,
		"tournaments/tournament_detail.html",
		{
			"tournament": tournament,
			"matches": matches,
			"match_form": match_form,
			"standings": standings,
		},
	)


def match_result_update(request, pk: int):
	match = get_object_or_404(
		Match.objects.select_related("tournament", "team_one", "team_two"), pk=pk
	)
	set_scores = list(match.set_scores.order_by("set_number"))
	formset = SetScoreFormSet(
		request.POST or None,
		instance=match,
		prefix="set",
	)
	points_form = MatchPointsForm(
		request.POST or None,
		prefix="points",
		initial={
			"team_one_points": ",".join(match.team_one_point_sequence),
			"team_two_points": ",".join(match.team_two_point_sequence),
		},
	)

	if request.method == "POST" and formset.is_valid() and points_form.is_valid():
		formset.save()
		match.set_points_for_team(match.team_one_position, points_form.cleaned_data["team_one_points"])
		match.set_points_for_team(match.team_two_position, points_form.cleaned_data["team_two_points"])
		match.tie_break_played = any(
			form.cleaned_data.get("tie_break_played")
			for form in formset.forms
			if form.cleaned_data and not form.cleaned_data.get("DELETE")
		)
		match.save(update_fields=["team_one_point_sequence", "team_two_point_sequence", "tie_break_played"])
		match.update_totals()
		messages.success(request, "Resultado da partida atualizado.")
		return redirect("tournaments:tournament_detail", pk=match.tournament_id)

	team_one_games = sum(score.team_one_games for score in set_scores)
	team_two_games = sum(score.team_two_games for score in set_scores)
	team_one_wins, team_one_losses = _team_record(match.team_one)
	team_two_wins, team_two_losses = _team_record(match.team_two)
	return render(
		request,
		"tournaments/match_result.html",
		{
			"match": match,
			"formset": formset,
			"points_form": points_form,
			"set_scores": set_scores,
			"team_one_games": team_one_games,
			"team_two_games": team_two_games,
			"team_one_wins": team_one_wins,
			"team_one_losses": team_one_losses,
			"team_two_wins": team_two_wins,
			"team_two_losses": team_two_losses,
		},
	)


def daily_guide_setup(request):
	form = DailyGuideSetupForm(request.POST or None)
	guides = (
		DailyGuide.objects.annotate(
			participant_total=Count("participants", distinct=True),
			team_total=Count("daily_teams", distinct=True),
			match_total=Count("matches", distinct=True),
		)
		.order_by("-created_at")
	)
	if request.method == "POST" and form.is_valid():
		guide = DailyGuide.objects.create(name=form.cleaned_data["guide_name"])
		for name in form.cleaned_data["participant_names"]:
			DailyParticipant.objects.create(guide=guide, name=name)
		messages.success(request, "Torneio Rápido criado com participantes.")
		return redirect("tournaments:daily_guide_detail", pk=guide.pk)
	return render(
		request,
		"tournaments/daily_guide_setup.html",
		{"form": form, "guides": guides},
	)


def daily_guide_detail(request, pk: int):
	guide = get_object_or_404(
		DailyGuide.objects.prefetch_related("participants", "daily_teams", "matches"), pk=pk
	)
	participants = guide.participants.order_by("name")
	available_participants = guide.participants.filter(
		primary_daily_teams__isnull=True,
		secondary_daily_teams__isnull=True,
	).order_by("name")
	pair_form = DailyPairForm(guide, prefix="pair")
	match_form = DailyMatchForm(guide, prefix="match")
	editing_match: DailyMatch | None = None
	if request.method == "POST":
		action = request.POST.get("action")
		if action == "manual_pair":
			pair_form = DailyPairForm(guide, request.POST, prefix="pair")
			if pair_form.is_valid():
				pair_form.save()
				if guide.pairing_mode == DailyGuide.PairingMode.UNDECIDED:
					guide.pairing_mode = DailyGuide.PairingMode.MANUAL
					guide.save(update_fields=["pairing_mode"])
				messages.success(request, "Dupla adicionada ao Torneio Rápido.")
				return redirect("tournaments:daily_guide_detail", pk=guide.pk)
		elif action == "random_pair":
			paired = _pair_randomly(guide)
			if paired:
				guide.pairing_mode = DailyGuide.PairingMode.RANDOM
				guide.save(update_fields=["pairing_mode"])
				messages.success(request, f"{paired} dupla(s) sorteada(s).")
			else:
				messages.warning(request, "Não há participantes suficientes livres para sortear.")
			return redirect("tournaments:daily_guide_detail", pk=guide.pk)
		elif action == "record_match":
			match_form = DailyMatchForm(guide, request.POST, prefix="match")
			if match_form.is_valid():
				match_form.save()
				messages.success(request, "Resultado registrado com sucesso.")
				return redirect("tournaments:daily_guide_detail", pk=guide.pk)
		elif action == "update_match":
			match_id = request.POST.get("match_id")
			target_match = guide.matches.filter(pk=match_id).first()
			if not target_match:
				messages.error(request, "Partida não encontrada para edição.")
				return redirect("tournaments:daily_guide_detail", pk=guide.pk)
			editing_match = target_match
			match_form = DailyMatchForm(guide, request.POST, prefix="match", instance=target_match)
			if match_form.is_valid():
				match_form.save()
				messages.success(request, "Resultado atualizado com sucesso.")
				return redirect("tournaments:daily_guide_detail", pk=guide.pk)
	else:
		edit_match_id = request.GET.get("editar")
		if edit_match_id:
			editing_match = guide.matches.filter(pk=edit_match_id).first()
			if editing_match:
				match_form = DailyMatchForm(guide, prefix="match", instance=editing_match)

	matches = guide.matches.select_related("team_one", "team_two", "winner").all()
	teams = guide.daily_teams.select_related("player_one", "player_two").order_by("name")
	assigned_ids = set(guide.daily_teams.values_list("player_one_id", flat=True)) | set(
		guide.daily_teams.values_list("player_two_id", flat=True)
	)
	manual_pair_available = pair_form.fields["player_one"].queryset.exists()
	standings = _daily_standings(guide)
	return render(
		request,
		"tournaments/daily_guide_detail.html",
		{
			"guide": guide,
			"participants": participants,
			"assigned_participant_ids": assigned_ids,
			"available_participants": available_participants,
			"pair_form": pair_form,
			"match_form": match_form,
			"editing_match": editing_match,
			"teams": teams,
			"matches": matches,
			"manual_pair_available": manual_pair_available,
			"standings": standings,
		},
	)


def _pair_randomly(guide: DailyGuide) -> int:
	available = list(
		guide.participants.filter(
			primary_daily_teams__isnull=True,
			secondary_daily_teams__isnull=True,
		)
	)
	random.shuffle(available)
	created = 0
	for idx in range(0, len(available) - 1, 2):
		DailyTeam.objects.create(
			guide=guide,
			player_one=available[idx],
			player_two=available[idx + 1],
		)
		created += 1
	return created


def _team_record(team: Team) -> tuple[int, int]:
	qs = Match.objects.filter(Q(team_one=team) | Q(team_two=team))
	wins = qs.filter(winner=team).count()
	losses = qs.filter(winner__isnull=False).exclude(winner=team).count()
	return wins, losses

def _daily_standings(guide: DailyGuide) -> list[dict[str, int | DailyTeam]]:
	stats: dict[int, dict[str, int | DailyTeam]] = {}
	for team in guide.daily_teams.select_related("player_one", "player_two"):
		stats[team.id] = {
			"team": team,
			"matches": 0,
			"wins": 0,
			"losses": 0,
			"games_for": 0,
			"games_against": 0,
		}

	for match in guide.matches.select_related("team_one", "team_two", "winner"):
		pairs = (
			(match.team_one, match.team_one_score, match.team_two_score),
			(match.team_two, match.team_two_score, match.team_one_score),
		)
		for team, scored, conceded in pairs:
			if team is None:
				continue
			entry = stats.setdefault(
				team.id,
				{
					"team": team,
					"matches": 0,
					"wins": 0,
					"losses": 0,
					"games_for": 0,
					"games_against": 0,
				},
			)
			entry["matches"] += 1
			entry["games_for"] += scored
			entry["games_against"] += conceded
			if match.winner_id == team.id:
				entry["wins"] += 1
			elif match.winner_id:
				entry["losses"] += 1

	standings = list(stats.values())
	for row in standings:
		row["game_diff"] = row["games_for"] - row["games_against"]

	standings.sort(
		key=lambda row: (
			-row["wins"],
			-row["game_diff"],
			-row["games_for"],
			row["team"].name,
		)
	)
	return standings

