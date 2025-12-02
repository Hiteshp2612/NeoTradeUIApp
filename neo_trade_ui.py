import json
import streamlit as st
from neo_api_client import NeoAPI


# ------------------------- Helpers for session state ------------------------- #

def get_client_key(env: str) -> str:
    """Key name to store the NeoAPI client in session_state."""
    return f"neo_client_{env}"


def get_client(env: str) -> NeoAPI | None:
    """Return existing client for environment from session_state, if any."""
    key = get_client_key(env)
    return st.session_state.get(key)


def set_client(env: str, client: NeoAPI) -> None:
    """Save client in session_state."""
    key = get_client_key(env)
    st.session_state[key] = client


# ----------------------------- Streamlit UI --------------------------------- #

st.set_page_config(
    page_title="Kotak Neo Trade API – Simple TOTP Order Panel",
    layout="wide",
)

st.title("Kotak Neo Trade API – Simple Order Panel (TOTP Flow)")
st.caption(
    "UI based **only** on the latest `neo_api_client` (v2.x) from "
    "https://github.com/Kotak-Neo/Kotak-neo-api-v2\n\n"
    "Flow: Consumer Token → TOTP Login → TOTP Validate (MPIN) → Place Order / Reports."
)

# --------------------------------------------------------------------------- #
# STEP 1 – API SETUP (Create NeoAPI client with consumer_key only)
# --------------------------------------------------------------------------- #

st.header("Step 1 — API Setup")

col_env, col_token = st.columns([1, 3])

with col_env:
    environment = st.selectbox(
        "Environment",
        options=["prod", "uat"],
        index=0,
        help="Use `prod` for live; `uat` only if KS has given you UAT access.",
    )

with col_token:
    consumer_key = st.text_input(
        "Consumer Key / Token",
        value="",
        type="password",
        help=(
            "Paste the **token** from Neo app/web: "
            "Invest → Trade API card → Generate application → copy token."
        ),
    )

create_client_btn = st.button("Create / Reset NeoAPI Client", type="primary")

client_status_placeholder = st.empty()

if create_client_btn:
    if not consumer_key.strip():
        client_status_placeholder.error("Please enter your Consumer Key / Token.")
    else:
        try:
            # ✅ Exactly as per GitHub README:
            client = NeoAPI(
                environment=environment,
                access_token=None,
                neo_fin_key=None,
                consumer_key=consumer_key.strip(),
            )
            set_client(environment, client)

            # Reset login & session flags
            st.session_state["logged_in"] = False
            st.session_state["last_login_response"] = None
            st.session_state["last_validate_response"] = None

            client_status_placeholder.success(
                f"NeoAPI client created successfully for environment: `{environment}`."
            )
        except Exception as e:
            client_status_placeholder.error(
                f"Failed to create NeoAPI client: {repr(e)}"
            )

# Show a small debug hint
with st.expander("Debug: NeoAPI client status", expanded=False):
    client = get_client(environment)
    if client is None:
        st.info("No NeoAPI client created yet for this environment.")
    else:
        st.write("Client object created for environment:", environment)
        st.write(str(client))


# --------------------------------------------------------------------------- #
# STEP 2 – LOGIN USING TOTP + MPIN (as per README)
# --------------------------------------------------------------------------- #

st.header("Step 2 — Login using TOTP & MPIN")

st.markdown(
    "> **Note:** This uses the new TOTP flow from the latest GitHub README:\n"
    "`client.totp_login(mobile_number, ucc, totp)` → "
    "`client.totp_validate(mpin)`"
)

col_mob, col_ucc = st.columns(2)
with col_mob:
    mobile_number = st.text_input(
        "Registered Mobile (+91XXXXXXXXXX)",
        value="",
        help="Enter your registered mobile with country code, e.g. +9190XXXXXX.",
    )
with col_ucc:
    ucc = st.text_input(
        "User Id / UCC / Client Code",
        value="",
        help="Your Neo UCC / Client Code (from profile).",
    )

col_totp, col_mpin = st.columns(2)
with col_totp:
    totp = st.text_input(
        "6-digit TOTP (from authenticator app)",
        value="",
        type="password",
    )
with col_mpin:
    mpin = st.text_input(
        "6-digit MPIN (Neo login MPIN)",
        value="",
        type="password",
    )

login_btn = st.button("Login & Generate Trading Session", type="primary")

login_status_placeholder = st.empty()

if login_btn:
    client = get_client(environment)
    if client is None:
        login_status_placeholder.error(
            "NeoAPI client is not created. Complete **Step 1** first."
        )
    elif not (mobile_number.strip() and ucc.strip() and totp.strip() and mpin.strip()):
        login_status_placeholder.error(
            "Please fill **Mobile**, **UCC**, **TOTP**, and **MPIN**."
        )
    else:
        try:
            # 1️⃣ TOTP login – generates view token + session id
            resp_login = client.totp_login(
                mobile_number=mobile_number.strip(),
                ucc=ucc.strip(),
                totp=totp.strip(),
            )

            st.session_state["last_login_response"] = resp_login

            # 2️⃣ TOTP validate – generates trade token
            resp_validate = client.totp_validate(mpin=mpin.strip())
            st.session_state["last_validate_response"] = resp_validate

            st.session_state["logged_in"] = True

            login_status_placeholder.success("Login successful. Trading session is active.")
        except Exception as e:
            st.session_state["logged_in"] = False
            login_status_placeholder.error(
                f"Login failed: {repr(e)}"
            )

with st.expander("Debug: Raw login responses", expanded=False):
    st.write("Logged in:", st.session_state.get("logged_in", False))
    if st.session_state.get("last_login_response") is not None:
        st.subheader("Response from client.totp_login(...)")
        st.write(st.session_state["last_login_response"])
    if st.session_state.get("last_validate_response") is not None:
        st.subheader("Response from client.totp_validate(...)")
        st.write(st.session_state["last_validate_response"])


# --------------------------------------------------------------------------- #
# STEP 3 – SIMPLE EQUITY ORDER (place_order)
# --------------------------------------------------------------------------- #

st.header("Step 3 — Place Simple Order")

if not st.session_state.get("logged_in", False):
    st.info("Complete **Step 2 (Login)** before placing orders.")
else:
    st.success("You are logged in. You can place a simple order below.")

    col_exch, col_prod = st.columns(2)
    with col_exch:
        exchange_segment = st.selectbox(
            "Exchange Segment",
            options=["nse_cm", "bse_cm", "nse_fo", "bse_fo", "mcx_fo", "cde_fo"],
            index=0,
        )
    with col_prod:
        product = st.selectbox(
            "Product",
            options=["CNC", "NRML", "MIS", "CO", "BO", "MTF"],
            index=0,
        )

    col_symbol, col_side = st.columns(2)
    with col_symbol:
        trading_symbol = st.text_input(
            "Trading Symbol",
            value="RELIANCE",
            help="Exact trading symbol from scrip master.",
        )
    with col_side:
        transaction_type = st.selectbox(
            "Transaction Type",
            options=["B", "S"],
            index=0,
            help="B = Buy, S = Sell",
        )

    col_qty, col_price = st.columns(2)
    with col_qty:
        quantity = st.number_input(
            "Quantity",
            min_value=1,
            step=1,
            value=1,
        )
    with col_price:
        price = st.text_input(
            "Price",
            value="0",
            help="For MKT orders, keep 0. For Limit/SL orders, set desired price.",
        )

    col_ordertype, col_validity = st.columns(2)
    with col_ordertype:
        order_type = st.selectbox(
            "Order Type",
            options=["MKT", "L", "SL", "SL-M"],
            index=0,
        )
    with col_validity:
        validity = st.selectbox(
            "Validity",
            options=["DAY", "IOC", "GTC", "EOS", "GTD"],
            index=0,
        )

    place_btn = st.button("Place Order")

    order_status_placeholder = st.empty()

    if place_btn:
        client = get_client(environment)
        if client is None:
            order_status_placeholder.error("NeoAPI client missing. Please redo Step 1.")
        elif not st.session_state.get("logged_in", False):
            order_status_placeholder.error("You are not logged in. Please complete Step 2.")
        else:
            try:
                resp = client.place_order(
                    exchange_segment=exchange_segment,
                    product=product,
                    price=str(price),
                    order_type=order_type,
                    quantity=str(quantity),
                    validity=validity,
                    trading_symbol=trading_symbol.strip(),
                    transaction_type=transaction_type,
                    amo="NO",
                    disclosed_quantity="0",
                    market_protection="0",
                    pf="N",
                    trigger_price="0",
                    tag=None,
                    scrip_token=None,
                    square_off_type=None,
                    stop_loss_type=None,
                    stop_loss_value=None,
                    square_off_value=None,
                    last_traded_price=None,
                    trailing_stop_loss=None,
                    trailing_sl_value=None,
                )
                order_status_placeholder.success("Order placed. Raw response shown below.")
                with st.expander("Order API Response", expanded=True):
                    st.write(resp)
            except Exception as e:
                order_status_placeholder.error(f"Order placement failed: {repr(e)}")


# --------------------------------------------------------------------------- #
# STEP 4 – QUICK REPORTS (Orders, Positions, Holdings)
# --------------------------------------------------------------------------- #

st.header("Step 4 — Quick Reports")

if not st.session_state.get("logged_in", False):
    st.info("Login first (Step 2) to view orders and positions.")
else:
    client = get_client(environment)

    col_r1, col_r2, col_r3 = st.columns(3)
    get_orders_btn = col_r1.button("Get Order Book")
    get_positions_btn = col_r2.button("Get Positions")
    get_holdings_btn = col_r3.button("Get Holdings")

    if get_orders_btn:
        try:
            resp = client.order_report()
            st.subheader("Order Book")
            st.write(resp)
        except Exception as e:
            st.error(f"Failed to fetch order report: {repr(e)}")

    if get_positions_btn:
        try:
            resp = client.positions()
            st.subheader("Positions")
            st.write(resp)
        except Exception as e:
            st.error(f"Failed to fetch positions: {repr(e)}")

    if get_holdings_btn:
        try:
            resp = client.holdings()
            st.subheader("Holdings")
            st.write(resp)
        except Exception as e:
            st.error(f"Failed to fetch holdings: {repr(e)}")


# --------------------------------------------------------------------------- #
# OPTIONAL – LOGOUT
# --------------------------------------------------------------------------- #

st.markdown("---")
logout_btn = st.button("Logout NeoAPI Session")

if logout_btn:
    client = get_client(environment)
    if client is None:
        st.warning("No client exists to logout.")
    else:
        try:
            resp = client.logout()
            st.session_state["logged_in"] = False
            st.success("Logout request sent. Session state reset.")
            with st.expander("Logout response", expanded=False):
                st.write(resp)
        except Exception as e:
            st.error(f"Logout failed: {repr(e)}")
