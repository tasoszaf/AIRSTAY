import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from st_aggrid import AgGrid, GridOptionsBuilder, DataReturnMode, GridUpdateMode

# ---------------------- ΡΥΘΜΙΣΕΙΣ ----------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# ---------------------- ΚΑΤΑΛΥΜΑΤΑ & ΡΥΘΜΙΣΕΙΣ ----------------------
APARTMENTS = {
    "ZED": [1439913,1439915,1439917],
    "KOMOS": [2160281,2160286,2160291],
    "CHELI": [2146456,2146461]
}

APARTMENT_SETTINGS = {
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "KOMOS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "CHELI": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
}

months_el = {
    1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
    7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"
}

# ---------------------- ΣΥΝΑΡΤΗΣΕΙΣ ----------------------
def compute_price_without_tax(price, nights, month, apt_name):
    if not price or not nights:
        return 0.0
    settings = APARTMENT_SETTINGS.get(apt_name, {"winter_base": 2, "summer_base": 8})
    base = settings["winter_base"] if month in [11,12,1,2] else settings["summer_base"]
    adjusted = price - base * nights
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

def compute_booking_fee(platform_name: str, price: float) -> float:
    if not platform_name:
        return 0.0
    p = platform_name.strip().lower()
    if p in {"website","direct","direct booking","direct-booking","site","web"}:
        rate = 0.00
    elif "booking" in p:
        rate = 0.17
    elif "airbnb" in p:
        rate = 0.15
    elif "expedia" in p:
        rate = 0.18
    else:
        rate = 0.00
    return round((price or 0)*rate, 2)

# ---------------------- ΛΗΨΗ ΚΡΑΤΗΣΕΩΝ ----------------------
@st.cache_data(ttl=3600)
def fetch_reservations(apt_name):
    all_rows = []
    for apt_id in APARTMENTS[apt_name]:
        from_date = "2025-01-01"
        to_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        params = {
            "from": from_date,
            "to": to_date,
            "apartmentId": apt_id,
            "excludeBlocked": "true",
            "showCancellation": "true",
            "page": 1,
            "pageSize": 100,
        }
        while True:
            try:
                r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.RequestException:
                break

            bookings = data.get("bookings", [])
            if not bookings:
                break

            for b in bookings:
                arrival_str = b.get("arrival")
                departure_str = b.get("departure")
                if not arrival_str or not departure_str:
                    continue
                arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d")
                departure_dt = datetime.strptime(departure_str, "%Y-%m-%d")
                if arrival_dt.date() > date.today() - timedelta(days=1):
                    continue

                platform = (b.get("channel") or {}).get("name") or "Direct booking"
                price = float(b.get("price") or 0)
                adults = int(b.get("adults") or 0)
                children = int(b.get("children") or 0)
                guests = adults + children
                days = max((departure_dt - arrival_dt).days, 0)
                if days == 0:
                    continue

                if "expedia" in platform.lower():
                    price = price / 0.82

                price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month, apt_name)
                fee = compute_booking_fee(platform, price)
                settings = APARTMENT_SETTINGS.get(apt_name, {"airstay_commission": 0.248})
                airstay_commission = round(price_wo_tax * settings["airstay_commission"], 2)
                owner_profit = round(price_wo_tax - fee - airstay_commission, 2)

                all_rows.append({
                    "ID": b.get("id"),
                    "Apartment": apt_name,
                    "Guest Name": b.get("guestName") or b.get("guest-name"),
                    "Arrival": arrival_dt.strftime("%Y-%m-%d"),
                    "Departure": departure_dt.strftime("%Y-%m-%d"),
                    "Days": days,
                    "Platform": platform,
                    "Guests": guests,
                    "Total Price": round(price,2),
                    "Booking Fee": round(fee,2),
                    "Price Without Tax": round(price_wo_tax,2),
                    "Airstay Commission": round(airstay_commission,2),
                    "Owner Profit": round(owner_profit,2),
                    "Month": arrival_dt.month
                })
            if data.get("page") and data.get("page") < data.get("page_count",1):
                params["page"] += 1
            else:
                break
    return pd.DataFrame(all_rows).drop_duplicates(subset=["ID"])

# ---------------------- Επιλογή Καταλύματος ----------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_apartment = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
df_all = fetch_reservations(selected_apartment)

# ---------------------- AgGrid - Inline φίλτρο ----------------------
st.subheader(f"📅 Κρατήσεις ({selected_apartment})")

gb = GridOptionsBuilder.from_dataframe(df_all)
gb.configure_default_column(editable=False, filter=True, sortable=True)
gb.configure_column("Month", header_name="Μήνας", type=["numericColumn"], filter="agNumberColumnFilter")
grid_options = gb.build()

grid_response = AgGrid(
    df_all,
    gridOptions=grid_options,
    height=400,
    enable_enterprise_modules=False,
    update_mode=GridUpdateMode.NO_UPDATE,
    fit_columns_on_grid_load=True,
    data_return_mode=DataReturnMode.FILTERED_AND_SORTED
)

filtered_df = pd.DataFrame(grid_response['data'])

# ---------------------- ΥΠΟΛΟΓΙΣΜΟΣ ΣΥΝΟΛΩΝ ----------------------
total_price = filtered_df["Total Price"].sum()
total_owner_profit = filtered_df["Owner Profit"].sum()
total_booking_fee = filtered_df["Booking Fee"].sum()

col1, col2, col3 = st.columns(3)
col1.metric("💰 Συνολική Τιμή Κρατήσεων", f"{total_price:.2f} €")
col2.metric("🧾 Συνολικά Έξοδα", f"{total_booking_fee:.2f} €")
col3.metric("📊 Κέρδος Ιδιοκτήτη", f"{total_owner_profit:.2f} €")

# ---------------------- ΕΞΟΔΑ ----------------------
EXPENSES_FILE = "expenses.xlsx"
if "expenses_df" not in st.session_state:
    try:
        st.session_state["expenses_df"] = pd.read_excel(EXPENSES_FILE)
    except:
        st.session_state["expenses_df"] = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])

expenses_df = st.session_state["expenses_df"]

st.subheader("💰 Καταχώρηση Εξόδων")
with st.form("expenses_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
    with col3:
        exp_category = st.selectbox("Κατηγορία", ["Cleaning","Linen","Maintenance","Utilities","Supplies"])
    exp_amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f")
    exp_description = st.text_input("Περιγραφή (προαιρετική)")
    submitted = st.form_submit_button("➕ Καταχώρηση Εξόδου")

    if submitted:
        new_row = pd.DataFrame([{
            "Date": exp_date.strftime("%Y-%m-%d"),
            "Month": exp_date.month,
            "Accommodation": exp_accommodation,
            "Category": exp_category,
            "Amount": exp_amount,
            "Description": exp_description
        }])
        st.session_state["expenses_df"] = pd.concat([st.session_state["expenses_df"], new_row], ignore_index=True)
        st.experimental_rerun()

# ---------------------- Εμφάνιση Εξόδων ----------------------
st.subheader("💸 Καταχωρημένα Έξοδα")
def display_expenses(apartment):
    df_exp = st.session_state["expenses_df"]
    df_exp = df_exp[df_exp["Accommodation"]==apartment]
    if df_exp.empty:
        st.info("Δεν υπάρχουν έξοδα.")
        return
    container = st.container()
    for i, row in df_exp.iterrows():
        cols = container.columns([1,1,1,1,2,1])
        cols[0].write(row["Date"])
        cols[1].write(row["Accommodation"])
        cols[2].write(row["Category"])
        cols[3].write(f"{row['Amount']:.2f} €")
        cols[4].write(row["Description"])
        if cols[5].button("🗑️", key=f"del_{i}"):
            st.session_state["expenses_df"].drop(i, inplace=True)
            st.session_state["expenses_df"].reset_index(drop=True, inplace=True)
            st.experimental_rerun()

display_expenses(selected_apartment)
