import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import os

# -------------------------------------------------------------
# 🎯 Ρυθμίσεις
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("📊 Smoobu Reservations Dashboard (2025 μέχρι χθες)")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"

# -------------------------------------------------------------
# 🔹 Ομάδες καταλυμάτων + υποκατηγορίες THRESH
# -------------------------------------------------------------
groups = {
    "ZED": [1439913, 1439915, 1439917, 1439919, 1439921, 1439923, 1439925, 1439927, 
             1439929, 1439931, 1439933, 1439935, 1439937, 1439939, 1439971, 1439973, 
             1439975, 1439977, 1439979, 1439981, 1439983, 1439985],
    "KOMOS": [2160281, 2160286, 2160291],
    "CHELI": [2146456, 2146461],
    "AKALI": [1713746],
    "NAMI": [1275248],
    "THRESH_A3": [1200587],
    "THRESH_A4": [563634],
    "THRESH_OTHER": [563628, 563631, 563637, 563640, 563643],
    "ZILEAN": [1756004, 1756007, 1756010, 1756013, 1756016, 1756019, 1756022, 1756025, 1756031],
    "NAUTILUS": [563712, 563724, 563718, 563721, 563715, 563727],
    "ANIVIA": [563703, 563706],
    "ELISE": [563625, 1405415],
    "ORIANNA": [1607131],
    "KALISTA": [750921],
    "JAAX": [2712218],
    "FINIKAS": [2715193,2715198,2715203,2715208,2715213,
                 2715218,2715223,2715228,2715233, 2715238,2715273]
}

# -------------------------------------------------------------
# 🔹 Ρυθμίσεις API
# -------------------------------------------------------------
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# 🔹 Sidebar φίλτρα
# -------------------------------------------------------------
st.sidebar.header("Φίλτρα")
months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",
             6:"Ιούνιος",7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",
             11:"Νοέμβριος",12:"Δεκέμβριος"}
month_options = ["Όλοι οι μήνες"] + [months_el[m] for m in sorted(months_el.keys())]
selected_month = st.sidebar.selectbox("Διάλεξε μήνα", month_options)
group_options = ["Όλα"] + list(groups.keys())
selected_group = st.sidebar.selectbox("Διάλεξε Κατάλυμα/Group", group_options)

# -------------------------------------------------------------
# 🔹 Ορισμός ημερομηνιών fetch για τον επιλεγμένο μήνα
# -------------------------------------------------------------
if selected_month != "Όλοι οι μήνες":
    month_index = [k for k,v in months_el.items() if v==selected_month][0]
    year = 2025
    start_date = datetime(year, month_index, 1).strftime("%Y-%m-%d")
    if month_index == 12:
        end_date = datetime(year, 12, 31).strftime("%Y-%m-%d")
    else:
        end_date = (datetime(year, month_index+1, 1) - timedelta(days=1)).strftime("%Y-%m-%d")
else:
    start_date = "2025-01-01"
    end_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

# -------------------------------------------------------------
# 🔹 Συνάρτηση fetch
# -------------------------------------------------------------
def fetch_bookings(start_date: str, end_date: str):
    params = {
        "from": start_date,
        "to": end_date,
        "excludeBlocked": "true",
        "showCancellation": "true",
        "page": 1,
        "pageSize": 100,
    }
    all_bookings = []
    while True:
        try:
            r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            bookings = data.get("bookings", [])
            if not bookings:
                break
            all_bookings.extend(bookings)
            if data.get("page") and data.get("page") < data.get("page_count", 1):
                params["page"] += 1
            else:
                break
        except requests.exceptions.RequestException as e:
            st.warning(f"❌ Σφάλμα API: {e}")
            break
    return all_bookings

try:
    all_bookings = fetch_bookings(start_date, end_date)
except Exception as e:
    st.error(f"❌ Σφάλμα API: {e}")
    all_bookings = []

# -------------------------------------------------------------
# 🔹 Υπολογισμοί για κρατήσεις
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

def parse_amount_euro(value):
    try:
        return float(str(value).replace(" €",""))
    except:
        return 0.0

def get_group_for_id(apartment_id):
    for grp, ids in groups.items():
        if apartment_id in ids:
            return grp
    return "UNKNOWN"

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

    apt = b.get("apartment", {}) or {}
    platform = (b.get("channel", {}) or {}).get("name") or "Direct booking"
    price = float(b.get("price") or 0)
    adults = int(b.get("adults") or 0)
    children = int(b.get("children") or 0)
    guests = adults + children
    days = max((departure_dt - arrival_dt).days, 0)
    fee = compute_booking_fee(platform, price)
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
        "Total Price": f"{round(price,2):.2f} €",
        "Booking Fee": f"{fee:.2f} €",
        "Owner Profit": f"{owner_profit:.2f} €",
        "Month": arrival_dt.month,
        "Group": get_group_for_id(b.get("id"))
    })

df = pd.DataFrame(rows)
if "Month" not in df.columns:
    df["Month"] = pd.to_datetime(df["Arrival"]).dt.month

# -------------------------------------------------------------
# Συνεχίζεται το υπόλοιπο script: φιλτράρισμα, totals, εμφάνιση ανά Group, έξοδα...
# -------------------------------------------------------------
