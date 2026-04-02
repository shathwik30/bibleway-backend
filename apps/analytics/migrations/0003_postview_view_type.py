from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0002_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="postview",
            name="view_type",
            field=models.CharField(
                choices=[("view", "View"), ("share", "Share")],
                db_index=True,
                default="view",
                max_length=10,
            ),
        ),
        migrations.RemoveIndex(
            model_name="postview",
            name="analytics_p_content_fa22ef_idx",
        ),
        migrations.AddIndex(
            model_name="postview",
            index=models.Index(
                fields=["content_type", "object_id", "view_type"],
                name="analytics_p_content_vt_idx",
            ),
        ),
    ]
