"""Django admin configuration for tournaments app."""

from django.contrib import admin

from .models import (
	Category,
	DailyGuide,
	DailyMatch,
	DailyParticipant,
	DailyTeam,
	Match,
	Participant,
	SetScore,
	Sponsor,
	Team,
	Tournament,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ("name", "description", "is_default", "created_at")
	search_fields = ("name",)
	list_filter = ("is_default",)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
	list_display = ("full_name", "gender", "category", "birth_date")
	search_fields = ("full_name",)
	list_filter = ("gender", "category")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
	list_display = ("name", "division", "category", "player_one", "player_two")
	list_filter = ("division", "category")
	search_fields = ("name", "player_one__full_name", "player_two__full_name")


class SetScoreInline(admin.TabularInline):
	model = SetScore
	extra = 1


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
	list_display = (
		"tournament",
		"round_name",
		"team_one",
		"team_two",
		"team_one_sets_won",
		"team_two_sets_won",
		"winner",
	)
	list_filter = ("tournament", "round_name")
	search_fields = ("team_one__name", "team_two__name", "tournament__name")
	inlines = [SetScoreInline]


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
	list_display = (
		"name",
		"division",
		"category",
		"start_date",
		"tie_break_enabled",
	)
	list_filter = ("division", "category", "tie_break_enabled")
	search_fields = ("name", "location")


class DailyParticipantInline(admin.TabularInline):
	model = DailyParticipant
	extra = 0
	readonly_fields = ("name",)
	can_delete = False


@admin.register(DailyGuide)
class DailyGuideAdmin(admin.ModelAdmin):
	list_display = ("name", "pairing_mode", "created_at")
	search_fields = ("name",)
	list_filter = ("pairing_mode",)
	inlines = [DailyParticipantInline]


@admin.register(DailyTeam)
class DailyTeamAdmin(admin.ModelAdmin):
	list_display = ("name", "guide", "player_one", "player_two")
	list_filter = ("guide",)
	search_fields = ("name", "player_one__name", "player_two__name")


@admin.register(DailyMatch)
class DailyMatchAdmin(admin.ModelAdmin):
	list_display = ("guide", "team_one", "team_two", "team_one_score", "team_two_score", "winner")
	list_filter = ("guide",)
	search_fields = ("team_one__name", "team_two__name", "guide__name")


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
	list_display = ("name", "is_active", "created_at")
	list_filter = ("is_active",)
	search_fields = ("name",)
