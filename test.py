import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import io

# -------------------------------------------------------------
# 🎯 Ρυθμίσεις Smoobu API
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("📊 Smoobu Reservations Dashboard")

# 💡 Βάλε το δικό σου API key εδώ ΜΟΝΙΜΑ
API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R" 
APARTMENT_ID = 750921

headers = {
    "Api-Key": API_KEY,
    "Content-Type": "application/json"
}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# 📅 Ορισμός ημερομηνιών
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
    "pageSize": 100
}

st.write(f"Ανάκτηση κρατήσεων από **{from_date}** έως **{to_date}**...")

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
# 🧱 Δημιουργία DataFrame
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
            "Arrival": arrival_str,
            "Departure": departure_str,
            "Days": days,
            "Platform": platform,
            "Guests": guests,
            "Total Price (€)": round(price, 2),
            "Booking Fee (€)": fee,
            "Price Without Tax (€)": price_wo_tax,
            "Owner Profit (€)": owner_profit
        })

if not rows:
    st.info(f"Δεν βρέθηκαν κρατήσεις για το διάστημα {from_date} έως {to_date}.")
    st.stop()

df = pd.DataFrame(rows)
df["Arrival"] = pd.to_datetime(df["Arrival"])
df["Month"] = df["Arrival"].dt.month

# ➕ Ελληνικά ονόματα μηνών
months_el = {
    1: "Ιανουάριος", 2: "Φεβρουάριος", 3: "Μάρτιος", 4: "Απρίλιος",
    5: "Μάιος", 6: "Ιούνιος", 7: "Ιούλιος", 8: "Αύγουστος",
    9: "Σεπτέμβριος", 10: "Οκτώβριος", 11: "Νοέμβριος", 12: "Δεκέμβριος"
}
df["Month Name"] = df["Month"].map(months_el)

# -------------------------------------------------------------
# 📊 Φίλτρο μόνο για μήνες
# -------------------------------------------------------------
st.sidebar.header("📅 Επιλογή Μήνα")
month_options = ["Όλοι οι μήνες"] + [months_el[m] for m in sorted(months_el.keys())]

selected_month = st.sidebar.selectbox("Διάλεξε μήνα", month_options)

if selected_month != "Όλοι οι μήνες":
    filtered_df = df[df["Month Name"] == selected_month]
else:
    filtered_df = df.copy()

filtered_df = filtered_df.sort_values(["Month", "Apartment", "Arrival"])

# -------------------------------------------------------------
# 📈 Εμφάνιση δεδομένων
# -------------------------------------------------------------
st.subheader(f"📅 Κρατήσεις ({selected_month})")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# 📦 Ανακεφαλαίωση
# -------------------------------------------------------------
st.subheader("📊 Σύνολα ανά μήνα & πλατφόρμα")
summary = (
    df.groupby(["Month Name", "Platform"])[["Total Price (€)", "Booking Fee (€)", "Owner Profit (€)"]]
    .sum()
    .round(2)
    .reset_index()
)
st.dataframe(summary, use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# 💾 Εξαγωγή Excel
# -------------------------------------------------------------
output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    filtered_df.to_excel(writer, index=False, sheet_name="Κρατήσεις")
    summary.to_excel(writer, index=False, sheet_name="Σύνολα")
excel_data = output.getvalue()

st.download_button(
    label="⬇️ Κατέβασε Excel",
    data=excel_data,
    file_name=f"reservations_2025_until_{to_date}_by_month.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
