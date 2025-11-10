import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, timedelta
import os
import uuid

# ======================
# ΡΥΘΜΙΣΕΙΣ ΚΑΤΑΛΥΜΑΤΩΝ
# ======================
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

RESERVATIONS_FILE = "reservations.xlsx"
EXPENSES_FILE = "expenses.xlsx"
API_URL = "https://login.smoobu.com/api/reservations"
API_TOKEN = st.secrets["SMOOBU_TOKEN"] if "SMOOBU_TOKEN" in st.secrets else os.getenv("SMOOBU_TOKEN")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

# ======================
# ΣΥΝΑΡΤΗΣΕΙΣ
# ======================
def fetch_reservations():
    st.info("🔄 Γίνεται ανάκτηση κρατήσεων από Smoobu...")
    try:
        r = requests.get(API_URL, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        bookings = data.get("bookings", data)
    except:
        st.error("Σφάλμα κατά την ανάκτηση κρατήσεων")
        return pd.DataFrame()

    all_rows = []
    for b in bookings:
        try:
            apt_real_id = b.get("apartment", {}).get("id")
            if not apt_real_id:
                continue

            apt_name = None
            for name, ids in APARTMENTS.items():
                if apt_real_id in ids:
                    apt_name = name
                    break
            if not apt_name:
                continue

            arrival_dt = datetime.fromisoformat(b.get("arrival")[:10])
            departure_dt = datetime.fromisoformat(b.get("departure")[:10])
            days = (departure_dt - arrival_dt).days
            price = float(b.get("price",0))
            guests = b.get("guests",0)
            platform = b.get("channel",{}).get("name","Unknown")

            settings = APARTMENT_SETTINGS[apt_name]
            commission = settings["airstay_commission"]
            price_wo_tax = price / 1.13
            airstay_commission = price_wo_tax * commission
            owner_profit = price_wo_tax - airstay_commission

            all_rows.append({
                "ID": b.get("id"),
                "Group": apt_name,
                "Apartment ID": apt_real_id,
                "Guest Name": b.get("guestName"),
                "Arrival": arrival_dt.strftime("%Y-%m-%d"),
                "Departure": departure_dt.strftime("%Y-%m-%d"),
                "Days": days,
                "Platform": platform,
                "Guests": guests,
                "Total Price": round(price,2),
                "Price Without Tax": round(price_wo_tax,2),
                "Airstay Commission": round(airstay_commission,2),
                "Owner Profit": round(owner_profit,2),
                "Month": arrival_dt.month
            })
        except:
            continue

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df.to_excel(RESERVATIONS_FILE, index=False)
        st.success(f"✅ Ενημερώθηκαν {len(df)} κρατήσεις.")
    return df

def load_expenses():
    try:
        df = pd.read_excel(EXPENSES_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["ID","Date","Month","Accommodation","Category","Amount","Description"])
    return df

def save_expenses(df):
    df.to_excel(EXPENSES_FILE,index=False)

def compute_metrics(df_res, df_exp, selected_group):
    monthly_metrics = {m:{"Total Price":0,"Owner Profit":0,"Total Expenses":0} for m in range(1,13)}
    filtered_res = df_res[df_res["Group"]==selected_group]
    for idx,row in filtered_res.iterrows():
        days = row["Days"]
        if days==0: continue
        price_per_day = row["Total Price"]/days
        owner_profit_per_day = row["Owner Profit"]/days
        arrival = pd.to_datetime(row["Arrival"])
        for i in range(days):
            day = arrival + pd.Timedelta(days=i)
            month = day.month
            monthly_metrics[month]["Total Price"] += price_per_day
            monthly_metrics[month]["Owner Profit"] += owner_profit_per_day
    for month in range(1,13):
        df_month = df_exp[(df_exp["Month"]==month) & (df_exp["Accommodation"].str.upper()==selected_group.upper())]
        monthly_metrics[month]["Total Expenses"] = df_month["Amount"].sum()
    return monthly_metrics

# ======================
# STREAMLIT APP
# ======================
st.title("🏨 Reservations & Expenses Dashboard")

# Κρατήσεις
if st.button("🔄 Fetch Reservations"):
    df_res = fetch_reservations()
else:
    try:
        df_res = pd.read_excel(RESERVATIONS_FILE)
    except FileNotFoundError:
        df_res = pd.DataFrame()

# Expenses
df_exp = load_expenses()

# Sidebar επιλογής group
selected_group = st.sidebar.selectbox("🏠 Επιλογή Group", list(APARTMENTS.keys()))

# Metrics ανά μήνα
monthly_metrics = compute_metrics(df_res, df_exp, selected_group)
months_el = {1:"Ιαν",2:"Φεβ",3:"Μαρ",4:"Απρ",5:"Μαι",6:"Ιουν",
             7:"Ιουλ",8:"Αυγ",9:"Σεπ",10:"Οκτ",11:"Νοε",12:"Δεκ"}

st.subheader(f"📊 Metrics ανά μήνα ({selected_group})")
metrics_table = pd.DataFrame([{
    "Μήνας": months_el[m],
    "Συνολική Τιμή Κρατήσεων (€)": f"{v['Total Price']:.2f}",
    "Συνολικά Έξοδα (€)": f"{v['Total Expenses']:.2f}",
    "Καθαρό Κέρδος Ιδιοκτήτη (€)": f"{v['Owner Profit'] - v['Total Expenses']:.2f}"
} for m,v in monthly_metrics.items()])
st.dataframe(metrics_table, hide_index=True)

# Εμφάνιση κρατήσεων
st.subheader(f"📅 Κρατήσεις ({selected_group})")
st.dataframe(
    df_res[df_res["Group"]==selected_group][[
        "ID", "Guest Name", "Arrival", "Departure", "Days",
        "Platform", "Guests", "Total Price", "Price Without Tax",
        "Airstay Commission", "Owner Profit", "Apartment ID", "Group"
    ]].sort_values("Arrival"),
    hide_index=True
)

# 💰 Διαχείριση εξόδων
st.subheader("💰 Καταχώρηση Εξόδων")
with st.form("expenses_form", clear_on_submit=True):
    col1,col2,col3 = st.columns(3)
    with col1:
        exp_date = st.date_input("Ημερομηνία", value=date.today())
    with col2:
        exp_accommodation = st.selectbox("Κατάλυμα", list(APARTMENTS.keys()))
    with col3:
        exp_category = st.selectbox("Κατηγορία", ["Cleaning","Linen","Maintenance","Utilities","Supplies","Other"])
    exp_amount = st.number_input("Ποσό (€)",0.0,format="%.2f")
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
        df_exp = pd.concat([df_exp,new_row],ignore_index=True)
        save_expenses(df_exp)
        st.success("✅ Το έξοδο καταχωρήθηκε!")

# Εμφάνιση εξόδων
st.subheader("💸 Καταχωρημένα Έξοδα")
filtered_exp = df_exp[df_exp["Accommodation"].str.upper()==selected_group.upper()]
if filtered_exp.empty:
    st.info("Δεν υπάρχουν έξοδα για αυτό το group.")
else:
    for i,row in filtered_exp.iterrows():
        with st.container():
            st.markdown(f"**Ημερομηνία:** {row['Date']} | **Κατηγορία:** {row['Category']}")
            st.markdown(f"**Ποσό:** {row['Amount']} €")
            st.markdown(f"**Περιγραφή:** {row.get('Description','-')}")
            delete_key = f"delete_btn_{i}_{row['ID']}"
            if st.button("🗑️ Διαγραφή", key=delete_key):
                df_exp = df_exp[df_exp["ID"]!=row["ID"]].reset_index(drop=True)
                save_expenses(df_exp)
                st.success(f"✅ Το έξοδο της {row['Date']} διαγράφηκε!")
                st.experimental_rerun()
