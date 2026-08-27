import great_expectations as gx


def create_nasdaq_suite():
    # 1. Initialize Context
    context = gx.get_context()

    # 2. Setup Data Asset
    datasource_name = "nasdaq_datasource"
    asset_name = "nasdaq_stock_data"

    datasource = context.get_datasource(datasource_name)

    try:
        asset = datasource.get_asset(asset_name)
    except Exception:
        asset = datasource.add_table_asset(
            name=asset_name,
            table_name="prices"
        )

    # 3. Batch Request
    batch_request = asset.build_batch_request()

    # 4. Ensure Suite Exists
    suite_name = "nasdaq_suite"

    try:
        context.get_expectation_suite(suite_name)
    except Exception:
        context.add_expectation_suite(expectation_suite_name=suite_name)

    # 5. Validator
    validator = context.get_validator(
        batch_request=batch_request,
        expectation_suite_name=suite_name
    )

    # Optional but recommended: clear old expectations (avoids duplicates)
    validator.expectation_suite.expectations = []

    # ─────────────────────────────────────────────
    # EXPECTATIONS
    # ─────────────────────────────────────────────

    # NULL CHECKS
    columns = ["symbol", "date", "open", "high", "low", "close", "volume"]
    for col in columns:
        validator.expect_column_values_to_not_be_null(column=col)

    # SYMBOL FORMAT
    validator.expect_column_values_to_match_regex(
        column="symbol",
        regex=r"^[A-Z]{1,5}$"
    )

    # OHLC INTEGRITY (SUPPORTED GX METHODS)

    # high >= low
    validator.expect_column_pair_values_A_to_be_greater_than_B(
        column_A="high",
        column_B="low",
        or_equal=True
    )

    # high >= open
    validator.expect_column_pair_values_A_to_be_greater_than_B(
        column_A="high",
        column_B="open",
        or_equal=True
    )

    # high >= close
    validator.expect_column_pair_values_A_to_be_greater_than_B(
        column_A="high",
        column_B="close",
        or_equal=True
    )

    # open >= low
    validator.expect_column_pair_values_A_to_be_greater_than_B(
        column_A="open",
        column_B="low",
        or_equal=True
    )

    # close >= low
    validator.expect_column_pair_values_A_to_be_greater_than_B(
        column_A="close",
        column_B="low",
        or_equal=True
    )

    # UNIQUENESS
    validator.expect_compound_columns_to_be_unique(
        column_list=["symbol", "date"]
    )

    # 6. Save
    validator.save_expectation_suite(discard_failed_expectations=False)

    print(f"✅ Successfully created/updated suite: {suite_name}")
    return "Suite created successfully"


if __name__ == "__main__":
    create_nasdaq_suite()