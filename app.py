import streamlit as st
import yfinance as yf
import pandas as pd

# 1. Page Config
st.set_page_config(page_title="Stock & ETF Valuation Tool", layout="wide")
st.title("📈 Multi-Asset DCF & Fundamental Analyzer")

# 2. Sidebar Inputs
st.sidebar.header("1. Asset Selection")
ticker_input = st.sidebar.text_input("Enter Ticker Symbol", value="MSFT").upper().strip()

st.sidebar.header("2. Valuation Parameters")
desired_return = st.sidebar.slider("Desired Return (%)", 5.0, 20.0, 10.0, 0.5) / 100
margin_of_safety = st.sidebar.slider("Margin of Safety (%)", 0.0, 40.0, 20.0, 1.0) / 100

st.sidebar.header("3. Growth & Multiple Scenarios")
col_l, col_m, col_h = st.sidebar.columns(3)

# Low Scenario Inputs
low_growth = st.sidebar.number_input("Low Growth (%)", value=6.0, step=0.5) / 100
low_mult = st.sidebar.number_input("Low Multiple (x)", value=18.0, step=1.0)

# Medium Scenario Inputs
med_growth = st.sidebar.number_input("Med Growth (%)", value=10.0, step=0.5) / 100
med_mult = st.sidebar.number_input("Med Multiple (x)", value=22.0, step=1.0)

# High Scenario Inputs
high_growth = st.sidebar.number_input("High Growth (%)", value=14.0, step=0.5) / 100
high_mult = st.sidebar.number_input("High Multiple (x)", value=26.0, step=1.0)

# 3. Helper Functions
def get_clean_stock_data(ticker):
    """Pulls clean financial metrics from Cash Flow Statement rather than raw info dict."""
    stock = yf.Ticker(ticker)
    info = stock.info
    
    quote_type = info.get("quoteType", "EQUITY")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("navPrice", 0.0)
    shares = info.get("sharesOutstanding", 0)
    
    calc_fcf = 0.0
    try:
        cf = stock.cashflow
        if not cf.empty:
            # Operating Cash Flow - Capital Expenditures
            op_cash = cf.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in cf.index else 0
            capex = abs(cf.loc['Capital Expenditure'].iloc[0]) if 'Capital Expenditure' in cf.index else 0
            calc_fcf = op_cash - capex
    except Exception:
        pass
        
    # Fallback if statement parsing returns zero
    if calc_fcf <= 0:
        calc_fcf = info.get("freeCashflow", 0)

    return stock, info, quote_type, current_price, shares, calc_fcf

def calculate_dcf(fcf, shares, growth, multiple, return_rate, years=10):
    future_fcf = fcf
    pv_sum = 0.0
    for year in range(1, years + 1):
        future_fcf *= (1 + growth)
        pv_sum += future_fcf / ((1 + return_rate) ** year)
    
    terminal_val = (future_fcf * multiple) / ((1 + return_rate) ** years)
    return (pv_sum + terminal_val) / shares

# 4. App Execution
if ticker_input:
    try:
        stock, info, quote_type, fetched_price, fetched_shares, fetched_fcf = get_clean_stock_data(ticker_input)
        company_name = info.get("longName", ticker_input)

        st.subheader(f"{company_name} ({ticker_input}) — Type: {quote_type}")

        # BRANCH 1: ETF Valuation Logic
        if quote_type == "ETF":
            st.info("ℹ️ **ETF Detected**: Evaluated using aggregate valuation, fund size, and yield metrics.")

            pe_ratio = info.get("trailingPE") or info.get("forwardPE", "N/A")
            yield_rate = info.get("yield", 0.0)
            yield_str = f"{yield_rate * 100:.2f}%" if yield_rate else "N/A"

            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price / NAV", f"${fetched_price:.2f}" if fetched_price else "N/A")
            c2.metric("Weighted P/E Ratio", f"{pe_ratio if isinstance(pe_ratio, str) else f'{pe_ratio:.2f}x'}")
            c3.metric("Distribution Yield", yield_str)

            st.markdown("---")
            st.subheader("Fund Overview")
            
            summary_data = {
                "Metric": ["Category / Family", "Total Assets", "52-Week Range"],
                "Value": [
                    f"{info.get('category', 'N/A')} / {info.get('fundFamily', 'N/A')}",
                    f"${info.get('totalAssets', 0) / 1e9:.2f} B" if info.get('totalAssets') else "N/A",
                    f"${info.get('fiftyTwoWeekLow', 0):.2f} - ${info.get('fiftyTwoWeekHigh', 0):.2f}"
                ]
            }
            st.table(pd.DataFrame(summary_data))

        # BRANCH 2: Individual Stock DCF Valuation Logic
        else:
            # Override Sidebar Controls for Data Safety
            with st.sidebar.expander("🛠️ Data Overrides (Advanced)"):
                st.caption("Adjust inputs if Yahoo Finance data displays unusual CapEx spikes or missing fields.")
                override_price = st.number_input("Override Share Price ($)", value=float(fetched_price), step=1.0)
                override_shares = st.number_input("Override Shares (Billions)", value=float(fetched_shares / 1e9), step=0.1) * 1e9
                override_fcf = st.number_input("Override TTM Free Cash Flow ($B)", value=float(fetched_fcf / 1e9), step=1.0) * 1e9

            # Apply final operational values
            final_price = override_price if override_price > 0 else fetched_price
            final_shares = override_shares if override_shares > 0 else fetched_shares
            final_fcf = override_fcf if override_fcf != 0 else fetched_fcf

            if final_fcf <= 0 or final_shares <= 0:
                st.warning(f"⚠️ Could not pull valid FCF or Share counts for **{ticker_input}**. Please enter values manually in the **Data Overrides** sidebar.")
            else:
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Share Price", f"${final_price:.2f}")
                c2.metric("Shares Outstanding", f"{final_shares / 1e9:.2f} B")
                c3.metric("TTM Free Cash Flow", f"${final_fcf / 1e9:.2f} B")

                st.markdown("---")
                st.subheader("DCF Intrinsic Valuation Scenarios")

                scenarios = {
                    "Low": {"growth": low_growth, "multiple": low_mult},
                    "Medium": {"growth": med_growth, "multiple": med_mult},
                    "High": {"growth": high_growth, "multiple": high_mult}
                }

                table_data = []
                results = {}

                for case, params in scenarios.items():
                    fair_val = calculate_dcf(final_fcf, final_shares, params["growth"], params["multiple"], desired_return)
                    buy_price = fair_val * (1 - margin_of_safety)
                    results[case] = buy_price

                    table_data.append({
                        "Scenario": case,
                        "Est. Growth Rate": f"{params['growth']*100:.1f}%",
                        "Exit Multiple": f"{params['multiple']}x",
                        "Calculated Fair Value": f"${fair_val:.2f}",
                        "Target Buy Price": f"${buy_price:.2f}"
                    })

                st.table(pd.DataFrame(table_data))

                # Verdict Display
                med_target = results["Medium"]
                high_target = results["High"]

                st.subheader("Verdict")
                if final_price <= med_target:
                    st.success(f"🟢 **BUY TARGET MET**: Market price (${final_price:.2f}) is below your Medium Target Buy Price (${med_target:.2f}).")
                elif final_price <= high_target:
                    st.info(f"🟡 **WATCHLIST / FAIR**: Market price (${final_price:.2f}) sits between Medium (${med_target:.2f}) and High (${high_target:.2f}) target scenarios.")
                else:
                    st.error(f"🔴 **OVERVALUED / WAIT**: Market price (${final_price:.2f}) exceeds your target conservative buy prices.")

    except Exception as e:
        st.error(f"Error loading asset data for {ticker_input}: {e}")
