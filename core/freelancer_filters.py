"""Database-side exact, case-insensitive membership for the supported JSON backends."""

import re

from django.db import NotSupportedError
from django.db.models import BooleanField, Func


class HabilidadeIExact(Func):
    output_field = BooleanField()
    arity = 2

    def as_sqlite(self, compiler, connection, **extra_context):
        field, field_params = compiler.compile(self.source_expressions[0])
        _, value_params = compiler.compile(self.source_expressions[1])
        pattern = r'(?i)\A' + re.escape(value_params[0]) + r'\Z'
        sql = (
            f"EXISTS (SELECT 1 FROM json_each(CASE WHEN json_type({field}) = 'array' "
            f"THEN {field} ELSE '[]' END) AS skill "
            "WHERE skill.type = 'text' AND skill.value REGEXP %s)"
        )
        return sql, [*field_params, *field_params, pattern]

    def as_postgresql(self, compiler, connection, **extra_context):
        field, field_params = compiler.compile(self.source_expressions[0])
        value, value_params = compiler.compile(self.source_expressions[1])
        sql = (
            f"EXISTS (SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof({field}) = 'array' "
            f"THEN {field} ELSE '[]'::jsonb END) AS skill(value) "
            f"WHERE jsonb_typeof(skill.value) = 'string' AND LOWER(skill.value #>> '{{}}') = LOWER({value}))"
        )
        return sql, [*field_params, *field_params, *value_params]

    def as_sql(self, compiler, connection, **extra_context):
        raise NotSupportedError('O diretório suporta habilidades JSON em SQLite e PostgreSQL.')
