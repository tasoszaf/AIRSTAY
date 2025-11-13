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
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "NAMI": {"winter_base": 4, "summer_base": 15, "airstay_commission": 0},
    "THRESH": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
    "THRESH_A3": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "THRESH_A4": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0.248},
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
# Sidebar & Φιλτράρισμα
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
filtered_df = reservations_df[reservations_df["Group"]==selected_group].copy()
filtered_df = filtered_df.sort_values(["Arrival"]).reset_index(drop=True)

# -------------------------------------------------------------
# FUNCTION: Υπολογισμοί για Price Without Tax, Booking Fee, Airstay Commission, Owner Profit
# -------------------------------------------------------------
def calculate_financials(row):
    month = row["Month"]
    platform = row["Platform"].upper()
    days = row["Days"]
    total_price = row["Total Price"]
    apartment = row["Group"]
    
    summer_months = [4,5,6,7,8,9,10]
    base = APARTMENT_SETTINGS[apartment]["summer_base"] if month in summer_months else APARTMENT_SETTINGS[apartment]["winter_base"]
    
    # Booking Fee / Platform Fee
    if platform == "BOOKING":
        fee = ((total_price - base*days)/1.005)*0.216
    elif platform == "AIRBNB":
        fee = total_price*0.15
    elif platform == "EXPEDIA":
        fee = total_price*0.18
    else:
        fee = 0
    
    # Price Without Tax
    price_without_tax = total_price - fee
    
    # Airstay Commission
    airstay_commission = (price_without_tax - fee) * APARTMENT_SETTINGS[apartment]["airstay_commission"]
    
    # Owner Profit
    owner_profit = total_price - fee - airstay_commission
    
    return pd.Series([fee, price_without_tax, airstay_commission, owner_profit])

# -------------------------------------------------------------
# FETCH_MODE = "save_and_show": Κράτησεις αποθηκεύονται + GitHub
# -------------------------------------------------------------
if FETCH_MODE == "save_and_show":
    # Υπολογισμοί
    financials = filtered_df.apply(calculate_financials, axis=1)
    filtered_df[["Booking Fee","Price Without Tax","Airstay Commission","Owner Profit"]] = financials
    
    # Αποθήκευση στο Excel
    filtered_df.to_excel(RESERVATIONS_FILE, index=False)
    st.success("✅ Οι κρατήσεις αποθηκεύτηκαν στο reservations.xlsx")
    
    # Ανεβάζουμε στο GitHub
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

        st.success("✅ Το αρχείο reservations.xlsx ενημερώθηκε στο GitHub")
    except Exception as e:
        st.warning(f"⚠️ Σφάλμα GitHub: {e}")

# -------------------------------------------------------------
# Metrics και εμφάνιση
# -------------------------------------------------------------
months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",
             5:"Μάιος",6:"Ιούνιος",7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",
             10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"}

monthly_metrics = defaultdict(lambda: {"Total Price":0, "Total Expenses":0, "Owner Profit":0})

for idx, row in filtered_df.iterrows():
    key = (row["Year"], row["Month"])
    monthly_metrics[key]["Total Price"] += row["Total Price"]
    monthly_metrics[key]["Owner Profit"] += row["Owner Profit"]

for idx, row in expenses_df.iterrows():
    if row["Accommodation"].upper() != selected_group.upper():
        continue
    key = (int(row["Year"]), int(row["Month"]))
    monthly_metrics[key]["Total Expenses"] += float(row["Amount"])

monthly_table = pd.DataFrame([
    {
        "Έτος": year,
        "Μήνας": months_el[month],
        "Συνολική Τιμή Κρατήσεων (€)": f"{v['Total Price']:,.2f}".replace(",","."),
        "Συνολικά Έξοδα (€)": f"{v['Total Expenses']:,.2f}".replace(",","."),
        "Καθαρό Κέρδος Ιδιοκτήτη (€)": f"{v['Owner Profit'] - v['Total Expenses']:,.2f}".replace(",",".")
    }
    for (year, month), v in sorted(monthly_metrics.items())
])

st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
st.dataframe(monthly_table, width="stretch", hide_index=True)

# -------------------------------------------------------------
# Εμφάνιση κρατήσεων & εξόδων
# -------------------------------------------------------------
st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(filtered_df, width="stretch", hide_index=True)

st.subheader(f"💰 Έξοδα για {selected_group}")
group_expenses = expenses_df[expenses_df["Accommodation"].str.upper()==selected_group.upper()].copy()
group_expenses = group_expenses.sort_values(["Year","Month"], ascending=[False,False]).reset_index(drop=True)
st.dataframe(group_expenses, width=700, hide_index=True)

# -------------------------------------------------------------
# Φόρμα προσθήκης εξόδου με GitHub
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
    exp_month = st.selectbox("Μήνας", list(range(1,13)), index=st.session_state["exp_month_select"]-1, key="exp_month_select")
    exp_category = st.text_input("Κατηγορία", value=st.session_state["exp_category_input"], key="exp_category_input")
    exp_amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f", value=st.session_state["exp_amount_input"], key="exp_amount_input")
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
        st.success("✅ Το έξοδο αποθηκεύτηκε στο Excel")

        # Ανεβάζουμε πάντα στο GitHub
        try:
            GITHUB_TOKEN = st.secrets["github"]["token"]
            GITHUB_USER = st.secrets["github"]["username"]
            GITHUB_REPO = st.secrets["github"]["repo"]

            g = Github(GITHUB_TOKEN)
            repo = g.get_user(GITHUB_USER).get_repo(GITHUB_REPO)
            FILE_PATH = "expenses.xlsx"

            with open(EXPENSES_FILE, "rb") as f:
                content = f.read()

            try:
                contents = repo.get_contents(FILE_PATH, ref="main")
                repo.update_file(FILE_PATH, "🔁 Update expenses.xlsx", content, contents.sha, branch="main")
            except Exception:
                repo.create_file(FILE_PATH, "🆕 Add expenses.xlsx", content, branch="main")

            st.success("✅ Το αρχείο **expenses.xlsx** ενημερώθηκε στο GitHub")
        except Exception as e:
            st.warning(f"⚠️ Σφάλμα GitHub: {e}")
