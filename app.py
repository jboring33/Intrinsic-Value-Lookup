import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Universal Asset Valuation & Intrinsic Value Model",
    page_icon="📈",
    layout="wide",
)

PHYSICAL_METALS_TICKERS = {
    "PHYS": ("Gold", "Sprott Physical Gold Trust"),
    "PSLV": ("Silver", "Sprott Physical Silver Trust"),
    "CEF": ("Gold & Silver", "Sprott Physical Gold and Silver Trust"),
    "SPPP": ("Platinum & Palladium", "Sprott Physical Platinum and Palladium Trust"),
    "GLD": ("Gold", "SPDR Gold Shares"),
    "GLDM": ("Gold", "SPDR Gold MiniShares Trust"),
    "IAU": ("Gold", "iShares Gold Trust"),
    "IAUM": ("Gold", "iShares Gold Trust Micro"),
    "SGOL": ("Gold", "abrdn Physical Gold Shares ETF"),
    "BAR": ("Gold", "GraniteShares Gold Trust"),
    "AAAU": ("Gold", "Goldman Sachs Physical Gold ETF"),
    "OUNZ": ("Gold", "VanEck Merk Gold ETF"),
    "SLV": ("Silver", "iShares Silver Trust"),
    "SIVR": ("Silver", "abrdn Physical Silver Shares ETF"),
    "PPLT": ("Platinum", "abrdn Physical Platinum Shares ETF"),
    "PALL": ("Palladium", "abrdn Physical Palladium Shares ETF"),
    "CPER": ("Copper", "United States Copper Index Fund"),
    "U.UN": ("Uranium", "Sprott Physical Uranium Trust"),
    "SRUUF": ("Uranium", "Sprott Physical Uranium Trust"),
}

MINING_KEYWORDS = (
    "gold",
    "silver",
    "precious metals",
    "metals & mining",
    "copper",
    "uranium",
    "platinum",
    "palladium",
    "miners",
    "mining",
)


def clamp(val: float, low: float, high: float) -> float:
    return max(low, min(float(val), high))


def classify_asset(ticker_symbol: str, info: dict) -> tuple[str, str]:
    """
    Classifies a ticker into one of:
    - Physical Bullion / Commodity Trust
    - Metals & Mining ETF
    - Metals & Mining Stock
    - Equity / Income ETF
    - Fund / Bond
    - Stock
    Returns (asset_class, metal_focus).
    """
    sym = ticker_symbol.upper().strip()
    quote_type = (info.get("quoteType") or "EQUITY").upper()
    name = (info.get("longName") or info.get("shortName") or "").lower()
    summary = (info.get("longBusinessSummary") or "").lower()
    industry = (info.get("industry") or "").lower()
    category = (info.get("category") or "").lower()

    if sym in PHYSICAL_METALS_TICKERS:
        return "Physical Bullion / Commodity Trust", PHYSICAL_METALS_TICKERS[sym][0]

    if (
        any(
            k in name
            for k in (
                "physical gold",
                "physical silver",
                "physical platinum",
                "physical palladium",
                "gold trust",
                "silver trust",
                "gold shares",
                "silver shares",
            )
        )
        and "miner" not in name
    ):
        metal = "Silver" if "silver" in name else ("Gold" if "gold" in name else "Precious Metals")
        return "Physical Bullion / Commodity Trust", metal

    is_metals_related = any(
        kw in text
        for kw in MINING_KEYWORDS
        for text in (name, industry, category, summary[:400])
    )

    if quote_type == "ETF":
        if is_metals_related:
            return "Metals & Mining ETF", "Metals & Mining"
        return "Equity / Income ETF", ""

    if quote_type in ("MUTUALFUND", "MONEYMARKET"):
        return "Fund / Bond", ""

    if is_metals_related:
        return "Metals & Mining Stock", industry.title() if industry else "Metals & Mining"

    return "Stock", ""


def fetch_current_price(ticker: yf.Ticker, info: dict) -> float:
    """Fetches current market price; raises ValueError if symbol is invalid/unpriced."""
    for key in ("currentPrice", "regularMarketPrice", "previousClose", "navPrice"):
        val = info.get(key)
        if val is not None and float(val) > 0:
            return float(val)

    hist = ticker.history(period="5d", auto_adjust=False)
    if not hist.empty and float(hist["Close"].iloc[-1]) > 0:
        return float(hist["Close"].iloc[-1])

    raise ValueError(f"No valid market price found for '{ticker.ticker}'. Check the ticker symbol.")


def compute_historical_cagr(ticker: yf.Ticker, years: int = 5, auto_adjust: bool = True) -> float | None:
    """Computes annualized return over `years` using adjusted close (total return) or unadjusted close."""
    try:
        hist = ticker.history(period=f"{years}y", auto_adjust=auto_adjust)
        if len(hist) >= 200:
            start_px = float(hist["Close"].iloc[0])
            end_px = float(hist["Close"].iloc[-1])
            actual_years = len(hist) / 252.0
            if start_px > 0 and actual_years > 0.5:
                return (end_px / start_px) ** (1.0 / actual_years) - 1.0
    except Exception:
        pass
    return None


def get_calibrated_inputs(ticker_symbol: str) -> dict:
    """Fetches yfinance data and calibrates realistic baseline inputs per asset class."""
    ticker = yf.Ticker(ticker_symbol)
    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    current_price = fetch_current_price(ticker, info)
    asset_class, metal_focus = classify_asset(ticker_symbol, info)

    nav_price = info.get("navPrice")
    nav_price = float(nav_price) if nav_price and float(nav_price) > 0 else None

    trailing_pe = info.get("trailingPE")
    trailing_pe = float(trailing_pe) if trailing_pe and float(trailing_pe) > 0 else None

    forward_pe = info.get("forwardPE")
    forward_pe = float(forward_pe) if forward_pe and float(forward_pe) > 0 else None

    trailing_eps = info.get("trailingEps")
    trailing_eps = float(trailing_eps) if trailing_eps is not None else None

    forward_eps = info.get("forwardEps")
    forward_eps = float(forward_eps) if forward_eps is not None else None

    if trailing_eps is None and trailing_pe:
        trailing_eps = current_price / trailing_pe
    if forward_eps is None and forward_pe:
        forward_eps = current_price / forward_pe

    rev_per_share = info.get("revenuePerShare")
    rev_per_share = float(rev_per_share) if rev_per_share and float(rev_per_share) > 0 else None
    ps_ratio = info.get("priceToSalesTrailing12Months")
    ps_ratio = float(ps_ratio) if ps_ratio and float(ps_ratio) > 0 else None

    div_yield = info.get("dividendYield") or info.get("yield") or 0.0
    div_yield = float(div_yield)
    if div_yield > 0.25:
        div_yield = div_yield / 100.0
    div_yield = clamp(div_yield, 0.0, 0.20)

    hist_cagr_5y = compute_historical_cagr(ticker, years=5, auto_adjust=True)

    if asset_class == "Physical Bullion / Commodity Trust":
        raw_growth = 0.05 if hist_cagr_5y is None else clamp(0.5 * hist_cagr_5y + 0.5 * 0.05, 0.02, 0.10)
        exit_multiple = 1.0
        valuation_basis = "NAV Premium/Discount + Spot Drift"

    elif asset_class in ("Equity / Income ETF", "Metals & Mining ETF"):
        long_run_anchor = 0.07 if asset_class == "Metals & Mining ETF" else 0.08
        if hist_cagr_5y is not None:
            raw_growth = 0.4 * hist_cagr_5y + 0.6 * long_run_anchor
        else:
            raw_growth = long_run_anchor
        raw_growth = clamp(raw_growth, -0.05, 0.14)
        exit_multiple = trailing_pe or 18.0
        valuation_basis = "Total-Return CAGR Discounted Model"

    elif asset_class == "Fund / Bond":
        raw_growth = clamp(div_yield if div_yield > 0 else (hist_cagr_5y or 0.045), 0.01, 0.10)
        exit_multiple = 1.0
        valuation_basis = "Yield & NAV Compounding"

    else:
        raw_eg = info.get("earningsGrowth")
        raw_rg = info.get("revenueGrowth")
        candidates = [float(x) for x in (raw_eg, raw_rg) if x is not None and -0.5 < float(x) < 1.0]
        if candidates:
            blended_g = np.mean(candidates)
            raw_growth = 0.6 * blended_g + 0.4 * 0.08
        elif hist_cagr_5y is not None:
            raw_growth = clamp(hist_cagr_5y, 0.02, 0.15)
        else:
            raw_growth = 0.08

        max_g = 0.15 if asset_class == "Metals & Mining Stock" else 0.22
        raw_growth = clamp(raw_growth, -0.10, max_g)

        base_pe = forward_pe or trailing_pe or (14.0 if asset_class == "Metals & Mining Stock" else 18.0)
        max_pe = 30.0 if asset_class == "Metals & Mining Stock" else 45.0
        exit_multiple = clamp(base_pe, 5.0, max_pe)

        if (forward_eps and forward_eps > 0) or (trailing_eps and trailing_eps > 0):
            valuation_basis = "EPS × Exit P/E + Dividends (DCF)"
        elif rev_per_share and rev_per_share > 0:
            valuation_basis = "Revenue/Share × Exit P/S (DCF)"
            exit_multiple = clamp(ps_ratio or 2.5, 0.5, 15.0)
        else:
            valuation_basis = "Price-Anchored Fallback (Missing EPS/Rev)"

    return {
        "ticker": ticker_symbol.upper(),
        "long_name": info.get("longName") or info.get("shortName") or ticker_symbol.upper(),
        "asset_class": asset_class,
        "metal_focus": metal_focus,
        "valuation_basis": valuation_basis,
        "current_price": current_price,
        "nav_price": nav_price,
        "growth_rate": float(raw_growth),
        "exit_multiple": float(exit_multiple),
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "trailing_eps": trailing_eps,
        "forward_eps": forward_eps,
        "rev_per_share": rev_per_share,
        "ps_ratio": ps_ratio,
        "div_yield": div_yield,
        "hist_cagr_5y": hist_cagr_5y,
        "raw_info_subset": {
            "quoteType": info.get("quoteType"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "category": info.get("category"),
            "currentPrice": current_price,
            "navPrice": nav_price,
            "trailingEps": trailing_eps,
            "forwardEps": forward_eps,
            "trailingPE": trailing_pe,
            "forwardPE": forward_pe,
            "revenuePerShare": rev_per_share,
            "dividendYield": round(div_yield * 100, 2),
            "5Y_TotalReturn_CAGR_%": round(hist_cagr_5y * 100, 2) if hist_cagr_5y is not None else None,
        },
    }


def calculate_scenario_valuation(
    data: dict,
    growth_rate: float,
    exit_multiple: float,
    proj_years: int,
    discount_rate: float,
) -> dict:
    """
    Calculates projected target price, present value of interim dividends, and intrinsic value.
    """
    init_price = data["current_price"]
    asset_class = data["asset_class"]
    div_yield = data["div_yield"]

    pv_dividends = 0.0
    if div_yield > 0:
        d0 = init_price * div_yield
        for y in range(1, proj_years + 1):
            dy = d0 * ((1.0 + growth_rate) ** y)
            pv_dividends += dy / ((1.0 + discount_rate) ** y)

    if asset_class in ("Stock", "Metals & Mining Stock"):
        anchor_eps = data["forward_eps"] if (data["forward_eps"] and data["forward_eps"] > 0) else data["trailing_eps"]
        if anchor_eps and anchor_eps > 0:
            future_eps = anchor_eps * ((1.0 + growth_rate) ** proj_years)
            target_price = future_eps * exit_multiple
        elif data["rev_per_share"] and data["rev_per_share"] > 0:
            future_rev = data["rev_per_share"] * ((1.0 + growth_rate) ** proj_years)
            target_price = future_rev * exit_multiple
        else:
            target_price = init_price * ((1.0 + growth_rate) ** proj_years)
    elif asset_class == "Physical Bullion / Commodity Trust":
        base_anchor = data["nav_price"] if data["nav_price"] else init_price
        target_price = base_anchor * ((1.0 + growth_rate) ** proj_years)
    else:
        target_price = init_price * ((1.0 + growth_rate) ** proj_years)

    pv_terminal = target_price / ((1.0 + discount_rate) ** proj_years)
    intrinsic_value = pv_terminal + pv_dividends

    total_value_at_horizon = target_price + sum(
        (init_price * div_yield) * ((1.0 + growth_rate) ** y) for y in range(1, proj_years + 1)
    )
    cagr = (((total_value_at_horizon / init_price) ** (1.0 / proj_years)) - 1.0) * 100.0

    return {
        "target_price": target_price,
        "pv_dividends": pv_dividends,
        "intrinsic_value": intrinsic_value,
        "cagr": cagr,
    }


def get_actionable_signal(
    current_price: float,
    intrinsic_value: float,
    nav_spread_pct: float | None = None,
) -> tuple[str, str, float]:
    """Generates Buy/Hold/Sell signal based on Margin of Safety (or NAV discount for physical trusts)."""
    if nav_spread_pct is not None:
        if nav_spread_pct <= -3.0:
            return "🟢 TRADING AT SIGNIFICANT DISCOUNT TO NAV", "success", -nav_spread_pct
        elif -3.0 < nav_spread_pct <= -1.0:
            return "🟢 MODEST DISCOUNT TO NAV", "success", -nav_spread_pct
        elif -1.0 < nav_spread_pct <= 1.5:
            return "🟡 TRADING NEAR FAIR NAV PARITY", "warning", -nav_spread_pct
        else:
            return "🔴 TRADING AT PREMIUM OVER NAV", "error", -nav_spread_pct

    upside = ((intrinsic_value - current_price) / current_price) * 100.0
    if upside >= 15.0:
        return "🟢 BUY (STRONG MARGIN OF SAFETY)", "success", upside
    elif 5.0 <= upside < 15.0:
        return "🟢 ACCUMULATE / MODERATE BUY", "success", upside
    elif -10.0 <= upside < 5.0:
        return "🟡 HOLD / FAIRLY VALUED", "warning", upside
    elif -25.0 <= upside < -10.0:
        return "🟠 TRIM / OVERVALUED", "warning", upside
    else:
        return "🔴 SELL / SIGNIFICANT OVERVALUATION", "error", upside


# --- STREAMLIT UI ---

st.title("📊 Universal Asset Valuation & Intrinsic Value Model")
st.markdown(
    "Fundamental DCF for **Stocks**, Total-Return Modeling for **ETFs**, "
    "and **NAV Discount / Spot Analysis** for **Physical Metals & Miners**."
)

col_search, col_examples = st.columns([1, 2])
with col_search:
    ticker_input = st.text_input("Enter Stock, ETF, or Metals Ticker:", value="AAPL").strip().upper()
with col_examples:
    st.caption(
        "Examples: `AAPL`, `MSFT` (Stocks) • `SCHD`, `SPYI`, `QQQ` (ETFs) • "
        "`PHYS`, `PSLV`, `GLD`, `IAU`, `SLV` (Physical Metals) • `NEM`, `GDX`, `SILJ` (Miners)"
    )

if ticker_input:
    try:
        with st.spinner(f"Fetching & calibrating {ticker_input}..."):
            data = get_calibrated_inputs(ticker_input)

        asset_class = data["asset_class"]
        init_price = data["current_price"]
        nav_price = data["nav_price"]

        st.subheader(f"{data['long_name']} ({ticker_input})")
        badge_text = f"Asset Class: **{asset_class}**"
        if data["metal_focus"]:
            badge_text += f" ({data['metal_focus']})"
        badge_text += f" | Method: **{data['valuation_basis']}**"
        st.caption(badge_text)

        st.sidebar.header("⚙️ Model Parameters")
        proj_years = st.sidebar.slider("Projection Horizon (Years)", 1, 15, 5)
        default_disc = 7.0 if asset_class == "Physical Bullion / Commodity Trust" else 9.0
        discount_rate = st.sidebar.slider("Discount Rate / Required Return (%)", 4.0, 15.0, default_disc, step=0.5) / 100.0

        base_growth_pct = round(data["growth_rate"] * 100.0, 2)
        spread = 3.0 if asset_class in ("Physical Bullion / Commodity Trust", "Equity / Income ETF", "Fund / Bond") else 4.0

        default_low = clamp(round(base_growth_pct - spread, 2), -20.0, 30.0)
        default_med = clamp(base_growth_pct, -20.0, 40.0)
        default_high = clamp(round(base_growth_pct + spread, 2), -20.0, 50.0)

        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Scenario Calibrations")
        growth_label = "Spot Appreciation" if asset_class == "Physical Bullion / Commodity Trust" else "Annual Growth"

        growth_low = st.sidebar.slider(f"Low {growth_label} (%)", -20.0, 30.0, float(default_low), step=0.5) / 100.0
        growth_med = st.sidebar.slider(f"Base {growth_label} (%)", -20.0, 40.0, float(default_med), step=0.5) / 100.0
        growth_high = st.sidebar.slider(f"High {growth_label} (%)", -20.0, 50.0, float(default_high), step=0.5) / 100.0

        if asset_class in ("Stock", "Metals & Mining Stock") and (data["forward_eps"] or data["trailing_eps"]):
            base_mult = round(data["exit_multiple"], 1)
            mult_low = st.sidebar.slider("Low Exit P/E", 4.0, 50.0, float(clamp(round(base_mult * 0.8, 1), 4.0, 50.0)), step=0.5)
            mult_med = st.sidebar.slider("Base Exit P/E", 4.0, 60.0, float(clamp(base_mult, 4.0, 60.0)), step=0.5)
            mult_high = st.sidebar.slider("High Exit P/E", 4.0, 70.0, float(clamp(round(base_mult * 1.2, 1), 4.0, 70.0)), step=0.5)
        else:
            mult_low = mult_med = mult_high = data["exit_multiple"]

        nav_spread_pct = None
        if asset_class == "Physical Bullion / Commodity Trust":
            st.write("### 🪙 Physical Bullion NAV & Premium/Discount Check")
            if nav_price:
                nav_spread_pct = ((init_price - nav_price) / nav_price) * 100.0
                n1, n2, n3 = st.columns(3)
                n1.metric("Market Price", f"${init_price:,.2f}")
                n2.metric("Underlying Metal NAV", f"${nav_price:,.2f}")
                n3.metric(
                    "Premium / Discount to NAV",
                    f"{nav_spread_pct:+.2f}%",
                    delta="Discount (Fear)" if nav_spread_pct < 0 else "Premium",
                    delta_color="normal" if nav_spread_pct < 0 else "inverse",
                )
            else:
                st.info(
                    f"`yfinance` did not return a live `navPrice` for **{ticker_input}**. "
                    "For Sprott trusts (`PHYS`, `PSLV`, `CEF`), verify the live NAV spread directly on Sprott.com or CEFConnect."
                )

        scenarios = {
            "Low Case": calculate_scenario_valuation(data, growth_low, mult_low, proj_years, discount_rate),
            "Medium (Base)": calculate_scenario_valuation(data, growth_med, mult_med, proj_years, discount_rate),
            "High Case": calculate_scenario_valuation(data, growth_high, mult_high, proj_years, discount_rate),
        }

        st.write("### 🏛️ Intrinsic Value vs. Current Market Price")
        st.caption(
            f"Current Market Price: **${init_price:,.2f}** | "
            f"Discount Rate: **{discount_rate*100:.1f}%** | "
            f"Dividend Yield: **{data['div_yield']*100:.2f}%**"
        )

        c1, c2, c3 = st.columns(3)
        for col, label in zip((c1, c2, c3), ("Low Case", "Medium (Base)", "High Case")):
            iv = scenarios[label]["intrinsic_value"]
            tp = scenarios[label]["target_price"]
            col.metric(
                f"{label} Intrinsic Value",
                f"${iv:,.2f}",
                delta=f"{((iv / init_price) - 1.0) * 100:,.1f}% vs Current",
            )
            col.caption(f"Target {proj_years}Y Price: **${tp:,.2f}** | Total CAGR: **{scenarios[label]['cagr']:.1f}%**")

        if scenarios["Medium (Base)"]["cagr"] > 18.0:
            st.warning(
                "⚠️ **Reality Check:** Base implied CAGR exceeds 18%/yr. Verify that single-quarter earnings growth or a recent bull run is not inflating your baseline."
            )

        med_iv = scenarios["Medium (Base)"]["intrinsic_value"]
        signal_text, signal_type, margin = get_actionable_signal(init_price, med_iv, nav_spread_pct)
        if signal_type == "success":
            st.success(f"**Model Signal:** {signal_text} ({margin:+.1f}%)")
        elif signal_type == "warning":
            st.warning(f"**Model Signal:** {signal_text} ({margin:+.1f}%)")
        else:
            st.error(f"**Model Signal:** {signal_text} ({margin:+.1f}%)")

        st.write("---")
        st.subheader("📈 Multi-Scenario Projection Trajectory")

        years_seq = list(range(0, proj_years + 1))
        chart_data = {"Year": years_seq}
        anchor_eps = data["forward_eps"] if (data["forward_eps"] and data["forward_eps"] > 0) else data["trailing_eps"]
        start_pe = data["forward_pe"] or data["trailing_pe"] or mult_med

        for sc_name, g_rate, m_val in [
            ("Low Case", growth_low, mult_low),
            ("Medium (Base)", growth_med, mult_med),
            ("High Case", growth_high, mult_high),
        ]:
            prices = []
            for y in years_seq:
                if y == 0:
                    prices.append(init_price)
                elif asset_class in ("Stock", "Metals & Mining Stock") and anchor_eps and anchor_eps > 0:
                    pe_step = start_pe + (m_val - start_pe) * (y / proj_years)
                    prices.append(anchor_eps * ((1.0 + g_rate) ** y) * pe_step)
                else:
                    base_anchor = nav_price if (asset_class == "Physical Bullion / Commodity Trust" and nav_price) else init_price
                    prices.append(base_anchor * ((1.0 + g_rate) ** y))
            chart_data[sc_name] = prices

        df_chart = pd.DataFrame(chart_data).set_index("Year")
        col_chart, col_table = st.columns([2, 1])
        with col_chart:
            st.line_chart(df_chart)
        with col_table:
            summary_df = pd.DataFrame(
                [
                    {
                        "Scenario": k,
                        "Intrinsic Value": v["intrinsic_value"],
                        "PV Dividends": v["pv_dividends"],
                        "Target Price": v["target_price"],
                        "Implied CAGR": v["cagr"],
                    }
                    for k, v in scenarios.items()
                ]
            ).set_index("Scenario")

            st.dataframe(
                summary_df.style.format(
                    {
                        "Intrinsic Value": "${:,.2f}",
                        "PV Dividends": "${:,.2f}",
                        "Target Price": "${:,.2f}",
                        "Implied CAGR": "{:,.2f}%",
                    }
                ),
                use_container_width=True,
            )

        with st.expander("🔍 Inspect Raw Yahoo Finance Inputs (Data Audit)"):
            st.json(data["raw_info_subset"])

    except Exception as e:
        st.error(f"Could not value '{ticker_input}': {e}")
