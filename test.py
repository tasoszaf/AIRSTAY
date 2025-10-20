import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import os
import pickle
from pathlib import Path

# -------------------------------------------------------------
# 🎯 Ρυθμίσεις
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# 🏘️ Ορισμός Ομάδων Καταλυμάτων
# -------------------------------------------------------------
groups = {
    "ZED": [1439913, 1439915, 1439917, 1439919, 1439921, 1439923, 1439925, 1439927,
             1439929, 1439931, 1439933, 1439935, 1439937, 1439939, 1439971, 1439973,
             1439975, 1439977, 1439979, 1439981, 1439983, 1439985],
    "KOMOS": [2160281, 2160286, 2160291],
    "CHELI": [2146456, 2146461],
    "AKALI": [1713746],
    "NAMI": [1275248],
    "THRESH": [563628, 563631, 1200587, 563634, 563637, 563640, 563643],
    "ZILEAN": [1756004, 1756007, 1756010, 1756013, 1756016, 1756019, 1756022, 1756025, 1756031],
    "NAUTILUS": [563712, 563724, 563718, 563721, 563715, 563727],
    "ANIVIA": [563703, 563706],
    "ELISE": [563625, 1405415],
    "ORIANNA": [1607131],
    "KALISTA": [750921],
    "JAAX": [2712218],
    "FINIKAS": [2715193,2715198,2715203,2715208,2715213,
                 2715218,2715223,2715228,2715233,2715238,2715273]
}

# -------------------------------------------------------------
# 🧭 Επιλογή Ομάδας (sidebar)
# -------------------------------------------------------------
st.sidebar.header("🏘️ Επιλογή Ομάδας Καταλυμάτων")
selected_group = st.sidebar.selectbox("Διάλεξε ομάδα", list(groups.keys()))
apartment_ids = groups[selected_group]

# -------------------------------------------------------------
# 📅 Δημιουργία λίστας μηνών για 2025
# -------------------------------------------------------------
def month_ranges(year: int):
    ranges = []
    for month in range(1, 13):
        start = date(year, month, 1)
        if month == 12:
            end = date(year, 12, 31)
        else:
            end = date(year, month + 1, 1) - timedelta(days=1)
        ranges.append((start, end))
    return ranges

year = 2025
month_periods = month_ranges(year)

# -------------------------------------------------------------
# 💾 Cache setup
# -------------------------------------------------------------
CACHE_DIR = Path("smoobu_cache")
CACHE_DIR.mkdir(exist_ok=True)

def cache_file(group: str, year: int, month: int) -> Path:
    return CACHE_DIR / f"{group}_{year}_{month:02d}.pkl"

def load_cached_bookings(group: str, year: int, month: int):
    path = cache_file(group, year, month)
    if path.exists():
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None
    return None

def save_cached_bookings(group: str, year: int, month: int, data):
    path = cache_file(group, year, month)
    with open(path, "wb") as f:
        pickle.dump(data, f)

# -------------------------------------------------------------
# 📦 Ανάκτηση κρατήσεων (με caching μόνο για παρελθόντες μήνες)
# -------------------------------------------------------------
today = date.today()
all_bookings = []
progress = st.progress(0)
step = 0
total_steps = len(apartment_ids) * len(month_periods)

for apt_id in apartment_ids:
    for (from_dt, to_dt) in month_periods:
        # Αγνόησε μελλοντικούς μήνες
        if to_dt > today:
            step += 1
            progress.progress(step / total_steps)
            continue

        # Cache μόνο για μήνες που έχουν ολοκληρωθεί
        use_cache = to_dt < date(today.year, today.month, 1)
        cached = load_cached_bookings(selected_group, year, from_dt.month) if use_cache else None

        if cached is not None:
            all_bookings.extend(cached)
            step += 1
            progress.progress(step / total_steps)
            continue

        params = {
            "from": from_dt.strftime("%Y-%m-%d"),
            "to": to_dt.strftime("%Y-%m-%d"),
            "apartmentId": apt_id,
            "excludeBlocked": "true",
            "showCancellation": "true",
            "page": 1,
            "pageSize": 100,
        }

        month_bookings = []
        while True:
            try:
                r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Σφάλμα ({apt_id}, {from_dt:%b}): {e}")
                break

            bookings = data.get("bookings", [])
            if not bookings:
                break
            month_bookings.extend(bookings)

            if data.get("page") and data.get("page") < data.get("page_count", 1):
                params["page"] += 1
            else:
                break

        all_bookings.extend(month_bookings)
        if use_cache:
            save_cached_bookings(selected_group, year, from_dt.month, month_bookings)

        step += 1
        progress.progress(step / total_steps)

progress.empty()
st.success(f"✅ Φορτώθηκαν {len(all_bookings)} κρατήσεις για την ομάδα: {selected_group}")

# -------------------------------------------------------------
# 🧮 Υπολογισμοί
# -------------------------------------------------------------
def compute_booking_fee(platform_name: str, price: float) -> float:
    if not platform_name:
        return 0.0
    p = platform_name.strip().lower()
    if p in {"website", "direct", "direct booking", "direct-booking", "site", "web"}:
        rate = 0.00
    elif "booking" in p:
        rate = 0.17
    elif "airbnb" in p:
        rate = 0.15
    elif "expedia" in p:
        rate = 0.18
    else:
        rate = 0.00
    return round((price or 0) * rate, 2)

def price_without_tax(price: float, vat: float = 0.13) -> float:
    if not price:
        return 0.0
    return round(price / (1 + vat), 2)

# -------------------------------------------------------------
# 🧱 Δημιουργία DataFrame κρατήσεων
# -------------------------------------------------------------
rows = []
for b in all_bookings:
    arrival_str = b.get("arrival")
    departure_str = b.get("departure")
    if not arrival_str or not departure_str:
        continue
    try:
        arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d")
        departure_dt = datetime.strptime(departure_str, "%Y-%m-%d")
    except Exception:
        continue
    if arrival_dt.year == 2025:
        apt = b.get("apartment", {}) or {}
        ch = b.get("channel", {}) or {}
        platform = ch.get("name") or "Direct booking"
        price = float(b.get("price") or 0)
        adults = int(b.get("adults") or 0)
        children = int(b.get("children") or 0)
        guests = adults + children
        days = max((departure_dt - arrival_dt).days, 0)
        fee = compute_booking_fee(platform, price)
        price_wo_tax = price_without_tax(price, vat=0.13)
        owner_profit = round(price - fee, 2)
        rows.append({
            "ID": b.get("id"),
            "Apartment": apt.get("name"),
            "Guest Name": b.get("guestName") or b.get("guest-name"),
            "Arrival": arrival_dt.strftime("%Y-%m-%d"),
            "Departure": departure_dt.strftime("%Y-%m-%d"),
            "Days": days,
            "Platform": platform,
            "Guests": guests,
            "Total Price": f"{round(price, 2):.2f} €",
            "Booking Fee": f"{fee:.2f} €",
            "Price Without Tax": f"{price_wo_tax:.2f} €",
            "Owner Profit": f"{owner_profit:.2f} €",
            "Month": arrival_dt.month
        })

if not rows:
    st.info("Δεν βρέθηκαν κρατήσεις.")
    st.stop()

df = pd.DataFrame(rows)

# -------------------------------------------------------------
# Sidebar filters, metrics & expenses (όπως πριν)
# -------------------------------------------------------------
months_el = {
    1: "Ιανουάριος", 2: "Φεβρουάριος", 3: "Μάρτιος", 4: "Απρίλιος",
    5: "Μάιος", 6: "Ιούνιος", 7: "Ιούλιος", 8: "Αύγουστος",
    9: "Σεπτέμβριος", 10: "Οκτώβριος", 11: "Νοέμβριος", 12: "Δεκέμβριος"
}

st.sidebar.header("📅 Επιλογή Μήνα")
month_options = [months_el[m] for m in sorted(months_el.keys())]
selected_month = st.sidebar.selectbox("Διάλεξε μήνα", month_options)
month_index = [k for k, v in months_el.items() if v == selected_month][0]

filtered_df = df[df["Month"] == month_index].sort_values(["Apartment", "Arrival"])

# -------------------------------------------------------------
# Έξοδα
# -------------------------------------------------------------
EXPENSES_FILE = f"expenses_{selected_group}.xlsx"

if "expenses_df" not in st.session_state:
    if os.path.exists(EXPENSES_FILE):
        st.session_state["expenses_df"] = pd.read_excel(EXPENSES_FILE)
    else:
        st.session_state["expenses_df"] = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])

expenses_df = st.session_state["expenses_df"].copy()

def parse_amount_euro(value):
    try:
        return float(str(value).replace(" €",""))
    except:
        return 0.0

total_price = filtered_df["Total Price"].apply(parse_amount_euro).sum()
total_owner_profit = filtered_df["Owner Profit"].apply(parse_amount_euro).sum()
total_expenses = expenses_df[expenses_df["Month"]==month_index]["Amount"].apply(parse_amount_euro).sum()
net_profit = total_owner_profit - total_expenses

col1, col2, col3 = st.columns(3)
col1.metric("💰 Συνολική Τιμή", f"{total_price:.2f} €")
col2.metric("🧾 Έξοδα", f"{total_expenses:.2f} €")
col3.metric("📊 Κέρδος Ιδιοκτήτη", f"{net_profit:.2f} €")

st.subheader(f"📅 Κρατήσεις ({selected_month})")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# Καταχώρηση Εξόδων
# -------------------------------------------------------------
st.subheader("💰 Καταχώρηση Εξόδων")
with st.form("expenses_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα", ["All", *df["Apartment"].dropna().unique()])
    with col3:
        exp_category = st.selectbox("Κατηγορία", ["Cleaning", "Linen", "Maintenance", "Utilities", "Supplies"])
    exp_amount = st.number_input("Ποσό", min_value=0.0, format="%.2f")
    exp_description = st.text_input("Περιγραφή (προαιρετική)")
    submitted = st.form_submit_button("➕ Καταχώρηση Εξόδου")

    if submitted:
        new_row = pd.DataFrame([{
            "Date": exp_date.strftime("%Y-%m-%d"),
            "Month": exp_date.month,
            "Accommodation": exp_accommodation,
            "Category": exp_category,
            "Amount": f"{exp_amount:.2f} €",
            "Description": exp_description,
        }])
        st.session_state["expenses_df"] = pd.concat([st.session_state["expenses_df"], new_row], ignore_index=True)
        st.session_state["expenses_df"].to_excel(EXPENSES_FILE, index=False)

st.subheader("💸 Καταχωρημένα Έξοδα")
if st.session_state["expenses_df"].empty:
    st.info("Δεν υπάρχουν καταχωρημένα έξοδα.")
else:
    for i, row in st.session_state["expenses_df"].iterrows():
        cols = st.columns([1,1,1,1,2,1])
        cols[0].write(row["Date"])
        cols[1].write(row["Accommodation"])
        cols[2].write(row["Category"])
        cols[3].write(row["Amount"])
        cols[4].write(row["Description"])
        if cols[5].button("🗑️", key=f"del_{i}"):
            st.session_state["expenses_df"].drop(i, inplace=True)
            st.session_state["expenses_df"].reset_index(drop=True, inplace=True)
            st.session_state["expenses_df"].to_excel(EXPENSES_FILE, index=False)
            st.experimental_rerun()
