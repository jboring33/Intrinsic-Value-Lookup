import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Set page config
st.set_page_config(
    page_title="Universal Asset Projection Model",
    page_icon="📈",
    layout="wide"
)

def get_calibrated_inputs(ticker_symbol: str) -> dict:
    """
    Fetches ticker metadata via yfinance and derives reasonable baseline
    growth rates and valuation metrics across Stocks, Bonds, and ETFs.
    """
    ticker = yf.Ticker(ticker_symbol)
    
    # yfinance info dictionary can sometimes throw errors or return empty
    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    quote_type = info.get("quoteType", "EQUITY")
    
    # Robust current price fallback chain
    current_price = (
        info.get("currentPrice") 
        or info.get("navPrice") 
        or info.get("previousClose")
        or info.get("regularMarketPrice")
    )
    
    # If info fails to get price, fall back to recent daily history
    if not current_price:
        try:
            hist = ticker.history(period="5d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
            else:
                current_price = 100.0
        except Exception:
            current_price = 100.0

    # Baseline defaults
    growth_rate = 0.05
    exit_multiple = 15.0
    asset_class = "Stock"

    # Asset Classification & Parameter Calibration
    if quote_type == "ETF":
        asset_class = "ETF"
        # Calculate 5-year historical CAGR if available
        try:
            hist = ticker.history(period="5y")
            if len(hist) > 250:
                start_price = float(hist["Close"].iloc[0])
                end_price = float(hist["Close"].iloc[-1])
                years = len(hist) / 252.0
                if start_price > 0:
                    growth_rate = (end_price / start_price) ** (1 / years) - 1.0
        except Exception:
            growth_rate = 0.06
        
        # Aggregate P/E if available, else benchmark
        exit_multiple = info.get("trailingPE") or 18.0

    elif quote_type in ["MUTUALFUND", "MONEYMARKET"]:
        asset_class = "Fund / Bond"
        # Use distribution yield or SEC yield
        growth_rate = info.get("yield") or info.get("threeYearAverageReturn") or 0.04
        exit_multiple = 1.0

    else:
        # Standard Equity / Stock
        asset_class = "Stock"
        
        # 1. Growth Rate Fallback: Analyst Earnings Growth -> Revenue Growth -> Default 7%
        growth_rate = (
            info.get("earningsGrowth") 
            or info.get("revenueGrowth") 
            or 0.07
        )
        
        # 2. Exit Multiple Fallback: Forward PE -> Trailing PE -> Baseline 20x
        exit_multiple = (
            info.get("forwardPE") 
            or info.get("trailingPE") 
            or 20.0
        )

    # Sanity Clamping: Prevent extreme outliers from breaking sliders
    growth_rate = max(-0.25, min(float(growth_rate), 0.50))
    if asset_class == "Stock":
        exit_multiple = max(3.0, min(float(exit_multiple), 80.0))

    return {
        "asset_class": asset_class,
        "current_price": float(current_price),
        "growth_rate": float(growth_rate),
        "exit_multiple": float(exit_multiple),
        "long_name": info.get("longName") or info.get("shortName") or ticker_symbol,
        "trailing_pe": info.get("trailingPE")
    }


# --- STREAMLIT UI ---

st.title("📊 Universal Asset Valuation & Projection Model")
st.markdown("Analyze and project target outcomes for **any Stock, ETF, Bond, or Fund** using dynamic fallback calibrations.")

col_search, _ = st.columns([1, 2])
with col_search:
    ticker_input = st.text_input("Enter Ticker Symbol:", value="AAPL").strip().upper()

if ticker_input:
    try:
        with st.spinner(f"Calibrating metadata for {ticker_input}..."):
            data = get_calibrated_inputs(ticker_input)

        st.subheader(f"{data['long_name']} ({ticker_input})")
        
        # Sidebar Controls
        st.sidebar.header("⚙️ Model Parameters")
        st.sidebar.caption(f"Detected Asset Class: **{data['asset_class']}**")

        proj_years = st.sidebar.slider(
            "Projection Horizon (Years)", 
            min_value=1, 
            max_value=20, 
            value=5
        )

        calibrated_growth_pct = round(data["growth_rate"] * 100, 2)
        growth_rate_input = st.sidebar.slider(
            "Projected Growth / Annual Return (%)",
            min_value=-20.0,
            max_value=50.0,
            value=float(calibrated_growth_pct),
            step=0.5
        ) / 100.0

        if data["asset_class"] == "Stock":
            multiple_input = st.sidebar.slider(
                "Target Exit P/E Multiple",
                min_value=3.0,
                max_value=80.0,
                value=round(data["exit_multiple"], 1),
                step=0.5
            )
        else:
            multiple_input = data["exit_multiple"]
            st.sidebar.info("💡 Exit multiples are locked or simplified for Funds, Bonds, and Index ETFs.")

        # Financial Calculations
        init_price = data["current_price"]
        compounded_val = init_price * ((1 + growth_rate_input) ** proj_years)

        if data["asset_class"] == "Stock" and data["trailing_pe"]:
            current_pe = data["trailing_pe"]
            pe_expansion = multiple_input / max(current_pe, 1.0)
            target_price = compounded_val * pe_expansion
        else:
            target_price = compounded_val

        total_return_pct = ((target_price / init_price) - 1) * 100
        cagr = (((target_price / init_price) ** (1 / proj_years)) - 1) * 100

        # Output Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current Price / NAV", f"${init_price:,.2f}")
        m2.metric(f"Projected {proj_years}Y Price", f"${target_price:,.2f}")
        m3.metric("Total Projected Return", f"{total_return_pct:,.1f}%")
        m4.metric("Implied CAGR", f"{cagr:,.2f}%")

        # Annual Trajectory Table & Chart
        st.write("---")
        st.subheader("📈 Projection Trajectory")
        
        years_seq = list(range(0, proj_years + 1))
        yearly_prices = []
        for y in years_seq:
            base_val = init_price * ((1 + growth_rate_input) ** y)
            if data["asset_class"] == "Stock" and data["trailing_pe"]:
                # Linearly interpolate PE expansion over time horizon
                current_pe = data["trailing_pe"]
                pe_step = current_pe + (multiple_input - current_pe) * (y / proj_years)
                price = base_val * (pe_step / max(current_pe, 1.0))
            else:
                price = base_val
            yearly_prices.append(price)

        df_proj = pd.DataFrame({
            "Year": years_seq,
            "Projected Price ($)": yearly_prices
        }).set_index("Year")

        col_chart, col_table = st.columns([2, 1])
        with col_chart:
            st.line_chart(df_proj)
        with col_table:
            st.dataframe(df_proj.style.format("${:,.2f}"), height=250)

    except Exception as e:
        st.error(f"Unable to process ticker '{ticker_input}'. Please verify the symbol and try again.")
        st.caption(f"Error details: {e}")
