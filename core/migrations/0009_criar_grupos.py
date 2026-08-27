from django.db import migrations
from django.contrib.auth.models import Group


def criar_grupos(apps, schema_editor):
    Group.objects.get_or_create(name='Empresa')
    Group.objects.get_or_create(name='Usuário')


def remover_grupos(apps, schema_editor):
    Group.objects.filter(name='Empresa').delete()
    Group.objects.filter(name='Usuário').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_user_profile_image_alter_freelance_descricao'),
    ]

    operations = [
        migrations.RunPython(criar_grupos, remover_grupos),
    ]