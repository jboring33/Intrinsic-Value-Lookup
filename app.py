import streamlit as st
import yfinance as yf
import pandas as pd

# 1. Page Config
st.set_page_config(page_title="Multi-Asset Valuation Assistant", layout="wide")
st.title("📈 Multi-Asset Valuation Assistant & Analyzer")

# 2. Sidebar Interactive Dialog Assistant
st.sidebar.header("1. Asset Selection & Guided Dialog")
ticker_input = st.sidebar.text_input("Enter Ticker Symbol", value="MSFT").upper().strip()

asset_type = st.sidebar.selectbox(
    "Select Asset Class",
    ["Individual Stock", "ETF / Index Fund", "Bond / Fixed Income"],
    index=0
)

# Dynamic Help Box based on Asset Selection
if asset_type == "Individual Stock":
    st.sidebar.info(
        "💡 **Stock Valuation Guidance**:\n"
        "Uses a 10-Year DCF Model based on Free Cash Flow. "
        "Adjust growth rate and exit multiples to reflect realistic long-term compound performance."
    )
    desired_return = st.sidebar.slider("Desired Annual Return (%)", 5.0, 20.0, 10.0, 0.5) / 100
    margin_of_safety = st.sidebar.slider("Margin of Safety (%)", 0.0, 40.0, 20.0, 1.0) / 100

    st.sidebar.subheader("Growth & Exit Multiple Scenarios")
    low_growth = st.sidebar.number_input("Low Growth (%)", value=6.0, step=0.5) / 100
    low_mult = st.sidebar.number_input("Low Multiple (x)", value=18.0, step=1.0)
    med_growth = st.sidebar.number_input("Med Growth (%)", value=10.0, step=0.5) / 100
    med_mult = st.sidebar.number_input("Med Multiple (x)", value=22.0, step=1.0)
    high_growth = st.sidebar.number_input("High Growth (%)", value=14.0, step=0.5) / 100
    high_mult = st.sidebar.number_input("High Multiple (x)", value=26.0, step=1.0)

elif asset_type == "ETF / Index Fund":
    st.sidebar.info(
        "💡 **ETF Evaluation Guidance**:\n"
        "ETFs hold baskets of assets and cannot be valued via DCF. "
        "Focus on Weighted P/E, Expense Ratio, and Yield to assess value."
    )
    max_acceptable_pe = st.sidebar.number_input("Max Acceptable Weighted P/E (x)", value=25.0, step=1.0)
    min_yield = st.sidebar.number_input("Target Dividend Yield (%)", value=1.5, step=0.1) / 100

elif asset_type == "Bond / Fixed Income":
    st.sidebar.info(
        "💡 **Bond / Fixed Income Guidance**:\n"
        "Fixed income is valued on yield, coupon, duration, and credit risk rather than equity cash flows."
    )
    required_ytm = st.sidebar.number_input("Required Yield to Maturity (YTM %)", value=5.0, step=0.25) / 100

# 3. Helper Functions
def get_clean_stock_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("navPrice", 0.0)
    shares = info.get("sharesOutstanding", 0)
    
    calc_fcf = 0.0
    try:
        cf = stock.cashflow
        if not cf.empty:
            op_cash = cf.loc['Operating Cash Flow'].iloc[0] if 'Operating Cash Flow' in cf.index else 0
            capex = abs(cf.loc['Capital Expenditure'].iloc[0]) if 'Capital Expenditure' in cf.index else 0
            calc_fcf = op_cash - capex
    except Exception:
        pass
        
    if calc_fcf <= 0:
        calc_fcf = info.get("freeCashflow", 0)

    return stock, info, current_price, shares, calc_fcf

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
        stock, info, fetched_price, fetched_shares, fetched_fcf = get_clean_stock_data(ticker_input)
        company_name = info.get("longName", ticker_input)

        st.subheader(f"{company_name} ({ticker_input}) — Mode: {asset_type}")

        # BRANCH 1: INDIVIDUAL STOCK DCF
        if asset_type == "Individual Stock":
            with st.sidebar.expander("🛠️ Data Overrides"):
                override_price = st.number_input("Override Share Price ($)", value=float(fetched_price), step=1.0)
                override_shares = st.number_input("Override Shares (Billions)", value=float(fetched_shares / 1e9), step=0.1) * 1e9
                override_fcf = st.number_input("Override TTM Free Cash Flow ($B)", value=float(fetched_fcf / 1e9), step=1.0) * 1e9

            final_price = override_price if override_price > 0 else fetched_price
            final_shares = override_shares if override_shares > 0 else fetched_shares
            final_fcf = override_fcf if override_fcf != 0 else fetched_fcf

            if final_fcf <= 0 or final_shares <= 0:
                st.warning(f"⚠️ Missing valid FCF or Share count for **{ticker_input}**. Adjust values manually in Data Overrides.")
            else:
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Price", f"${final_price:.2f}")
                c2.metric("Shares Outstanding", f"{final_shares / 1e9:.2f} B")
                c3.metric("TTM Free Cash Flow", f"${final_fcf / 1e9:.2f} B")

                st.markdown("---")
                st.subheader("DCF Valuation Results")

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

                med_target = results["Medium"]
                high_target = results["High"]

                st.subheader("Verdict")
                if final_price <= med_target:
                    st.success(f"🟢 **BUY**: Price (${final_price:.2f}) is below Medium Target (${med_target:.2f}).")
                elif final_price <= high_target:
                    st.info(f"🟡 **FAIR**: Price (${final_price:.2f}) sits between Medium (${med_target:.2f}) and High (${high_target:.2f}) targets.")
                else:
                    st.error(f"🔴 **OVERVALUED**: Price (${final_price:.2f}) exceeds conservative buy targets.")

        # BRANCH 2: ETF / INDEX FUND
        elif asset_type == "ETF / Index Fund":
            pe_ratio = info.get("trailingPE") or info.get("forwardPE", 0.0)
            yield_rate = info.get("yield", 0.0)

            c1, c2, c3 = st.columns(3)
            c1.metric("Current NAV / Price", f"${fetched_price:.2f}" if fetched_price else "N/A")
            c2.metric("Weighted P/E Ratio", f"{pe_ratio:.2f}x" if pe_ratio else "N/A")
            c3.metric("Distribution Yield", f"{yield_rate * 100:.2f}%" if yield_rate else "N/A")

            st.markdown("---")
            st.subheader("ETF Evaluation Check")
            
            pe_check = pe_ratio <= max_acceptable_pe if pe_ratio else False
            yield_check = yield_rate >= min_yield if yield_rate else False

            st.write(f"• **Valuation Check**: Weighted P/E ({pe_ratio:.2f}x) vs Target Max ({max_acceptable_pe:.2f}x) ➔ {'🟢 Pass' if pe_check else '🔴 High Valuation'}")
            st.write(f"• **Yield Check**: Distribution Yield ({yield_rate*100:.2f}%) vs Minimum Target ({min_yield*100:.2f}%) ➔ {'🟢 Pass' if yield_check else '🔴 Low Yield'}")

        # BRANCH 3: BOND / FIXED INCOME
        elif asset_type == "Bond / Fixed Income":
            coupon = info.get("couponRate", 0.0)
            yield_to_mat = info.get("yield", 0.0) or info.get("fiveYearAvgDividendYield", 0.0)

            c1, c2 = st.columns(2)
            c1.metric("Current Price", f"${fetched_price:.2f}" if fetched_price else "N/A")
            c2.metric("Indicated Yield / Coupon", f"{yield_to_mat:.2f}%" if yield_to_mat else "N/A")

            st.markdown("---")
            st.subheader("Fixed Income Guidance")
            st.write("Bonds pay fixed coupon cash flows over time until maturity. Evaluate the yield relative to inflation and your target hurdle rate.")

    except Exception as e:
        st.error(f"Error evaluating asset {ticker_input}: {e}")
