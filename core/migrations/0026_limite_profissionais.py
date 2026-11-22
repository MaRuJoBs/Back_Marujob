from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0025_notificacoes_freelancer_push')]

    operations = [
        migrations.AddField(
            model_name='freelance',
            name='max_profissionais',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
