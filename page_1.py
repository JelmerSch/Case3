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

# Selecteer alleen de 30-seconden vluchten op basis van bestandsnaam
flights_30s = {
    naam: df
    for naam, df in flights.items()
    if "30" in naam  # pas aan als je naamgeving anders is
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

######################
### Pagina-inhoud  ###
######################

st.title("Vluchten van Zippie")
st.divider()

######################
### Figuur 1 & 2   ###
######################

col1, col2 = st.columns(2)

# --- Figuur 1: Hoogte ---
with col1:
    st.subheader("Hoogte per vlucht (30 sec)")
    fig_hoogte = go.Figure()

    for i, (naam, df) in enumerate(flights_30s.items()):
        kleur = COLORS[i % len(COLORS)]
        # Kolommen veilig ophalen
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
        kleur = COLORS[i % len(COLORS)]
        if "Time (secs)" not in df.columns or "TRUE AIRSPEED (derived)" not in df.columns:
            st.warning(f"Kolommen niet gevonden in {naam}")
            continue
        fig_snelheid.add_trace(go.Scatter(
            x=df["Time (secs)"],
            y=df["TRUE AIRSPEED (derived)"],
            mode="lines",
            name=naam,
            line=dict(color=kleur, width=2),
            hovertemplate=(
                "<b>%{fullData.name}</b><br>"
                "Tijd: %{x} sec<br>"
                "Snelheid: %{y:.1f}<extra></extra>"
            ),
        ))

    fig_snelheid.update_layout(
        xaxis_title="Tijd (seconden)",
        yaxis_title="True Airspeed (derived)",
        legend_title="Vlucht",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=30, b=40),
        height=400,
    )
    st.plotly_chart(fig_snelheid, use_container_width=True)

st.divider()

######################
### Figuur 3: Route ###
######################

st.subheader("Vliegroutes op de kaart (30 sec)")

fig_kaart = go.Figure()

for i, (naam, df) in enumerate(flights_30s.items()):
    kleur = COLORS[i % len(COLORS)]
    if "[3d Latitude]" not in df.columns or "[3d Longitude]" not in df.columns:
        st.warning(f"Lat/Lon kolommen niet gevonden in {naam}")
        continue

    # Verwijder rijen zonder coördinaten
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

# Centreer kaart op gemiddelde van alle vluchten
all_lats = pd.concat([
    df["[3d Latitude]"].dropna()
    for df in flights_30s.values()
    if "[3d Latitude]" in df.columns
])
all_lons = pd.concat([
    df["[3d Longitude]"].dropna()
    for df in flights_30s.values()
    if "[3d Longitude]" in df.columns
])

center_lat = float(all_lats.mean()) if not all_lats.empty else 52.3
center_lon = float(all_lons.mean()) if not all_lons.empty else 4.9

fig_kaart.update_layout(
    mapbox=dict(
        style="open-street-map",
        center=dict(lat=center_lat, lon=center_lon),
        zoom=10,
    ),
    legend_title="Vlucht",
    margin=dict(l=0, r=0, t=0, b=0),
    height=500,
)

st.plotly_chart(fig_kaart, use_container_width=True)