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
### Filter 30-sec  ###
######################

flights_30s = {
    naam: df
    for naam, df in flights.items()
    if "30" in naam
}

if not flights_30s:
    st.error("Geen 30-seconden vluchtbestanden gevonden. Controleer de bestandsnamen in de ZIP.")
    st.stop()

# Vaste kleurenreeks voor maximaal 7 vluchten
COLORS = [
    "#1f77b4",  # blauw
    "#ff7f0e",  # oranje
    "#2ca02c",  # groen
    "#d62728",  # rood
    "#9467bd",  # paars
    "#8c564b",  # bruin
    "#e377c2",  # roze
]

# Knoop factor: airspeed is in knoten → km/h
KNOTS_TO_KMH = 1.852

######################
### Pagina-inhoud  ###
######################

st.title("Vluchten van Zippie")
st.divider()

######################
### 1. Statistieken ##
######################

st.subheader("Gemiddelden over alle vluchten (30 sec)")

# Bereken statistieken over alle vluchten
gem_tijden    = []
gem_snelheden = []
max_hoogtes   = []

for naam, df in flights_30s.items():
    if "Time (secs)" in df.columns:
        gem_tijden.append(df["Time (secs)"].max())  # totale vluchtduur
    if "TRUE AIRSPEED (derived)" in df.columns:
        gem_snelheden.append(df["TRUE AIRSPEED (derived)"].mean() * KNOTS_TO_KMH)
    if "[3d Altitude M]" in df.columns:
        max_hoogtes.append(df["[3d Altitude M]"].max())

gem_duur    = sum(gem_tijden)    / len(gem_tijden)    if gem_tijden    else 0
gem_snelh   = sum(gem_snelheden) / len(gem_snelheden) if gem_snelheden else 0
max_hoogte  = max(max_hoogtes)                        if max_hoogtes   else 0

# Voor berkening snelste vlucht:
snelste_duur   = min(gem_tijden) if gem_tijden else 0
snelste_min    = int(snelste_duur // 60)
snelste_sec    = int(snelste_duur % 60)

# Omzetten naar minuten en seconden
duur_min = int(gem_duur // 60)
duur_sec = int(gem_duur % 60)

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("⏱️ Gemiddelde vluchtduur",   f"{duur_min}m {duur_sec}s")
col_m2.metric("⚡ Snelste vluchtduur",       f"{snelste_min}m {snelste_sec}s")
col_m3.metric("💨 Gemiddelde snelheid",      f"{gem_snelh:.1f} km/h")
col_m4.metric("🏔️ Max. behaalde hoogte",    f"{max_hoogte:.0f} m")

st.divider()

######################
### 2. Kaart        ###
######################

st.subheader("Vliegroutes op de kaart (30 sec)")

fig_kaart = go.Figure()

for i, (naam, df) in enumerate(flights_30s.items()):
    kleur = COLORS[i % len(COLORS)]
    if "[3d Latitude]" not in df.columns or "[3d Longitude]" not in df.columns:
        st.warning(f"Lat/Lon kolommen niet gevonden in {naam}")
        continue

    df_clean = df.dropna(subset=["[3d Latitude]", "[3d Longitude]"])

    fig_kaart.add_trace(go.Scattermapbox(
        lat=df_clean["[3d Latitude]"],
        lon=df_clean["[3d Longitude]"],
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

# Amsterdam → Barcelona: centrum op 43N en 3.5L
fig_kaart.update_layout(
    mapbox=dict(
        style="open-street-map",
        center=dict(lat=40.0, lon=3.5),
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
        kleur = COLORS[i % len(COLORS)]
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

# --- Figuur 2: Snelheid in km/h ---
with col2:
    st.subheader("Snelheid per vlucht (30 sec)")
    fig_snelheid = go.Figure()

    for i, (naam, df) in enumerate(flights_30s.items()):
        kleur = COLORS[i % len(COLORS)]
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
