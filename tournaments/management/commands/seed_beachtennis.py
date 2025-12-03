"""Management command to populate demo Beach Tennis data."""

from __future__ import annotations

import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from tournaments.models import Category, Match, Participant, SetScore, Team, Tournament


SEED_NOTES = "Gerado automaticamente (seed)"
MALE_FIRST_NAMES = [
    "Arthur",
    "Benjamin",
    "Bruno",
    "Caio",
    "Carlos",
    "Daniel",
    "Eduardo",
    "Felipe",
    "Gabriel",
    "Gustavo",
    "Henrique",
    "Igor",
    "João",
    "Leonardo",
    "Lucas",
    "Luiz",
    "Marcelo",
    "Matheus",
    "Miguel",
    "Paulo",
    "Pedro",
    "Rafael",
    "Ricardo",
    "Rodrigo",
    "Samuel",
    "Thiago",
    "Vinicius",
]
FEMALE_FIRST_NAMES = [
    "Alice",
    "Amanda",
    "Ana",
    "Beatriz",
    "Bianca",
    "Bruna",
    "Camila",
    "Carla",
    "Clara",
    "Daniela",
    "Eduarda",
    "Fernanda",
    "Gabriela",
    "Helena",
    "Isabela",
    "Júlia",
    "Larissa",
    "Laura",
    "Luana",
    "Mariana",
    "Nathalia",
    "Paloma",
    "Patrícia",
    "Renata",
    "Sofia",
    "Taís",
    "Vitória",
]
LAST_NAMES = [
    "Almeida",
    "Andrade",
    "Azevedo",
    "Barbosa",
    "Batista",
    "Cavalcanti",
    "Costa",
    "Dias",
    "Duarte",
    "Fernandes",
    "Ferraz",
    "Ferreira",
    "Freitas",
    "Gomes",
    "Lima",
    "Lopes",
    "Martins",
    "Melo",
    "Monteiro",
    "Moreira",
    "Oliveira",
    "Pereira",
    "Ribeiro",
    "Rocha",
    "Santos",
    "Silva",
    "Souza",
    "Teixeira",
]


class Command(BaseCommand):
    help = "Popula o banco com participantes, duplas e torneios de teste para Beach Tennis."

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-gender",
            type=int,
            default=100,
            help="Quantidade de participantes masculinos e femininos (default: 100 de cada).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Remove dados de demonstração previamente criados antes de popular novamente.",
        )

    def handle(self, *args, **options):
        per_gender = options["per_gender"]
        force = options["force"]
        random.seed(42)
        self.generated_names: set[str] = set()

        with transaction.atomic():
            if force:
                self.stdout.write("Removendo dados anteriores marcados como demonstração...")
                Tournament.objects.filter(notes=SEED_NOTES).delete()
                Participant.objects.filter(notes=SEED_NOTES).delete()

            total_participants = Participant.objects.count()
            target = per_gender * 2
            if total_participants >= target and not force:
                self.stdout.write(self.style.WARNING("Já existem participantes suficientes. Use --force se precisar recriar."))
                return

            categories = list(Category.objects.order_by("name"))
            if len(categories) < 4:
                raise CommandError("Crie pelo menos as categorias A, B, C e D antes de rodar o seed.")

            participants = self._create_participants(per_gender, categories)
            teams_by_key = self._create_teams(categories)
            tournaments_created = self._create_tournaments(teams_by_key, categories)

        self.stdout.write(self.style.SUCCESS(
            f"Seed finalizado: {participants['male_count']} masculinos, {participants['female_count']} femininos, {teams_by_key['total_teams']} duplas, {tournaments_created} torneios."
        ))

    def _create_participants(self, per_gender: int, categories: list[Category]) -> dict[str, int]:
        male_count = self._create_participants_for_gender(per_gender, Participant.Gender.MALE, categories)
        female_count = self._create_participants_for_gender(per_gender, Participant.Gender.FEMALE, categories)
        return {"male_count": male_count, "female_count": female_count}

    def _create_participants_for_gender(self, amount: int, gender: str, categories: list[Category]) -> int:
        created = 0
        today = date.today()
        for idx in range(amount):
            category = categories[idx % len(categories)]
            birth_date = today - timedelta(days=18 * 365 + random.randint(0, 15 * 365))
            name = self._generate_unique_name(gender)
            _, made = Participant.objects.get_or_create(
                full_name=name,
                defaults={
                    "birth_date": birth_date,
                    "gender": gender,
                    "category": category,
                    "notes": SEED_NOTES,
                },
            )
            if made:
                created += 1
        return created

    def _generate_unique_name(self, gender: str) -> str:
        pool = MALE_FIRST_NAMES if gender == Participant.Gender.MALE else FEMALE_FIRST_NAMES
        for _ in range(50):
            candidate = f"{random.choice(pool)} {random.choice(LAST_NAMES)}"
            if candidate not in self.generated_names:
                self.generated_names.add(candidate)
                return candidate
        # fallback in unlikely case of duplicates
        suffix = len(self.generated_names) + 1
        candidate = f"{random.choice(pool)} {random.choice(LAST_NAMES)} {suffix}"
        self.generated_names.add(candidate)
        return candidate

    def _create_teams(self, categories: list[Category]):
        teams_by_key: dict[tuple[int, str], list[Team]] = {}
        total_teams = 0
        for category in categories:
            male_players = list(
                Participant.objects.filter(category=category, gender=Participant.Gender.MALE)
            )
            female_players = list(
                Participant.objects.filter(category=category, gender=Participant.Gender.FEMALE)
            )
            random.shuffle(male_players)
            random.shuffle(female_players)

            male_teams = self._pair_players(male_players, category, Team.Division.MALE)
            female_teams = self._pair_players(female_players, category, Team.Division.FEMALE)
            mixed_teams = self._pair_mixed_players(male_players, female_players, category)

            teams_by_key[(category.id, Team.Division.MALE)] = male_teams
            teams_by_key[(category.id, Team.Division.FEMALE)] = female_teams
            teams_by_key[(category.id, Team.Division.MIXED)] = mixed_teams
            total_teams += len(male_teams) + len(female_teams) + len(mixed_teams)

        teams_by_key["total_teams"] = total_teams
        return teams_by_key

    def _pair_players(self, players: list[Participant], category: Category, division: str) -> list[Team]:
        teams: list[Team] = []
        for i in range(0, len(players) - 1, 2):
            player_one, player_two = players[i], players[i + 1]
            if player_one.id > player_two.id:
                player_one, player_two = player_two, player_one
            team, created = Team.objects.get_or_create(
                player_one=player_one,
                player_two=player_two,
                category=category,
                division=division,
                defaults={"name": f"{player_one.full_name} / {player_two.full_name}"},
            )
            if created:
                teams.append(team)
        return teams

    def _pair_mixed_players(self, male_players: list[Participant], female_players: list[Participant], category: Category) -> list[Team]:
        teams: list[Team] = []
        for idx in range(min(len(male_players), len(female_players))):
            player_one = male_players[idx]
            player_two = female_players[idx]
            if player_one.id > player_two.id:
                player_one, player_two = player_two, player_one
            team, created = Team.objects.get_or_create(
                player_one=player_one,
                player_two=player_two,
                category=category,
                division=Team.Division.MIXED,
                defaults={"name": f"{player_one.full_name} / {player_two.full_name}"},
            )
            if created:
                teams.append(team)
        return teams

    def _create_tournaments(self, teams_by_key: dict, categories: list[Category]) -> int:
        tournaments_created = 0
        for category in categories:
            for division, label in (
                (Team.Division.MALE, "Masculino"),
                (Team.Division.FEMALE, "Feminino"),
                (Team.Division.MIXED, "Misto"),
            ):
                tournament_name = f"Torneio {label} {category.name}"
                tournament, created = Tournament.objects.get_or_create(
                    name=tournament_name,
                    defaults={
                        "category": category,
                        "division": division,
                        "location": "Arena Central",
                        "start_date": date.today(),
                        "max_sets": 3,
                        "tie_break_enabled": True,
                        "tie_break_points": random.choice([7, 10]),
                        "notes": SEED_NOTES,
                    },
                )
                if created:
                    tournaments_created += 1
                teams = teams_by_key.get((category.id, division), [])
                self._create_matches_for_tournament(tournament, teams)
        return tournaments_created

    def _create_matches_for_tournament(self, tournament: Tournament, teams: list[Team]):
        if len(teams) < 2:
            return
        matches_to_create = min(3, len(teams) // 2)
        for idx in range(matches_to_create):
            team_one = teams[idx * 2]
            team_two = teams[idx * 2 + 1]
            match, _ = Match.objects.get_or_create(
                tournament=tournament,
                team_one=team_one,
                team_two=team_two,
                round_name=f"Rodada {idx + 1}",
            )
            match.set_points_for_team(Match.team_one_position, ["15", "30", "40", "GAME"])
            match.set_points_for_team(Match.team_two_position, ["15", "30", "30", "40"])
            match.save(update_fields=["team_one_point_sequence", "team_two_point_sequence"])
            self._ensure_set_scores(match)

    def _ensure_set_scores(self, match: Match):
        if match.set_scores.exists():
            return
        SetScore.objects.create(
            match=match,
            set_number=1,
            team_one_games=6,
            team_two_games=4,
        )
        SetScore.objects.create(
            match=match,
            set_number=2,
            team_one_games=4,
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
