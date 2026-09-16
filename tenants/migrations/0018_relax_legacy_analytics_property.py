from django.db import migrations


def relax_legacy_analytics_property(apps, schema_editor):
    """Compatibilidade com bancos que receberam a antiga migração 0009.

    A coluna não pertence mais ao modelo atual. Preservamos os dados antigos,
    mas permitimos INSERTs do ORM que não enviam esse campo. Bancos novos não
    possuem a coluna e não precisam de alteração.
    """
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        return
    table = apps.get_model('tenants', 'TenantSettings')._meta.db_table
    column = 'google_analytics_property_id'
    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(cursor, table)
    if any(field.name == column and not field.null_ok for field in columns):
        quote = schema_editor.quote_name
        schema_editor.execute(
            f'ALTER TABLE {quote(table)} ALTER COLUMN {quote(column)} DROP NOT NULL'
        )


class Migration(migrations.Migration):
    dependencies = [('tenants', '0017_tenantsettings_tag_google_analytics')]
    operations = [
        migrations.RunPython(relax_legacy_analytics_property, migrations.RunPython.noop),
    ]
