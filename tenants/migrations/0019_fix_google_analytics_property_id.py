from django.db import migrations


def fix_legacy_google_analytics_column(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name = 'tenants_tenantsettings' 
                          AND column_name = 'google_analytics_property_id'
                    ) THEN
                        ALTER TABLE tenants_tenantsettings ALTER COLUMN google_analytics_property_id DROP NOT NULL;
                        ALTER TABLE tenants_tenantsettings ALTER COLUMN google_analytics_property_id SET DEFAULT NULL;
                    END IF;
                END $$;
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0018_relax_legacy_analytics_property'),
    ]

    operations = [
        migrations.RunPython(fix_legacy_google_analytics_column, migrations.RunPython.noop),
    ]
