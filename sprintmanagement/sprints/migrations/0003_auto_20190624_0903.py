# Generated by Django 2.2.1 on 2019-06-24 09:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sprints", "0002_auto_20190622_2321"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicalsprint",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sprint",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
