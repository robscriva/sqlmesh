# type: ignore
import typing as t
from unittest.mock import call

import pandas as pd
import pytest
from pytest_mock.plugin import MockerFixture
from sqlglot import expressions as exp
from sqlglot import parse_one

from sqlmesh.core.engine_adapter import EngineAdapter, EngineAdapterWithIndexSupport
from sqlmesh.core.schema_diff import (
    ColumnPosition,
    DiffConfig,
    ParentColumns,
    SchemaDelta,
)


def test_create_view(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.create_view("test_view", parse_one("SELECT a FROM tbl"))
    adapter.create_view("test_view", parse_one("SELECT a FROM tbl"), replace=False)

    cursor_mock.execute.assert_has_calls(
        [
            call('CREATE OR REPLACE VIEW "test_view" AS SELECT "a" FROM "tbl"'),
            call('CREATE VIEW "test_view" AS SELECT "a" FROM "tbl"'),
        ]
    )


def test_create_schema(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.create_schema("test_schema")
    adapter.create_schema("test_schema", ignore_if_exists=False)

    cursor_mock.execute.assert_has_calls(
        [
            call('CREATE SCHEMA IF NOT EXISTS "test_schema"'),
            call('CREATE SCHEMA "test_schema"'),
        ]
    )


def test_columns(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()

    connection_mock.cursor.return_value = cursor_mock
    cursor_mock.fetchall.return_value = [
        ("id", "int"),
        ("name", "string"),
        ("price", "double"),
        ("ds", "string"),
        ("# Partition Information", ""),
        ("# col_name", "data_type"),
        ("ds", "string"),
    ]

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    assert adapter.columns("test_table") == {
        "id": exp.DataType.build("int"),
        "name": exp.DataType.build("string"),
        "price": exp.DataType.build("double"),
        "ds": exp.DataType.build("string"),
    }

    cursor_mock.execute.assert_called_once_with('DESCRIBE "test_table"')


def test_table_exists(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    assert adapter.table_exists("test_table")
    cursor_mock.execute.assert_called_once_with(
        'DESCRIBE "test_table"',
    )

    cursor_mock = mocker.Mock()
    cursor_mock.execute.side_effect = RuntimeError("error")
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    assert not adapter.table_exists("test_table")
    cursor_mock.execute.assert_called_once_with(
        'DESCRIBE "test_table"',
    )


def test_insert_overwrite_by_time_partition(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter._insert_overwrite_by_condition(
        "test_table",
        parse_one("SELECT a FROM tbl"),
        where=parse_one("b BETWEEN '2022-01-01' and '2022-01-02'"),
        columns_to_types={"a": exp.DataType.build("INT")},
    )

    cursor_mock.begin.assert_called_once()
    cursor_mock.commit.assert_called_once()

    cursor_mock.execute.assert_has_calls(
        [
            call("DELETE FROM \"test_table\" WHERE \"b\" BETWEEN '2022-01-01' AND '2022-01-02'"),
            call('INSERT INTO "test_table" ("a") SELECT "a" FROM "tbl"'),
        ]
    )


def test_insert_append_query(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.insert_append(
        "test_table",
        parse_one("SELECT a FROM tbl"),
        columns_to_types={"a": exp.DataType.build("INT")},
    )

    cursor_mock.execute.assert_called_once_with(
        'INSERT INTO "test_table" ("a") SELECT "a" FROM "tbl"'
    )


def test_insert_append_pandas(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    adapter.insert_append(
        "test_table",
        df,
        columns_to_types={
            "a": exp.DataType.build("INT"),
            "b": exp.DataType.build("INT"),
        },
    )

    cursor_mock.begin.assert_called_once()
    cursor_mock.commit.assert_called_once()

    cursor_mock.execute.assert_has_calls(
        [
            call(
                'INSERT INTO "test_table" ("a", "b") SELECT CAST("a" AS INT) AS "a", CAST("b" AS INT) AS "b" FROM (VALUES (CAST(1 AS INT), CAST(4 AS INT)), (2, 5), (3, 6)) AS "t"("a", "b")'
            ),
        ]
    )


def test_create_table(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    columns_to_types = {
        "cola": exp.DataType.build("INT"),
        "colb": exp.DataType.build("TEXT"),
    }

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.create_table("test_table", columns_to_types)

    cursor_mock.execute.assert_called_once_with(
        'CREATE TABLE IF NOT EXISTS "test_table" ("cola" INT, "colb" TEXT)'
    )


def test_create_table_properties(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    columns_to_types = {
        "cola": exp.DataType.build("INT"),
        "colb": exp.DataType.build("TEXT"),
    }

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.create_table(
        "test_table",
        columns_to_types,
        partitioned_by=["colb"],
        storage_format="ICEBERG",
    )

    cursor_mock.execute.assert_called_once_with(
        'CREATE TABLE IF NOT EXISTS "test_table" ("cola" INT, "colb" TEXT)'
    )


@pytest.mark.parametrize(
    "diff_config, operations, expected",
    [
        (
            DiffConfig(),
            [
                SchemaDelta.drop("c"),
                SchemaDelta.drop("d"),
                # Positions are ignored
                SchemaDelta.add("e", "INT", ColumnPosition.create_middle("a")),
                SchemaDelta.add("f", "TEXT", ColumnPosition.create_first()),
                # Alter is converted to drop/add
                SchemaDelta.alter_type("e", "TEXT", "INT"),
            ],
            [
                """ALTER TABLE "test_table" DROP COLUMN "c\"""",
                """ALTER TABLE "test_table" DROP COLUMN "d\"""",
                """ALTER TABLE "test_table" ADD COLUMN "e" INT""",
                """ALTER TABLE "test_table" ADD COLUMN "f" TEXT""",
                """ALTER TABLE "test_table" DROP COLUMN "e\"""",
                """ALTER TABLE "test_table" ADD COLUMN "e" TEXT""",
            ],
        ),
        (
            DiffConfig(support_positional_add=True),
            [
                SchemaDelta.drop("c"),
                SchemaDelta.drop("d"),
                # Positions are implemented
                SchemaDelta.add("e", "INT", ColumnPosition.create_middle("a")),
                SchemaDelta.add("f", "TEXT", ColumnPosition.create_first()),
                # Alter is converted to drop/add
                SchemaDelta.alter_type("e", "TEXT", "INT"),
            ],
            [
                """ALTER TABLE "test_table" DROP COLUMN "c\"""",
                """ALTER TABLE "test_table" DROP COLUMN "d\"""",
                """ALTER TABLE "test_table" ADD COLUMN "e" INT AFTER a""",
                """ALTER TABLE "test_table" ADD COLUMN "f" TEXT FIRST""",
                """ALTER TABLE "test_table" DROP COLUMN "e\"""",
                """ALTER TABLE "test_table" ADD COLUMN "e" TEXT""",
            ],
        ),
        (
            DiffConfig(
                support_positional_add=True,
                compatible_types={exp.DataType.build("INT"): {exp.DataType.build("TEXT")}},
            ),
            [
                SchemaDelta.drop("c"),
                SchemaDelta.drop("d"),
                # Positions are ignored
                SchemaDelta.add("e", "INT", ColumnPosition.create_middle("a")),
                SchemaDelta.add("f", "TEXT", ColumnPosition.create_first()),
                # Alter is supported
                SchemaDelta.alter_type("e", "TEXT", "INT"),
            ],
            [
                """ALTER TABLE "test_table" DROP COLUMN "c\"""",
                """ALTER TABLE "test_table" DROP COLUMN "d\"""",
                """ALTER TABLE "test_table" ADD COLUMN "e" INT AFTER a""",
                """ALTER TABLE "test_table" ADD COLUMN "f" TEXT FIRST""",
                """ALTER TABLE "test_table" ALTER COLUMN "e" TYPE TEXT""",
            ],
        ),
        (
            DiffConfig(
                support_positional_add=True,
                compatible_types={exp.DataType.build("INT"): {exp.DataType.build("TEXT")}},
                support_struct_add=True,
                array_suffix=".element",
            ),
            [
                SchemaDelta.drop("c"),
                SchemaDelta.drop("d"),
                # Positions are ignored
                SchemaDelta.add("e", "INT", ColumnPosition.create_middle("a")),
                SchemaDelta.add("f", "TEXT", ColumnPosition.create_first()),
                # Struct add is supported
                SchemaDelta.add(
                    "nested_b",
                    "INT",
                    ColumnPosition.create_middle("nested_a"),
                    ParentColumns.create(("nested", "STRUCT")),
                ),
                SchemaDelta.add(
                    "array_b",
                    "INT",
                    ColumnPosition.create_middle("array_a"),
                    ParentColumns.create(("array", "ARRAY")),
                ),
                # Alter is supported
                SchemaDelta.alter_type("e", "TEXT", "INT"),
            ],
            [
                """ALTER TABLE "test_table" DROP COLUMN "c\"""",
                """ALTER TABLE "test_table" DROP COLUMN "d\"""",
                """ALTER TABLE "test_table" ADD COLUMN "e" INT AFTER a""",
                """ALTER TABLE "test_table" ADD COLUMN "f" TEXT FIRST""",
                """ALTER TABLE "test_table" ADD COLUMN "nested.nested_b" INT AFTER nested_a""",
                """ALTER TABLE "test_table" ADD COLUMN "array.element.array_b" INT AFTER array_a""",
                """ALTER TABLE "test_table" ALTER COLUMN "e" TYPE TEXT""",
            ],
        ),
    ],
)
def test_alter_table(
    mocker: MockerFixture,
    diff_config: DiffConfig,
    operations: t.List[SchemaDelta],
    expected: t.List[str],
):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")
    adapter.DIFF_CONFIG = diff_config
    adapter.alter_table(
        "test_table",
        operations=operations,
    )

    cursor_mock.begin.assert_called_once()
    cursor_mock.commit.assert_called_once()
    print(cursor_mock.execute.call_args_list)
    cursor_mock.execute.assert_has_calls([call(x) for x in expected])


def test_merge(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.merge(
        target_table="target",
        source_table="SELECT id, ts, val FROM source",
        column_names=["id", "ts", "val"],
        unique_key=["id"],
    )
    cursor_mock.execute.assert_called_once_with(
        'MERGE INTO "target" AS "__MERGE_TARGET__" USING (SELECT id, ts, val FROM source) AS __MERGE_SOURCE__ ON "__MERGE_TARGET__"."id" = "__MERGE_SOURCE__"."id" '
        'WHEN MATCHED THEN UPDATE SET "__MERGE_TARGET__"."id" = "__MERGE_SOURCE__"."id", "__MERGE_TARGET__"."ts" = "__MERGE_SOURCE__"."ts", "__MERGE_TARGET__"."val" = "__MERGE_SOURCE__"."val" '
        'WHEN NOT MATCHED THEN INSERT ("id", "ts", "val") VALUES ("__MERGE_SOURCE__"."id", "__MERGE_SOURCE__"."ts", "__MERGE_SOURCE__"."val")'
    )

    cursor_mock.reset_mock()
    adapter.merge(
        target_table="target",
        source_table="SELECT id, ts, val FROM source",
        column_names=["id", "ts", "val"],
        unique_key=["id", "ts"],
    )
    cursor_mock.execute.assert_called_once_with(
        'MERGE INTO "target" AS "__MERGE_TARGET__" USING (SELECT id, ts, val FROM source) AS __MERGE_SOURCE__ ON "__MERGE_TARGET__"."id" = "__MERGE_SOURCE__"."id" AND "__MERGE_TARGET__"."ts" = "__MERGE_SOURCE__"."ts" '
        'WHEN MATCHED THEN UPDATE SET "__MERGE_TARGET__"."id" = "__MERGE_SOURCE__"."id", "__MERGE_TARGET__"."ts" = "__MERGE_SOURCE__"."ts", "__MERGE_TARGET__"."val" = "__MERGE_SOURCE__"."val" '
        'WHEN NOT MATCHED THEN INSERT ("id", "ts", "val") VALUES ("__MERGE_SOURCE__"."id", "__MERGE_SOURCE__"."ts", "__MERGE_SOURCE__"."val")'
    )


def test_replace_query(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.replace_query("test_table", parse_one("SELECT a FROM tbl"), {"a": "int"})

    cursor_mock.execute.assert_called_once_with(
        'CREATE OR REPLACE TABLE "test_table" AS SELECT "a" FROM "tbl"'
    )


def test_replace_query_pandas(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
    adapter.replace_query("test_table", df, {"a": "int", "b": "int"})

    cursor_mock.execute.assert_called_once_with(
        'CREATE OR REPLACE TABLE "test_table" AS SELECT CAST("a" AS INT) AS "a", CAST("b" AS INT) AS "b" FROM (VALUES (CAST(1 AS INT), CAST(4 AS INT)), (2, 5), (3, 6)) AS "test_table"("a", "b")'
    )


def test_create_table_like(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.create_table_like("target_table", "source_table")

    cursor_mock.execute.assert_called_once_with(
        'CREATE TABLE IF NOT EXISTS "target_table" LIKE "source_table"'
    )


def test_create_table_primary_key(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    columns_to_types = {
        "cola": exp.DataType.build("INT"),
        "colb": exp.DataType.build("TEXT"),
    }

    adapter = EngineAdapterWithIndexSupport(lambda: connection_mock, "")  # type: ignore
    adapter.create_table("test_table", columns_to_types, primary_key=("cola", "colb"))

    cursor_mock.execute.assert_called_once_with(
        'CREATE TABLE IF NOT EXISTS "test_table" ("cola" INT, "colb" TEXT, PRIMARY KEY("cola", "colb"))'
    )


def test_create_index(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapterWithIndexSupport(lambda: connection_mock, "")  # type: ignore
    adapter.create_index("test_table", "test_index", ("cola", "colb"))

    cursor_mock.execute.assert_called_once_with(
        'CREATE INDEX IF NOT EXISTS "test_index" ON "test_table" ("cola", "colb")'
    )


def test_rename_table(mocker: MockerFixture):
    connection_mock = mocker.NonCallableMock()
    cursor_mock = mocker.Mock()
    connection_mock.cursor.return_value = cursor_mock

    adapter = EngineAdapter(lambda: connection_mock, "")  # type: ignore
    adapter.rename_table("old_table", "new_table")

    cursor_mock.execute.assert_called_once_with('ALTER TABLE "old_table" RENAME TO "new_table"')
