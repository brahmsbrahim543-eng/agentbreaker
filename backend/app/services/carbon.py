"""Carbon Impact Calculator -- converts compute metrics to environmental impact.

Based on published data:
- GPU power consumption: NVIDIA A100 (300W), H100 (700W)
- Token-to-kWh ratios derived from MLPerf benchmarks
- CO2 emission factors from IEA and EPA (2024 data)
- Equivalence factors from EPA GHG Equivalencies Calculator
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Token-to-kWh ratios per 1 000 tokens by model class
TOKEN_KWH_PER_1K: dict[str, float] = {
    "small": 0.0003,   # GPT-3.5, Haiku, Llama 7B
    "medium": 0.0008,  # GPT-4o-mini, Sonnet, Llama 70B
    "large": 0.002,    # GPT-4, Opus, Llama 405B
    "xl": 0.005,       # GPT-4 + tools + long context
}

# CO2 emission factors (kg CO2 per kWh) by cloud region
# Source: IEA Electricity Maps 2024
CO2_KG_PER_KWH: dict[str, float] = {
    "us-east": 0.39,     # Virginia -- natural gas heavy
    "us-west": 0.08,     # Oregon -- hydroelectric
    "eu-west": 0.23,     # Ireland -- mixed
    "eu-north": 0.01,    # Sweden -- nearly 100% renewable
    "asia-east": 0.45,   # Japan -- coal + gas
    "us-central": 0.42,  # Iowa -- coal heavy
    "eu-central": 0.30,  # Germany -- mixed
}

# Equivalence factors
TREE_CO2_ABSORPTION_KG_PER_YEAR: float = 22.0   # EPA: mature tree absorbs ~22 kg CO2/year
CAR_CO2_PER_KM_GRAMS: float = 120.0             # EU average passenger car
PHONE_CHARGE_CO2_GRAMS: float = 8.22            # EPA: full smartphone charge
NETFLIX_HOUR_CO2_GRAMS: float = 36.0            # IEA: 1 hour streaming

# Defaults
_DEFAULT_MODEL_CLASS = "large"
_DEFAULT_REGION = "us-east"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_kwh(tokens: int, model_class: str = _DEFAULT_MODEL_CLASS) -> float:
    """Convert token count to estimated kWh consumed.

    Parameters
    ----------
    tokens:
        Total number of tokens processed (input + output).
    model_class:
        One of ``"small"``, ``"medium"``, ``"large"``, ``"xl"``.
        Unknown values fall back to ``"large"``.

    Returns
    -------
    float
        Estimated energy consumption in kilowatt-hours.
    """
    if tokens <= 0:
        return 0.0
    ratio = TOKEN_KWH_PER_1K.get(model_class, TOKEN_KWH_PER_1K[_DEFAULT_MODEL_CLASS])
    return (tokens / 1000.0) * ratio


def calculate_co2_grams(kwh: float, region: str = _DEFAULT_REGION) -> float:
    """Convert kWh to CO2 grams based on cloud region.

    Parameters
    ----------
    kwh:
        Energy consumed in kilowatt-hours.
    region:
        Cloud-region key (e.g. ``"us-east"``).  Unknown regions fall back
        to ``"us-east"``.

    Returns
    -------
    float
        Estimated CO2 emissions in **grams**.
    """
    if kwh <= 0.0:
        return 0.0
    factor_kg = CO2_KG_PER_KWH.get(region, CO2_KG_PER_KWH[_DEFAULT_REGION])
    return kwh * factor_kg * 1000.0  # kg -> grams


def calculate_equivalences(co2_grams: float) -> dict:
    """Convert CO2 grams to human-readable equivalences.

    Parameters
    ----------
    co2_grams:
        Total CO2 in grams.

    Returns
    -------
    dict
        Keys: ``equivalent_trees``, ``equivalent_km_car``,
        ``equivalent_phone_charges``, ``equivalent_netflix_hours``.
    """
    if co2_grams <= 0.0:
        return {
            "equivalent_trees": 0.0,
            "equivalent_km_car": 0.0,
            "equivalent_phone_charges": 0.0,
            "equivalent_netflix_hours": 0.0,
        }

    co2_kg = co2_grams / 1000.0

    return {
        # How many tree-years of absorption this CO2 represents
        "equivalent_trees": co2_kg / TREE_CO2_ABSORPTION_KG_PER_YEAR,
        # Driving distance in km producing the same CO2
        "equivalent_km_car": co2_grams / CAR_CO2_PER_KM_GRAMS,
        # Number of full smartphone charges
        "equivalent_phone_charges": co2_grams / PHONE_CHARGE_CO2_GRAMS,
        # Hours of Netflix streaming
        "equivalent_netflix_hours": co2_grams / NETFLIX_HOUR_CO2_GRAMS,
    }


def estimate_avoided_impact(
    tokens_avoided: int,
    model_class: str = _DEFAULT_MODEL_CLASS,
    region: str = _DEFAULT_REGION,
) -> dict:
    """Full chain: tokens -> kWh -> CO2 -> equivalences for avoided compute.

    Parameters
    ----------
    tokens_avoided:
        Number of tokens that were *not* processed thanks to optimisation.
    model_class:
        Model size bucket (``"small"`` | ``"medium"`` | ``"large"`` | ``"xl"``).
    region:
        Cloud-region key for emission factor lookup.

    Returns
    -------
    dict
        Keys: ``kwh``, ``co2_grams``, ``equivalent_trees``,
        ``equivalent_km_car``, ``equivalent_phone_charges``.
    """
    kwh = calculate_kwh(tokens_avoided, model_class)
    co2 = calculate_co2_grams(kwh, region)
    eq = calculate_equivalences(co2)

    return {
        "kwh": kwh,
        "co2_grams": co2,
        "equivalent_trees": eq["equivalent_trees"],
        "equivalent_km_car": eq["equivalent_km_car"],
        "equivalent_phone_charges": eq["equivalent_phone_charges"],
    }


def infer_model_class(cost_per_1k_tokens: float) -> str:
    """Guess model class from price per 1 000 tokens.

    Thresholds (USD per 1 000 tokens):
    - < $0.002  -> ``"small"``
    - < $0.01   -> ``"medium"``
    - < $0.05   -> ``"large"``
    - >= $0.05  -> ``"xl"``

    Parameters
    ----------
    cost_per_1k_tokens:
        Price in USD for 1 000 tokens.

    Returns
    -------
    str
        One of ``"small"``, ``"medium"``, ``"large"``, ``"xl"``.
    """
    if cost_per_1k_tokens < 0.002:
        return "small"
    if cost_per_1k_tokens < 0.01:
        return "medium"
    if cost_per_1k_tokens < 0.05:
        return "large"
    return "xl"
