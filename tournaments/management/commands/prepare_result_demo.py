"""Create a ready-to-test match result page with sample data."""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from tournaments.models import Category, Match, Participant, SetScore, Team, Tournament


class Command(BaseCommand):
    help = "Cria um torneio e uma partida com placar preenchido para testar a tela de resultados."

    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(
            name="Resumo Automático",
            defaults={"description": "Categoria criada automaticamente para testes", "is_default": False},
        )
        mixed_team_a = self._create_team(
            category,
            ("Lucas Prado", "1990-05-05", Participant.Gender.MALE),
            ("Bianca Torres", "1992-06-06", Participant.Gender.FEMALE),
            Team.Division.MIXED,
        )
        mixed_team_b = self._create_team(
            category,
            ("Pedro Nunes", "1989-07-07", Participant.Gender.MALE),
            ("Lara Menezes", "1994-08-08", Participant.Gender.FEMALE),
            Team.Division.MIXED,
        )

        tournament, _ = Tournament.objects.get_or_create(
            name="Torneio Rápido - Resumo Automático",
            defaults={
                "category": category,
                "division": Team.Division.MIXED,
                "location": "Quadra Central",
                "start_date": date.today(),
                "tie_break_enabled": True,
            },
        )
        match, _ = Match.objects.get_or_create(
            tournament=tournament,
            team_one=mixed_team_a,
            team_two=mixed_team_b,
            defaults={"round_name": "Partida ilustrativa"},
        )
        match.team_one_point_sequence = ["15", "30", "40", "GAME"]
        match.team_two_point_sequence = ["15", "30", "30", "40"]
        match.save(update_fields=["team_one_point_sequence", "team_two_point_sequence"])

        match.set_scores.all().delete()
        SetScore.objects.create(
            match=match,
            set_number=1,
            team_one_games=6,
            team_two_games=4,
        )
        SetScore.objects.create(
            match=match,
            set_number=2,
            team_one_games=3,
            team_two_games=6,
        )
        SetScore.objects.create(
            match=match,
            set_number=3,
            team_one_games=10,
            team_two_games=8,
            tie_break_played=True,
            team_one_tie_break_points=10,
            team_two_tie_break_points=8,
        )
        match.refresh_from_db()
        match.update_totals()

        self.stdout.write(self.style.SUCCESS(
            f"Partida pronta! Acesse /partidas/{match.pk}/resultado/ para ver o resumo em ação."
        ))

    def _create_team(
        self,
        category: Category,
        player_one_data: tuple[str, str, str],
        player_two_data: tuple[str, str, str],
        division: str,
    ) -> Team:
        player_one = self._upsert_participant(category, *player_one_data)
        player_two = self._upsert_participant(category, *player_two_data)
        team, _ = Team.objects.get_or_create(
            player_one=player_one,
            player_two=player_two,
            category=category,
            division=division,
        )
        return team

    def _upsert_participant(
        self,
        category: Category,
        name: str,
        birth: str,
        gender: str,
    ) -> Participant:
        participant, _ = Participant.objects.get_or_create(
            full_name=name,
            defaults={
                "birth_date": birth,
                "gender": gender,
                "category": category,
            },
        )
        if participant.category_id != category.id:
            participant.category = category
            participant.save(update_fields=["category"])
        return participant
