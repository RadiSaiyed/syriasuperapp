from sqlalchemy import inspect, text


def test_schema_has_expected_columns():
    # Use the live engine from app
    from app.database import engine
    insp = inspect(engine)

    # merchants has fee_bps column
    cols = {c["name"]: c for c in insp.get_columns("merchants")}
    assert "fee_bps" in cols

    # qr_codes has non-nullable mode column
    qcols = {c["name"]: c for c in insp.get_columns("qr_codes")}
    assert "mode" in qcols and qcols["mode"]["nullable"] is False

    # payment_links table exists with core columns
    assert insp.has_table("payment_links")
    lcols = {c["name"]: c for c in insp.get_columns("payment_links")}
    for name in ("user_id", "code", "amount_cents", "mode", "status", "created_at"):
        assert name in lcols

    # subscriptions exists with next_charge_at
    assert insp.has_table("subscriptions")
    scols = {c["name"]: c for c in insp.get_columns("subscriptions")}
    assert "next_charge_at" in scols

