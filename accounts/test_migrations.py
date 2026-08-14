from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase


class RetiredAISchemaMigrationTests(TransactionTestCase):
    def test_cleanup_drops_stale_user_foreign_key_tables(self):
        user = get_user_model().objects.create_user("legacy-ai-user")
        user_pk = user.pk
        quote = connection.ops.quote_name

        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE {quote('accounts_aiprovider')} ("
                f"{quote('id')} integer PRIMARY KEY)"
            )
            cursor.execute(
                f"CREATE TABLE {quote('accounts_useraimodelcredential')} ("
                f"{quote('id')} integer PRIMARY KEY, "
                f"{quote('user_id')} integer NOT NULL REFERENCES "
                f"{quote('auth_user')} ({quote('id')}), "
                f"{quote('provider_id')} integer NOT NULL REFERENCES "
                f"{quote('accounts_aiprovider')} ({quote('id')}))"
            )
            cursor.execute(
                f"INSERT INTO {quote('accounts_aiprovider')} ({quote('id')}) "
                "VALUES (1)"
            )
            cursor.execute(
                f"INSERT INTO {quote('accounts_useraimodelcredential')} "
                f"({quote('id')}, {quote('user_id')}, {quote('provider_id')}) "
                "VALUES (1, %s, 1)",
                [user.pk],
            )

        migration = import_module(
            "accounts.migrations.0021_drop_retired_ai_schema"
        )
        with connection.schema_editor(atomic=False) as schema_editor:
            migration.drop_retired_ai_schema(apps, schema_editor)

        table_names = connection.introspection.table_names()
        self.assertNotIn("accounts_useraimodelcredential", table_names)
        self.assertNotIn("accounts_aiprovider", table_names)

        user.delete()
        self.assertFalse(get_user_model().objects.filter(pk=user_pk).exists())
