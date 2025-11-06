import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import uuid
import os

# -------------------------------------------------------------
# Streamlit Config
# -------------------------------------------------------------
st.set_page_config(page_title="Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# Paths για αρχεία Excel
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXPENSES_FILE = os.path.join(BASE_DIR, "expenses.xlsx")

# -------------------------------------------------------------
# Καταλύματα και Grouping με βάση apartment IDs
# -------------------------------------------------------------
APARTMENT_GROUPS = {
    "THRESH": [563628,563631,563637,563640,563643],
    "THRESH A3": [1200587],
    "THRESH A4": [563634],
    "ZED": [1439913,1439915,1439917,1439919,1439921,1439923,1439925,1439927,1439929,
            1439931,1439933,1439935,1439937,1439939,1439971,1439973,1439975,1439977,
            1439979,1439981,1439983,1439985],
}

APARTMENT_SETTINGS = {
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "THRESH A3": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "THRESH A4": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
}

# -------------------------------------------------------------
# Ημερομηνίες για fetch
# -------------------------------------------------------------
today = date.today()
from_date = "2025-01-01"
to_date = today.strftime("%Y-%m-%d")

# -------------------------------------------------------------
# Συνάρτηση υπολογισμού τιμών
# -------------------------------------------------------------
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

def parse_amount(v):
    try:
        return float(str(v).replace("€","").strip())
    except:
        return 0.0

# -------------------------------------------------------------
# Φόρτωση εξόδων
# -------------------------------------------------------------
try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Date","Month","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# Fetch κρατήσεων για όλα τα groups
# -------------------------------------------------------------
all_bookings = []

for group_name, ids in APARTMENT_GROUPS.items():
    for apt_id in ids:
        page = 1
        while True:
            params = {
                "from": from_date,
                "to": to_date,
                "apartmentId": apt_id,
                "excludeBlocked": "true",
                "showCancellation": "false",
                "page": page,
                "pageSize": 100
            }
            try:
                r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()
            except requests.exceptions.RequestException as e:
                st.error(f"Σφάλμα κατά τη λήψη κρατήσεων: {e}")
                break

            bookings = data.get("bookings", [])
            if not bookings:
                break

            for b in bookings:
                b["group"] = group_name
                all_bookings.append(b)

            if page >= data.get("page_count", 1):
                break
            else:
                page += 1

# -------------------------------------------------------------
# Υπολογισμός metrics για κάθε booking
# -------------------------------------------------------------
bookings_list = []
for b in all_bookings:
    arrival = datetime.strptime(b["arrival"], "%Y-%m-%d")
    departure = datetime.strptime(b["departure"], "%Y-%m-%d")
    nights = max((departure - arrival).days, 1)
    price = float(b.get("price") or 0)
    platform = b.get("channel", {}).get("name", "Direct booking")
    price_wo_tax = compute_price_without_tax(price, nights, arrival.month, b["group"])
    fee = compute_booking_fee(platform, price)
    airstay_commission = round(price_wo_tax * APARTMENT_SETTINGS.get(b["group"], {}).get("airstay_commission",0),2)
    owner_profit = round(price_wo_tax - fee - airstay_commission,2)

    bookings_list.append({
        "ID": b["id"],
        "Group": b["group"],
        "Apartment ID": b["apartment"]["id"],
        "Apartment Name": b["apartment"]["name"],
        "Guest Name": b.get("guest-name"),
        "Arrival": b["arrival"],
        "Departure": b["departure"],
        "Nights": nights,
        "Total Price": price,
        "Price Without Tax": price_wo_tax,
        "Booking Fee": fee,
        "Airstay Commission": airstay_commission,
        "Owner Profit": owner_profit
    })

bookings_df = pd.DataFrame(bookings_list)

# -------------------------------------------------------------
# Metrics ανά group με έξοδα
# -------------------------------------------------------------
monthly_metrics = []

for group_name in APARTMENT_GROUPS.keys():
    df_group = bookings_df[bookings_df["Group"]==group_name]
    total_price = df_group["Total Price"].sum()
    total_owner = df_group["Owner Profit"].sum()

    # Υπολογισμός εξόδων
    df_exp = expenses_df[expenses_df["Accommodation"].str.upper().str.strip() == group_name.upper()]
    total_exp = df_exp["Amount"].apply(parse_amount).sum()

    net_profit = total_owner - total_exp

    monthly_metrics.append({
        "Group": group_name,
        "Total Price (€)": round(total_price,2),
        "Total Owner Profit (€)": round(total_owner,2),
        "Total Expenses (€)": round(total_exp,2),
        "Net Profit (€)": round(net_profit,2),
        "Bookings Count": len(df_group)
    })

metrics_df = pd.DataFrame(monthly_metrics)

st.subheader("📊 Metrics ανά Group με Έξοδα")
st.dataframe(metrics_df, width=1000)

# -------------------------------------------------------------
# Επιλογή group για εμφάνιση κρατήσεων
# -------------------------------------------------------------
selected_group = st.selectbox("Επιλογή Group για κρατήσεις", APARTMENT_GROUPS.keys())
filtered_df = bookings_df[bookings_df["Group"]==selected_group]
st.subheader(f"📅 Κρατήσεις για {selected_group}")
st.dataframe(filtered_df, width=1000)

# -------------------------------------------------------------
# Καταχώρηση νέου εξόδου
# -------------------------------------------------------------
st.subheader("💰 Καταχώρηση Εξόδων")

with st.form("expenses_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα", list(APARTMENT_GROUPS.keys()))
    with col3:
        exp_category = st.text_input("Κατηγορία")
    exp_amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f")
    exp_description = st.text_input("Περιγραφή (προαιρετική)")
    submitted = st.form_submit_button("➕ Καταχώρηση Εξόδου")

    if submitted:
        new_row = pd.DataFrame([{
            "ID": str(uuid.uuid4()),
            "Date": exp_date.strftime("%Y-%m-%d"),
            "Month": exp_date.month,
            "Accommodation": exp_accommodation.upper(),
            "Category": exp_category,
            "Amount": exp_amount,
            "Description": exp_description
        }])
        expenses_df = pd.concat([expenses_df, new_row], ignore_index=True)
        expenses_df.to_excel(EXPENSES_FILE, index=False)
        st.success("✅ Το έξοδο καταχωρήθηκε επιτυχώς!")
