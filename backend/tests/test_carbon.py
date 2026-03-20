"""Tests for the Carbon Impact Calculator."""

import pytest

from app.services.carbon import (
    calculate_co2_grams,
    calculate_equivalences,
    calculate_kwh,
    estimate_avoided_impact,
    infer_model_class,
)


# ---------------------------------------------------------------------------
# calculate_kwh
# ---------------------------------------------------------------------------


def test_kwh_from_tokens_large():
    result = calculate_kwh(1000, "large")
    assert result == pytest.approx(0.002, rel=0.01)


def test_kwh_from_tokens_small():
    result = calculate_kwh(1000, "small")
    assert result == pytest.approx(0.0003, rel=0.01)


def test_kwh_zero_tokens():
    assert calculate_kwh(0) == 0.0


def test_kwh_negative_tokens():
    assert calculate_kwh(-500) == 0.0


def test_kwh_unknown_model_defaults_to_large():
    result = calculate_kwh(1000, "unknown-model")
    assert result == calculate_kwh(1000, "large")


# ---------------------------------------------------------------------------
# calculate_co2_grams
# ---------------------------------------------------------------------------


def test_co2_us_east():
    result = calculate_co2_grams(1.0, "us-east")
    assert 380 < result < 400


def test_co2_eu_north():
    result = calculate_co2_grams(1.0, "eu-north")
    assert result < 15  # Nearly all renewable


def test_co2_unknown_region_defaults():
    result = calculate_co2_grams(1.0, "unknown-region")
    assert result == calculate_co2_grams(1.0, "us-east")


def test_co2_zero_kwh():
    assert calculate_co2_grams(0.0) == 0.0


def test_co2_negative_kwh():
    assert calculate_co2_grams(-1.0) == 0.0


# ---------------------------------------------------------------------------
# calculate_equivalences
# ---------------------------------------------------------------------------


def test_equivalences_positive():
    eq = calculate_equivalences(1000)
    assert eq["equivalent_trees"] > 0
    assert eq["equivalent_km_car"] > 0
    assert eq["equivalent_phone_charges"] > 0
    assert eq["equivalent_netflix_hours"] > 0


def test_equivalences_zero():
    eq = calculate_equivalences(0)
    assert eq["equivalent_trees"] == 0
    assert eq["equivalent_km_car"] == 0
    assert eq["equivalent_phone_charges"] == 0
    assert eq["equivalent_netflix_hours"] == 0


def test_equivalences_negative():
    eq = calculate_equivalences(-100)
    assert eq["equivalent_trees"] == 0.0


# ---------------------------------------------------------------------------
# estimate_avoided_impact
# ---------------------------------------------------------------------------


def test_avoided_impact_full_chain():
    result = estimate_avoided_impact(10000, "large", "us-east")
    assert result["kwh"] > 0
    assert result["co2_grams"] > 0
    assert result["equivalent_phone_charges"] > 0
    assert result["equivalent_trees"] > 0
    assert result["equivalent_km_car"] > 0


def test_avoided_impact_zero_tokens():
    result = estimate_avoided_impact(0)
    assert result["kwh"] == 0.0
    assert result["co2_grams"] == 0.0


# ---------------------------------------------------------------------------
# infer_model_class
# ---------------------------------------------------------------------------


def test_infer_model_class():
    assert infer_model_class(0.001) == "small"
    assert infer_model_class(0.005) == "medium"
    assert infer_model_class(0.03) == "large"
    assert infer_model_class(0.08) == "xl"


def test_infer_model_class_boundaries():
    assert infer_model_class(0.002) == "medium"   # exactly at boundary -> medium
    assert infer_model_class(0.01) == "large"      # exactly at boundary -> large
    assert infer_model_class(0.05) == "xl"         # exactly at boundary -> xl
