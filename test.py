import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import os

# -------------------------------------------------------------
# Ρυθμίσεις
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
APARTMENT_ID = 750921
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

BOOKINGS_FILE = "bookings.xlsx"

# -------------------------------------------------------------
# Διαχείριση προηγούμενων κρατήσεων
# -------------------------------------------------------------
if os.path.exists(BOOKINGS_FILE):
    bookings_df = pd.read_excel(BOOKINGS_FILE)
else:
    bookings_df = pd.DataFrame()

# Υπολογισμός από πού να ξεκινήσει η κλήση API
if not bookings_df.empty:
    last_date_str = bookings_df["Arrival"].max()
    from_date = (datetime.strptime(last_date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
else:
    from_date = "2025-01-01"

to_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

params = {
    "from": from_date,
    "to": to_date,
    "apartmentId": APARTMENT_ID,
    "excludeBlocked": "true",
    "showCancellation": "true",
    "page": 1,
    "pageSize": 100,
}

# -------------------------------------------------------------
# Ανάκτηση νέων κρατήσεων
# -------------------------------------------------------------
new_bookings = []
while True:
    try:
        r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Σφάλμα σύνδεσης: {e}")
        break

    bookings = data.get("bookings", [])
    if not bookings:
        break
    new_bookings.extend(bookings)

    if data.get("page") and data.get("page") < data.get("page_count", 1):
        params["page"] += 1
    else:
        break

# -------------------------------------------------------------
# Υπολογισμοί
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

def compute_price_without_tax(price, nights, month):
    if not price or not nights:
        return 0.0
    base = 2 if month in [11,12,1,2] else 8
    adjusted = price - base * nights
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

# -------------------------------------------------------------
# Δημιουργία DataFrame για νέες κρατήσεις
# -------------------------------------------------------------
rows = []
for b in new_bookings:
    arrival_str = b.get("arrival")
    departure_str = b.get("departure")
    if not arrival_str or not departure_str:
        continue
    try:
        arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d")
        departure_dt = datetime.strptime(departure_str, "%Y-%m-%d")
    except:
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

        platform_lower = platform.lower().strip() if platform else ""
        if "expedia" in platform_lower:
            price = price / 0.82

        price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month)
        airstay_commission = round(price_wo_tax * 0.248, 2)
        fee = compute_booking_fee(platform, price)
        owner_profit = round(price_wo_tax - fee - airstay_commission, 2)

        rows.append({
            "ID": b.get("id"),
            "Apartment": apt.get("name"),
            "Guest Name": b.get("guestName") or b.get("guest-name"),
            "Arrival": arrival_dt.strftime("%Y-%m-%d"),
            "Departure": departure_dt.strftime("%Y-%m-%d"),
            "Days": days,
            "Platform": platform,
            "Guests": guests,
            "Total Price": round(price, 2),
            "Booking Fee": round(fee, 2),
            "Price Without Tax": round(price_wo_tax, 2),
            "Airstay Commission": round(airstay_commission, 2),
            "Owner Profit": round(owner_profit, 2),
            "Month": arrival_dt.month
        })

new_df = pd.DataFrame(rows)

# Αποφυγή διπλοτύπων βάσει ID
if not bookings_df.empty:
    new_df = new_df[~new_df["ID"].isin(bookings_df["ID"])]

# Ενημέρωση Excel
bookings_df = pd.concat([bookings_df, new_df], ignore_index=True)
bookings_df.to_excel(BOOKINGS_FILE, index=False)

df = bookings_df.copy()

# -------------------------------------------------------------
# Sidebar επιλογής μήνα
# -------------------------------------------------------------
st.sidebar.header("📅 Επιλογή Μήνα")
months_el = {
    1: "Ιανουάριος", 2: "Φεβρουάριος", 3: "Μάρτιος", 4: "Απρίλιος",
    5: "Μάιος", 6: "Ιούνιος", 7: "Ιούλιος", 8: "Αύγουστος",
    9: "Σεπτέμβριος", 10: "Οκτώβριος", 11: "Νοέμβριος", 12: "Δεκέμβριος"
}
month_options = ["Όλοι οι μήνες"] + [months_el[m] for m in sorted(months_el.keys())]
selected_month = st.sidebar.selectbox("Διάλεξε μήνα", month_options)

if selected_month != "Όλοι οι μήνες":
    month_index = [k for k,v in months_el.items() if v==selected_month][0]
    filtered_df = df[df["Month"]==month_index]
else:
    filtered_df = df.copy()

filtered_df = filtered_df.sort_values(["Month","Apartment","Arrival"])

# ---------------------------
# Υπολογισμός totals με ασφαλή μετατροπή
# ---------------------------
total_price = pd.to_numeric(filtered_df["Total Price"], errors="coerce").sum()
total_owner_profit = pd.to_numeric(filtered_df["Owner Profit"], errors="coerce").sum()
total_airstay = pd.to_numeric(filtered_df["Airstay Commission"], errors="coerce").sum()

col1, col2, col3 = st.columns(3)
col1.metric("💰 Συνολική Τιμή Κρατήσεων", f"{total_price:.2f} €")
col2.metric("📊 Συνολικό Κέρδος Ιδιοκτήτη", f"{total_owner_profit:.2f} €")
col3.metric("💼 Συνολική Airstay Commission", f"{total_airstay:.2f} €")

# ---------------------------
# Πίνακας κρατήσεων
# ---------------------------
st.subheader(f"📅 Κρατήσεις ({selected_month})")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)
