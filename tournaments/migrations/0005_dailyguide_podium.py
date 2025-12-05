from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tournaments", "0004_tournamentparticipant_tournamentteam"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailyguide",
            name="champion",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="champion_guides",
                to="tournaments.dailyteam",
            ),
        ),
        migrations.AddField(
            model_name="dailyguide",
            name="runner_up",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="runner_up_guides",
                to="tournaments.dailyteam",
            ),
        ),
        migrations.AddField(
            model_name="dailyguide",
            name="third_place",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.SET_NULL,
                related_name="third_place_guides",
                to="tournaments.dailyteam",
            ),
        ),
        migrations.AddField(
            model_name="dailyguide",
            name="finished_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
