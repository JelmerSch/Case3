import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from Startdash import initialize_data

# Session_state aanroepen voor data
initialize_data()

######################
###  Inladen data  ###
######################

airports = st.session_state["airports"]
flights  = st.session_state["flights"]

######################
### Filter bestanden #
######################

# 30-seconden bestanden
flights_30s_raw = {
    naam: df
    for naam, df in flights.items()
    if "30" in naam
}

if not flights_30s_raw:
    st.error("Geen 30-seconden vluchtbestanden gevonden. Controleer de bestandsnamen in de ZIP.")
    st.stop()

######################
### Data cleaning   ###
######################

def clean_flight(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1. Hoogte onder 0 → 0 (meters)
    if "[3d Altitude M]" in df.columns:
        df["[3d Altitude M]"] = df["[3d Altitude M]"].clip(lower=0)

    # 2. Hoogte onder 0 → 0 (feet)
    if "[3d Altitude Ft]" in df.columns:
        df["[3d Altitude Ft]"] = df["[3d Altitude Ft]"].clip(lower=0)

    # 3. Verwijder "*" uit snelheidskolom
    if "TRUE AIRSPEED (derived)" in df.columns:
        df["TRUE AIRSPEED (derived)"] = (
            df["TRUE AIRSPEED (derived)"]
            .astype(str)
            .str.replace("*", "", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
        )

    # 4. Rijen verwijderen waar lat of lon leeg is
    lat_col = "[3d Latitude]"
    lon_col = "[3d Longitude]"
    if lat_col in df.columns and lon_col in df.columns:
        df = df.dropna(subset=[lat_col, lon_col])

    return df

flights_30s = {naam: clean_flight(df) for naam, df in flights_30s_raw.items()}

# Knoop factor: airspeed is in knoten → km/h
KNOTS_TO_KMH = 1.852

# Kleurenreeks voor maximaal 7 vluchten
COLORS_DARK = [
    "#1f77b4",  # blauw
    "#ff7f0e",  # oranje
    "#2ca02c",  # groen
    "#d62728",  # rood
    "#9467bd",  # paars
    "#8c564b",  # bruin
    "#e377c2",  # roze
]

######################
### Pagina-inhoud  ###
######################

st.title("Vluchten van Zippie")
st.divider()

######################
### 1. Statistieken ##
######################

st.subheader("Statistieken over alle vluchten (30 sec)")

gem_tijden         = []
gem_snelheden      = []
max_hoogtes        = []
alle_max_snelheden = []

for naam, df in flights_30s.items():
    if "Time (secs)" in df.columns:
        gem_tijden.append(df["Time (secs)"].max())
    if "TRUE AIRSPEED (derived)" in df.columns:
        gem_snelheden.append(df["TRUE AIRSPEED (derived)"].mean() * KNOTS_TO_KMH)
        alle_max_snelheden.append(df["TRUE AIRSPEED (derived)"].max() * KNOTS_TO_KMH)
    if "[3d Altitude M]" in df.columns:
        max_hoogtes.append(df["[3d Altitude M]"].max())

gem_duur     = sum(gem_tijden)    / len(gem_tijden)    if gem_tijden         else 0
gem_snelh    = sum(gem_snelheden) / len(gem_snelheden) if gem_snelheden      else 0
max_hoogte   = max(max_hoogtes)                        if max_hoogtes        else 0
max_snelheid = max(alle_max_snelheden)                 if alle_max_snelheden else 0

snelste_duur = min(gem_tijden) if gem_tijden else 0
snelste_min  = int(snelste_duur // 60)
snelste_sec  = int(snelste_duur % 60)

duur_min = int(gem_duur // 60)
duur_sec = int(gem_duur % 60)

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
col_m1.metric("⏱️ Gemiddelde vluchtduur",  f"{duur_min}m {duur_sec}s")
col_m2.metric("⚡ Snelste vluchtduur",      f"{snelste_min}m {snelste_sec}s")
col_m3.metric("💨 Gemiddelde snelheid",     f"{gem_snelh:.1f} km/h")
col_m4.metric("🚀 Max. snelheid",           f"{max_snelheid:.1f} km/h")
col_m5.metric("🏔️ Max. behaalde hoogte",   f"{max_hoogte:.0f} m")

st.divider()

######################
### 2. Kaart        ###
######################

st.subheader("Vliegroutes op de kaart")

fig_kaart = go.Figure()

for i, (naam, df) in enumerate(flights_30s.items()):
    kleur = COLORS_DARK[i % len(COLORS_DARK)]
    if "[3d Latitude]" not in df.columns or "[3d Longitude]" not in df.columns:
        st.warning(f"Lat/Lon kolommen niet gevonden in {naam}")
        continue

    fig_kaart.add_trace(go.Scattermapbox(
        lat=df["[3d Latitude]"],
        lon=df["[3d Longitude]"],
        mode="lines+markers",
        name=naam,
        line=dict(width=2, color=kleur),
        marker=dict(size=4, color=kleur),
        hovertemplate=(
            "<b>%{fullData.name}</b><br>"
            "Lat: %{lat:.4f}<br>"
            "Lon: %{lon:.4f}<extra></extra>"
        ),
    ))

fig_kaart.update_layout(
    mapbox=dict(
        style="open-street-map",
        center=dict(lat=46.0, lon=3.5),
        zoom=4,
    ),
    legend_title="Vlucht",
    margin=dict(l=0, r=0, t=0, b=0),
    height=550,
)

st.plotly_chart(fig_kaart, use_container_width=True)

st.divider()

######################
### 3. Grafieken    ###
######################

col1, col2 = st.columns(2)

# --- Figuur 1: Hoogte ---
with col1:
    st.subheader("Hoogte per vlucht (30 sec)")
    fig_hoogte = go.Figure()

    for i, (naam, df) in enumerate(flights_30s.items()):
        kleur = COLORS_DARK[i % len(COLORS_DARK)]
        if "Time (secs)" not in df.columns or "[3d Altitude M]" not in df.columns:
            st.warning(f"Kolommen niet gevonden in {naam}")
            continue
        fig_hoogte.add_trace(go.Scatter(
            x=df["Time (secs)"],
            y=df["[3d Altitude M]"],
            mode="lines",
            name=naam,
            line=dict(color=kleur, width=2),
            hovertemplate=(
                "<b>%{fullData.name}</b><br>"
                "Tijd: %{x} sec<br>"
                "Hoogte: %{y:.1f} m<extra></extra>"
            ),
        ))

    fig_hoogte.update_layout(
        xaxis_title="Tijd (seconden)",
        yaxis_title="Hoogte (meter)",
        legend_title="Vlucht",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=30, b=40),
        height=400,
    )
    st.plotly_chart(fig_hoogte, use_container_width=True)

# --- Figuur 2: Snelheid ---
with col2:
    st.subheader("Snelheid per vlucht (30 sec)")
    fig_snelheid = go.Figure()

    for i, (naam, df) in enumerate(flights_30s.items()):
        kleur = COLORS_DARK[i % len(COLORS_DARK)]
        if "Time (secs)" not in df.columns or "TRUE AIRSPEED (derived)" not in df.columns:
            st.warning(f"Kolommen niet gevonden in {naam}")
            continue
        fig_snelheid.add_trace(go.Scatter(
            x=df["Time (secs)"],
            y=df["TRUE AIRSPEED (derived)"] * KNOTS_TO_KMH,
            mode="lines",
            name=naam,
            line=dict(color=kleur, width=2),
            hovertemplate=(
                "<b>%{fullData.name}</b><br>"
                "Tijd: %{x} sec<br>"
                "Snelheid: %{y:.1f} km/h<extra></extra>"
            ),
        ))

    fig_snelheid.update_layout(
        xaxis_title="Tijd (seconden)",
        yaxis_title="Snelheid (km/h)",
        legend_title="Vlucht",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=30, b=40),
        height=400,
    )
    st.plotly_chart(fig_snelheid, use_container_width=True)

###Einde script###
