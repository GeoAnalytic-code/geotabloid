# Generated by Django 2.0.3 on 2018-04-12 14:40

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0006_auto_20180412_0100'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profileset',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='profilesets', to=settings.AUTH_USER_MODEL),
        ),
    ]
