from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0010_fix_index_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="assigned_at",
            field=models.DateTimeField(
                blank=True, help_text="Timestamp de asignación a vendedor", null=True
            ),
        ),
        migrations.AddField(
            model_name="chatsession",
            name="first_response_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp del primer mensaje OUTBOUND del vendedor",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="chatsession",
            name="closed_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp de cierre (GANADO/PERDIDO/ABANDONO)",
                null=True,
            ),
        ),
    ]
