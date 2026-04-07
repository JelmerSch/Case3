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

# Airport label maken (naam + stad + land)
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
### 1. Overzicht    ###
######################

st.subheader("Overzicht vertraging")

totaal     = len(df)
on_time    = (df["delay_cat"] == "On time").sum()
small_del  = (df["delay_cat"] == "Small delay").sum()
large_del  = (df["delay_cat"] == "Large delay").sum()
gem_vertr  = df["vertraging_min"].mean()
med_vertr  = df["vertraging_min"].median()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Totaal vluchten",   f"{totaal:,}")
c2.metric("✅ On time",         f"{on_time:,}",   f"{on_time/totaal*100:.1f}%")
c3.metric("🟡 Small delay",    f"{small_del:,}",  f"{small_del/totaal*100:.1f}%")
c4.metric("🔴 Large delay",    f"{large_del:,}",  f"{large_del/totaal*100:.1f}%")
c5.metric("📊 Gem. vertraging", f"{gem_vertr:.1f} min")
c6.metric("📈 Mediaan",         f"{med_vertr:.1f} min")

st.divider()
######################
### 2. Grafieken   ###
######################

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("Verdeling vertragingscategorieën")
    cat_counts = df["delay_cat"].value_counts().reindex(
        ["On time", "Small delay", "Large delay"]
    )
    fig_pie = go.Figure(go.Pie(
        labels=cat_counts.index,
        values=cat_counts.values,
        marker=dict(colors=["#2ca02c", "#ff7f0e", "#d62728"]),
        hole=0.4,
        textinfo="percent+label",
    ))
    fig_pie.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0),
                          showlegend=False)
    st.plotly_chart(fig_pie, use_container_width=True)

with col_g2:
    st.subheader("Vertraging per uur van de dag")
    if "uur" in df.columns:
        uur_gem = (
            df.groupby("uur")["vertraging_min"]
            .mean()
            .reset_index()
            .rename(columns={"vertraging_min": "gem_vertraging"})
        )
        fig_uur = go.Figure(go.Bar(
            x=uur_gem["uur"],
            y=uur_gem["gem_vertraging"],
            marker_color="#1f77b4",
        ))
        fig_uur.update_layout(
            xaxis_title="Uur van de dag",
            yaxis_title="Gem. vertraging (min)",
            height=350,
            margin=dict(l=40, r=20, t=10, b=40),
        )
        st.plotly_chart(fig_uur, use_container_width=True)

# Histogram vertraging (geclipt voor leesbaarheid)
st.subheader("Histogram vertraging (−30 t/m +120 min)")
df_clip = df[df["vertraging_min"].between(-30, 120)]
fig_hist = px.histogram(
    df_clip, x="vertraging_min", nbins=60,
    color="delay_cat",
    color_discrete_map={
        "On time":     "#2ca02c",
        "Small delay": "#ff7f0e",
        "Large delay": "#d62728",
    },
    labels={"vertraging_min": "Vertraging (min)", "delay_cat": "Categorie"},
)
fig_hist.update_layout(
    height=350,
    margin=dict(l=40, r=20, t=10, b=40),
    bargap=0.05,
    legend_title="Categorie",
)
st.plotly_chart(fig_hist, use_container_width=True)

st.divider()
######################
### 3. Regressie   ###
######################

st.subheader("Lineaire regressie – vertraging voorspellen")

# Beschikbare features
ALLE_FEATURES = {
    "Uur van de dag":        "uur",
    "Inbound / Outbound":    "is_inbound",
    "Vliegtuigtype":         "actype_code",
    "Runway":                "rwy_code",
    "Bestemming/afkomst":    "dest_code",
    "Dag van de week":       "dag_vd_week",
    "Maand":                 "maand",
    "Dag van de maand":      "dag_vd_maand",
}

# Alleen features tonen die daadwerkelijk in df zitten
beschikbare = {
    label: col
    for label, col in ALLE_FEATURES.items()
    if col in df.columns
}

with st.expander("⚙️ Instellingen regressie", expanded=True):
    gekozen_labels = st.multiselect(
        "Kies de features voor het model:",
        options=list(beschikbare.keys()),
        default=list(beschikbare.keys()),
    )
    test_size = st.slider("Testset grootte (%)", 10, 40, 20, step=5)
    target_col = st.radio(
        "Doelvariabele:",
        ["Vertraging in minuten (regressie)", "Vertragingscategorie (0/1/2)"],
        horizontal=True,
    )

if not gekozen_labels:
    st.warning("Selecteer minimaal één feature.")
    st.stop()

gekozen_cols = [beschikbare[l] for l in gekozen_labels]
y_col = "vertraging_min" if "minuten" in target_col else "delay_code"

df_model = df[gekozen_cols + [y_col]].dropna()

if len(df_model) < 50:
    st.error("Te weinig rijen na cleaning om een model te trainen.")
    st.stop()

X = df_model[gekozen_cols].values
y = df_model[y_col].values

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=test_size / 100, random_state=42
)

model = LinearRegression()
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

mae  = mean_absolute_error(y_test, y_pred)
rmse = np.sqrt(mean_squared_error(y_test, y_pred))
r2   = r2_score(y_test, y_pred)

######################
### 4. Resultaten  ###
######################

st.subheader("Modelresultaten")

m1, m2, m3, m4 = st.columns(4)
m1.metric("R² score",   f"{r2:.3f}")
m2.metric("MAE",        f"{mae:.2f} min")
m3.metric("RMSE",       f"{rmse:.2f} min")
m4.metric("Trainrijen", f"{len(X_train):,}")

# Actual vs Predicted scatter
col_r1, col_r2 = st.columns(2)

with col_r1:
    st.markdown("**Werkelijk vs. voorspeld**")
    sample_n = min(500, len(y_test))
    idx = np.random.choice(len(y_test), sample_n, replace=False)
    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=y_test[idx], y=y_pred[idx],
        mode="markers",
        marker=dict(size=4, color="#1f77b4", opacity=0.5),
        name="Voorspelling",
    ))
    # Ideale lijn
    mn, mx = float(y_test.min()), float(y_test.max())
    fig_scatter.add_trace(go.Scatter(
        x=[mn, mx], y=[mn, mx],
        mode="lines",
        line=dict(color="red", dash="dash", width=1),
        name="Ideaal",
    ))
    fig_scatter.update_layout(
        xaxis_title="Werkelijke vertraging",
        yaxis_title="Voorspelde vertraging",
        height=380,
        margin=dict(l=40, r=20, t=10, b=40),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

with col_r2:
    st.markdown("**Feature importantie (coëfficiënten)**")
    coef_df = pd.DataFrame({
        "Feature":     gekozen_labels,
        "Coëfficiënt": model.coef_,
    }).sort_values("Coëfficiënt", key=abs, ascending=True)

    fig_coef = go.Figure(go.Bar(
        x=coef_df["Coëfficiënt"],
        y=coef_df["Feature"],
        orientation="h",
        marker_color=[
            "#d62728" if c > 0 else "#1f77b4"
            for c in coef_df["Coëfficiënt"]
        ],
    ))
    fig_coef.update_layout(
        xaxis_title="Coëfficiënt (effect op vertraging)",
        height=380,
        margin=dict(l=10, r=20, t=10, b=40),
    )
    st.plotly_chart(fig_coef, use_container_width=True)

st.divider()

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
