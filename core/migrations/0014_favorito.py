from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0013_user_geolocation_accuracy_user_geolocation_timestamp_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Favorito',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('oportunidade', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favoritos', to='core.freelance')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favoritos', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-criado_em', '-id'],
                'constraints': [models.UniqueConstraint(fields=('usuario', 'oportunidade'), name='favorito_usuario_oportunidade_unico')],
            },
        ),
    ]
