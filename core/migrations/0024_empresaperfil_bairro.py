from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0023_avaliacoes_reputacao'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresaperfil',
            name='bairro',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
