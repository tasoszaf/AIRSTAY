import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import os

# -------------------------------------------------------------
# 🎯 Ρυθμίσεις
# -------------------------------------------------------------
st.set_page_config(page_title="Smoobu Reservations Dashboard", layout="wide")
st.title("📊 Smoobu Reservations Dashboard")

API_KEY = "3MZqrgDd0OluEWaBywbhp7P9Zp8P2ACmVpX79rPc9R"

# -------------------------------------------------------------
# 🔹 Ομάδες καταλυμάτων + υποκατηγορίες THRESH
# -------------------------------------------------------------
groups = {
    "ZED": [1439913, 1439915, 1439917, 1439919, 1439921, 1439923, 1439925, 1439927, 
             1439929, 1439931, 1439933, 1439935, 1439937, 1439939, 1439971, 1439973, 
             1439975, 1439977, 1439979, 1439981, 1439983, 1439985],
    "KOMOS": [2160281, 2160286, 2160291],
    "CHELI": [2146456, 2146461],
    "AKALI": [1713746],
    "NAMI": [1275248],
    "THRESH_A3": [1200587],
    "THRESH_A4": [563634],
    "THRESH_OTHER": [563628, 563631, 563637, 563640, 563643],
    "ZILEAN": [1756004, 1756007, 1756010, 1756013, 1756016, 1756019, 1756022, 1756025, 1756031],
    "NAUTILUS": [563712, 563724, 563718, 563721, 563715, 563727],
    "ANIVIA": [563703, 563706],
    "ELISE": [563625, 1405415],
    "ORIANNA": [1607131],
    "KALISTA": [750921],
    "JAAX": [2712218],
    "FINIKAS": [2715193,2715198,2715203,2715208,2715213,
                 2715218,2715223,2715228,2715233, 2715238,2715273]
}

# -------------------------------------------------------------
# 🔹 Ρυθμίσεις API
# -------------------------------------------------------------
headers = {"Api-Key": API_KEY, "Content-Type": "application/json"}
reservations_url = "https://login.smoobu.com/api/reservations"

# -------------------------------------------------------------
# 🔹 Από/Έως ημερομηνίες
# -------------------------------------------------------------
from_date = "2025-01-01"
to_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

# -------------------------------------------------------------
# 🔹 Συνάρτηση fetch
# -------------------------------------------------------------
def fetch_bookings(start_date: str, end_date: str):
    params = {
        "from": start_date,
        "to": end_date,
        "excludeBlocked": "true",
        "showCancellation": "true",
        "page": 1,
        "pageSize": 100,
    }
    all_bookings = []
    while True:
        try:
            r = requests.get(reservations_url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            bookings = data.get("bookings", [])
            if not bookings:
                break
            all_bookings.extend(bookings)
            if data.get("page") and data.get("page") < data.get("page_count", 1):
                params["page"] += 1
            else:
                break
        except requests.exceptions.RequestException as e:
            st.warning(f"❌ Σφάλμα API: {e}")
            break
    return all_bookings

all_bookings = fetch_bookings(from_date, to_date)

# -------------------------------------------------------------
# 🔹 Υπολογισμοί για κρατήσεις
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

def parse_amount_euro(value):
    try:
        return float(str(value).replace(" €",""))
    except:
        return 0.0

def get_group_for_id(apartment_id):
    for grp, ids in groups.items():
        if apartment_id in ids:
            return grp
    return "UNKNOWN"

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

    apt = b.get("apartment", {}) or {}
    platform = (b.get("channel", {}) or {}).get("name") or "Direct booking"
    price = float(b.get("price") or 0)
    adults = int(b.get("adults") or 0)
    children = int(b.get("children") or 0)
    guests = adults + children
    days = max((departure_dt - arrival_dt).days, 0)
    fee = compute_booking_fee(platform, price)
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
        "Total Price": f"{round(price,2):.2f} €",
        "Booking Fee": f"{fee:.2f} €",
        "Owner Profit": f"{owner_profit:.2f} €",
        "Month": arrival_dt.month,
        "Group": get_group_for_id(b.get("id"))
    })

df = pd.DataFrame(rows)

# -------------------------------------------------------------
# 🔹 Sidebar φίλτρα
# -------------------------------------------------------------
st.sidebar.header("Φίλτρα")
months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",
             6:"Ιούνιος",7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",
             11:"Νοέμβριος",12:"Δεκέμβριος"}
month_options = ["Όλοι οι μήνες"] + [months_el[m] for m in sorted(months_el.keys())]
selected_month = st.sidebar.selectbox("Διάλεξε μήνα", month_options)
group_options = ["Όλα"] + list(groups.keys())
selected_group = st.sidebar.selectbox("Διάλεξε Κατάλυμα/Group", group_options)

filtered_df = df.copy()
if selected_month != "Όλοι οι μήνες":
    month_index = [k for k,v in months_el.items() if v==selected_month][0]
    filtered_df = filtered_df[filtered_df["Month"]==month_index]
if selected_group != "Όλα":
    filtered_df = filtered_df[filtered_df["Group"]==selected_group]

# -------------------------------------------------------------
# 🔹 Session state & Excel για έξοδα
# -------------------------------------------------------------
EXPENSES_FILE = "expenses.xlsx"
if "expenses_df" not in st.session_state:
    if os.path.exists(EXPENSES_FILE):
        st.session_state["expenses_df"] = pd.read_excel(EXPENSES_FILE)
    else:
        st.session_state["expenses_df"] = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])

expenses_df = st.session_state["expenses_df"].copy()
filtered_expenses = expenses_df.copy()
if selected_month != "Όλοι οι μήνες":
    month_index = [k for k,v in months_el.items() if v==selected_month][0]
    filtered_expenses = filtered_expenses[filtered_expenses["Month"]==month_index]
if selected_group != "Όλα":
    filtered_expenses = filtered_expenses[filtered_expenses["Accommodation"]==selected_group]

# -------------------------------------------------------------
# 🔹 Υπολογισμός totals
# -------------------------------------------------------------
total_price = filtered_df["Total Price"].apply(parse_amount_euro).sum()
total_owner_profit = filtered_df["Owner Profit"].apply(parse_amount_euro).sum()
total_expenses = filtered_expenses["Amount"].apply(parse_amount_euro).sum()
net_owner_profit = total_owner_profit - total_expenses

col1,col2,col3 = st.columns(3)
col1.metric("💰 Συνολική Τιμή Κρατήσεων", f"{total_price:.2f} €")
col2.metric("🧾 Συνολικά Έξοδα", f"{total_expenses:.2f} €")
col3.metric("📊 Καθαρό Κέρδος Ιδιοκτήτη", f"{net_owner_profit:.2f} €")

# -------------------------------------------------------------
# 🔹 Πίνακας κρατήσεων ανά Group με expander
# -------------------------------------------------------------
st.subheader(f"📅 Κρατήσεις ({selected_month}) ανά Κατάλυμα/Group")
for grp in filtered_df["Group"].unique():
    grp_df = filtered_df[filtered_df["Group"]==grp].copy()
    display_grp_df = grp_df.drop(columns=["Group"])
    with st.expander(f"{grp} ({len(grp_df)} κρατήσεις)"):
        st.dataframe(display_grp_df, use_container_width=True, hide_index=True)

# -------------------------------------------------------------
# 🔹 Καταχώρηση εξόδων
# -------------------------------------------------------------
st.subheader("💰 Καταχώρηση Εξόδων")
with st.form("expenses_form", clear_on_submit=True):
    col1,col2,col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα/Group", group_options[1:])
    with col3:
        exp_category = st.selectbox("Κατηγορία", ["Cleaning", "Linen", "Maintenance", "Utilities", "Supplies"])
    exp_amount = st.number_input("Ποσό", min_value=0.0, format="%.2f")
    exp_description = st.text_input("Περιγραφή (προαιρετική)")
    submitted = st.form_submit_button("➕ Καταχώρηση Εξόδου")
    if submitted:
        new_row = pd.DataFrame([{
            "Date": exp_date.strftime("%Y-%m-%d"),
            "Month": exp_date.month,
            "Accommodation": exp_accommodation,
            "Category": exp_category,
            "Amount": f"{exp_amount:.2f} €",
            "Description": exp_description,
        }])
        st.session_state["expenses_df"] = pd.concat([st.session_state["expenses_df"], new_row], ignore_index=True)
        st.session_state["expenses_df"].to_excel(EXPENSES_FILE, index=False)

# -------------------------------------------------------------
# 🔹 Εμφάνιση εξόδων
# -------------------------------------------------------------
st.subheader("💸 Καταχωρημένα Έξοδα")
def display_expenses():
    if filtered_expenses.empty:
        st.info("Δεν υπάρχουν καταχωρημένα έξοδα.")
        return
    container = st.container()
    for i,row in filtered_expenses.iterrows():
        cols = container.columns([1,1,1,1,2,1])
        cols[0].write(row["Date"])
        cols[1].write(row["Accommodation"])
        cols[2].write(row["Category"])
        cols[3].write(row["Amount"])
        cols[4].write(row["Description"])
        if cols[5].button("🗑️", key=f"del_{i}"):
            st.session_state["expenses_df"].drop(i,inplace=True)
            st.session_state["expenses_df"].reset_index(drop=True,inplace=True)
            st.session_state["expenses_df"].to_excel(EXPENSES_FILE,index=False)
            break

display_expenses()
