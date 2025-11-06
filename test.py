import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
from collections import defaultdict
import os
import base64

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

# Flag για πλήρη ιστορικό
UPDATE_FULL_HISTORY = False  # True φέρνει από 1/1 έως προηγούμενο μήνα

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
# Ημερομηνίες
# -------------------------------------------------------------
today = date.today()
yesterday = today - timedelta(days=1)

# 👉 Αυτές οι ημερομηνίες χρησιμοποιούνται ΜΟΝΟ για εμφάνιση
display_from_date = "2025-01-01"  # Από πότε θέλεις να ξεκινάει η εμφάνιση στο dashboard
display_to_date = yesterday.strftime("%Y-%m-%d")

# -------------------------------------------------------------
# Περίοδος αποθήκευσης κρατήσεων στο Excel
# -------------------------------------------------------------
if UPDATE_FULL_HISTORY:
    # Εσύ ορίζεις ποιο διάστημα να κατεβάζει & αποθηκεύει
    START_MONTH = 1   # Π.χ. Μάρτιος
    END_MONTH = 10     # Π.χ. Ιούνιος
    YEAR = 2025

    from_date = date(YEAR, START_MONTH, 1).strftime("%Y-%m-%d")

    # Υπολογίζει την τελευταία ημέρα του END_MONTH
    if END_MONTH == 12:
        to_date = date(YEAR, 12, 31).strftime("%Y-%m-%d")
    else:
        to_date = (date(YEAR, END_MONTH + 1, 1) - timedelta(days=1)).strftime("%Y-%m-%d")

else:
    # Όταν είναι False, φέρνει κρατήσεις μέχρι χθες, αλλά ΔΕΝ τις αποθηκεύει
    from_date = date(today.year, 1, 1).strftime("%Y-%m-%d")  # Από αρχή έτους
    to_date = yesterday.strftime("%Y-%m-%d")


# -------------------------------------------------------------
# Συναρτήσεις υπολογισμού
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
# Συνάρτηση upload με debug
# -------------------------------------------------------------

def upload_file_to_github(file_path, repo, branch="main", commit_message="Auto update file"):
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        return  # Δεν υπάρχει token, απλά σταματάει

    filename = os.path.basename(file_path)

    # Διάβασμα αρχείου
    try:
        with open(file_path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
    except:
        return  # Αν αποτύχει το διάβασμα, σταματάει

    url = f"https://api.github.com/repos/{repo}/contents/{filename}"

    # Έλεγχος αν υπάρχει ήδη το αρχείο
    try:
        response = requests.get(url, headers={"Authorization": f"token {github_token}"})
        if response.status_code == 200:
            sha = response.json()["sha"]
        elif response.status_code == 404:
            sha = None
        else:
            return
    except:
        return

    data = {
        "message": f"{commit_message} on {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": content,
        "branch": branch
    }
    if sha:
        data["sha"] = sha

    # Upload/Update
    try:
        r = requests.put(url, headers={"Authorization": f"token {github_token}"}, json=data)
        # Δεν εμφανίζουμε κανένα μήνυμα
        return
    except:
        return

# -------------------------------------------------------------
# Φόρτωση Excel ή κενά DataFrames
# -------------------------------------------------------------
try:
    reservations_df = pd.read_excel(RESERVATIONS_FILE)
except FileNotFoundError:
    reservations_df = pd.DataFrame(columns=[
        "ID","Apartment","Guest Name","Arrival","Departure","Days",
        "Platform","Guests","Total Price","Booking Fee",
        "Price Without Tax","Airstay Commission","Owner Profit","Month"
    ])
# -------------------------------------------------------------
# Χωρισμός παλιών THRESH σε A1, A2, A3
# -------------------------------------------------------------
THRESH_MAPPING = {
    563628: "THRESH",
    563631,: "THRESH",
    1200587: "THRESH A3",
    563634]: "THRESH A4",
    563637: "THRESH",
    563640: "THRESH",
    563643: "THRESH",
}

reservations_df["Apartment"] = reservations_df.apply(
    lambda row: THRESH_MAPPING.get(row["ID"], row["Apartment"])
    if row["Apartment"].strip().upper() == "THRESH" else row["Apartment"],
    axis=1
)

# Αποθήκευση νέου Excel με τα split THRESH
reservations_df.to_excel(RESERVATIONS_FILE, index=False)

try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=["Date","Month","Accommodation","Category","Amount","Description"])

# -------------------------------------------------------------
# Ανάκτηση νέων κρατήσεων από Smoobu
# -------------------------------------------------------------
all_rows = []
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

                platform_lower = platform.lower().strip()
                if "expedia" in platform_lower:
                    price = price / 0.82

                price_wo_tax = compute_price_without_tax(price, days, arrival_dt.month, apt_name)
                fee = compute_booking_fee(platform, price)
                settings = APARTMENT_SETTINGS.get(apt_name, {"airstay_commission": 0.248})
                airstay_commission = round(price_wo_tax * settings["airstay_commission"], 2)
                owner_profit = round(price_wo_tax - fee - airstay_commission, 2)

                all_rows.append({
                    "ID": b.get("id"),
                    "Apartment": apt_name,
                    "Guest Name": b.get("guestName") or b.get("guest-name"),
                    "Arrival": arrival_dt.strftime("%Y-%m-%d"),
                    "Departure": departure_dt.strftime("%Y-%m-%d"),
                    "Days": days,
                    "Platform": platform,
                    "Guests": guests,
                    "Total Price": round(price,2),
                    "Booking Fee": round(fee,2),
                    "Price Without Tax": round(price_wo_tax,2),
                    "Airstay Commission": round(airstay_commission,2),
                    "Owner Profit": round(owner_profit,2),
                    "Month": arrival_dt.month
                })

            if data.get("page") and data.get("page") < data.get("page_count",1):
                params["page"] += 1
            else:
                break

# Προσθήκη νέων κρατήσεων στο Excel
if all_rows and UPDATE_FULL_HISTORY:
    reservations_df = pd.concat([reservations_df, pd.DataFrame(all_rows)], ignore_index=True)
    reservations_df.drop_duplicates(subset=["ID"], inplace=True)
    reservations_df.to_excel(RESERVATIONS_FILE, index=False)
    upload_file_to_github(RESERVATIONS_FILE, repo="tasoszaf/AIRSTAY")

# -------------------------------------------------------------
# Sidebar επιλογής καταλύματος
# -------------------------------------------------------------
st.sidebar.header("🏠 Επιλογή Καταλύματος")
selected_apartment = st.sidebar.selectbox("Κατάλυμα", list(APARTMENTS.keys()))

# -------------------------------------------------------------
# Ονόματα μηνών για εμφανή labels
# -------------------------------------------------------------
months_el = {
    1:"Ιανουάριος",2:"Φεβρουάριος",3:"Μάρτιος",4:"Απρίλιος",5:"Μάιος",6:"Ιούνιος",
    7:"Ιούλιος",8:"Αύγουστος",9:"Σεπτέμβριος",10:"Οκτώβριος",11:"Νοέμβριος",12:"Δεκέμβριος"
}

# -------------------------------------------------------------
# Υπολογισμός metrics ανά μήνα
# -------------------------------------------------------------
monthly_metrics = defaultdict(lambda: {"Total Price":0, "Total Expenses":0, "Owner Profit":0})

# Κατανομή κρατήσεων ανά ημέρα/μήνα
for idx, row in reservations_df[reservations_df["Apartment"]==selected_apartment].iterrows():
    arrival = pd.to_datetime(row["Arrival"])
    departure = pd.to_datetime(row["Departure"])
    days_total = (departure - arrival).days
    if days_total == 0:
        continue
    price_per_day = row["Total Price"] / days_total
    owner_profit_per_day = row["Owner Profit"] / days_total

    for i in range(days_total):
        day = arrival + pd.Timedelta(days=i)
        month = day.month
        if month > today.month:
            continue  # αγνοούμε μελλοντικούς μήνες
        monthly_metrics[month]["Total Price"] += price_per_day
        monthly_metrics[month]["Owner Profit"] += owner_profit_per_day

# Προσθήκη εξόδων ανά μήνα
for month in range(1, today.month+1):
    df_exp_month = expenses_df[
        (expenses_df["Month"]==month) & 
        (expenses_df["Accommodation"]==selected_apartment)
    ]
    expenses_total = df_exp_month["Amount"].apply(parse_amount).sum()
    monthly_metrics[month]["Total Expenses"] = expenses_total

# Δημιουργία DataFrame για εμφάνιση
monthly_table = pd.DataFrame([
    {
        "Μήνας": months_el[m],
        "Συνολική Τιμή Κρατήσεων (€)": f"{v['Total Price']:.2f}",
        "Συνολικά Έξοδα (€)": f"{v['Total Expenses']:.2f}",
        "Καθαρό Κέρδος Ιδιοκτήτη (€)": f"{v['Owner Profit'] - v['Total Expenses']:.2f}"
    }
    for m,v in sorted(monthly_metrics.items())
])

st.subheader(f"📊 Metrics ανά μήνα ({selected_apartment})")
st.dataframe(monthly_table, width="stretch", hide_index=True)

# -------------------------------------------------------------
# Εμφάνιση όλων των κρατήσεων
# -------------------------------------------------------------
st.subheader(f"📅 Κρατήσεις ({selected_apartment})")
filtered_df = reservations_df[reservations_df["Apartment"]==selected_apartment].copy()
filtered_df = filtered_df.sort_values(["Arrival"])
st.dataframe(filtered_df, width="stretch", hide_index=True)


# -------------------------------------------------------------
# 💰 Διαχείριση Εξόδων
# -------------------------------------------------------------
import uuid
import pandas as pd
from datetime import date
import streamlit as st

# -------------------------------
# Αρχικοποίηση ή φόρτωση Excel
# -------------------------------
EXPENSES_FILE = "expenses.xlsx"

try:
    expenses_df = pd.read_excel(EXPENSES_FILE)
except FileNotFoundError:
    expenses_df = pd.DataFrame(columns=[
        "ID","Date","Month","Accommodation","Category","Amount","Description"
    ])

# Εξασφάλιση ύπαρξης μοναδικού ID για κάθε γραμμή
if "ID" not in expenses_df.columns:
    expenses_df["ID"] = [str(uuid.uuid4()) for _ in range(len(expenses_df))]

# -------------------------------------------------------------
# Καταχώρηση νέου εξόδου
# -------------------------------------------------------------
st.subheader("💰 Καταχώρηση Εξόδων")

with st.form("expenses_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
    with col3:
        exp_category = st.selectbox("Κατηγορία", [
            "Cleaning", "Linen", "Maintenance", "Utilities", "Supplies", "Other"
        ])
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
# Εμφάνιση & Διαγραφή εξόδων (σίγουρη εκδοχή)
# -------------------------------------------------------------
st.subheader("💸 Καταχωρημένα Έξοδα")

selected_apartment_upper = selected_apartment.upper()

# Φίλτρο για το επιλεγμένο κατάλυμα
filtered_expenses = expenses_df[
    expenses_df["Accommodation"].str.strip().str.upper() == selected_apartment_upper
].copy().sort_values("Date").reset_index(drop=True)

if filtered_expenses.empty:
    st.info("Δεν υπάρχουν έξοδα για αυτό το κατάλυμα.")
else:
    st.markdown("### 📋 Λίστα Εξόδων")

    # Εμφάνιση κάθε εξόδου σε ξεχωριστό container
    for i, row in filtered_expenses.iterrows():
        with st.container():
            st.markdown(f"**Ημερομηνία:** {row['Date']}  |  **Κατηγορία:** {row['Category']}")
            st.markdown(f"**Ποσό:** {row['Amount']} €")
            st.markdown(f"**Περιγραφή:** {row.get('Description','-')}")

            # --- Κουμπί διαγραφής (με μοναδικό key) ---
            delete_key = f"delete_btn_{i}_{row['ID']}"
            if st.button("🗑️ Διαγραφή", key=delete_key):
                expenses_df = expenses_df[expenses_df["ID"] != row["ID"]].reset_index(drop=True)
                expenses_df.to_excel(EXPENSES_FILE, index=False)
                st.success(f"✅ Το έξοδο της {row['Date']} διαγράφηκε!")
                st.experimental_rerun()

            st.divider()  # γραμμή διαχωρισμού μεταξύ εξόδων

    # Υπολογισμός συνολικού ποσού
    total_expenses = filtered_expenses["Amount"].sum()
    st.markdown(f"### 💵 **Σύνολο Εξόδων:** {total_expenses:.2f} €")



