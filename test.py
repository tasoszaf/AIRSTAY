import streamlit as st
import pandas as pd
import os
from datetime import date, datetime
import uuid
import requests

# -------------------------------------------------------------
# Streamlit Config
# -------------------------------------------------------------
st.set_page_config(page_title="Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

# -------------------------------------------------------------
# Apartments Definitions
# -------------------------------------------------------------
APARTMENTS = {
    "ZED": [1439913,1439915,1439917,1439919,1439921,1439923,1439925,1439927,1439929,
            1439931,1439933,1439935,1439937,1439939,1439971,1439973,1439975,1439977,
            1439979,1439981,1439983,1439985],
    "KOMOS": [2160281,2160286,2160291],
    "CHELI": [2146456,2146461],
    "AKALI": [1713746],
    "NAMI": [1275248],
    "THRESH": [563628,563631,563637,563640,563643],
    "THRESH A3": [1200587],
    "THRESH A4": [563634],
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

ID_TO_GROUP = {apt_id: group_name for group_name, ids in APARTMENTS.items() for apt_id in ids}

APARTMENT_SETTINGS = {
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "THRESH A3": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "THRESH A4": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
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

# -------------------------------------------------------------
# Paths
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations-21.xlsx")
EXPENSES_FILE = os.path.join(BASE_DIR, "expenses.xlsx")

# -------------------------------------------------------------
# Ρυθμίσεις True/False & Μήνες
# -------------------------------------------------------------
FETCH_FROM_API = True  # True = επιπλέον μήνες από API, False = μόνο Excel + τρέχων μήνας
MONTHS_TO_FETCH = [1,2]  # Αν True, αυτοί οι μήνες θα κατέβουν επιπλέον

# -------------------------------------------------------------
# Helper Functions
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
    return round((price or 0) * rate, 2)

def parse_amount(v):
    try:
        return float(str(v).replace("€","").strip())
    except:
        return 0.0

# -------------------------------------------------------------
# Load Expenses
# -------------------------------------------------------------
try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
    st.success(f"✅ Φορτώθηκαν {len(expenses_df)} έξοδα από Excel")
except FileNotFoundError:
    st.warning(f"⚠️ Δεν βρέθηκε το αρχείο {EXPENSES_FILE}")
    expenses_df = pd.DataFrame(columns=["ID","Date","Month","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# Fetch Reservations
# -------------------------------------------------------------
all_bookings = []
today = date.today()
current_month = today.month
current_year = today.year

def fetch_from_api_for_months(months_list):
    API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
    headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
    reservations_url = "https://login.smoobu.com/api/reservations"

    bookings_result = []

    for group_name, ids in APARTMENTS.items():
        for apt_id in ids:
            page = 1
            for month in months_list:
                from_date = f"{current_year}-{month:02d}-01"
                to_date = f"{current_year}-{month:02d}-31"
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
                        apt_id2 = b["apartment"]["id"]
                        b["group"] = ID_TO_GROUP.get(apt_id2, "UNKNOWN")
                        bookings_result.append(b)

                    if page >= data.get("page_count", 1):
                        break
                    else:
                        page += 1
    return bookings_result

# Πάντα κατεβάζουμε τρέχοντα μήνα
all_bookings.extend(fetch_from_api_for_months([current_month]))

# Αν FETCH_FROM_API = True, κατεβάζουμε και άλλους μήνες
if FETCH_FROM_API and MONTHS_TO_FETCH:
    months_to_fetch = [m for m in MONTHS_TO_FETCH if m != current_month]
    if months_to_fetch:
        all_bookings.extend(fetch_from_api_for_months(months_to_fetch))

# -------------------------------------------------------------
# Process Bookings & Add Metrics Columns
# -------------------------------------------------------------
bookings_list = []
for b in all_bookings:
    arrival = datetime.strptime(b["arrival"], "%Y-%m-%d")
    departure = datetime.strptime(b["departure"], "%Y-%m-%d")
    nights = max((departure - arrival).days, 1)
    price = float(b.get("price") or 0)
    platform = b.get("channel", {}).get("name", "Direct booking")
    group_name = b["group"]

    price_wo_tax = compute_price_without_tax(price, nights, arrival.month, group_name)
    fee = compute_booking_fee(platform, price)
    airstay_commission = round(price_wo_tax * APARTMENT_SETTINGS.get(group_name, {}).get("airstay_commission", 0), 2)
    owner_profit = round(price_wo_tax - fee - airstay_commission, 2)

    bookings_list.append({
        "ID": b["id"],
        "Group": group_name,
        "Apartment ID": b["apartment"]["id"],
        "Apartment Name": b["apartment"]["name"],
        "Guest Name": b.get("guest-name"),
        "Arrival": b["arrival"],
        "Departure": b["departure"],
        "Nights": nights,
        "Total Price (€)": price,
        "Price Without Tax (€)": price_wo_tax,
        "Booking Fee (€)": fee,
        "Airstay Commission (€)": airstay_commission,
        "Owner Profit (€)": owner_profit
    })

bookings_df_api = pd.DataFrame(bookings_list)

# Αν FETCH_FROM_API = False, διαβάζουμε και από Excel
if not FETCH_FROM_API:
    try:
        bookings_df_excel = pd.read_excel(RESERVATIONS_FILE)
        st.success(f"✅ Φορτώθηκαν {len(bookings_df_excel)} κρατήσεις από Excel")
    except FileNotFoundError:
        bookings_df_excel = pd.DataFrame(columns=bookings_df_api.columns)
    bookings_df = pd.concat([bookings_df_api, bookings_df_excel], ignore_index=True)
else:
    bookings_df = bookings_df_api

# Αποθήκευση στο Excel για μελλοντική χρήση
bookings_df.to_excel(RESERVATIONS_FILE, index=False)

# -------------------------------------------------------------
# Metrics ανά Group
# -------------------------------------------------------------
metrics_list = []
for group_name in APARTMENTS.keys():
    df_group = bookings_df[bookings_df["Group"] == group_name]
    total_price = df_group["Total Price (€)"].sum() if not df_group.empty else 0.0

    df_exp = expenses_df[expenses_df["Accommodation"].str.upper().str.strip() == group_name.upper()]
    total_exp = df_exp["Amount"].apply(parse_amount).sum() if not df_exp.empty else 0.0

    owner_profit = total_price - total_exp

    metrics_list.append({
        "Group": group_name,
        "Total Price (€)": round(total_price,2),
        "Total Expenses (€)": round(total_exp,2),
        "Owner Profit (€)": round(owner_profit,2)
    })

metrics_df = pd.DataFrame(metrics_list)

# -------------------------------------------------------------
# UI - Επιλογή Group & Metrics
# -------------------------------------------------------------
st.subheader("📊 Metrics ανά Group")
selected_group = st.selectbox("Επιλογή Group", APARTMENTS.keys())
filtered_metrics = metrics_df[metrics_df["Group"] == selected_group].iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric("Total Price (€)", f"{filtered_metrics['Total Price (€)']:,}")
col2.metric("Total Expenses (€)", f"{filtered_metrics['Total Expenses (€)']:,}")
col3.metric("Owner Profit (€)", f"{filtered_metrics['Owner Profit (€)']:,}")

# -------------------------------------------------------------
# Εμφάνιση κρατήσεων για το επιλεγμένο Group
# -------------------------------------------------------------
st.subheader(f"📅 Κρατήσεις για {selected_group}")
filtered_bookings = bookings_df[bookings_df["Group"] == selected_group]
st.dataframe(filtered_bookings, width=1200)

# -------------------------------------------------------------
# Φόρμα καταχώρησης εξόδων
# -------------------------------------------------------------
st.subheader("💰 Καταχώρηση Εξόδων")
with st.form("expenses_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
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

# -------------------------------------------------------------
# Εμφάνιση όλων των εξόδων
# -------------------------------------------------------------
st.subheader("📄 Καταχωρημένα Έξοδα")
if not expenses_df.empty:
    st.dataframe(expenses_df, width=1000)
else:
    st.info("Δεν υπάρχουν καταχωρημένα έξοδα.")
