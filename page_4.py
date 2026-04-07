import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
from Startdash import initialize_data

initialize_data()

######################
### Data laden
######################

flights_raw = st.session_state.get("flights", {})
airports = st.session_state.get("airports", pd.DataFrame())

# 👉 Airport label maken (naam + stad + land)
if not airports.empty:
    airports["label"] = (
        airports["Name"].astype(str) + " (" +
        airports["City"].astype(str) + ", " +
        airports["Country"].astype(str) + ")"
    )

    iata_to_name = (
        airports.dropna(subset=["IATA"])
        .set_index("IATA")["label"]
        .to_dict()
    )
else:
    iata_to_name = {}

schedule_key = None
for k in flights_raw:
    if "schedule" in k.lower() or "airport" in k.lower():
        schedule_key = k
        break

if schedule_key is None:
    st.error("Geen schedule-bestand gevonden.")
    st.stop()

df_raw = flights_raw[schedule_key].copy()

######################
### Feature engineering
######################

def parse_time_col(series: pd.Series) -> pd.Series:
    def _to_minutes(val):
        if pd.isna(val):
            return np.nan
        s = str(val).strip()
        parts = s.split(":")
        try:
            if len(parts) >= 2:
                return int(parts[0]) * 60 + int(parts[1])
        except:
            pass
        return np.nan
    return series.apply(_to_minutes)


@st.cache_data(show_spinner="Features berekenen...")
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["gepland_min"] = parse_time_col(df["STA_STD_ltc"])
    df["werkelijk_min"] = parse_time_col(df["ATA_ATD_ltc"])
    df["vertraging_min"] = df["werkelijk_min"] - df["gepland_min"]
    df = df.dropna(subset=["vertraging_min"])

    def categorize(v):
        if v < 5:
            return "On time"
        elif v <= 45:
            return "Small delay"
        else:
            return "Large delay"

    df["delay_cat"] = df["vertraging_min"].apply(categorize)
    df["delay_code"] = df["delay_cat"].map(
        {"On time": 0, "Small delay": 1, "Large delay": 2}
    )

    if "STD" in df.columns:
        df["STD_dt"] = pd.to_datetime(df["STD"], errors="coerce", dayfirst=True)
        df["dag_vd_week"] = df["STD_dt"].dt.dayofweek
        df["maand"] = df["STD_dt"].dt.month
        df["dag_vd_maand"] = df["STD_dt"].dt.day

    df["uur"] = (df["gepland_min"] // 60).clip(0, 23).astype("Int64")

    if "LSV" in df.columns:
        df["is_inbound"] = (
            df["LSV"].astype(str).str.strip().str.upper() == "L"
        ).astype(int)

    # ✈️ Aircraft type (label + code)
    if "ACT" in df.columns:
        df["actype_label"] = df["ACT"].astype(str).str.strip().fillna("ONBEKEND")

        le_act = LabelEncoder()
        df["actype_code"] = le_act.fit_transform(df["actype_label"])

    # 🛫 Runway
    if "RWY" in df.columns:
        le_rwy = LabelEncoder()
        df["rwy_code"] = le_rwy.fit_transform(
            df["RWY"].astype(str).str.strip().fillna("ONBEKEND")
        )

    # 🌍 Airport mapping (IATA → naam)
    if "Org/Des" in df.columns:
        df["airport_name"] = df["Org/Des"].map(iata_to_name)
        df["airport_name"] = df["airport_name"].fillna(df["Org/Des"])

        top_dest = df["airport_name"].value_counts().nlargest(30).index
        df["dest_top"] = df["airport_name"].where(
            df["airport_name"].isin(top_dest),
            other="OVERIG"
        )

        le_dest = LabelEncoder()
        df["dest_code"] = le_dest.fit_transform(df["dest_top"].astype(str))

        df["dest_label"] = df["dest_top"]

    return df


df = build_features(df_raw)

######################
### UI
######################

st.title("Vertragingsanalyse & Regressie")

######################
### Model
######################

ALLE_FEATURES = {
    "Uur van de dag": "uur",
    "Inbound / Outbound": "is_inbound",
    "Vliegtuigtype": "actype_code",
    "Runway": "rwy_code",
    "Bestemming/afkomst": "dest_code",
    "Dag van de week": "dag_vd_week",
    "Maand": "maand",
    "Dag van de maand": "dag_vd_maand",
}

beschikbare = {
    label: col
    for label, col in ALLE_FEATURES.items()
    if col in df.columns
}

gekozen_labels = list(beschikbare.keys())
gekozen_cols = [beschikbare[l] for l in gekozen_labels]

df_model = df[gekozen_cols + ["vertraging_min"]].dropna()

X = df_model[gekozen_cols].values
y = df_model["vertraging_min"].values

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = LinearRegression()
model.fit(X_train, y_train)

######################
### Predictor
######################

st.subheader("🔮 Voorspel een vertraging")

pred_input = {}
cols_pred = st.columns(4)
col_map = {col: i % 4 for i, col in enumerate(gekozen_labels)}

for label in gekozen_labels:
    col_key = beschikbare[label]

    with cols_pred[col_map[label]]:

        if col_key == "uur":
            pred_input[col_key] = st.number_input(label, 0, 23, 10)

        elif col_key == "is_inbound":
            pred_input[col_key] = st.selectbox(
                label, [0, 1],
                format_func=lambda x: "Inbound" if x else "Outbound"
            )

        elif col_key == "actype_code":
            opties = sorted(df["actype_label"].unique())
            keuze = st.selectbox(label, opties)

            code = df[df["actype_label"] == keuze]["actype_code"].iloc[0]
            pred_input[col_key] = int(code)

        elif col_key == "dest_code":
            opties = sorted(df["dest_label"].unique())
            keuze = st.selectbox(label, opties)

            code = df[df["dest_label"] == keuze]["dest_code"].iloc[0]
            pred_input[col_key] = int(code)

        else:
            min_val = int(df[col_key].min())
            max_val = int(df[col_key].max())
            med_val = int(df[col_key].median())

            pred_input[col_key] = st.number_input(
                label, min_val, max_val, med_val
            )

if st.button("Voorspel vertraging"):
    X_new = np.array([[pred_input[c] for c in gekozen_cols]])
    voorspelling = model.predict(X_new)[0]

    st.success(f"Voorspelde vertraging: {voorspelling:.1f} minuten")
