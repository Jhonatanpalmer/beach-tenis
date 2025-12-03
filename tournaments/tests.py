from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Category, Match, Participant, SetScore, Team, Tournament


class TeamModelTest(TestCase):
	def setUp(self):
		self.category = Category.objects.create(name="Teste")
		self.male = Participant.objects.create(
			full_name="João",
			birth_date="1990-01-01",
			gender=Participant.Gender.MALE,
			category=self.category,
		)
		self.female = Participant.objects.create(
			full_name="Maria",
			birth_date="1992-02-02",
			gender=Participant.Gender.FEMALE,
			category=self.category,
		)

	def test_mixed_team_requires_valid_combination(self):
		team = Team(
			player_one=self.male,
			player_two=self.female,
			category=self.category,
			division=Team.Division.MIXED,
		)
		team.save()
		self.assertIn("João", team.name)

	def test_invalid_category_combination_raises(self):
		other_category = Category.objects.create(name="Outra")
		participant_other = Participant.objects.create(
			full_name="Ana",
			birth_date="1995-03-03",
			gender=Participant.Gender.FEMALE,
			category=other_category,
		)
		team = Team(
			player_one=self.male,
			player_two=participant_other,
			category=self.category,
			division=Team.Division.MIXED,
		)
		with self.assertRaises(ValidationError):
			team.save()


class MatchScoreTest(TestCase):
	def setUp(self):
		category = Category.objects.create(name="Ranking")
		self.male = Participant.objects.create(
			full_name="Carlos",
			birth_date="1991-04-04",
			gender=Participant.Gender.MALE,
			category=category,
		)
		self.female = Participant.objects.create(
			full_name="Lara",
			birth_date="1993-05-05",
			gender=Participant.Gender.FEMALE,
			category=category,
		)
		self.male2 = Participant.objects.create(
			full_name="Pedro",
			birth_date="1994-06-06",
			gender=Participant.Gender.MALE,
			category=category,
		)
		self.female2 = Participant.objects.create(
			full_name="Bianca",
			birth_date="1996-07-07",
			gender=Participant.Gender.FEMALE,
			category=category,
		)
		self.team_one = Team.objects.create(
			player_one=self.male,
			player_two=self.female,
			category=category,
			division=Team.Division.MIXED,
		)
		self.team_two = Team.objects.create(
			player_one=self.male2,
			player_two=self.female2,
			category=category,
			division=Team.Division.MIXED,
		)
		self.tournament = Tournament.objects.create(
			name="Aberto",
			category=category,
			division=Team.Division.MIXED,
			start_date="2025-12-01",
		)
		self.match = Match.objects.create(
			tournament=self.tournament,
			team_one=self.team_one,
			team_two=self.team_two,
			round_name="Grupo",
		)

	def test_point_sequence_accumulation(self):
		self.match.set_points_for_team(Match.team_one_position, ["15", "30", "game"])
		self.assertEqual(self.match.team_one_point_sequence, ["15", "30", "GAME"])
		self.assertEqual(self.match.accumulated_points(Match.team_one_position), 105)

	def test_set_scores_define_winner(self):
		SetScore.objects.create(
			match=self.match,
			set_number=1,
			team_one_games=6,
			team_two_games=4,
		)
		SetScore.objects.create(
			match=self.match,
			set_number=2,
			team_one_games=4,
			team_two_games=6,
		)
		SetScore.objects.create(
			match=self.match,
			set_number=3,
			team_one_games=10,
			team_two_games=8,
			tie_break_played=True,
			team_one_tie_break_points=10,
			team_two_tie_break_points=8,
		)
		self.match.refresh_from_db()
		self.assertEqual(self.match.winner, self.team_one)
		self.assertEqual(self.match.team_one_sets_won, 2)
		self.assertEqual(self.match.team_two_sets_won, 1)
