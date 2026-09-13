import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# Set page config
st.set_page_config(
    page_title="Universal Asset Valuation & Intrinsic Value Model",
    page_icon="📈",
    layout="wide"
)

def get_calibrated_inputs(ticker_symbol: str) -> dict:
    """
    Fetches ticker metadata via yfinance and derives reasonable baseline
    growth rates and valuation metrics across Stocks, Bonds, and ETFs.
    """
    ticker = yf.Ticker(ticker_symbol)
    
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
    
    if not current_price:
        try:
            hist = ticker.history(period="5d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])
            else:
                current_price = 100.0
        except Exception:
            current_price = 100.0

    growth_rate = 0.05
    exit_multiple = 15.0
    asset_class = "Stock"

    # Asset Classification & Parameter Calibration
    if quote_type == "ETF":
        asset_class = "ETF"
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
        
        exit_multiple = info.get("trailingPE") or 18.0

    elif quote_type in ["MUTUALFUND", "MONEYMARKET"]:
        asset_class = "Fund / Bond"
        growth_rate = info.get("yield") or info.get("threeYearAverageReturn") or 0.04
        exit_multiple = 1.0

    else:
        asset_class = "Stock"
        growth_rate = (
            info.get("earningsGrowth") 
            or info.get("revenueGrowth") 
            or 0.07
        )
        exit_multiple = (
            info.get("forwardPE") 
            or info.get("trailingPE") 
            or 20.0
        )

    # Sanity Clamping
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


def calculate_scenario_valuation(init_price, growth_rate, exit_multiple, proj_years, trailing_pe, asset_class, discount_rate=0.09):
    """
    Calculates projected target price and present intrinsic value for a given scenario.
    """
    compounded_val = init_price * ((1 + growth_rate) ** proj_years)
    
    if asset_class == "Stock" and trailing_pe:
        pe_expansion = exit_multiple / max(trailing_pe, 1.0)
        target_price = compounded_val * pe_expansion
    else:
        target_price = compounded_val

    # Present Intrinsic Value via Discounted Present Value
    intrinsic_value = target_price / ((1 + discount_rate) ** proj_years)
    total_return = ((target_price / init_price) - 1) * 100
    cagr = (((target_price / init_price) ** (1 / proj_years)) - 1) * 100

    return {
        "target_price": target_price,
        "intrinsic_value": intrinsic_value,
        "total_return": total_return,
        "cagr": cagr
    }


# --- STREAMLIT UI ---

st.title("📊 Universal Valuation & Intrinsic Value Scenario Model")
st.markdown("Project **Low, Medium (Base), and High Intrinsic Value** scenarios for any Stock, ETF, Bond, or Fund.")

col_search, _ = st.columns([1, 2])
with col_search:
    ticker_input = st.text_input("Enter Ticker Symbol:", value="AAPL").strip().upper()

if ticker_input:
    try:
        with st.spinner(f"Fetching & calibrating scenarios for {ticker_input}..."):
            data = get_calibrated_inputs(ticker_input)

        st.subheader(f"{data['long_name']} ({ticker_input})")
        
        # Sidebar Controls
        st.sidebar.header("⚙️ Model Parameters")
        st.sidebar.caption(f"Detected Asset Class: **{data['asset_class']}**")

        proj_years = st.sidebar.slider("Projection Horizon (Years)", 1, 20, 5)
        discount_rate = st.sidebar.slider("Discount Rate / Required Return (%)", 4.0, 15.0, 9.0, step=0.5) / 100.0

        # Base growth rate & multiple inputs
        base_growth = round(data["growth_rate"] * 100, 2)
        base_multiple = round(data["exit_multiple"], 1)

        st.sidebar.markdown("---")
        st.sidebar.subheader("🎯 Scenario Calibrations")
        
        # Scenario Sliders for Growth
        growth_low = st.sidebar.slider("Low Growth Rate (%)", -20.0, 30.0, float(round(base_growth * 0.6, 2)), step=0.5) / 100.0
        growth_med = st.sidebar.slider("Medium (Base) Growth Rate (%)", -20.0, 40.0, float(base_growth), step=0.5) / 100.0
        growth_high = st.sidebar.slider("High Growth Rate (%)", -20.0, 60.0, float(round(base_growth * 1.4, 2)), step=0.5) / 100.0

        if data["asset_class"] == "Stock":
            mult_low = st.sidebar.slider("Low Exit P/E", 3.0, 60.0, float(round(base_multiple * 0.75, 1)), step=0.5)
            mult_med = st.sidebar.slider("Medium Exit P/E", 3.0, 70.0, float(base_multiple), step=0.5)
            mult_high = st.sidebar.slider("High Exit P/E", 3.0, 80.0, float(round(base_multiple * 1.25, 1)), step=0.5)
        else:
            mult_low = mult_med = mult_high = data["exit_multiple"]

        init_price = data["current_price"]
        trailing_pe = data["trailing_pe"]
        asset_class = data["asset_class"]

        # Run Scenario Calculations
        scenarios = {
            "Low Case": calculate_scenario_valuation(init_price, growth_low, mult_low, proj_years, trailing_pe, asset_class, discount_rate),
            "Medium (Base)": calculate_scenario_valuation(init_price, growth_med, mult_med, proj_years, trailing_pe, asset_class, discount_rate),
            "High Case": calculate_scenario_valuation(init_price, growth_high, mult_high, proj_years, trailing_pe, asset_class, discount_rate)
        }

        # Display Intrinsic Value Metric Cards
        st.write("### 🏛️ Intrinsic Value vs Current Price")
        st.caption(f"Current Market Price / NAV: **${init_price:,.2f}** | Required Discount Rate: **{discount_rate*100:.1f}%**")

        c1, c2, c3 = st.columns(3)
        
        # Low Case
        low_iv = scenarios["Low Case"]["intrinsic_value"]
        c1.metric(
            "Low Intrinsic Value", 
            f"${low_iv:,.2f}", 
            delta=f"{((low_iv / init_price) - 1) * 100:,.1f}% vs Current",
            delta_color="normal"
        )
        c1.caption(f"Target {proj_years}Y Price: **${scenarios['Low Case']['target_price']:,.2f}**")

        # Base Case
        med_iv = scenarios["Medium (Base)"]["intrinsic_value"]
        c2.metric(
            "Medium (Base) Intrinsic Value", 
            f"${med_iv:,.2f}", 
            delta=f"{((med_iv / init_price) - 1) * 100:,.1f}% vs Current",
            delta_color="normal"
        )
        c2.caption(f"Target {proj_years}Y Price: **${scenarios['Medium (Base)']['target_price']:,.2f}**")

        # High Case
        high_iv = scenarios["High Case"]["intrinsic_value"]
        c3.metric(
            "High Intrinsic Value", 
            f"${high_iv:,.2f}", 
            delta=f"{((high_iv / init_price) - 1) * 100:,.1f}% vs Current",
            delta_color="normal"
        )
        c3.caption(f"Target {proj_years}Y Price: **${scenarios['High Case']['target_price']:,.2f}**")

        # Trajectory Chart & Data Table
        st.write("---")
        st.subheader("📈 Multi-Scenario Projection Trajectory")

        years_seq = list(range(0, proj_years + 1))
        chart_data = {"Year": years_seq}

        for sc_name, g_rate, m_val in [
            ("Low Case", growth_low, mult_low),
            ("Medium (Base)", growth_med, mult_med),
            ("High Case", growth_high, mult_high)
        ]:
            prices = []
            for y in years_seq:
                base_val = init_price * ((1 + g_rate) ** y)
                if asset_class == "Stock" and trailing_pe:
                    pe_step = trailing_pe + (m_val - trailing_pe) * (y / proj_years)
                    price = base_val * (pe_step / max(trailing_pe, 1.0))
                else:
                    price = base_val
                prices.append(price)
            chart_data[sc_name] = prices

        df_chart = pd.DataFrame(chart_data).set_index("Year")

        col_chart, col_table = st.columns([2, 1])
        with col_chart:
            st.line_chart(df_chart)
        with col_table:
            summary_df = pd.DataFrame([
                {
                    "Scenario": k,
                    "Intrinsic Value": v["intrinsic_value"],
                    "Target Price": v["target_price"],
                    "Implied CAGR": v["cagr"]
                }
                for k, v in scenarios.items()
            ]).set_index("Scenario")
            
            st.dataframe(
                summary_df.style.format({
                    "Intrinsic Value": "${:,.2f}",
                    "Target Price": "${:,.2f}",
                    "Implied CAGR": "{:,.2f}%"
                }),
                use_container_width=True
            )

    except Exception as e:
        st.error(f"Unable to process ticker '{ticker_input}'. Please verify the symbol and try again.")
        st.caption(f"Error details: {e}")
