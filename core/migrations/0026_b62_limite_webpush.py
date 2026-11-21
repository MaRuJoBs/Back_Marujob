from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('core', '0025_notificacoes_freelancer_push')]

    operations = [
        migrations.AddField(
            model_name='freelance',
            name='max_profissionais',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='WebPushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.URLField(max_length=2048, unique=True)),
                ('p256dh', models.CharField(max_length=128)),
                ('auth', models.CharField(max_length=64)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='webpush_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['id']},
        ),
    ]
