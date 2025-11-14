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
# Επιλογή λειτουργίας
# -------------------------------------------------------------
FETCH_MODE = "save_and_show"  # ή "show_only" ή "save_and_show"
start_month = 1
end_month = 10

# -------------------------------------------------------------
# Ημερομηνίες
# -------------------------------------------------------------
today = date.today()
yesterday = today - timedelta(days=1)

if FETCH_MODE == "show_only":
    from_date = date(today.year, today.month, 1).strftime("%Y-%m-%d")
    to_date = yesterday.strftime("%Y-%m-%d")
else:
    from_date = date(today.year, start_month, 1).strftime("%Y-%m-%d")
    next_month = date(today.year, end_month, 28) + timedelta(days=4)
    last_day = (next_month - timedelta(days=next_month.day)).day
    to_date = date(today.year, end_month, last_day).strftime("%Y-%m-%d")

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
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_com_commission":0.216},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0, "booking_com_commission":0.166},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_com_commission":0.166},
    "THRESH_A3": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_com_commission":0.166},
    "THRESH_A4": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_com_commission":0.166},
    "KALISTA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_com_commission":0.166},
    "KOMOS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_com_commission":0.216},
    "CHELI": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_com_commission":0.216},
    "AKALI": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0, "booking_com_commission":0.166},
    "ZILEAN": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248, "booking_com_commission":0.166},
    "NAUTILUS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.186, "booking_com_commission":0.216},
    "ANIVIA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_com_commission":0.166},
    "ELISE": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_com_commission":0.166},
    "ORIANNA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248, "booking_com_commission":0.216},
    "JAAX": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.0, "booking_com_commission":0.166},
    "FINIKAS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0, "booking_com_commission":0.166}
}

# -----------------------------
# Load Excel
# -----------------------------
try:
    reservations_df = pd.read_excel(RESERVATIONS_FILE)
except FileNotFoundError:
    reservations_df = pd.DataFrame(columns=[
        "ID","Apartment_ID","Group","Guest Name","Arrival","Departure","Days",
        "Platform","Guests","Total Price","Booking Fee","Price Without Tax",
        "Airstay Commission","Owner Profit","Month","Year"
    ])

try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Month","Year","Accommodation","Category","Amount","Description"])

# -----------------------------
# GitHub Upload Function
# -----------------------------
def upload_to_github(file_path, commit_message):
    try:
        GITHUB_TOKEN = st.secrets["github"]["token"]
        GITHUB_USER = st.secrets["github"]["username"]
        GITHUB_REPO = st.secrets["github"]["repo"]

        g = Github(GITHUB_TOKEN)
        repo = g.get_user(GITHUB_USER).get_repo(GITHUB_REPO)
        file_name = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            content = f.read()

        try:
            contents = repo.get_contents(file_name, ref="main")
            repo.update_file(file_name, commit_message, content, contents.sha, branch="main")
        except Exception:
            repo.create_file(file_name, commit_message, content, branch="main")

        st.success(f"✅ Το αρχείο **{file_name}** ενημερώθηκε στο GitHub.")
    except Exception as e:
        st.warning(f"⚠️ Σφάλμα κατά το ανέβασμα στο GitHub: {e}")

# -----------------------------
# API Fetch (Paginated)
# -----------------------------
all_bookings = []
page = 1
while True:
    params = {"from": from_date, "to": to_date, "page": page, "pageSize": 100, "includePriceElements": True}
    response = requests.get(reservations_url, headers=headers, params=params)
    if response.status_code != 200:
        st.warning(f"API Error {response.status_code}")
        break
    data = response.json()
    bookings = data.get("bookings", [])
    if not bookings:
        break
    all_bookings.extend(bookings)
    if page >= data.get("page_count", 0):
        break
    page += 1

def map_booking_to_excel(b):
    arrival = pd.to_datetime(b.get("arrival"))
    departure = pd.to_datetime(b.get("departure"))
    days = (departure - arrival).days if arrival and departure else 0
    return {
        "ID": b.get("id"),
        "Apartment_ID": b.get("apartment", {}).get("id"),
        "Group": b.get("apartment", {}).get("name"),
        "Guest Name": b.get("guest-name"),
        "Arrival": arrival,
        "Departure": departure,
        "Days": days,
        "Platform": b.get("channel", {}).get("name"),
        "Guests": b.get("adults",0)+b.get("children",0),
        "Total Price": b.get("price",0),
        "Month": arrival.month if arrival else 0,
        "Year": arrival.year if arrival else 0
    }

if all_bookings:
    new_reservations_df = pd.DataFrame([map_booking_to_excel(b) for b in all_bookings])
    reservations_df = pd.concat([reservations_df, new_reservations_df], ignore_index=True)
    st.success(f"Φορτώθηκαν {len(new_reservations_df)} νέες κρατήσεις.")

# -----------------------------
# Financial Calculations
# -----------------------------
def safe_float(x, default=0.0):
    try: return float(x)
    except: return default

def calculate_booking_fee(row):
    try:
        month = int(row.get("Month") or pd.to_datetime(row.get("Arrival")).month)
        platform = str(row.get("Platform","")).upper()
        total_price = safe_float(row.get("Total Price"))
        days = safe_float(row.get("Days"))
        group = row.get("Group", "UNKNOWN")
        winter_months = {1,2,3,11,12}
        base = APARTMENT_SETTINGS.get(group, {}).get("winter_base" if month in winter_months else "summer_base", 0)
        booking_com_comm = APARTMENT_SETTINGS.get(group, {}).get("booking_com_commission", 0)
        if "BOOKING" in platform:
            return ((total_price - base * days)/1.005) * booking_com_comm
        elif "AIRBNB" in platform:
            return total_price * 0.15
        elif "EXPEDIA" in platform:
            return total_price * 0.18
        else:
            return 0.0
    except: return 0.0

def calculate_price_without_tax(row):
    try:
        month = int(row.get("Month") or pd.to_datetime(row.get("Arrival")).month)
        platform = str(row.get("Platform","")).upper()
        total_price = safe_float(row.get("Total Price"))
        days = safe_float(row.get("Days"))
        group = row.get("Group", "UNKNOWN")
        winter_months = {1,2,3,11,12}
        base = APARTMENT_SETTINGS.get(group, {}).get("winter_base" if month in winter_months else "summer_base", 0)
        if "EXPEDIA" in platform:
            net_price = (total_price * 0.82) - base * days
            return (net_price / 1.13) - (net_price * 0.005) + (total_price * 0.18)
        else:
            net_price = total_price - base * days
            return (net_price / 1.13) - (net_price * 0.005)
    except: return 0.0

def calculate_airstay_commission(row):
    try:
        rate = APARTMENT_SETTINGS.get(row.get("Group","UNKNOWN"), {}).get("airstay_commission", 0)
        return safe_float(row.get("Price Without Tax")) * rate
    except: return 0.0

def calculate_owner_profit(row):
    try:
        return safe_float(row.get("Price Without Tax")) - safe_float(row.get("Booking Fee")) - safe_float(row.get("Airstay Commission"))
    except: return 0.0

# Initialize columns
for col in ["Booking Fee","Price Without Tax","Airstay Commission","Owner Profit"]:
    if col not in reservations_df.columns:
        reservations_df[col] = 0.0

if not reservations_df.empty:
    reservations_df["Booking Fee"] = reservations_df.apply(calculate_booking_fee, axis=1)
    reservations_df["Price Without Tax"] = reservations_df.apply(calculate_price_without_tax, axis=1)
    reservations_df["Airstay Commission"] = reservations_df.apply(calculate_airstay_commission, axis=1)
    reservations_df["Owner Profit"] = reservations_df.apply(calculate_owner_profit, axis=1)

# Save and upload reservations
if FETCH_MODE=="save_and_show":
    reservations_df.to_excel(RESERVATIONS_FILE, index=False)
    upload_to_github(RESERVATIONS_FILE, "🔁 Update reservations.xlsx")

# -----------------------------
# Sidebar & Filtering
# -----------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
apartments = reservations_df["Group"].unique() if not reservations_df.empty else []
selected_group = st.sidebar.selectbox("Κατάλυμα", apartments)
filtered_df = reservations_df[reservations_df["Group"]==selected_group].copy()
filtered_df = filtered_df.sort_values("Arrival").reset_index(drop=True)

# -----------------------------
# Monthly Metrics
# -----------------------------
months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
             7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"}

monthly_metrics = defaultdict(lambda: {"Total Price":0, "Total Expenses":0, "Owner Profit":0})

for idx, row in filtered_df.iterrows():
    month = pd.to_datetime(row["Arrival"]).month
    year = pd.to_datetime(row["Arrival"]).year
    key = (year, month)
    monthly_metrics[key]["Total Price"] += safe_float(row.get("Total Price"))
    monthly_metrics[key]["Owner Profit"] += safe_float(row.get("Owner Profit"))

for idx, row in expenses_df.iterrows():
    if row["Accommodation"].upper() != selected_group.upper():
        continue
    key = (int(row["Year"]), int(row["Month"]))
    monthly_metrics[key]["Total Expenses"] += safe_float(row.get("Amount"))

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

st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
st.dataframe(monthly_table, width="stretch", hide_index=True)

st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(filtered_df[[
    "ID","Apartment_ID","Group","Guest Name","Arrival","Departure","Days","Platform",
    "Guests","Total Price","Booking Fee","Price Without Tax","Airstay Commission","Owner Profit"
]], width="stretch", hide_index=True)

# -----------------------------
# Expenses Table
# -----------------------------
group_expenses = expenses_df[expenses_df["Accommodation"].str.upper()==selected_group.upper()].copy()
group_expenses = group_expenses.sort_values(["Year","Month"], ascending=[False,False]).reset_index(drop=True)
st.subheader(f"💰 Έξοδα για {selected_group}")
if group_expenses.empty:
    st.info("Δεν υπάρχουν έξοδα για αυτό το group.")
else:
    st.dataframe(group_expenses[["Month","Year","Accommodation","Category","Amount","Description"]],
                 width=700, hide_index=True)

# -----------------------------
# Add New Expense Form
# -----------------------------
st.subheader("➕ Προσθήκη νέου εξόδου")
if "exp_month_select" not in st.session_state: st.session_state["exp_month_select"] = today.month
if "exp_category_input" not in st.session_state: st.session_state["exp_category_input"] = ""
if "exp_amount_input" not in st.session_state: st.session_state["exp_amount_input"] = 0.0
if "exp_description_input" not in st.session_state: st.session_state["exp_description_input"] = ""

with st.form("add_expense_form"):
    exp_month = st.selectbox("Μήνας", list(range(1,13)), index=st.session_state["exp_month_select"]-1, key="exp_month_select")
    exp_category = st.text_input("Κατηγορία", value=st.session_state["exp_category_input"], key="exp_category_input")
    exp_amount = st.number_input("Ποσό (€)", min_value=0.0, value=st.session_state["exp_amount_input"], key="exp_amount_input")
    exp_description = st.text_area("Περιγραφή", value=st.session_state["exp_description_input"], key="exp_description_input")
    submitted = st.form_submit_button("💾 Αποθήκευση εξόδου", use_container_width=True)
    
    if submitted:
        new_expense = pd.DataFrame([{
            "ID": len(expenses_df)+1,
            "Month": exp_month,
            "Year": today.year,
            "Accommodation": selected_group,
            "Category": exp_category,
            "Amount": exp_amount,
            "Description": exp_description
        }])
        expenses_df = pd.concat([expenses_df, new_expense], ignore_index=True)
        expenses_df.to_excel(EXPENSES_FILE, index=False)
        st.success("✅ Το έξοδο αποθηκεύτηκε επιτυχώς.")
        upload_to_github(EXPENSES_FILE, "🔁 Update expenses.xlsx")
