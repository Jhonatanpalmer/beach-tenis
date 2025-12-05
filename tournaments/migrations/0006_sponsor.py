from django.db import migrations, models


class Migration(migrations.Migration):

	dependencies = [
		("tournaments", "0005_dailyguide_podium"),
	]

	operations = [
		migrations.CreateModel(
			name="Sponsor",
			fields=[
				(
					"id",
					models.BigAutoField(
						auto_created=True,
						primary_key=True,
						serialize=False,
						verbose_name="ID",
					)
				),
				("name", models.CharField(max_length=120)),
				("logo", models.ImageField(upload_to="sponsors/")),
				("website", models.URLField(blank=True)),
				("is_active", models.BooleanField(default=True)),
				("created_at", models.DateTimeField(auto_now_add=True)),
			],
			options={
				"ordering": ("-created_at", "name"),
			},
		),
	]