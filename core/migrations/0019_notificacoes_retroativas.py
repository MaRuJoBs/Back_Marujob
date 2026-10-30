from itertools import islice

from django.db import migrations


def criar_notificacoes_retroativas(apps, schema_editor):
    candidatura = apps.get_model('core', 'Candidatura')
    notificacao = apps.get_model('core', 'Notificacao')
    alias = schema_editor.connection.alias
    rows = (
        candidatura.objects.using(alias)
        .filter(oportunidade__empresa__isnull=False, notificacao__isnull=True)
        .order_by('pk')
        .values_list('pk', 'oportunidade__empresa_id')
        .iterator(chunk_size=500)
    )
    while batch := list(islice(rows, 500)):
        notificacao.objects.using(alias).bulk_create(
            [notificacao(candidatura_id=pk, empresa_id=empresa_id) for pk, empresa_id in batch],
            batch_size=500,
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [('core', '0018_notificacao')]

    operations = [
        # Reversing this data step must not erase existing notifications/read state.
        migrations.RunPython(criar_notificacoes_retroativas, migrations.RunPython.noop),
    ]
