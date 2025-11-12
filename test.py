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
FETCH_MODE = "show_only"  # ή "show_only" ή "save_and_show"
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
    expenses_df = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# Συνάρτηση υπολογισμού booking fee
# -------------------------------------------------------------
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

# -------------------------------------------------------------
# Συνάρτηση ανάκτησης κρατήσεων
# -------------------------------------------------------------
def fetch_reservations(from_date, to_date):
    rows = []
    for group_name, id_list in APARTMENTS.items():
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
                except requests.exceptions.RequestException:
                    break

                bookings = data.get("bookings", [])
                if not bookings:
                    break

                for b in bookings:
                    arrival_str = b.get("arrival")
                    departure_str = b.get("departure")
                    if not arrival_str or not departure_str:
                        continue
                    try:
                        arrival_dt = datetime.strptime(arrival_str, "%Y-%m-%d")
                        departure_dt = datetime.strptime(departure_str, "%Y-%m-%d")
                    except:
                        continue

                    platform = (b.get("channel") or {}).get("name") or "Direct booking"
                    price = float(b.get("price") or 0)
                    adults = int(b.get("adults") or 0)
                    children = int(b.get("children") or 0)
                    guests = adults + children
                    days = max((departure_dt - arrival_dt).days, 0)

                    fee = compute_booking_fee(platform, price)
                    owner_profit = price - fee

                    rows.append({
                        "ID": b.get("id"),
                        "Apartment_ID": apt_id,
                        "Group": group_name,
                        "Guest Name": b.get("guest-name"),
                        "Arrival": arrival_dt.strftime("%Y-%m-%d"),
                        "Departure": departure_dt.strftime("%Y-%m-%d"),
                        "Days": days,
                        "Platform": platform,
                        "Guests": guests,
                        "Total Price": round(price,2),
                        "Booking Fee": round(fee,2),
                        "Price Without Tax": round(price,2),
                        "Airstay Commission": 0,
                        "Owner Profit": round(owner_profit,2),
                        "Month": arrival_dt.month,
                        "Year": arrival_dt.year
                    })

                if data.get("page") and data.get("page") < data.get("page_count",1):
                    params["page"] += 1
                else:
                    break
    return rows

# -------------------------------------------------------------
# Fetch & αποθήκευση κρατήσεων
# -------------------------------------------------------------
all_rows = fetch_reservations(from_date, to_date)

if FETCH_MODE == "save_and_show":
    reservations_df = pd.concat([reservations_df, pd.DataFrame(all_rows)], ignore_index=True)
    reservations_df.drop_duplicates(subset=["ID"], inplace=True)
    reservations_df.to_excel(RESERVATIONS_FILE, index=False)
    st.success(f"✅ Αποθηκεύτηκαν {len(all_rows)} κρατήσεις ({from_date} → {to_date})")
else:
    new_df = pd.DataFrame(all_rows)
    reservations_df = pd.concat([reservations_df, new_df], ignore_index=True)
    reservations_df.drop_duplicates(subset=["ID"], inplace=True)
    st.info(f"ℹ️ Φορτώθηκαν {len(new_df)} κρατήσεις τρέχοντος μήνα μόνο για εμφάνιση")

# -------------------------------------------------------------
# Sidebar επιλογής καταλύματος
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_group = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
filtered_df = reservations_df[reservations_df["Group"]==selected_group].copy()
filtered_df = filtered_df.sort_values(["Arrival"]).reset_index(drop=True)

# -------------------------------------------------------------
# Metrics ανά μήνα
# -------------------------------------------------------------
monthly_metrics = defaultdict(lambda: {"Total Price":0, "Owner Profit":0})

for idx, row in filtered_df.iterrows():
    arrival = pd.to_datetime(row["Arrival"])
    departure = pd.to_datetime(row["Departure"])
    days_total = (departure - arrival).days
    if days_total == 0:
        continue
    price_per_day = row["Total Price"] / days_total
    owner_profit_per_day = row["Owner Profit"] / days_total

    for i in range(days_total):
        day = arrival + pd.Timedelta(days=i)
        if day.date() > today:
            continue
        key = (day.year, day.month)
        monthly_metrics[key]["Total Price"] += price_per_day
        monthly_metrics[key]["Owner Profit"] += owner_profit_per_day

# Φιλτράρουμε μόνο 2025 μέχρι τρέχον μήνα
monthly_metrics = {k:v for k,v in monthly_metrics.items() if k[0]==2025 and k[1]<=today.month}

months_el = {1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
             7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"}

monthly_table = pd.DataFrame([
    {
        "Έτος": year,
        "Μήνας": months_el[month],
        "Συνολική Τιμή Κρατήσεων (€)": f"{v['Total Price']:.2f}",
        "Καθαρό Κέρδος Ιδιοκτήτη (€)": f"{v['Owner Profit']:.2f}"
    }
    for (year, month), v in sorted(monthly_metrics.items())
])

st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
st.dataframe(monthly_table, width="stretch", hide_index=True)

# -------------------------------------------------------------
# Εμφάνιση κρατήσεων
# -------------------------------------------------------------
st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(
    filtered_df[[
        "ID","Apartment_ID","Group","Guest Name","Arrival","Departure","Days",
        "Platform","Guests","Total Price","Booking Fee",
        "Price Without Tax","Airstay Commission","Owner Profit"
    ]],
    width="stretch",
    hide_index=True
)

# -------------------------------------------------------------
# Πίνακας εξόδων για το επιλεγμένο group
# -------------------------------------------------------------
group_expenses = expenses_df[expenses_df["Accommodation"] == selected_group].copy()
group_expenses = group_expenses.sort_values("Date", ascending=False).reset_index(drop=True)

st.subheader(f"💰 Έξοδα για {selected_group}")
st.dataframe(group_expenses[["Date","Category","Amount","Description"]], width=700, hide_index=True)

# -------------------------------------------------------------
# Φόρμα προσθήκης νέου εξόδου
# -------------------------------------------------------------
st.subheader(f"➕ Προσθήκη νέου εξόδου για {selected_group}")
with st.form(f"add_expense_form_{selected_group}"):
    exp_date = st.date_input("Ημερομηνία", value=date.today())
    exp_category = st.text_input("Κατηγορία")
    exp_amount = st.number_input("Ποσό (€)", min_value=0.0, format="%.2f")
    exp_description = st.text_area("Περιγραφή")
    submitted = st.form_submit_button("Αποθήκευση εξόδου")

    if submitted:
        new_expense = pd.DataFrame([{
            "Date": exp_date.strftime("%Y-%m-%d"),
            "Month": exp_date.month,
            "Accommodation": selected_group,
            "Category": exp_category,
            "Amount": exp_amount,
            "Description": exp_description
        }])
        
        expenses_df = pd.concat([expenses_df, new_expense], ignore_index=True)
        expenses_df.drop_duplicates(subset=["Date","Accommodation","Category","Amount"], inplace=True)
        expenses_df.to_excel(EXPENSES_FILE, index=False)
        st.success("✅ Το έξοδο αποθηκεύτηκε στο Excel!")
        st.experimental_rerun()  # Ανανεώνει τη σελίδα για να δεις το νέο έξοδο
