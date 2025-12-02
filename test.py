import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import os
import time
from github import Github
import plotly.express as px

# ---------------- Streamlit config ----------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

# ---------------- Config / Paths ----------------
API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESERVATIONS_FILE = os.path.join(BASE_DIR, "reservations.xlsx")
EXPENSES_FILE = os.path.join(BASE_DIR, "expenses.xlsx")

# ---------------- GitHub Config ----------------
GITHUB_TOKEN = st.secrets["github"]["token"]
GITHUB_USERNAME = st.secrets["github"]["username"]
REPO_NAME = "AIRSTAY"

# ---------------- Parameters ----------------
START_MONTH = 11
END_MONTH = 11
today = date.today()

# ---------------- Apartments & Settings ----------------
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

# ---------------- Helper functions ----------------
def to2(v):
    try:
        return round(float(v), 2)
    except:
        return 0.00

def get_group_by_apartment(apt_id):
    for g, apt_list in APARTMENTS.items():
        if apt_id in apt_list:
            return g
    return None

# ---------------- Load or Fetch Reservations ----------------
if os.path.exists(RESERVATIONS_FILE):
    df_display_source = pd.read_excel(RESERVATIONS_FILE)
else:
    df_display_source = pd.DataFrame(columns=[
        "booking_id","apartment_id","apartment_name","platform","guest_name",
        "arrival","departure","Guests","price","Price Without Tax","Booking Fee",
        "Airstay Commission","Owner Profit"
    ])

# ---------------- Load Expenses ----------------
try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["ID","Month","Year","Accommodation","Category","Amount","Description"])
if not expenses_df.empty and "Amount" in expenses_df.columns:
    expenses_df["Amount"] = pd.to_numeric(expenses_df["Amount"], errors="coerce").fillna(0).apply(to2)

# ---------------- Sidebar / URL parameter handling ----------------
query_params = st.experimental_get_query_params()
url_group = query_params.get("group", [None])[0]  # παίρνουμε το πρώτο αν υπάρχει
if url_group in APARTMENTS.keys():
    selected_group = url_group
    lock_group = True
else:
    selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
    lock_group = False

if lock_group:
    st.sidebar.markdown(f"**Group locked via URL:** {selected_group}")

# ---------------- Filter Reservations ----------------
df_filtered = df_display_source[df_display_source["apartment_id"].isin(APARTMENTS[selected_group])].copy()

# ---------------- Monthly Metrics ----------------
monthly_metrics = defaultdict(lambda: {
    "Total Price": 0.0,
    "Total Expenses":0.0,
    "Owner Profit":0.0,
    "Airstay Commission":0.0
})
for idx, row in df_filtered.iterrows():
    try:
        checkin = pd.to_datetime(row["arrival"])
        checkout = pd.to_datetime(row["departure"])
    except:
        continue
    total_days = (checkout - checkin).days
    if total_days <= 0: continue
    daily_price = float(row.get("price",0))/total_days
    daily_profit = float(row.get("Owner Profit",0))/total_days
    daily_airstay = float(row.get("Airstay Commission",0))/total_days
    current_day = checkin
    while current_day < checkout:
        year, month = current_day.year, current_day.month
        next_month_day = (current_day.replace(day=28) + timedelta(days=4)).replace(day=1)
        days_in_month = (min(checkout, next_month_day) - current_day).days
        monthly_metrics[(year,month)]["Total Price"] += daily_price * days_in_month
        monthly_metrics[(year,month)]["Owner Profit"] += daily_profit * days_in_month
        monthly_metrics[(year,month)]["Airstay Commission"] += daily_airstay * days_in_month
        current_day = next_month_day
for idx, row in expenses_df.iterrows():
    if str(row.get("Accommodation","")).upper() != selected_group.upper(): continue
    try:
        key = (int(row["Year"]), int(row["Month"]))
    except:
        continue
    monthly_metrics[key]["Total Expenses"] += to2(row.get("Amount",0))
for key in monthly_metrics.keys():
    for k2 in ["Total Price","Total Expenses","Owner Profit","Airstay Commission"]:
        monthly_metrics[key][k2] = to2(monthly_metrics[key][k2])

months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
             7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"}

monthly_table = pd.DataFrame([
    {"Έτος": year,"Μήνας": months_el[month],
     "Συνολική Τιμή Κρατήσεων (€)": v["Total Price"],
     "Συνολικά Έξοδα (€)": v["Total Expenses"],
     "Καθαρό Κέρδος Ιδιοκτήτη (€)": v["Owner Profit"] - v["Total Expenses"],
     "Συνολικά Έσοδα Airstay (€)": v["Airstay Commission"]}
    for (year,month),v in sorted(monthly_metrics.items())
])
monthly_table = monthly_table[
    ((monthly_table["Καθαρό Κέρδος Ιδιοκτήτη (€)"] + monthly_table["Συνολικά Έσοδα Airstay (€)"]) != 0)
    & (monthly_table["Έτος"]==today.year)
    & (monthly_table["Μήνας"].map(lambda m: list(months_el.values()).index(m)+1) <= today.month)
]

# ---------------- Display Metrics ----------------
st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
st.dataframe(monthly_table, use_container_width=True)

# ---------------- Display Reservations ----------------
st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(df_filtered, use_container_width=True)

# ---------------- Expenses Section ----------------
st.subheader(f"💸 Έξοδα ({selected_group})")
allow_add_expense = not lock_group
with st.form(f"add_expense_form_{selected_group}", clear_on_submit=True):
    month = st.selectbox("Μήνας", list(range(1,13)))
    amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f")
    category = st.text_input("Κατηγορία Έξοδου")
    description = st.text_input("Περιγραφή")
    submit = st.form_submit_button("Προσθήκη Έξοδου", disabled=not allow_add_expense)
    if submit:
        new_expense = {
            "ID": int(expenses_df["ID"].max() + 1) if not expenses_df.empty else 1,
            "Month": int(month),
            "Year": today.year,
            "Accommodation": selected_group,
            "Category": category,
            "Amount": to2(amount),
            "Description": description
        }
        expenses_df = pd.concat([expenses_df, pd.DataFrame([new_expense])], ignore_index=True)
        expenses_df.to_excel(EXPENSES_FILE, index=False)
        st.success(f"Έξοδο προστέθηκε για {selected_group}!")

st.dataframe(expenses_df[expenses_df["Accommodation"]==selected_group], use_container_width=True)

# ---------------- Plotly Metrics Graph ----------------
df_plot = monthly_table.copy()
df_plot["Έτος"] = df_plot["Έτος"].astype(str)
fig = px.line(
    df_plot,
    x="Μήνας",
    y=["Συνολική Τιμή Κρατήσεων (€)","Καθαρό Κέρδος Ιδιοκτήτη (€)","Συνολικά Έσοδα Airstay (€)","Συνολικά Έξοδα (€)"],
    markers=True,
    title=f"Metrics ανά μήνα ({selected_group})",
    labels={"value":"€","variable":"Metric"}
)
st.plotly_chart(fig, use_container_width=True)
