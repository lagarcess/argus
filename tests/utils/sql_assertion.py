from typing import List, Optional

import sqlglot
from sqlglot import exp


def assert_sql_equal(actual: str, expected: str, dialect: str = "bigquery") -> None:
    """
    Assert that two SQL strings are semantically equivalent using sqlglot.

    Args:
        actual: The generated SQL string.
        expected: The expected SQL string.
        dialect: The SQL dialect to use for parsing (default: "bigquery").

    Raises:
        AssertionError: If the SQL strings are not semantically equivalent.
    """
    try:
        # Transpile both to a canonical form (strips comments, normalizes case/whitespace)
        # We use sqlglot.transpile which returns a list of strings
        actual_canon = sqlglot.transpile(actual, read=dialect, write=dialect)[0]
        expected_canon = sqlglot.transpile(expected, read=dialect, write=dialect)[0]

        assert actual_canon == expected_canon, (
            f"SQL mismatch!\n"
            f"EXPECTED (Canonical):\n{expected_canon}\n\n"
            f"ACTUAL (Canonical):\n{actual_canon}\n"
        )
    except Exception as e:
        # Fallback for parsing errors or other issues, though we want to catch them
        raise AssertionError(f"SQL comparison failed. Error: {e}") from e


def _extract_column_name(node: exp.Expression) -> Optional[str]:
    """Extract column name from a Column or Identifier expression."""
    if isinstance(node, exp.Column):
        return node.this.this
    elif isinstance(node, exp.Identifier):
        return node.this
    return None


def _check_target_table(expression: exp.Merge, target_table: str, dialect: str) -> None:
    """Verify the MERGE target table matches expected."""
    target = expression.this

    # Strip alias for comparison
    if isinstance(target, exp.Table):
        target.set("alias", None)
    elif isinstance(target, exp.Alias):
        target = target.this

    actual_target = target.sql(dialect=dialect)
    expected_target = sqlglot.parse_one(target_table, read=dialect).sql(dialect=dialect)

    assert actual_target.replace("`", "") == expected_target.replace(
        "`", ""
    ), f"Target table mismatch. Expected {expected_target}, got {actual_target}"


def _check_source_table(expression: exp.Merge, source_table: str, dialect: str) -> None:
    """Verify the USING clause source table matches expected."""
    using = expression.args.get("using")
    if not using:
        raise AssertionError("Missing USING clause")

    # Strip alias for comparison
    if isinstance(using, exp.Table):
        using.set("alias", None)
    elif isinstance(using, exp.Alias):
        using = using.this

    actual_source = using.sql(dialect=dialect)
    expected_source = sqlglot.parse_one(source_table, read=dialect).sql(dialect=dialect)

    assert actual_source.replace("`", "") == expected_source.replace(
        "`", ""
    ), f"Source table mismatch. Expected {expected_source}, got {actual_source}"


def _check_on_clause(expression: exp.Merge, join_keys: List[str]) -> None:
    """Verify the ON clause contains expected join keys."""
    on_clause = expression.args.get("on")
    if not on_clause:
        raise AssertionError("Missing ON clause")

    # Collect all equality comparisons in the ON clause
    found_keys = set()

    for node in on_clause.find_all(exp.EQ):
        left = node.this
        right = node.expression

        left_col = _extract_column_name(left)
        right_col = _extract_column_name(right)

        # If both sides refer to the same column (typical join), add it
        if left_col and right_col and left_col == right_col:
            found_keys.add(left_col)

    for key in join_keys:
        assert (
            key in found_keys
        ), f"Join key '{key}' not found in ON clause equality conditions"


def _check_when_clauses(
    expression: exp.Merge,
    update_columns: Optional[List[str]],
    insert_columns: Optional[List[str]],
    dialect: str = "bigquery",
) -> None:
    """Verify the WHEN MATCHED and WHEN NOT MATCHED clauses."""
    whens = expression.args.get("whens")
    if not whens:
        raise AssertionError("Missing WHEN clauses")

    matched_found = False
    not_matched_found = False

    for when in whens:
        is_matched = when.args.get("matched")

        if is_matched:
            matched_found = True
            if update_columns:
                then = when.args.get("then")
                if not isinstance(then, exp.Update):
                    raise AssertionError("WHEN MATCHED should be UPDATE")

                # Check updated columns
                actual_updates = []
                for eq in then.expressions:
                    if isinstance(eq, exp.EQ):
                        col_name = _extract_column_name(eq.this)
                        if col_name:
                            actual_updates.append(col_name)

                actual_updates.sort()
                expected_updates = sorted(update_columns)
                assert (
                    actual_updates == expected_updates
                ), f"Update columns mismatch. Expected {expected_updates}, got {actual_updates}"

        else:
            # NOT MATCHED
            not_matched_found = True
            if insert_columns:
                then = when.args.get("then")
                if not isinstance(then, exp.Insert):
                    raise AssertionError("WHEN NOT MATCHED should be INSERT")

                # Check inserted columns and values
                actual_inserts = []
                actual_vals = []
                if hasattr(then, "this") and then.this:
                    cols = then.this.expressions
                    for col in cols:
                        col_name = _extract_column_name(col)
                        if col_name:
                            actual_inserts.append(col_name)

                if (
                    hasattr(then, "expression")
                    and then.expression
                    and isinstance(then.expression, exp.Values)
                ):
                    if then.expression.expressions:
                        # `then.expression.expressions` is a list of tuples (rows). Get the first row's values.
                        vals = then.expression.expressions[0].expressions
                        for val in vals:
                            actual_vals.append(val.sql(dialect=dialect))

                # Verify column list
                actual_inserts_sorted = sorted(actual_inserts)
                expected_inserts = sorted(insert_columns)
                assert (
                    actual_inserts_sorted == expected_inserts
                ), f"Insert columns mismatch. Expected {expected_inserts}, got {actual_inserts_sorted}"

                # Verify that each column has a corresponding S.column value
                # (BigQuery MERGE standard in our pipelines)
                for col, val in zip(actual_inserts, actual_vals):
                    expected_val = f"S.{col}"
                    # Normalize backticks for comparison
                    norm_val = val.replace("`", "")
                    norm_expected = expected_val.replace("`", "")
                    assert (
                        norm_val == norm_expected
                    ), f"Insert value mismatch for column {col}. Expected {expected_val}, got {val}"

    if update_columns and not matched_found:
        raise AssertionError("Expected WHEN MATCHED clause not found")

    if insert_columns and not not_matched_found:
        raise AssertionError("Expected WHEN NOT MATCHED clause not found")


def assert_merge_query_structure(
    sql: str,
    target_table: str,
    source_table: str,
    join_keys: List[str],
    update_columns: Optional[List[str]] = None,
    insert_columns: Optional[List[str]] = None,
    dialect: str = "bigquery",
) -> None:
    """
    Assert that a MERGE query has the correct structure and components.

    Args:
        sql: The generated SQL string.
        target_table: The expected target table name (or ID).
        source_table: The expected source table name (or ID).
        join_keys: List of column names used in the ON clause (e.g. ["id", "ds"]).
        update_columns: List of columns updated in WHEN MATCHED clause.
        insert_columns: List of columns inserted in WHEN NOT MATCHED clause.
        dialect: The SQL dialect to use.
    """
    expression = sqlglot.parse_one(sql, read=dialect)

    if not isinstance(expression, exp.Merge):
        raise AssertionError(f"Expected MERGE statement, got {type(expression)}")

    _check_target_table(expression, target_table, dialect)
    _check_source_table(expression, source_table, dialect)
    _check_on_clause(expression, join_keys)
    _check_when_clauses(expression, update_columns, insert_columns, dialect=dialect)
