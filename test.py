import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta

# -------------------------------------------------------------
# 🎯 Ρυθμίσεις
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("📊 Smoobu Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
APARTMENT_ID = 750921

headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# 📅 Ημερομηνίες
# -------------------------------------------------------------
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
# 📦 Ανάκτηση κρατήσεων
# -------------------------------------------------------------
all_bookings = []
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
    all_bookings.extend(bookings)

    if data.get("page") and data.get("page") < data.get("page_count", 1):
        params["page"] += 1
    else:
        break

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
            "Owner Profit": f"{owner_profit:.2f} €"
        })

if not rows:
    st.info(f"Δεν βρέθηκαν κρατήσεις για το διάστημα {from_date} έως {to_date}.")
    st.stop()

df = pd.DataFrame(rows)

# -------------------------------------------------------------
# Φίλτρο μήνα (sidebar)
# -------------------------------------------------------------
st.sidebar.header("📅 Επιλογή Μήνα")
months_el = {
    1: "Ιανουάριος", 2: "Φεβρουάριος", 3: "Μάρτιος", 4: "Απρίλιος",
    5: "Μάιος", 6: "Ιούνιος", 7: "Ιούλιος", 8: "Αύγουστος",
    9: "Σεπτέμβριος", 10: "Οκτώβριος", 11: "Νοέμβριος", 12: "Δεκέμβριος"
}
df["Month"] = pd.to_datetime(df["Arrival"]).dt.month

month_options = ["Όλοι οι μήνες"] + [months_el[m] for m in sorted(months_el.keys())]
selected_month = st.sidebar.selectbox("Διάλεξε μήνα", month_options)

if selected_month != "Όλοι οι μήνες":
    filtered_df = df[df["Month"].map(months_el) == selected_month]
else:
    filtered_df = df.copy()

filtered_df = filtered_df.sort_values(["Month", "Apartment", "Arrival"])

# -------------------------------------------------------------
# Session state για έξοδα
# -------------------------------------------------------------
if "expenses_df" not in st.session_state:
    st.session_state["expenses_df"] = pd.DataFrame(columns=["Date", "Accommodation", "Category", "Amount", "Description"])

# -------------------------------------------------------------
# Συνάρτηση parse για € amounts
# -------------------------------------------------------------
def parse_amount_euro(value):
    """Μετατρέπει string '123.45 €' σε float 123.45"""
    try:
        return float(str(value).replace(" €", ""))
    except:
        return 0.0

# -------------------------------------------------------------
# Υπολογισμός συνολικών
# -------------------------------------------------------------
total_price = filtered_df["Total Price"].apply(parse_amount_euro).sum()
total_owner_profit = filtered_df["Owner Profit"].apply(parse_amount_euro).sum()
total_price_wo_tax = filtered_df["Price Without Tax"].apply(parse_amount_euro).sum()
total_expenses = st.session_state["expenses_df"]["Amount"].apply(parse_amount_euro).sum()

total_owner_profit_after_expenses = total_owner_profit - total_expenses
total_price_wo_tax_after_expenses = total_price_wo_tax - total_expenses

# -------------------------------------------------------------
# Εμφάνιση συνολικών σε κουτάκια
# -------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("💰 Συνολική Τιμή Κρατήσεων", f"{total_price:.2f} €")
col2.metric("🧾 Συνολικές Δαπάνες", f"{total_expenses:.2f} €")
col3.metric("📊 Καθαρό Κέρδος Ιδιοκτήτη", f"{total_owner_profit_after_expenses:.2f} €")
col4.metric("💵 Τιμή χωρίς ΦΠΑ μετά έξοδα", f"{total_price_wo_tax_after_expenses:.2f} €")

# -------------------------------------------------------------
# Εμφάνιση κρατήσεων
# -------------------------------------------------------------
st.subheader(f"📅 Κρατήσεις ({selected_month})")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# Καταχώρηση εξόδων
# -------------------------------------------------------------
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
            "Accommodation": exp_accommodation,
            "Category": exp_category,
            "Amount": f"{exp_amount:.2f} €",
            "Description": exp_description,
        }])
        st.session_state["expenses_df"] = pd.concat(
            [st.session_state["expenses_df"], new_row], ignore_index=True
        )

# -------------------------------------------------------------
# Εμφάνιση εξόδων με κουμπί διαγραφής χωρίς rerun
# -------------------------------------------------------------
st.subheader("💸 Καταχωρημένα Έξοδα")

def display_expenses():
    if st.session_state["expenses_df"].empty:
        st.info("Δεν υπάρχουν καταχωρημένα έξοδα.")
        return

    container = st.container()
    for i, row in st.session_state["expenses_df"].iterrows():
        cols = container.columns([1,1,1,1,2,1])
        cols[0].write(row["Date"])
        cols[1].write(row["Accommodation"])
        cols[2].write(row["Category"])
        cols[3].write(row["Amount"])
        cols[4].write(row["Description"])
        if cols[5].button("🗑️", key=f"del_{i}"):
            st.session_state["expenses_df"].drop(i, inplace=True)
            st.session_state["expenses_df"].reset_index(drop=True, inplace=True)
            break  # σταματάμε loop για αποφυγή conflict

display_expenses()
