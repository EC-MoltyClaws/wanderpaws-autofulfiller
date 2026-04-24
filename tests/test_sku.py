"""
SKU System — Behavioural Spec
==============================
These tests define the expected behaviour of the two-phase SKU system.
They are the source of truth. Implementation must satisfy these tests.

Phase 1 — expand_sku(pseudo_sku, qty)
    Maps a single Shopify pseudo SKU + quantity to a list of display strings,
    one per actual fulfilled product.

Phase 2 — build_lineitem_name(order)
    Collates all expanded SKUs across an order's line items into one string.
"""

import pytest

from scripts.generate_report import build_lineitem_name, expand_sku


# ─── Helpers ──────────────────────────────────────────────────────────────────


def order(items: list[tuple[str, int]]) -> dict:
    """Build a minimal order dict from a list of (pseudo_sku, qty) tuples."""
    return {
        "lineItems": [
            {"sku": sku, "quantity": qty}
            for sku, qty in items
        ]
    }


# ─── expand_sku: harness (bundle — expands to harness + leash) ───────────────


def test_harness_black_xs():
    assert expand_sku("harness-black-xs", 1) == ["1x Harness-Black/XS", "1x Leash-Black"]


def test_harness_blue_s():
    assert expand_sku("harness-blue-s", 1) == ["1x Harness-Blue/S", "1x Leash-Blue"]


def test_harness_pink_m():
    assert expand_sku("harness-pink-m", 1) == ["1x Harness-Pink/M", "1x Leash-Pink"]


def test_harness_qty_applied_to_all_products_in_bundle():
    assert expand_sku("harness-black-xs", 2) == ["2x Harness-Black/XS", "2x Leash-Black"]


# ─── expand_sku: sip cup ──────────────────────────────────────────────────────


def test_sipcup_blue():
    assert expand_sku("sipcup-blue", 1) == ["1x Food and Water Dispensor-Blue"]


def test_sipcup_red():
    assert expand_sku("sipcup-red", 1) == ["1x Food and Water Dispensor-Red"]


def test_sipcup_qty_applied():
    assert expand_sku("sipcup-blue", 3) == ["3x Food and Water Dispensor-Blue"]


# ─── expand_sku: retractable leash ───────────────────────────────────────────


def test_retractable_leash():
    assert expand_sku("retractableleash", 1) == ["1x Retractable Leash"]


# ─── expand_sku: trackers ─────────────────────────────────────────────────────


def test_tracker_apple():
    assert expand_sku("generic-tracker-apple", 1) == ["1x Tracker-Apple"]


def test_tracker_android():
    assert expand_sku("generic-tracker-android", 1) == ["1x Tracker-Android"]


# ─── expand_sku: skip SKUs (return empty list) ───────────────────────────────


def test_freeleashupgrade_skipped():
    assert expand_sku("freeleashupgrade", 1) == []


def test_freepriorityshipping_skipped():
    assert expand_sku("freepriorityshipping", 1) == []


def test_freewarranty_skipped():
    assert expand_sku("freewarranty", 1) == []


def test_guide30_skipped():
    assert expand_sku("guide30", 1) == []


def test_guide7_skipped():
    assert expand_sku("guide7", 1) == []


def test_nonfulfil_shipping_skipped():
    assert expand_sku("nonfulfil-shipping", 1) == []


def test_defaultleash_black_skipped():
    assert expand_sku("defaultleash-black", 1) == []


def test_defaultleash_blue_skipped():
    assert expand_sku("defaultleash-blue", 1) == []


def test_defaultleash_pink_skipped():
    assert expand_sku("defaultleash-pink", 1) == []


def test_defaultleash_orange_skipped():
    assert expand_sku("defaultleash-orange", 1) == []


def test_defaultleash_yellow_skipped():
    assert expand_sku("defaultleash-yellow", 1) == []


def test_defaultleash_purple_skipped():
    assert expand_sku("defaultleash-purple", 1) == []


def test_defaultleash_red_skipped():
    assert expand_sku("defaultleash-red", 1) == []


# ─── expand_sku: unknown SKU raises ValueError ───────────────────────────────


def test_unknown_sku_raises_value_error():
    with pytest.raises(ValueError):
        expand_sku("bogus-sku-xyz", 1)


def test_unknown_sku_error_message_contains_the_sku():
    with pytest.raises(ValueError, match="bogus-sku-xyz"):
        expand_sku("bogus-sku-xyz", 1)


# ─── build_lineitem_name: single line item ────────────────────────────────────


def test_single_harness_order():
    assert build_lineitem_name(order([("harness-black-xs", 1)])) == (
        "1x Harness-Black/XS, 1x Leash-Black"
    )


def test_single_sipcup_order():
    assert build_lineitem_name(order([("sipcup-blue", 1)])) == (
        "1x Food and Water Dispensor-Blue"
    )


# ─── build_lineitem_name: multiple line items ─────────────────────────────────


def test_harness_and_retractable_leash():
    assert build_lineitem_name(order([
        ("harness-black-xs", 1),
        ("retractableleash", 1),
    ])) == "1x Harness-Black/XS, 1x Leash-Black, 1x Retractable Leash"


def test_multiple_quantities():
    assert build_lineitem_name(order([
        ("harness-black-xs", 2),
        ("retractableleash", 1),
    ])) == "2x Harness-Black/XS, 2x Leash-Black, 1x Retractable Leash"

def test_multiple_quantities_collation():
    assert build_lineitem_name(order([
        ("harness-black-xs", 1),
        ("harness-black-m", 1),
        ("retractableleash", 1),
    ])) == "1x Harness-Black/XS, 1x Harness-Black/M, 2x Leash-Black, 1x Retractable Leash"


# ─── build_lineitem_name: skip SKUs are excluded ─────────────────────────────


def test_skip_sku_excluded_from_lineitem_name():
    assert build_lineitem_name(order([
        ("harness-black-xs", 1),
        ("freeleashupgrade", 1),
    ])) == "1x Harness-Black/XS, 1x Leash-Black"


def test_multiple_skip_skus_all_excluded():
    assert build_lineitem_name(order([
        ("harness-black-xs", 1),
        ("freeleashupgrade", 1),
        ("freepriorityshipping", 1),
        ("nonfulfil-shipping", 1),
    ])) == "1x Harness-Black/XS, 1x Leash-Black"


# ─── build_lineitem_name: unknown SKU raises ─────────────────────────────────


def test_unknown_sku_in_order_raises():
    with pytest.raises(ValueError, match="bogus-sku-xyz"):
        build_lineitem_name(order([("bogus-sku-xyz", 1)]))


def test_unknown_sku_mixed_with_valid_still_raises():
    with pytest.raises(ValueError):
        build_lineitem_name(order([
            ("harness-black-xs", 1),
            ("bogus-sku-xyz", 1),
        ]))
