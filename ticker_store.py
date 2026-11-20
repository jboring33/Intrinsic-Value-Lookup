import copy
import json
from pathlib import Path

CONFIG_FILE = Path(__file__).resolve().parent / "tickers.json"

ASSET_CLASSES = (
    "Markets",
    "Covered Calls",
    "Dividends",
    "Foreign",
    "US Equities",
)

DEFAULT_VARIABLES: dict[str, dict] = {
    "Markets": {
        "valuation_mode": "benchmark_trend",
        "default_discount_rate": 0.08,
        "growth_spread_pct": 3.0,
        "min_growth_pct": -20.0,
        "max_growth_pct": 25.0,
        "use_exit_multiple": False,
        "default_exit_multiple": 1.0,
        "min_exit_multiple": 1.0,
        "max_exit_multiple": 1.0,
        "track_nav_spread": False,
        "max_realistic_cagr_pct": 15.0,
    },
    "Covered Calls": {
        "valuation_mode": "covered_call_income_total_return",
        "default_discount_rate": 0.075,
        "growth_spread_pct": 2.5,
        "min_growth_pct": -15.0,
        "max_growth_pct": 18.0,
        "use_exit_multiple": False,
        "default_exit_multiple": 1.0,
        "min_exit_multiple": 1.0,
        "max_exit_multiple": 1.0,
        "track_nav_spread": False,
        "max_realistic_cagr_pct": 14.0,
    },
    "Dividends": {
        "valuation_mode": "dividend_etf_total_return",
        "default_discount_rate": 0.075,
        "growth_spread_pct": 2.5,
        "min_growth_pct": -15.0,
        "max_growth_pct": 18.0,
        "use_exit_multiple": False,
        "default_exit_multiple": 1.0,
        "min_exit_multiple": 1.0,
        "max_exit_multiple": 1.0,
        "track_nav_spread": False,
        "max_realistic_cagr_pct": 13.0,
    },
    "Foreign": {
        "valuation_mode": "foreign_etf_total_return",
        "default_discount_rate": 0.085,
        "growth_spread_pct": 3.5,
        "min_growth_pct": -20.0,
        "max_growth_pct": 22.0,
        "use_exit_multiple": False,
        "default_exit_multiple": 1.0,
        "min_exit_multiple": 1.0,
        "max_exit_multiple": 1.0,
        "track_nav_spread": False,
        "max_realistic_cagr_pct": 15.0,
    },
    "US Equities": {
        "valuation_mode": "fundamental_dcf",
        "default_discount_rate": 0.09,
        "growth_spread_pct": 4.0,
        "min_growth_pct": -20.0,
        "max_growth_pct": 45.0,
        "use_exit_multiple": True,
        "default_exit_multiple": 20.0,
        "min_exit_multiple": 4.0,
        "max_exit_multiple": 60.0,
        "track_nav_spread": False,
        "max_realistic_cagr_pct": 20.0,
    },
}

DEFAULT_TICKERS: dict[str, list[str]] = {
    "Markets": ["VIX", "$DXY", "RSP", "DIA", "USO", "IWM", "SPY", "QQQ", "SMH"],
    "Covered Calls": ["JEPI", "SPYI", "JEPQ", "QQQI"],
    "Dividends": ["HDV", "SCHD"],
    "Foreign": ["SCHY", "SDIV", "DIVI", "VEA", "EMXC"],
    "US Equities": ["COST", "BRK/B", "AAPL", "SPCX", "NVDA", "CRWV", "GOOGL", "SNDK"],
}

YF_SYMBOL_OVERRIDES: dict[str, str] = {
    "$DXY": "DX-Y.NYB",
    "DXY": "DX-Y.NYB",
    "VIX": "^VIX",
    "^VIX": "^VIX",
    "BRK/B": "BRK-B",
}


def to_yf_symbol(display_symbol: str) -> str:
    """Converts display/config symbols like '$DXY', 'VIX', or 'BRK/B' into yfinance symbols."""
    cleaned = display_symbol.strip().upper()
    if cleaned in YF_SYMBOL_OVERRIDES:
        return YF_SYMBOL_OVERRIDES[cleaned]
    return cleaned.replace("/", "-")


def _clean_tickers(items: list) -> list[str]:
    out: list[str] = []
    for item in items:
        sym = str(item).strip().upper()
        if sym and sym not in out:
            out.append(sym)
    return out


def default_config() -> dict[str, dict]:
    return {
        cls: {
            "tickers": list(DEFAULT_TICKERS[cls]),
            "variables": copy.deepcopy(DEFAULT_VARIABLES[cls]),
        }
        for cls in ASSET_CLASSES
    }


def load_config(file_path: Path = CONFIG_FILE) -> dict[str, dict]:
    """Loads asset classes, tickers, and per-class variables from tickers.json."""
    base = default_config()
    if not file_path.exists():
        save_config(base, file_path)
        return base

    raw = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return base

    for cls in ASSET_CLASSES:
        section = raw.get(cls)
        if isinstance(section, dict):
            if isinstance(section.get("tickers"), list):
                base[cls]["tickers"] = _clean_tickers(section["tickers"])
            if isinstance(section.get("variables"), dict):
                base[cls]["variables"].update(section["variables"])
    return base


def save_config(config: dict[str, dict], file_path: Path = CONFIG_FILE) -> dict[str, dict]:
    """Saves normalized config to tickers.json."""
    normalized = default_config()
    for cls in ASSET_CLASSES:
        section = config.get(cls, {})
        normalized[cls]["tickers"] = _clean_tickers(section.get("tickers", []))
        vars_update = section.get("variables", {})
        if isinstance(vars_update, dict):
            normalized[cls]["variables"].update(vars_update)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return normalized


def add_ticker(asset_class: str, symbol: str, file_path: Path = CONFIG_FILE) -> dict[str, dict]:
    """Adds a ticker to a single asset class (removing duplicates from other classes)."""
    if asset_class not in ASSET_CLASSES:
        raise ValueError(f"Unknown asset class '{asset_class}'. Expected one of {ASSET_CLASSES}.")
    sym = symbol.strip().upper()
    cfg = load_config(file_path)
    if not sym:
        return cfg
    for cls in ASSET_CLASSES:
        cfg[cls]["tickers"] = [t for t in cfg[cls]["tickers"] if t != sym]
    cfg[asset_class]["tickers"].append(sym)
    return save_config(cfg, file_path)


def remove_ticker(symbol: str, asset_class: str | None = None, file_path: Path = CONFIG_FILE) -> dict[str, dict]:
    """Removes a ticker from one asset class or across all five."""
    sym = symbol.strip().upper()
    cfg = load_config(file_path)
    targets = (asset_class,) if asset_class in ASSET_CLASSES else ASSET_CLASSES
    for cls in targets:
        cfg[cls]["tickers"] = [t for t in cfg[cls]["tickers"] if t != sym]
    return save_config(cfg, file_path)


def update_class_variables(asset_class: str, updates: dict, file_path: Path = CONFIG_FILE) -> dict[str, dict]:
    """Updates one or more variables for a specific asset class and saves to tickers.json."""
    if asset_class not in ASSET_CLASSES:
        raise ValueError(f"Unknown asset class '{asset_class}'. Expected one of {ASSET_CLASSES}.")
    cfg = load_config(file_path)
    cfg[asset_class]["variables"].update(updates)
    return save_config(cfg, file_path)
