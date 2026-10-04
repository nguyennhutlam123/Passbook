from django.db import migrations, models


def add_shipment_tracking_provenance(apps, schema_editor):
    table_name = 'shipment_tracking'
    if table_name not in schema_editor.connection.introspection.table_names():
        return

    model = apps.get_model('books', 'ShipmentTracking')
    columns = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    if 'source' not in columns:
        source = models.CharField(max_length=30, default='LEGACY')
        source.set_attributes_from_name('source')
        source.model = model
        schema_editor.add_field(model, source)
    if 'changed_by_id' not in columns:
        changed_by_id = models.BigIntegerField(null=True, blank=True)
        changed_by_id.set_attributes_from_name('changed_by_id')
        changed_by_id.model = model
        schema_editor.add_field(model, changed_by_id)


def remove_shipment_tracking_provenance(apps, schema_editor):
    table_name = 'shipment_tracking'
    if table_name not in schema_editor.connection.introspection.table_names():
        return

    model = apps.get_model('books', 'ShipmentTracking')
    columns = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    for name, field in (
        ('changed_by_id', models.BigIntegerField(null=True, blank=True)),
        ('source', models.CharField(max_length=30, default='LEGACY')),
    ):
        if name in columns:
            field.set_attributes_from_name(name)
            field.model = model
            schema_editor.remove_field(model, field)


class Migration(migrations.Migration):
    dependencies = [
        ('books', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_shipment_tracking_provenance,
                    remove_shipment_tracking_provenance,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='shipmenttracking',
                    name='source',
                    field=models.CharField(default='LEGACY', max_length=30),
                ),
                migrations.AddField(
                    model_name='shipmenttracking',
                    name='changed_by_id',
                    field=models.BigIntegerField(blank=True, null=True),
                ),
            ],
        ),
    ]
