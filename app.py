import streamlit as st
import yfinance as yf
import pandas as pd

# 1. Page Configuration
st.set_page_config(page_title="DCF Stock Valuation Tool", layout="wide")
st.title("📈 Everything Money Style - DCF Stock Analyzer")

# 2. Sidebar Parameters
st.sidebar.header("1. Input Asset")
ticker = st.sidebar.text_input("Ticker Symbol", value="AAPL").upper().strip()

st.sidebar.header("2. Valuation Metrics")
desired_return = st.sidebar.slider("Desired Annual Return (%)", 5.0, 20.0, 10.0, 0.5) / 100
margin_of_safety = st.sidebar.slider("Margin of Safety (%)", 0.0, 40.0, 20.0, 1.0) / 100

st.sidebar.header("3. Scenario Assumption Tuning")
col_low, col_med, col_high = st.sidebar.columns(3)

# Low Scenario Inputs
low_growth = st.sidebar.number_input("Low Growth (%)", value=4.0, step=0.5) / 100
low_mult = st.sidebar.number_input("Low Multiple (x)", value=12.0, step=1.0)

# Medium Scenario Inputs
med_growth = st.sidebar.number_input("Med Growth (%)", value=7.0, step=0.5) / 100
med_mult = st.sidebar.number_input("Med Multiple (x)", value=15.0, step=1.0)

# High Scenario Inputs
high_growth = st.sidebar.number_input("High Growth (%)", value=10.0, step=0.5) / 100
high_mult = st.sidebar.number_input("High Multiple (x)", value=18.0, step=1.0)

# 3. Core DCF Logic
def calculate_dcf(fcf, shares, growth, multiple, return_rate, years=10):
    future_fcf = fcf
    pv_sum = 0.0
    for year in range(1, years + 1):
        future_fcf *= (1 + growth)
        pv_sum += future_fcf / ((1 + return_rate) ** year)
    
    terminal_val = (future_fcf * multiple) / ((1 + return_rate) ** years)
    return (pv_sum + terminal_val) / shares

# 4. Data Fetching & App Execution
if ticker:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Extract Fundamentals
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        shares = info.get("sharesOutstanding")
        fcf = info.get("freeCashflow")
        
        # ETF vs Stock Guard Clause
        if not fcf or not shares:
            st.warning(f"⚠️ **{ticker}** appears to be an ETF or lacks cash flow data. DCF models only apply to operating equities.")
        else:
            # Display Key Overview Stats
            col1, col2, col3 = st.columns(3)
            col1.metric("Current Share Price", f"${current_price:.2f}")
            col2.metric("Shares Outstanding", f"{shares / 1e9:.2f} B")
            col3.metric("Trailing 12M Free Cash Flow", f"${fcf / 1e9:.2f} B")

            st.markdown("---")
            st.subheader("Valuation Scenarios")

            # Scenarios processing
            scenarios = {
                "Low": {"growth": low_growth, "multiple": low_mult},
                "Medium": {"growth": med_growth, "multiple": med_mult},
                "High": {"growth": high_growth, "multiple": high_mult}
            }

            table_data = []
            results = {}

            for case, params in scenarios.items():
                fair_val = calculate_dcf(fcf, shares, params["growth"], params["multiple"], desired_return)
                buy_price = fair_val * (1 - margin_of_safety)
                results[case] = buy_price
                
                table_data.append({
                    "Scenario": case,
                    "Est. Growth Rate": f"{params['growth']*100:.1f}%",
                    "Exit Multiple": f"{params['multiple']}x",
                    "Fair Value": f"${fair_val:.2f}",
                    "Target Buy Price": f"${buy_price:.2f}"
                })

            st.table(pd.DataFrame(table_data))

            # Verdict Display
            med_target = results["Medium"]
            st.subheader("Verdict")
            if current_price <= med_target:
                st.success(f"🟢 **BUY SIGNAL**: Market price (${current_price:.2f}) is below your Medium Target (${med_target:.2f}).")
            else:
                st.error(f"🔴 **OVERVALUED / WAIT**: Market price (${current_price:.2f}) exceeds your target buy price (${med_target:.2f}).")

    except Exception as e:
        st.error(f"Error loading ticker data: {e}")
