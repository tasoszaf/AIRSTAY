import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import os

# -------------------------------------------------------------
# 🎯 Ρυθμίσεις
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
APARTMENT_ID = 750921
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# 📦 Αρχεία αποθήκευσης
# -------------------------------------------------------------
BOOKINGS_FILE = "bookings_history.xlsx"
EXPENSES_FILE = "expenses.xlsx"

# Φόρτωση προηγούμενων κρατήσεων
if os.path.exists(BOOKINGS_FILE):
    old_bookings_df = pd.read_excel(BOOKINGS_FILE)
else:
    old_bookings_df = pd.DataFrame()

# Φόρτωση προηγούμενων εξόδων
if os.path.exists(EXPENSES_FILE):
    expenses_df = pd.read_excel(EXPENSES_FILE)
else:
    expenses_df = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# 📅 Ημερομηνίες για κατέβασμα νέων κρατήσεων
# -------------------------------------------------------------
if not old_bookings_df.empty:
    last_saved_date = old_bookings_df["Arrival"].max()
    from_date = (datetime.strptime(last_saved_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
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
# 📦 Ανάκτηση νέων κρατήσεων
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
# 🧱 Δημιουργία DataFrame νέων κρατήσεων
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

rows = []
for b in new_bookings:
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
    ch = b.get("channel", {}) or {}
    platform = ch.get("name") or "Direct booking"

    price = float(b.get("price") or 0)

    # 🔹 Αν η πλατφόρμα είναι Expedia, διαιρούμε με 0.82
    if "Expedia" in platform.strip().lower():
        price = round(price / 0.82, 2)

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
        "Total Price": price,
        "Booking Fee": fee,
        "Price Without Tax": price_wo_tax,
        "Owner Profit": owner_profit,
        "Month": arrival_dt.month
    })

new_bookings_df = pd.DataFrame(rows)

# -------------------------------------------------------------
# Συνένωση με παλιές κρατήσεις και αποθήκευση
# -------------------------------------------------------------
if not old_bookings_df.empty:
    bookings_df = pd.concat([old_bookings_df, new_bookings_df], ignore_index=True)
else:
    bookings_df = new_bookings_df.copy()

# Σιγουρεύουμε ότι οι στήλες είναι numeric
numeric_cols = ["Total Price","Booking Fee","Price Without Tax","Owner Profit"]
for col in numeric_cols:
    bookings_df[col] = pd.to_numeric(bookings_df[col], errors='coerce').fillna(0)

bookings_df.to_excel(BOOKINGS_FILE, index=False)

# -------------------------------------------------------------
# Σιγουρεύουμε ότι τα έξοδα είναι numeric
# -------------------------------------------------------------
if not expenses_df.empty:
    expenses_df["Amount"] = pd.to_numeric(expenses_df["Amount"], errors='coerce').fillna(0)
else:
    expenses_df["Amount"] = 0.0

# -------------------------------------------------------------
# Sidebar: επιλογή μήνα
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
    filtered_df = bookings_df[bookings_df["Month"]==month_index]
else:
    filtered_df = bookings_df.copy()
filtered_df = filtered_df.sort_values(["Month","Apartment","Arrival"])

# -------------------------------------------------------------
# Υπολογισμός totals
# -------------------------------------------------------------
total_price = filtered_df["Total Price"].sum()
total_owner_profit = filtered_df["Owner Profit"].sum()
total_expenses = expenses_df["Amount"].sum() if not expenses_df.empty else 0.0
net_owner_profit = total_owner_profit - total_expenses

# ---------------------------
# 1️⃣ Κουτάκια με συνολικά
# ---------------------------
col1, col2, col3 = st.columns(3)
col1.metric("💰 Συνολική Τιμή Κρατήσεων", f"{total_price:.2f} €")
col2.metric("🧾 Συνολικά Έξοδα", f"{total_expenses:.2f} €")
col3.metric("📊 Καθαρό Κέρδος Ιδιοκτήτη", f"{net_owner_profit:.2f} €")

# ---------------------------
# 2️⃣ Πίνακας κρατήσεων
# ---------------------------
st.subheader(f"📅 Κρατήσεις ({selected_month})")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# ---------------------------
# 3️⃣ Καταχώρηση & εμφάνιση εξόδων
# ---------------------------
st.subheader("💰 Καταχώρηση Εξόδων")
with st.form("expenses_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα", ["Kalista"])
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
            "Amount": round(exp_amount,2),
            "Description": exp_description,
        }])
        expenses_df = pd.concat([expenses_df, new_row], ignore_index=True)
        expenses_df.to_excel(EXPENSES_FILE, index=False)
        st.success("✔️ Έξοδο καταχωρήθηκε!")

st.subheader("💸 Καταχωρημένα Έξοδα")
st.dataframe(expenses_df, use_container_width=True, hide_index=True)
