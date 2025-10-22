import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import requests

# ---------------------- ΡΥΘΜΙΣΕΙΣ ----------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# ---------------------- Καταλύματα ----------------------
APARTMENTS = {
    "ZED": [1439913,1439915,1439917,1439919,1439921,1439923,1439925,1439927,1439929,
            1439931,1439933,1439935,1439937,1439939,1439971,1439973,1439975,1439977,
            1439979,1439981,1439983,1439985],
    "KOMOS": [2160281,2160286,2160291],
    "CHELI": [2146456,2146461],
    "AKALI": [1713746],
    "NAMI": [1275248],
    "THRESH": [563628,563631,1200587,563634,563637,563640,563643],
    "ZILEAN": [1756004,1756007,1756010,1756013,1756016,1756019,1756022,1756025,1756031],
    "NAUTILUS": [563712,563724,563718,563721,563715,563727],
    "ANIVIA": [563703,563706],
    "ELISE": [563625,1405415],
    "ORIANNA": [1607131],
    "KALISTA": [750921],
    "JAAX": [2712218],
    "FINIKAS": [2715193,2715198,2715203,2715208,2715213,2715218,2715223,2715228,2715233,2715238,2715273]
}

APARTMENT_SETTINGS = {
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "KALISTA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248},
    "KOMOS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "CHELI": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "AKALI": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0},
    "ZILEAN": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "NAUTILUS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.186},
    "ANIVIA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248},
    "ELISE": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248},
    "ORIANNA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248},
    "JAAX": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.0},
    "FINIKAS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
}

months_el = {
    1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
    7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"
}

# ---------------------- Συναρτήσεις ----------------------
def compute_price_without_tax(price, nights, month, apt_name):
    settings = APARTMENT_SETTINGS.get(apt_name, {"winter_base": 2, "summer_base": 8})
    base = settings["winter_base"] if month in [11,12,1,2] else settings["summer_base"]
    adjusted = price - base * nights
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

def compute_booking_fee(platform_name: str, price: float) -> float:
    p = platform_name.strip().lower() if platform_name else ''
    if p in {"website","direct","direct booking","direct-booking","site","web"}:
        rate = 0.0
    elif "booking" in p:
        rate = 0.17
    elif "airbnb" in p:
        rate = 0.15
    elif "expedia" in p:
        rate = 0.18
    else:
        rate = 0.0
    return round((price or 0) * rate, 2)

# ---------------------- Fetch κρατήσεων ----------------------
@st.cache_data(ttl=3600)
def fetch_all_reservations():
    all_rows = []
    from_date = "2025-01-01"
    to_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    for apt_name, id_list in APARTMENTS.items():
        for apt_id in id_list:
            params = {"from": from_date, "to": to_date,
                      "apartmentId": apt_id, "excludeBlocked": "true",
                      "showCancellation": "true", "page": 1, "pageSize": 100}
            try:
                r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
                data = r.json()
            except:
                continue
            for b in data.get("bookings", []):
                arrival = b.get("arrival")
                departure = b.get("departure")
                if not arrival or not departure: continue
                arrival_dt = datetime.strptime(arrival, "%Y-%m-%d")
                departure_dt = datetime.strptime(departure, "%Y-%m-%d")
                platform = (b.get("channel") or {}).get("name") or "Direct booking"
                price = float(b.get("price") or 0)
                days = max((departure_dt - arrival_dt).days, 0)
                if "expedia" in platform.lower(): price /= 0.82
                price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month, apt_name)
                fee = compute_booking_fee(platform, price)
                settings = APARTMENT_SETTINGS.get(apt_name, {"airstay_commission":0.248})
                airstay_commission = round(price_wo_tax*settings["airstay_commission"],2)
                owner_profit = round(price_wo_tax - fee - airstay_commission, 2)
                all_rows.append({
                    "Apartment": apt_name,
                    "Arrival": arrival_dt,
                    "Departure": departure_dt,
                    "Days": days,
                    "Platform": platform,
                    "Total Price": round(price,2),
                    "Booking Fee": round(fee,2),
                    "Owner Profit": owner_profit,
                    "Month": arrival_dt.month
                })
    return pd.DataFrame(all_rows)

# ---------------------- Φόρτωση δεδομένων ----------------------
df_all = fetch_all_reservations()

# ---------------------- Sidebar ----------------------
st.sidebar.header("🏠 Φίλτρα")
selected_apartment = st.sidebar.selectbox("Κατάλυμα", ["Όλα"] + list(APARTMENTS.keys()))
selected_month = st.sidebar.selectbox("Μήνας", ["Όλοι"] + [months_el[m] for m in range(1,13)])

# ---------------------- Φίλτρα ----------------------
if selected_apartment != "Όλα":
    df_filtered = df_all[df_all["Apartment"] == selected_apartment]
else:
    df_filtered = df_all.copy()

if selected_month != "Όλοι":
    month_num = [k for k,v in months_el.items() if v == selected_month][0]
    df_filtered = df_filtered[df_filtered["Month"] == month_num]

# ---------------------- Φόρτωση εξόδων ----------------------
EXPENSES_FILE = "expenses.xlsx"
if "expenses_df" not in st.session_state:
    try:
        st.session_state["expenses_df"] = pd.read_excel(EXPENSES_FILE)
    except:
        st.session_state["expenses_df"] = pd.DataFrame(columns=["Date","Accommodation","Category","Amount","Description"])

df_exp = st.session_state["expenses_df"].copy()
df_exp["Date"] = pd.to_datetime(df_exp["Date"], errors="coerce")

# φίλτρο εξόδων με βάση κατάλυμα και μήνα
if selected_apartment != "Όλα":
    df_exp = df_exp[df_exp["Accommodation"] == selected_apartment]
if selected_month != "Όλοι":
    df_exp = df_exp[df_exp["Date"].dt.month == month_num]

# ---------------------- Υπολογισμός στατιστικών ----------------------
total_income = df_filtered["Total Price"].sum()
total_expenses = df_exp["Amount"].sum()
total_owner_profit = df_filtered["Owner Profit"].sum() - total_expenses

# ---------------------- ΠΑΝΩ ΚΟΥΤΑΚΙΑ ----------------------
col1, col2, col3 = st.columns(3)
col1.metric("💰 Συνολικά Έσοδα", f"{total_income:,.2f} €")
col2.metric("💸 Συνολικά Έξοδα", f"{total_expenses:,.2f} €")
col3.metric("🏠 Owner Profit", f"{total_owner_profit:,.2f} €")

# ---------------------- Πίνακας κρατήσεων ----------------------
st.subheader("📅 Κρατήσεις")
df_display = df_filtered.copy()
df_display["Month"] = df_display["Month"].map(months_el)
st.dataframe(df_display, use_container_width=True)

# ---------------------- Καταχώρηση εξόδων ----------------------
st.subheader("💰 Καταχώρηση Εξόδων")
with st.form("expenses_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
    with col3:
        exp_category = st.selectbox("Κατηγορία", ["Cleaning","Linen","Maintenance","Utilities","Supplies","Other"])
    exp_amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f")
    exp_description = st.text_input("Περιγραφή (προαιρετική)")
    submitted = st.form_submit_button("➕ Καταχώρηση Εξόδου")
    if submitted:
        new_row = pd.DataFrame([{
            "Date": exp_date.strftime("%Y-%m-%d"),
            "Accommodation": exp_accommodation,
            "Category": exp_category,
            "Amount": exp_amount,
            "Description": exp_description
        }])
        st.session_state["expenses_df"] = pd.concat([st.session_state["expenses_df"], new_row], ignore_index=True)
        st.success("✅ Το έξοδο καταχωρήθηκε!")

# ---------------------- Εμφάνιση εξόδων ----------------------
st.subheader("💸 Καταχωρημένα Έξοδα")
st.dataframe(df_exp, use_container_width=True)
