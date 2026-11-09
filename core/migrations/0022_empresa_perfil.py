import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    # Join both integrated leaves without rewriting either feature's migration.
    dependencies = [
        ('core', '0021_freelance_contrato_b47'),
        ('core', '0021_publicacao_perfil_portfolio'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmpresaPerfil',
            fields=[
                (
                    'empresa',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name='empresa_perfil',
                        serialize=False,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ('descricao_institucional', models.TextField(blank=True, default='', max_length=2000)),
                ('area_atuacao', models.CharField(blank=True, default='', max_length=120)),
                ('cidade', models.CharField(blank=True, default='', max_length=100)),
                (
                    'uf',
                    models.CharField(
                        blank=True,
                        default='',
                        max_length=2,
                        choices=[
                            ('AC', 'AC'),
                            ('AL', 'AL'),
                            ('AP', 'AP'),
                            ('AM', 'AM'),
                            ('BA', 'BA'),
                            ('CE', 'CE'),
                            ('DF', 'DF'),
                            ('ES', 'ES'),
                            ('GO', 'GO'),
                            ('MA', 'MA'),
                            ('MT', 'MT'),
                            ('MS', 'MS'),
                            ('MG', 'MG'),
                            ('PA', 'PA'),
                            ('PB', 'PB'),
                            ('PR', 'PR'),
                            ('PE', 'PE'),
                            ('PI', 'PI'),
                            ('RJ', 'RJ'),
                            ('RN', 'RN'),
                            ('RS', 'RS'),
                            ('RO', 'RO'),
                            ('RR', 'RR'),
                            ('SC', 'SC'),
                            ('SP', 'SP'),
                            ('SE', 'SE'),
                            ('TO', 'TO'),
                        ],
                    ),
                ),
                (
                    'website',
                    models.URLField(
                        blank=True,
                        default='',
                        max_length=200,
                        validators=[django.core.validators.URLValidator(schemes=['http', 'https'])],
                    ),
                ),
                ('contato_comercial', models.CharField(blank=True, default='', max_length=255)),
            ],
        ),
    ]
