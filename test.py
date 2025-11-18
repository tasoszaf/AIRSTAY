import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import os
from github import Github

# -------------------------------------------------------------
# Streamlit Config
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# Paths για αρχεία Excel
# -------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations.xlsx")
EXPENSES_FILE = os.path.join(BASE_DIR, "expenses.xlsx")

# -------------------------------------------------------------
# Hardcoded Months Range
# -------------------------------------------------------------
START_MONTH = 5   # π.χ. Ιανουάριος
END_MONTH = 6  # π.χ. Οκτώβριος

today = date.today()
from_date = date(today.year, START_MONTH, 1).strftime("%Y-%m-%d")
next_month = date(today.year, END_MONTH, 28) + timedelta(days=4)
last_day = (next_month - timedelta(days=next_month.day)).day
to_date = date(today.year, END_MONTH, last_day).strftime("%Y-%m-%d")


# -------------------------------------------------------------
# Καταλύματα & Settings
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
    "THRESH_A3": [1200587],
    "THRESH_A4": [563634],
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
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.216},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.166},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "THRESH_A3": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.166},
    "THRESH_A4": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "KALISTA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "KOMOS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.216},
    "CHELI": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.216},
    "AKALI": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.166},
    "ZILEAN": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_fee_other": 0.10, "booking_fee": 0.166},
    "NAUTILUS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.186, "booking_fee_other": 0, "booking_fee": 0.216},
    "ANIVIA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "ELISE": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.166},
    "ORIANNA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_fee_other": 0, "booking_fee": 0.216},
    "JAAX": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.0, "booking_fee_other": 0, "booking_fee": 0.166},
    "FINIKAS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_fee_other": 0, "booking_fee": 0.166},
}

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------
def fetch_reservations(from_date, to_date):
    params = {
        "from": from_date,
        "to": to_date,
        "includePriceElements": True,
        "showCancellation": False,
        "excludeBlocked": True,
        "page": 1,
        "pageSize": 100
    }
    all_bookings = []
    while True:
        r = requests.get(reservations_url, headers=headers, params=params)
        if r.status_code != 200:
            st.error(f"Σφάλμα API: {r.status_code}")
            return pd.DataFrame()
        data = r.json()
        all_bookings.extend(data.get("bookings", []))
        if params["page"] >= data.get("page_count", 1):
            break
        params["page"] += 1

    if not all_bookings:
        return pd.DataFrame()

    df = pd.json_normalize(all_bookings)
    
    # Rename columns για ευκολία
    df = df.rename(columns={
        "id": "booking_id",
        "apartment.id": "apartment_id",
        "apartment.name": "apartment_name",
        "channel.name": "platform",
        "guest-name": "guest_name",
        "adults": "adults",
        "children": "children",
        "price": "price"
    })
    
    # Αποκλείουμε blocked bookings
    df = df[df.get("is-blocked-booking", False) == False]
    
    return df

def get_group_by_apartment(apt_id):
    for g, apt_list in APARTMENTS.items():
        if apt_id in apt_list:
            return g
    return None

def calculate_price_without_tax(group, platform, price, nights, month):
    platform = platform.lower()

    # Επιλογή βάσης (winter ή summer)
    if month in [1, 2, 3, 11, 12]:
        base = APARTMENT_SETTINGS[group]["winter_base"]
    else:
        base = APARTMENT_SETTINGS[group]["summer_base"]

    # ---- 1. EXPEDIA --------------------------------------------------------
    if platform == "expedia":
        net_price = (price * 0.82) - (base * nights)
        return (
            (net_price / 1.13)
            - (net_price * 0.005)
            + (price * 0.18)
        )

    # ---- 4. ΟΛΕΣ ΟΙ ΑΛΛΕΣ ΠΛΑΤΦΟΡΜΕΣ ---------------------------------------
    net_price = price - (base * nights)
    return (net_price / 1.13) - (net_price * 0.005)


def get_booking_fee(row):
    platform = str(row.get("platform", "")).lower()
    total = float(row.get("price", 0))
    apartment_id = row.get("apartment_id")
    group = get_group_by_apartment(apartment_id)
    if not group:
        return 0.0

    settings = APARTMENT_SETTINGS[group]

    if "booking.com" in platform:
        return total * settings.get("booking_fee", 0.166)
    elif "airbnb" in platform:
        return total * 0.15
    elif "expedia" in platform:
        return total * 0.18
    else:
        return total * settings.get("booking_fee_other", 0.0)

def calculate_airstay_commission(row):
    price_without_tax = row.get("Price Without Tax", 0)
    apartment_id = row.get("apartment_id")
    group = get_group_by_apartment(apartment_id)
    if not group:
        return 0.0
    rate = APARTMENT_SETTINGS[group].get("airstay_commission", 0.0)
    return price_without_tax * rate

def calculate_columns(df):
    if df.empty:
        return df
    df["Price Without Tax"] = df.apply(calculate_price_without_tax, axis=1)
    df["Booking Fee"] = df.apply(get_booking_fee, axis=1)
    df["Airstay Commission"] = df.apply(calculate_airstay_commission, axis=1)
    df["Owner Profit"] = df["Price Without Tax"] - df["Booking Fee"] - df["Airstay Commission"]
    df["Guests"] = df["adults"] + df["children"]
    return df

# -------------------------------------------------------------
# Load Expenses
# -------------------------------------------------------------
try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Month","Year","Accommodation","Category","Amount","Description"])

def parse_amount(v):
    try:
        return float(v)
    except:
        return 0.0

# -------------------------------------------------------------
# Fetch All Reservations
# -------------------------------------------------------------
df_new = fetch_reservations(from_date, to_date)
df_new = calculate_columns(df_new)

# -------------------------------------------------------------
# Sidebar Dropdown for Group Selection
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

# Filter for selected group
df_filtered = df_new[df_new["apartment_id"].isin(APARTMENTS[selected_group])]

# Keep only needed columns
columns_to_keep = [
    "booking_id", "apartment_id", "apartment_name", "platform",
    "guest_name", "arrival", "departure",
    "Guests",
    "price", "Price Without Tax", "Booking Fee", "Airstay Commission", "Owner Profit"
]
df_filtered = df_filtered[columns_to_keep]

# -------------------------------------------------------------
# Metrics per month
# -------------------------------------------------------------
monthly_metrics = defaultdict(lambda: {"Total Price": 0, "Total Expenses": 0, "Owner Profit": 0})
for idx, row in df_filtered.iterrows():
    checkin = pd.to_datetime(row["arrival"])
    checkout = pd.to_datetime(row["departure"])
    total_days = (checkout - checkin).days
    if total_days == 0:
        continue

    daily_price = row["Price Without Tax"] / total_days
    daily_profit = row["Owner Profit"] / total_days
    current_day = checkin
    while current_day < checkout:
        year, month = current_day.year, current_day.month
        next_month_day = (current_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        days_in_month = (min(checkout, next_month_day) - current_day).days

        monthly_metrics[(year, month)]["Total Price"] += daily_price * days_in_month
        monthly_metrics[(year, month)]["Owner Profit"] += daily_profit * days_in_month

        current_day = next_month_day

# Add expenses
for idx, row in expenses_df.iterrows():
    if row["Accommodation"].upper() != selected_group.upper():
        continue
    key = (int(row["Year"]), int(row["Month"]))
    monthly_metrics[key]["Total Expenses"] += parse_amount(row["Amount"])

months_el = {
    1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
    7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"
}

monthly_table = pd.DataFrame([
    {
        "Έτος": year,
        "Μήνας": months_el[month],
        "Συνολική Τιμή Κρατήσεων (€)": f"{v['Total Price']:.2f}",
        "Συνολικά Έξοδα (€)": f"{v['Total Expenses']:.2f}",
        "Καθαρό Κέρδος Ιδιοκτήτη (€)": f"{v['Owner Profit'] - v['Total Expenses']:.2f}"
    }
    for (year, month), v in sorted(monthly_metrics.items())
])

# -------------------------------------------------------------
# Display in Streamlit
# -------------------------------------------------------------
st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
st.dataframe(monthly_table, use_container_width=True)

st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(df_filtered, use_container_width=True)

# -------------------------------------------------------------
# Save to Excel
# -------------------------------------------------------------
df_filtered.to_excel(RESERVATIONS_FILE, index=False)
st.success(f"✅ Οι κρατήσεις αποθηκεύτηκαν στο {RESERVATIONS_FILE}")

# -------------------------------------------------------------
# Upload to GitHub
# -------------------------------------------------------------
try:
    GITHUB_TOKEN = st.secrets["github"]["token"]
    GITHUB_USER = st.secrets["github"]["username"]
    GITHUB_REPO = st.secrets["github"]["repo"]
    FILE_PATH = "reservations.xlsx"

    g = Github(GITHUB_TOKEN)
    repo = g.get_user(GITHUB_USER).get_repo(GITHUB_REPO)

    with open(RESERVATIONS_FILE, "rb") as f:
        content = f.read()

    try:
        contents = repo.get_contents(FILE_PATH, ref="main")
        repo.update_file(FILE_PATH, "🔁 Update reservations.xlsx", content, contents.sha, branch="main")
    except Exception:
        repo.create_file(FILE_PATH, "🆕 Add reservations.xlsx", content, branch="main")

    st.success("✅ Το αρχείο **reservations.xlsx** ενημερώθηκε επιτυχώς στο GitHub.")
except Exception as e:
    st.warning(f"⚠️ Σφάλμα κατά το ανέβασμα στο GitHub: {e}")
