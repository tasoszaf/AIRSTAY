import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from github import Github
import io

# -------------------------------------------------------------
# Streamlit setup
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# GitHub setup
# -------------------------------------------------------------
GITHUB_TOKEN = "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"
GITHUB_REPO = "tasoszaf/AIRSTAY"  # π.χ. "myuser/myrepo"
g = Github(GITHUB_TOKEN)
repo = g.get_repo(GITHUB_REPO)

RESERVATIONS_FILE = "reservations.xlsx"
EXPENSES_FILE = "expenses.xlsx"

def read_github_excel(filename):
    try:
        contents = repo.get_contents(filename)
        df = pd.read_excel(io.BytesIO(contents.decoded_content))
        return df
    except:
        return None

def write_github_excel(df, filename, commit_msg):
    with io.BytesIO() as buffer:
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        content = buffer.read()
    try:
        contents = repo.get_contents(filename)
        repo.update_file(contents.path, commit_msg, content, contents.sha)
    except:
        repo.create_file(filename, commit_msg, content)

# -------------------------------------------------------------
# Apartments & Settings
# -------------------------------------------------------------
APARTMENTS = {
    "ZED": [1439913,1439915],
    "KOMOS": [2160281,2160286],
    "CHELI": [2146456]
}

APARTMENT_SETTINGS = {
    "ZED": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "KOMOS": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
    "CHELI": {"winter_base": 0.5, "summer_base": 2, "airstay_commission": 0},
}

# -------------------------------------------------------------
# Dates
# -------------------------------------------------------------
today = date.today()
first_day_of_month = today.replace(day=1)
last_month = (first_day_of_month - timedelta(days=1)).month
last_month_year = (first_day_of_month - timedelta(days=1)).year

# -------------------------------------------------------------
# Load reservations & expenses from GitHub or create empty
# -------------------------------------------------------------
reservations_df = read_github_excel(RESERVATIONS_FILE)
if reservations_df is None:
    reservations_df = pd.DataFrame(columns=[
        "ID","Apartment","Guest Name","Arrival","Departure","Days",
        "Platform","Guests","Total Price","Booking Fee",
        "Price Without Tax","Airstay Commission","Owner Profit","Month"
    ])
    first_load = True
else:
    first_load = False

expenses_df = read_github_excel(EXPENSES_FILE)
if expenses_df is None:
    expenses_df = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# Utility functions
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
    if "booking" in p:
        rate = 0.17
    elif "airbnb" in p:
        rate = 0.15
    else:
        rate = 0.0
    return round((price or 0)*rate, 2)

def parse_amount(v):
    try:
        return float(str(v).replace("€","").strip())
    except:
        return 0.0

# -------------------------------------------------------------
# Fetch reservations from Smoobu
# -------------------------------------------------------------
all_rows = []

if first_load:
    from_date = "2025-01-01"
    to_date = (today - timedelta(days=1)).strftime("%Y-%m-%d")
else:
    from_date = first_day_of_month.strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

for apt_name, id_list in APARTMENTS.items():
    for apt_id in id_list:
        params = {
            "from": from_date,
            "to": to_date,
            "apartmentId": apt_id,
            "excludeBlocked": "true",
            "showCancellation": "false",
            "page": 1,
            "pageSize": 100,
        }
        while True:
            try:
                r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()
            except:
                break
            bookings = data.get("bookings", [])
            if not bookings:
                break
            for b in bookings:
                arrival_dt = datetime.strptime(b["arrival"], "%Y-%m-%d")
                departure_dt = datetime.strptime(b["departure"], "%Y-%m-%d")
                price = float(b.get("price",0))
                days = (departure_dt - arrival_dt).days
                platform = (b.get("channel") or {}).get("name","Direct booking")
                price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month, apt_name)
                fee = compute_booking_fee(platform, price)
                airstay_commission = round(price_wo_tax * APARTMENT_SETTINGS[apt_name]["airstay_commission"],2)
                owner_profit = round(price_wo_tax - fee - airstay_commission,2)
                all_rows.append({
                    "ID": b.get("id"),
                    "Apartment": apt_name,
                    "Guest Name": b.get("guestName"),
                    "Arrival": arrival_dt.strftime("%Y-%m-%d"),
                    "Departure": departure_dt.strftime("%Y-%m-%d"),
                    "Days": days,
                    "Platform": platform,
                    "Guests": b.get("adults",0)+b.get("children",0),
                    "Total Price": price,
                    "Booking Fee": fee,
                    "Price Without Tax": price_wo_tax,
                    "Airstay Commission": airstay_commission,
                    "Owner Profit": owner_profit,
                    "Month": arrival_dt.month
                })
            if data.get("page") < data.get("page_count",1):
                params["page"] += 1
            else:
                break

# Merge & save to GitHub
if all_rows:
    reservations_df = pd.concat([reservations_df, pd.DataFrame(all_rows)], ignore_index=True)
    reservations_df.drop_duplicates(subset=["ID"], inplace=True)
    write_github_excel(reservations_df, RESERVATIONS_FILE, "Update reservations")

# -------------------------------------------------------------
# Sidebar selection
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_apartment = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

# Filter
filtered_df = reservations_df[reservations_df["Apartment"]==selected_apartment].copy()
filtered_df = filtered_df.sort_values(["Arrival"])

# Metrics
total_price = filtered_df["Total Price"].sum()
total_owner_profit = filtered_df["Owner Profit"].sum()
total_expenses = expenses_df[expenses_df["Accommodation"]==selected_apartment]["Amount"].apply(parse_amount).sum()
net_profit = total_owner_profit - total_expenses

col1, col2, col3 = st.columns(3)
col1.metric("💰 Συνολική Τιμή Κρατήσεων", f"{total_price:.2f} €")
col2.metric("🧾 Συνολικά Έξοδα", f"{total_expenses:.2f} €")
col3.metric("📊 Κέρδος Ιδιοκτήτη", f"{net_profit:.2f} €")

# Table reservations
st.subheader(f"📅 Κρατήσεις ({selected_apartment})")
st.dataframe(filtered_df, use_container_width=True, hide_index=True)

# Expenses form
st.subheader("💰 Καταχώρηση Εξόδων")
with st.form("expenses_form", clear_on_submit=True):
    exp_date = st.date_input("Ημερομηνία", value=date.today())
    exp_category = st.selectbox("Κατηγορία", ["Cleaning","Linen","Maintenance"])
    exp_amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f")
    exp_description = st.text_input("Περιγραφή")
    submitted = st.form_submit_button("➕ Καταχώρηση Εξόδου")
    if submitted:
        new_row = pd.DataFrame([{
            "Date": exp_date.strftime("%Y-%m-%d"),
            "Month": exp_date.month,
            "Accommodation": selected_apartment,
            "Category": exp_category,
            "Amount": exp_amount,
            "Description": exp_description
        }])
        expenses_df = pd.concat([expenses_df, new_row], ignore_index=True)
        write_github_excel(expenses_df, EXPENSES_FILE, "Update expenses")
        st.experimental_rerun()

# Display expenses
st.subheader("💸 Καταχωρημένα Έξοδα")
df_exp = expenses_df[expenses_df["Accommodation"]==selected_apartment]
if df_exp.empty:
    st.info("Δεν υπάρχουν έξοδα.")
else:
    st.dataframe(df_exp, use_container_width=True, hide_index=True)
