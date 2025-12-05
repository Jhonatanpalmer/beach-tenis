"""Views that power the Beach Tennis management workflow."""

from __future__ import annotations

from datetime import datetime
import random
import string
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (
	CategoryForm,
	DailyGuideSetupForm,
	DailyMatchForm,
	DailyPairForm,
	MatchPointsForm,
	ParticipantForm,
	SetScoreFormSet,
	TeamForm,
	TournamentAutoPairForm,
	TournamentForm,
	TournamentGroupingForm,
	TournamentManualPairForm,
	TournamentParticipantForm,
	TournamentQuickResultForm,
	MatchGameEditForm,
)
from .models import (
	Category,
	DailyGuide,
	DailyMatch,
	DailyParticipant,
	DailyTeam,
	LandingAccess,
	LandingStat,
	Match,
	Participant,
	Sponsor,
	Team,
	Tournament,
	TournamentParticipant,
	TournamentTeam,
)


def landing_page(request):
	stat, _ = LandingStat.objects.get_or_create(pk=1)
	ip_address = _get_client_ip(request)
	should_refresh = False
	if ip_address:
		access, created = LandingAccess.objects.get_or_create(
			ip_address=ip_address,
			defaults={
				"user_agent": (request.META.get("HTTP_USER_AGENT") or "")[:255],
			},
		)
		if created:
			LandingStat.objects.filter(pk=stat.pk).update(
				total_views=F("total_views") + 1,
				updated_at=timezone.now(),
			)
			should_refresh = True
		else:
			updated_fields = ["updated_at"]
			user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:255]
			if user_agent and user_agent != access.user_agent:
				access.user_agent = user_agent
				updated_fields.append("user_agent")
			access.save(update_fields=updated_fields)
	if should_refresh:
		stat.refresh_from_db(fields=["total_views"])
	featured_sponsors = Sponsor.objects.filter(is_active=True).order_by("-created_at")[:6]
	landing_total_views = stat.total_views or LandingAccess.objects.count()
	return render(
		request,
		"tournaments/landing.html",
		{
			"featured_sponsors": featured_sponsors,
			"landing_total_views": landing_total_views,
		},
	)


def _get_client_ip(request):
	forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
	if forwarded_for:
		return forwarded_for.split(",")[0].strip()
	return request.META.get("REMOTE_ADDR", "")


def sponsor_page(request):
	sponsors = Sponsor.objects.filter(is_active=True).order_by("name")
	benefits = [
		{
			"title": "Visibilidade constante",
			"description": "Sua marca aparece no portal e nas ativações dos torneios rápidos durante todo o mês.",
		},
		{
			"title": "Ativações em quadra",
			"description": "Espaços reservados para banners, brindes e experiências com os atletas do clube.",
		},
		{
			"title": "Conteúdo digital",
			"description": "Divulgação nos cards do mural dos campeões e nas redes sociais do Play do Babuzão.",
		},
	]
	return render(
		request,
		"tournaments/sponsor_page.html",
		{
			"sponsors": sponsors,
			"benefits": benefits,
			"contact_email": "contato@playdobabuzao.com",
			"contact_whatsapp_url": "https://wa.me/5534999382133?text=Ol%C3%A1!%20Quero%20patrocinar%20o%20Play%20do%20Babuz%C3%A3o.",
		},
	)


def dashboard(request):
	"""Homepage with quick overview of tournaments and partidas."""

	daily_pneus = list(
		DailyMatch.objects.select_related("team_one", "team_two")
		.filter(
			(Q(team_one_score__in=[5, 6], team_two_score=0))
			| (Q(team_two_score__in=[5, 6], team_one_score=0))
		)
		.order_by("-created_at")
	)
	tournament_pneus = list(
		Match.objects.select_related("team_one", "team_two", "tournament")
		.filter(
			(Q(team_one_sets_won__in=[5, 6], team_two_sets_won=0))
			| (Q(team_two_sets_won__in=[5, 6], team_one_sets_won=0))
		)
		.order_by("-created_at")
	)
	pneu_matches = []
	for match in daily_pneus:
		pneu_matches.append(
			{
				"team_one_name": match.team_one.name,
				"team_two_name": match.team_two.name,
				"score_text": f"{match.team_one_score} x {match.team_two_score}",
				"has_zero": True,
				"source_label": "Torneio Rápido",
				"created_at": match.created_at,
			}
		)
	for match in tournament_pneus:
		source_label = match.tournament.name if match.tournament_id else "Torneio"
		pneu_matches.append(
			{
				"team_one_name": match.team_one.name,
				"team_two_name": match.team_two.name,
				"score_text": f"{match.team_one_sets_won} x {match.team_two_sets_won}",
				"has_zero": True,
				"source_label": source_label,
				"created_at": match.created_at,
			}
		)
	pneu_matches.sort(key=lambda item: item["created_at"], reverse=True)
	champion_wall_qs = (
		DailyGuide.objects.select_related("champion", "runner_up", "third_place")
		.filter(champion__isnull=False)
		.order_by("-finished_at", "-created_at")
	)
	champion_wall = []
	for guide in champion_wall_qs:
		champion_wall.append(
			{
				"tournament": guide.name,
				"finished_at": guide.finished_at,
				"champion": guide.champion.name if guide.champion else None,
				"runner_up": guide.runner_up.name if guide.runner_up else None,
				"third_place": guide.third_place.name if guide.third_place else None,
			}
		)
	champion_paginator = Paginator(champion_wall, 5)
	champion_page_number = request.GET.get("champion_page")
	champion_page_obj = champion_paginator.get_page(champion_page_number)
	pneu_paginator = Paginator(pneu_matches, 6)
	pneu_page_number = request.GET.get("pneu_page")
	pneu_page_obj = pneu_paginator.get_page(pneu_page_number)
	return render(
		request,
		"tournaments/dashboard.html",
		{
			"pneu_page_obj": pneu_page_obj,
			"champion_page_obj": champion_page_obj,
			"pneu_page_param": pneu_page_obj.number,
			"champion_page_param": champion_page_obj.number,
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
	name_query = request.GET.get("name", "").strip()
	category_filter = request.GET.get("category", "").strip()
	gender_filter = request.GET.get("gender", "").strip().upper()
	birth_date_query = request.GET.get("birth_date", "").strip()
	birth_date_value = _parse_search_date(birth_date_query) if birth_date_query else None
	has_filters = any([name_query, category_filter, gender_filter, birth_date_query])
	category_id: int | None = None
	if category_filter:
		try:
			category_id = int(category_filter)
		except (TypeError, ValueError):
			category_id = None
	if name_query:
		participants = participants.filter(full_name__icontains=name_query)
	if category_id:
		participants = participants.filter(category_id=category_id)
	if gender_filter in {Participant.Gender.MALE, Participant.Gender.FEMALE}:
		participants = participants.filter(gender=gender_filter)
	if birth_date_query:
		if birth_date_value:
			participants = participants.filter(birth_date=birth_date_value)
		else:
			messages.warning(
				request,
				"Data de nascimento inválida. Use o formato DD/MM/AAAA ou AAAA-MM-DD.",
			)
	page_size_options = [10, 20, 30, 50]
	try:
		page_size = int(request.GET.get("page_size", page_size_options[0]))
		if page_size not in page_size_options:
			raise ValueError
	except (TypeError, ValueError):
		page_size = page_size_options[0]
	paginator = Paginator(participants, page_size)
	page_number = request.GET.get("page")
	page_obj = paginator.get_page(page_number)
	participants = page_obj.object_list
	query_params = request.GET.copy()
	if "page" in query_params:
		query_params.pop("page")
	base_querystring = query_params.urlencode()
	form = ParticipantForm(request.POST or None)
	if request.method == "POST" and form.is_valid():
		form.save()
		messages.success(request, "Participante cadastrado.")
		return redirect("tournaments:participant_list")
	categories = Category.objects.order_by("name")
	return render(
		request,
		"tournaments/participant_list.html",
		{
			"participants": participants,
			"form": form,
			"name_query": name_query,
			"category_filter": category_filter,
			"gender_filter": gender_filter,
			"birth_date_query": birth_date_query,
			"page_obj": page_obj,
			"paginator": paginator,
			"page_size": page_size,
			"page_size_options": page_size_options,
			"total_results": paginator.count,
			"base_querystring": base_querystring,
			"categories": categories,
			"gender_choices": [
				(Participant.Gender.MALE, "Masculino"),
				(Participant.Gender.FEMALE, "Feminino"),
			],
			"has_filters": has_filters,
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
	action = request.POST.get("action") if request.method == "POST" else None
	quick_result_form = None
	editing_match: Match | None = None
	game_edit_form = None
	if tournament.enrolled_teams.exists():
		quick_result_form = TournamentQuickResultForm(
			tournament,
			data=request.POST if action == "quick_result" else None,
			prefix="quick",
		)
		edit_match_id = request.GET.get("editar_partida")
		if edit_match_id:
			editing_match = (
				tournament.matches.select_related("team_one", "team_two").filter(pk=edit_match_id).first()
			)
			if editing_match:
				game_edit_form = MatchGameEditForm(editing_match, prefix="edit")
	participant_form = TournamentParticipantForm(tournament, prefix="participant")
	manual_pair_form = TournamentManualPairForm(tournament, prefix="manual")
	auto_pair_form = TournamentAutoPairForm(prefix="auto")
	grouping_form = TournamentGroupingForm(prefix="grouping")
	if request.method == "POST":
		if action == "add_participants":
			participant_form = TournamentParticipantForm(tournament, request.POST, prefix="participant")
			if participant_form.is_valid():
				added = 0
				for participant in participant_form.cleaned_data["participants"]:
					_, created = TournamentParticipant.objects.get_or_create(
						tournament=tournament,
						participant=participant,
					)
					if created:
						added += 1
				if added:
					messages.success(request, f"{added} participante(s) adicionado(s) ao torneio.")
				else:
					messages.info(request, "Todos os participantes selecionados já estavam na lista.")
				return redirect("tournaments:tournament_detail", pk=tournament.pk)
		elif action == "manual_pair":
			manual_pair_form = TournamentManualPairForm(tournament, request.POST, prefix="manual")
			if manual_pair_form.is_valid():
				try:
					entry = _create_tournament_team(
						tournament,
						manual_pair_form.cleaned_data["player_one"],
						manual_pair_form.cleaned_data["player_two"],
						manual_pair_form.cleaned_data.get("custom_name", ""),
					)
				except ValidationError as exc:
					manual_pair_form.add_error(None, exc.messages[0] if exc.messages else str(exc))
					messages.error(request, "Não foi possível criar esta dupla. Confira os gêneros selecionados.")
				else:
					messages.success(request, f"Dupla {entry.team.name} adicionada ao torneio.")
					return redirect("tournaments:tournament_detail", pk=tournament.pk)
		elif action == "auto_pair":
			auto_pair_form = TournamentAutoPairForm(request.POST, prefix="auto")
			if auto_pair_form.is_valid():
				created, skipped = _auto_pair_tournament_participants(
					tournament,
					shuffle=auto_pair_form.cleaned_data.get("shuffle", True),
				)
				if created:
					messages.success(request, f"{created} dupla(s) formada(s) automaticamente.")
				if skipped:
					messages.warning(
						request,
						"Algumas combinações foram ignoradas por não atenderem aos critérios da divisão mista.",
					)
				if not created and not skipped:
					messages.warning(request, "Nenhum participante disponível para montar novas duplas.")
				return redirect("tournaments:tournament_detail", pk=tournament.pk)
		elif action == "grouping":
			grouping_form = TournamentGroupingForm(request.POST, prefix="grouping")
			if grouping_form.is_valid():
				group_size = grouping_form.cleaned_data.get("group_size") or 3
				qualifiers_per_group = grouping_form.cleaned_data.get("qualifiers_per_group") or 2
				small_group_qualifiers = grouping_form.cleaned_data.get("small_group_qualifiers") or 1
				performed_action = False
				if grouping_form.cleaned_data.get("create_groups"):
					performed_action = True
					updated = _assign_groups_to_tournament(tournament, group_size=group_size)
					match_count = _generate_group_round_robin_matches(tournament)
					if updated:
						messages.success(request, "Grupos atualizados com sucesso.")
					else:
						messages.info(request, "Nenhuma dupla para agrupar no momento.")
					if match_count:
						messages.success(request, f"{match_count} partida(s) da fase de grupos geradas.")
				if grouping_form.cleaned_data.get("build_knockout"):
					performed_action = True
					created, error = _progress_knockout(
						tournament,
						qualifiers_per_group=qualifiers_per_group,
						small_group_qualifiers=small_group_qualifiers,
						expected_group_size=group_size,
					)
					if created:
						messages.success(request, f"{created} partida(s) eliminatórias geradas.")
					elif error:
						messages.warning(request, error)
					else:
						messages.info(request, "Nenhuma nova partida eliminatória para criar.")
				if not performed_action:
					messages.info(request, "Selecione ao menos uma ação (criar grupos ou gerar mata-mata).")
				return redirect("tournaments:tournament_detail", pk=tournament.pk)
		elif action == "quick_result" and quick_result_form is not None:
			quick_result_form = TournamentQuickResultForm(tournament, request.POST, prefix="quick")
			if quick_result_form.is_valid():
				_record_quick_result(tournament, quick_result_form.cleaned_data)
				messages.success(request, "Resultado registrado.")
				return redirect("tournaments:tournament_detail", pk=tournament.pk)
		elif action == "edit_result":
			game_edit_form = MatchGameEditForm(None, request.POST, prefix="edit")
			if game_edit_form.is_valid():
				match = (
					tournament.matches.select_related("team_one", "team_two").filter(
						pk=game_edit_form.cleaned_data["match_id"]
					).first()
				)
				if not match:
					messages.error(request, "Partida não encontrada para edição.")
				else:
					_apply_game_edit(
						match,
						game_edit_form.cleaned_data["team_one_sets"],
						game_edit_form.cleaned_data["team_two_sets"],
					)
					messages.success(request, "Resultado atualizado.")
				return redirect("tournaments:tournament_detail", pk=tournament.pk)
	participants_qs = list(
		tournament.participants.select_related("participant").order_by("participant__full_name")
	)
	enrolled_teams = list(
		tournament.enrolled_teams.select_related("team__player_one", "team__player_two").order_by(
		"group_label",
		"team__name",
	)
	)
	unpaired_participants = list(_participants_without_team(tournament))
	unpaired_ids = {participant.id for participant in unpaired_participants}
	group_summary: dict[str, list[TournamentTeam]] = {}
	for entry in enrolled_teams:
		group_summary.setdefault(entry.group_label or "Sem grupo", []).append(entry)
	standings = tournament.build_standings()
	return render(
		request,
		"tournaments/tournament_detail.html",
		{
			"tournament": tournament,
			"matches": matches,
			"quick_result_form": quick_result_form,
			"editing_match": editing_match,
			"game_edit_form": game_edit_form,
			"standings": standings,
			"participant_form": participant_form,
			"manual_pair_form": manual_pair_form,
			"auto_pair_form": auto_pair_form,
			"grouping_form": grouping_form,
			"tournament_participants": participants_qs,
			"enrolled_teams": enrolled_teams,
			"unpaired_participants": unpaired_participants,
			"unpaired_ids": unpaired_ids,
			"group_summary": group_summary,
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
		guide = DailyGuide.objects.create(
			name=form.cleaned_data["guide_name"],
			created_at=timezone.now(),
		)
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
		if guide.finished_at and action != "finalize":
			messages.warning(request, "Este torneio rápido já foi finalizado e não pode mais ser editado.")
			return redirect("tournaments:daily_guide_detail", pk=guide.pk)
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
		elif action == "finalize":
			if guide.finished_at:
				messages.info(request, "Este torneio rápido já foi finalizado.")
				return redirect("tournaments:daily_guide_detail", pk=guide.pk)
			if not guide.matches.exists():
				messages.warning(request, "Registre ao menos uma partida antes de finalizar.")
				return redirect("tournaments:daily_guide_detail", pk=guide.pk)
			standings = _daily_standings(guide)
			if not any(row["matches"] for row in standings):
				messages.warning(request, "Nenhum resultado computado para determinar o campeão.")
				return redirect("tournaments:daily_guide_detail", pk=guide.pk)
			champion_team = standings[0]["team"] if standings else None
			runner_up_team = standings[1]["team"] if len(standings) > 1 else None
			third_team = standings[2]["team"] if len(standings) > 2 else None
			guide.champion = champion_team
			guide.runner_up = runner_up_team
			guide.third_place = third_team
			guide.finished_at = timezone.now()
			guide.save(update_fields=["champion", "runner_up", "third_place", "finished_at"])
			messages.success(request, "Torneio rápido finalizado. Campeões registrados!")
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
	can_finalize = not guide.finished_at and guide.matches.exists()
	allow_editing = guide.finished_at is None
	podium = {
		"champion": guide.champion,
		"runner_up": guide.runner_up,
		"third_place": guide.third_place,
		"finished_at": guide.finished_at,
	}
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
			"can_finalize": can_finalize,
			"allow_editing": allow_editing,
			"podium": podium,
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


def _parse_search_date(raw_value: str):
	value = raw_value.strip()
	if not value:
		return None
	for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
		try:
			return datetime.strptime(value, fmt).date()
		except ValueError:
			continue
	return None

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
			-row["games_for"],
			-row["game_diff"],
			row["team"].name,
		)
	)
	return standings


def _participants_without_team(tournament: Tournament):
	participant_ids = list(
		TournamentParticipant.objects.filter(tournament=tournament).values_list("participant_id", flat=True)
	)
	paired_ids: set[int] = set()
	for entry in tournament.enrolled_teams.select_related("team__player_one", "team__player_two"):
		if entry.team.player_one_id:
			paired_ids.add(entry.team.player_one_id)
		if entry.team.player_two_id:
			paired_ids.add(entry.team.player_two_id)
	queryset = Participant.objects.filter(id__in=participant_ids).order_by("full_name")
	if paired_ids:
		queryset = queryset.exclude(id__in=paired_ids)
	return queryset


def _create_tournament_team(
	tournament: Tournament,
	player_one: Participant,
	player_two: Participant,
	custom_name: str = "",
) -> TournamentTeam:
	players = sorted([player_one, player_two], key=lambda player: player.pk)
	category = tournament.category or players[0].category
	defaults: dict[str, str] = {}
	if custom_name:
		defaults["name"] = custom_name
	team, _ = Team.objects.get_or_create(
		player_one=players[0],
		player_two=players[1],
		category=category,
		division=tournament.division,
		defaults=defaults,
	)
	if custom_name and team.name != custom_name:
		team.name = custom_name
		team.save(update_fields=["name"])
	for participant in players:
		TournamentParticipant.objects.get_or_create(tournament=tournament, participant=participant)
	entry, _ = TournamentTeam.objects.get_or_create(tournament=tournament, team=team)
	return entry


def _auto_pair_tournament_participants(tournament: Tournament, shuffle: bool = True) -> tuple[int, int]:
	available = list(_participants_without_team(tournament))
	if not available:
		return 0, 0
	if shuffle:
		random.shuffle(available)
	if tournament.division == Team.Division.MIXED:
		return _auto_pair_mixed_participants(tournament, available)
	created = 0
	skipped = 0
	for idx in range(0, len(available) - 1, 2):
		try:
			_create_tournament_team(tournament, available[idx], available[idx + 1])
		except ValidationError:
			skipped += 1
		else:
			created += 1
	return created, skipped


def _auto_pair_mixed_participants(
	tournament: Tournament,
	participants: list[Participant],
) -> tuple[int, int]:
	male_pool: list[Participant] = []
	female_pool: list[Participant] = []
	flex_pool: list[Participant] = []
	for participant in participants:
		if participant.gender == Participant.Gender.MALE:
			male_pool.append(participant)
		elif participant.gender == Participant.Gender.FEMALE:
			female_pool.append(participant)
		else:
			flex_pool.append(participant)
	pairs: list[tuple[Participant, Participant]] = []
	while male_pool and female_pool:
		pairs.append((male_pool.pop(), female_pool.pop()))
	while male_pool and flex_pool:
		pairs.append((male_pool.pop(), flex_pool.pop()))
	while female_pool and flex_pool:
		pairs.append((flex_pool.pop(), female_pool.pop()))
	while len(flex_pool) >= 2:
		pairs.append((flex_pool.pop(), flex_pool.pop()))
	leftover_participants = len(male_pool) + len(female_pool) + len(flex_pool)
	created = 0
	skipped = 0
	for player_one, player_two in pairs:
		try:
			_create_tournament_team(tournament, player_one, player_two)
		except ValidationError:
			skipped += 1
		else:
			created += 1
	return created, skipped + leftover_participants


def _assign_groups_to_tournament(tournament: Tournament, group_size: int = 3) -> int:
	tentries = list(
		tournament.enrolled_teams.select_related("team").order_by("group_label", "team__name", "created_at")
	)
	if not tentries:
		return 0
	labels = list(string.ascii_uppercase)
	updated = 0
	for idx, entry in enumerate(tentries):
		label_index = idx // group_size
		if label_index >= len(labels):
			break
		label = f"Grupo {labels[label_index]}"
		if entry.group_label != label:
			entry.group_label = label
			entry.save(update_fields=["group_label"])
			updated += 1
	return updated


def _generate_group_round_robin_matches(tournament: Tournament) -> int:
	entries = (
		tournament.enrolled_teams.select_related("team")
		.filter(group_label__isnull=False)
		.order_by("group_label", "team__name")
	)
	groups: dict[str, list[Team]] = {}
	for entry in entries:
		if not entry.team:
			continue
		groups.setdefault(entry.group_label, []).append(entry.team)
	created = 0
	for label, teams in groups.items():
		if len(teams) < 2:
			continue
		for idx in range(len(teams) - 1):
			team_one = teams[idx]
			for jdx in range(idx + 1, len(teams)):
				team_two = teams[jdx]
				exists = tournament.matches.filter(round_name=label).filter(
					Q(team_one=team_one, team_two=team_two) | Q(team_one=team_two, team_two=team_one)
				).exists()
				if exists:
					continue
				Match.objects.create(
					tournament=tournament,
					round_name=label,
					team_one=team_one,
					team_two=team_two,
				)
				created += 1
	return created


def _collect_group_qualifiers(
	tournament: Tournament,
	default_slots: int,
	small_group_slots: int,
	expected_group_size: int,
) -> list[Team]:
	entries = {entry.team_id: entry for entry in tournament.enrolled_teams.select_related("team") if entry.group_label}
	if not entries:
		return []
	group_rows: dict[str, list[dict]] = {}
	for row in tournament.build_standings():
		entry = entries.get(row["team"].id)
		if not entry or not entry.group_label:
			continue
		group_rows.setdefault(entry.group_label, []).append(row)
	qualifiers: list[Team] = []
	for label in sorted(group_rows.keys()):
		group_data = group_rows[label]
		group_data.sort(
			key=lambda item: (
				item["wins"],
				item["games_for"],
				item.get("game_balance", 0),
			),
			reverse=True,
		)
		slots = default_slots
		if expected_group_size and len(group_data) < expected_group_size:
			slots = small_group_slots
		slots = max(1, min(slots, len(group_data)))
		for row in group_data[:slots]:
			qualifiers.append(row["team"])
	return qualifiers


def _round_name_for_team_count(team_count: int) -> str:
	label_map = {
		2: "Final",
		4: "Semifinais",
		8: "Quartas de final",
		16: "Oitavas de final",
		32: "16 avos de final",
	}
	label = label_map.get(team_count)
	if label:
		return f"Mata-mata - {label}"
	return f"Mata-mata ({team_count} duplas)"


def _create_knockout_round(tournament: Tournament, teams: list[Team]) -> int:
	team_count = len(teams)
	if team_count < 2 or team_count % 2 != 0:
		return 0
	round_name = _round_name_for_team_count(team_count)
	created = 0
	for idx in range(0, team_count, 2):
		team_one = teams[idx]
		team_two = teams[idx + 1]
		exists = tournament.matches.filter(round_name=round_name).filter(
			Q(team_one=team_one, team_two=team_two) | Q(team_one=team_two, team_two=team_one)
		).exists()
		if exists:
			continue
		Match.objects.create(
			tournament=tournament,
			round_name=round_name,
			team_one=team_one,
			team_two=team_two,
		)
		created += 1
	entries = {
		entry.team_id: entry
		for entry in tournament.enrolled_teams.filter(team__in=teams)
	}
	for seed, team in enumerate(teams, start=1):
		entry = entries.get(team.id)
		if not entry:
			entry = TournamentTeam.objects.create(tournament=tournament, team=team)
		updates: list[str] = []
		if entry.stage != TournamentTeam.Stage.KNOCKOUT:
			entry.stage = TournamentTeam.Stage.KNOCKOUT
			updates.append("stage")
		if entry.seed != seed:
			entry.seed = seed
			updates.append("seed")
		if updates:
			entry.save(update_fields=updates)
	return created


def _record_quick_result(tournament: Tournament, data: dict) -> Match:
	team_one: Team = data["team_one"]
	team_two: Team = data["team_two"]
	sets_one: int = data["team_one_sets"]
	sets_two: int = data["team_two_sets"]
	winner = team_one if sets_one > sets_two else team_two
	match = Match.objects.create(
		tournament=tournament,
		round_name=data.get("round_name", "Fase de grupos"),
		team_one=team_one,
		team_two=team_two,
		team_one_sets_won=sets_one,
		team_two_sets_won=sets_two,
		winner=winner,
	)
	return match


def _apply_game_edit(match: Match, sets_one: int, sets_two: int) -> None:
	match.team_one_sets_won = sets_one
	match.team_two_sets_won = sets_two
	match.winner = match.team_one if sets_one > sets_two else match.team_two
	match.save(update_fields=["team_one_sets_won", "team_two_sets_won", "winner"])



def _progress_knockout(
	tournament: Tournament,
	qualifiers_per_group: int = 2,
	small_group_qualifiers: int = 1,
	expected_group_size: int = 3,
) -> tuple[int, str | None]:
	knockout_matches = tournament.matches.filter(round_name__startswith="Mata-mata")
	if not knockout_matches.exists():
		qualifiers = _collect_group_qualifiers(
			tournament,
			default_slots=qualifiers_per_group,
			small_group_slots=small_group_qualifiers,
			expected_group_size=expected_group_size,
		)
		if len(qualifiers) < 2:
			return 0, "Precisamos de ao menos duas duplas classificadas a partir dos grupos."
		if len(qualifiers) & (len(qualifiers) - 1) != 0:
			return 0, "A quantidade de duplas classificadas precisa ser uma potência de 2 para montar o mata-mata. Ajuste os critérios."
		if len(qualifiers) % 2 != 0:
			return 0, "Quantidade de duplas classificadas é ímpar; ajuste os grupos."
		created = _create_knockout_round(tournament, qualifiers)
		return created, None if created else "As partidas da fase eliminatória já existem."
	latest_round = knockout_matches.order_by("-created_at").values_list("round_name", flat=True).first()
	if not latest_round:
		return 0, None
	current_round_matches = knockout_matches.filter(round_name=latest_round).order_by("created_at")
	if current_round_matches.filter(winner__isnull=True).exists():
		return 0, "Registre todos os vencedores da fase atual antes de avançar."
	winners = [match.winner for match in current_round_matches if match.winner]
	if len(winners) < 2:
		return 0, "Precisamos de pelo menos duas duplas classificadas para a próxima fase."
	if len(winners) % 2 != 0:
		return 0, "Número de vencedores é ímpar; aguarde mais resultados."
	created = _create_knockout_round(tournament, winners)
	if created:
		return created, None
	return 0, "Próxima fase já está criada."

