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

# -------------------------------------------------------------
# API Config
# -------------------------------------------------------------
API_KEY = st.secrets.get("smoobu_api_key", "")  # καλύτερα να το έχεις στο st.secrets
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
FETCH_MODE = "save_and_show"  # "show_only" ή "save_and_show"
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
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0,"booking_commission": 0.216},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0,"booking_commission": 0.166},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248,"booking_commission": 0.166},
    "THRESH_A3": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0,"booking_commission": 0.166},
    "THRESH_A4": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "KALISTA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248,"booking_commission": 0.166},
    "KOMOS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0,"booking_commission": 0.216},
    "CHELI": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0,"booking_commission": 0.216},
    "AKALI": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0,"booking_commission": 0.166},
    "ZILEAN": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248,"booking_commission": 0.166},
    "NAUTILUS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.186,"booking_commission": 0.216},
    "ANIVIA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248,"booking_commission": 0.166},
    "ELISE": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248,"booking_commission": 0.166},
    "ORIANNA": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.248,"booking_commission": 0.216},
    "JAAX": {"winter_base": 2, "summer_base": 8, "airstay_commission": 0.0,"booking_commission": 0.216},
    "FINIKAS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0,"booking_commission": 0.166},
}

# -------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------
def compute_price_without_tax(price, nights, month, apt_name):
    if not price or not nights:
        return 0.0
    settings = APARTMENT_SETTINGS.get(apt_name, {"winter_base": 2, "summer_base": 8})
    base = settings["winter_base"] if month in [11,12,1,2] else settings["summer_base"]
    adjusted = max(price - base * nights, 0)
    return round((adjusted / 1.13) - (adjusted * 0.005), 2)

def compute_booking_fee(platform_name: str, price: float, apt_name: str) -> float:
    if not platform_name or not price:
        return 0.0
    p = platform_name.strip().lower()
    
    if "booking.com" in p:
        rate = APARTMENT_SETTINGS.get(apt_name, {}).get("booking_commission", 0.0)
    elif "airbnb" in p:
        rate = 0.15
    elif "expedia" in p:
        rate = 0.18
    else:
        rate = 0.0

    return round(price * rate, 2)

def compute_airstay_commission(price_without_tax: float, apt_name: str) -> float:
    if not price_without_tax or not apt_name:
        return 0.0
    rate = APARTMENT_SETTINGS.get(apt_name, {}).get("airstay_commission", 0.0)
    return round(price_without_tax * rate, 2)

def parse_amount(v):
    try:
        return float(str(v).replace("€","").strip())
    except (ValueError, TypeError):
        return 0.0

# -------------------------------------------------------------
# Φόρτωση Excel
# -------------------------------------------------------------
try:
    reservations_df = pd.read_excel(RESERVATIONS_FILE)
except FileNotFoundError:
    reservations_df = pd.DataFrame(columns=[
        "ID","Apartment_ID","Group","Guest Name","Arrival","Departure","Days",
        "Platform","Guests","Total Price","Booking Fee",
        "Price Without Tax","Airstay Commission","Owner Profit","Month","Year"
    ])

try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Month","Year","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# Fetch & Save Reservations (μόνο αν save_and_show)
# -------------------------------------------------------------
if FETCH_MODE == "save_and_show":
    response = requests.get(reservations_url, headers=headers, params={"from": from_date, "to": to_date})
    if response.ok:
        reservations_data = response.json()
        new_rows = []

        for r in reservations_data:
            apartment_id = r.get("Apartment_ID")
            group = next((k for k,v in APARTMENTS.items() if apartment_id in v), "Unknown")
            arrival_date = datetime.strptime(r["Arrival"], "%Y-%m-%d").date()
            departure_date = datetime.strptime(r["Departure"], "%Y-%m-%d").date()
            nights = (departure_date - arrival_date).days
            price = r.get("Total Price", 0)
            platform = r.get("Platform", "")

            price_without_tax = compute_price_without_tax(price, nights, arrival_date.month, group)
            booking_fee = compute_booking_fee(platform, price, group)
            airstay_commission = compute_airstay_commission(price_without_tax, group)
            owner_profit = round(price - booking_fee - airstay_commission, 2)

            new_rows.append({
                "ID": r.get("ID"),
                "Apartment_ID": apartment_id,
                "Group": group,
                "Guest Name": r.get("Guest Name"),
                "Arrival": arrival_date,
                "Departure": departure_date,
                "Days": nights,
                "Platform": platform,
                "Guests": r.get("Guests", 1),
                "Total Price": price,
                "Booking Fee": booking_fee,
                "Price Without Tax": price_without_tax,
                "Airstay Commission": airstay_commission,
                "Owner Profit": owner_profit,
                "Month": arrival_date.month,
                "Year": arrival_date.year
            })

        new_df = pd.DataFrame(new_rows)
        reservations_df = pd.concat([reservations_df, new_df], ignore_index=True)
        reservations_df.to_excel(RESERVATIONS_FILE, index=False)
        st.success("✅ Οι κρατήσεις αποθηκεύτηκαν με σωστούς υπολογισμούς.")



# -------------------------------------------------------------
# Sidebar & Φιλτράρισμα
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
filtered_df = reservations_df[reservations_df["Group"]==selected_group].copy()
filtered_df = filtered_df.sort_values(["Arrival"]).reset_index(drop=True)

# -------------------------------------------------------------
# Metrics ανά μήνα
# -------------------------------------------------------------
months_el = {
    1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
    7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"
}

monthly_metrics = defaultdict(lambda: {"Total Price":0, "Total Expenses":0, "Owner Profit":0})

for idx, row in filtered_df.iterrows():
    days_total = row["Days"]
    if days_total == 0:
        continue
    month = row["Month"]
    year = row["Year"]
    key = (year, month)
    monthly_metrics[key]["Total Price"] += row["Total Price"]
    monthly_metrics[key]["Owner Profit"] += row["Owner Profit"]

for idx, row in expenses_df.iterrows():
    if row["Accommodation"].upper() != selected_group.upper():
        continue
    key = (int(row["Year"]), int(row["Month"]))
    monthly_metrics[key]["Total Expenses"] += parse_amount(row["Amount"])

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
    "ID","Apartment_ID","Group","Arrival","Departure","Days",
    "Platform","Guests","Total Price","Booking Fee","Price Without Tax",
    "Airstay Commission","Owner Profit"
]], width="stretch", hide_index=True)

group_expenses = expenses_df[expenses_df["Accommodation"].str.upper() == selected_group.upper()].copy()
group_expenses = group_expenses.sort_values(["Year","Month"], ascending=[False,False]).reset_index(drop=True)

st.subheader(f"💰 Έξοδα για {selected_group}")
if group_expenses.empty:
    st.info("Δεν υπάρχουν ακόμη έξοδα για αυτό το group.")
else:
    st.dataframe(
        group_expenses[["Month","Year","Accommodation","Category","Amount","Description"]],
        width=700,
        hide_index=True
    )

# -------------------------------------------------------------
# Φόρμα προσθήκης νέου εξόδου
# -------------------------------------------------------------
st.subheader("➕ Προσθήκη νέου εξόδου")

if "exp_month_select" not in st.session_state:
    st.session_state["exp_month_select"] = today.month
if "exp_category_input" not in st.session_state:
    st.session_state["exp_category_input"] = ""
if "exp_amount_input" not in st.session_state:
    st.session_state["exp_amount_input"] = 0.0
if "exp_description_input" not in st.session_state:
    st.session_state["exp_description_input"] = ""

with st.form("add_expense_form"):
    exp_month = st.selectbox("Μήνας", list(range(1, 13)), index=st.session_state["exp_month_select"]-1, key="exp_month_select")
    exp_category = st.text_input("Κατηγορία", value=st.session_state["exp_category_input"], key="exp_category_input")
    exp_amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f", value=st.session_state["exp_amount_input"], key="exp_amount_input")
    exp_description = st.text_area("Περιγραφή", value=st.session_state["exp_description_input"], key="exp_description_input")

    submitted = st.form_submit_button("💾 Αποθήκευση εξόδου", use_container_width=True)

    if submitted:
        new_expense = pd.DataFrame([{
            "ID": len(expenses_df) + 1,
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

        # GitHub Upload
        try:
            GITHUB_TOKEN = st.secrets["github"]["token"]
            GITHUB_USER = st.secrets["github"]["username"]
            GITHUB_REPO = st.secrets["github"]["repo"]
            FILE_PATH = "expenses.xlsx"

            g = Github(GITHUB_TOKEN)
            repo = g.get_user(GITHUB_USER).get_repo(GITHUB_REPO)

            with open(EXPENSES_FILE, "rb") as f:
                content = f.read()

            try:
                contents = repo.get_contents(FILE_PATH, ref="main")
                repo.update_file(FILE_PATH, "🔁 Update expenses.xlsx", content, contents.sha, branch="main")
            except Exception:
                repo.create_file(FILE_PATH, "🆕 Add expenses.xlsx", content, branch="main")

            st.success("✅ Το αρχείο **expenses.xlsx** ενημερώθηκε επιτυχώς στο GitHub.")
        except Exception as e:
            st.warning(f"⚠️ Σφάλμα κατά το ανέβασμα στο GitHub: {e}")

