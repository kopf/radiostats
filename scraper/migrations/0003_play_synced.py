# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-10-30 10:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scraper', '0002_auto_20161030_1039'),
    ]

    operations = [
        migrations.AddField(
            model_name='play',
            name='synced',
            field=models.BooleanField(default=False),
        ),
    ]