import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import os

# ---------------------- ΡΥΘΜΙΣΕΙΣ STREAMLIT ----------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# ---------------------- CACHE ----------------------
DATA_DIR = "cached_reservations"
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------- ΚΑΤΑΛΥΜΑΤΑ & ΡΥΘΜΙΣΕΙΣ ----------------------
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
    "FINIKAS": [2715193,2715198,2715203,2715208,2715213,
                2715218,2715223,2715228,2715233,2715238,2715273]
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

# ---------------------- CACHE ----------------------
def load_cached_month(apt_name, month_idx):
    file_path = os.path.join(DATA_DIR, f"{apt_name}_{month_idx:02d}.xlsx")
    if os.path.exists(file_path):
        try:
            return pd.read_excel(file_path)
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def save_month_cache(apt_name, month_idx, df):
    file_path = os.path.join(DATA_DIR, f"{apt_name}_{month_idx:02d}.xlsx")
    df.to_excel(file_path, index=False)

# ---------------------- SIDEBAR ----------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
apartment_options = list(APARTMENTS.keys())
selected_apartment = st.sidebar.selectbox("Κατάλυμα", apartment_options)

months_el = {
    1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
    7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"
}
month_options = ["Όλοι οι μήνες"] + [months_el[m] for m in range(1,13)]
selected_month = st.selectbox("📅 Επιλογή Μήνα", month_options)

# ---------------------- ΛΗΨΗ ΚΡΑΤΗΣΕΩΝ ----------------------
def fetch_reservations_for_month(apt_name, month_idx):
    all_rows = []
    month_start = date(2025, month_idx, 1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    from_date = month_start.strftime("%Y-%m-%d")
    to_date = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")

    for apt_id in APARTMENTS[apt_name]:
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
                try:
                    arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d")
                    departure_dt = datetime.strptime(departure_str, "%Y-%m-%d")
                except:
                    continue
                if arrival_dt.year != 2025:
                    continue
                # Φιλτράρισμα μέχρι χθες
                if arrival_dt.date() > date.today() - timedelta(days=1):
                    continue
                # Φιλτράρισμα μήνα άφιξης
                if arrival_dt.month != month_idx:
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

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["ID"])
    return df

# ---------------------- ΦΟΡΤΩΣΗ ΑΠΟ CACHE Ή API ----------------------
if selected_month == "Όλοι οι μήνες":
    dfs = []
    for m in range(1,13):
        df_month = load_cached_month(selected_apartment, m)
        if df_month.empty:
            df_month = fetch_reservations_for_month(selected_apartment, m)
            save_month_cache(selected_apartment, m, df_month)
        dfs.append(df_month)
    filtered_df = pd.concat(dfs, ignore_index=True)
else:
    month_idx = [k for k,v in months_el.items() if v==selected_month][0]
    filtered_df = load_cached_month(selected_apartment, month_idx)
    if filtered_df.empty:
        filtered_df = fetch_reservations_for_month(selected_apartment, month_idx)
        save_month_cache(selected_apartment, month_idx, filtered_df)

# ---------------------- ΕΞΟΔΑ ----------------------
EXPENSES_FILE = "expenses.xlsx"
if "expenses_df" not in st.session_state:
    try:
        st.session_state["expenses_df"] = pd.read_excel(EXPENSES_FILE)
    except:
        st.session_state["expenses_df"] = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])
expenses_df = st.session_state["expenses_df"]

filtered_expenses = expenses_df[expenses_df["Accommodation"]==selected_apartment]
if selected_month != "Όλοι οι μήνες":
    filtered_expenses = filtered_expenses[filtered_expenses["Month"]==month_idx]

def parse_amount(v):
    try:
        return float(str(v).replace("€","").strip())
    except:
        return 0.0

total_price = filtered_df["Total Price"].sum()
total_owner_profit = filtered_df["Owner Profit"].sum()
total_expenses = filtered_expenses["Amount"].apply(parse_amount).sum()
net_profit = total_owner_profit - total_expenses

# ---------------------- METRICS ----------------------
col1, col2, col3 = st.columns(3)
col1.metric("💰 Συνολική Τιμή Κρατήσεων", f"{total_price:.2f} €")
col2.metric("🧾 Συνολικά Έξοδα", f"{total_expenses:.2f} €")
col3.metric("📊 Κέρδος Ιδιοκτήτη", f"{net_profit:.2f} €")

# ---------------------- ΠΙΝΑΚΑΣ ΚΡΑΤΗΣΕΩΝ ----------------------
st.subheader(f"📅 Κρατήσεις ({selected_apartment} – {selected_month})")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# ---------------------- ΚΑΤΑΧΩΡΗΣΗ ΕΞΟΔΩΝ ----------------------
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

# ---------------------- ΕΜΦΑΝΙΣΗ ΕΞΟΔΩΝ ----------------------
st.subheader("💸 Καταχωρημένα Έξοδα")
def display_expenses(apartment, month):
    df_exp = st.session_state["expenses_df"]
    df_exp = df_exp[df_exp["Accommodation"]==apartment]
    if month != "Όλοι οι μήνες":
        month_idx = [k for k,v in months_el.items() if v==month][0]
        df_exp = df_exp[df_exp["Month"]==month_idx]
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

display_expenses(selected_apartment, selected_month)
