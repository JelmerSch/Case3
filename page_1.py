import streamlit as st
import pandas as pd
import numpy as np
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

    if "[3d Altitude M]" in df.columns:
        df["[3d Altitude M]"] = df["[3d Altitude M]"].clip(lower=0)

    if "[3d Altitude Ft]" in df.columns:
        df["[3d Altitude Ft]"] = df["[3d Altitude Ft]"].clip(lower=0)

    if "TRUE AIRSPEED (derived)" in df.columns:
        df["TRUE AIRSPEED (derived)"] = (
            df["TRUE AIRSPEED (derived)"]
            .astype(str)
            .str.replace("*", "", regex=False)
            .pipe(pd.to_numeric, errors="coerce")
        )

    lat_col = "[3d Latitude]"
    lon_col = "[3d Longitude]"
    if lat_col in df.columns and lon_col in df.columns:
        df = df.dropna(subset=[lat_col, lon_col])

    return df

flights_30s = {naam: clean_flight(df) for naam, df in flights_30s_raw.items()}

KNOTS_TO_KMH = 1.852

COLORS_DARK = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2"]

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
duur_min     = int(gem_duur // 60)
duur_sec     = int(gem_duur % 60)

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
col_m1.metric("⏱️ Gemiddelde vluchtduur",  f"{duur_min}m {duur_sec}s")
col_m2.metric("⚡ Snelste vluchtduur",      f"{snelste_min}m {snelste_sec}s")
col_m3.metric("💨 Gemiddelde snelheid",     f"{gem_snelh:.1f} km/h")
col_m4.metric("🚀 Max. snelheid",           f"{max_snelheid:.1f} km/h")
col_m5.metric("🏔️ Max. behaalde hoogte",   f"{max_hoogte:.0f} m")

st.divider()

######################
### 2. Tabs kaart  ###
######################

st.subheader("Vliegroutes & Heading")

tab_kaart, tab_animatie = st.tabs(["🗺️ Kaart", "▶️ Animatie"])

# ──────────────────────────────────────────────
# TAB 1 — Kaart
# ──────────────────────────────────────────────
with tab_kaart:
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

# ──────────────────────────────────────────────
# TAB 2 — Animatie
# ──────────────────────────────────────────────
with tab_animatie:
    st.markdown(
        "Selecteer één vlucht om de animatie te starten. "
        "Het vliegtuigje beweegt over de route en de staart toont het afgelegde pad."
    )

    vlucht_namen = list(flights_30s.keys())
    gekozen_naam = st.selectbox("Kies een vlucht", vlucht_namen, key="anim_selectbox")
    df_anim      = flights_30s[gekozen_naam]
    kleur_anim   = COLORS_DARK[vlucht_namen.index(gekozen_naam) % len(COLORS_DARK)]

    if "[3d Latitude]" not in df_anim.columns or "[3d Longitude]" not in df_anim.columns:
        st.warning("Lat/Lon kolommen niet gevonden voor de geselecteerde vlucht.")
    else:
        lats = df_anim["[3d Latitude]"].tolist()
        lons = df_anim["[3d Longitude]"].tolist()

        # Extra hover-informatie indien beschikbaar
        heeft_hoogte   = "[3d Altitude M]" in df_anim.columns
        heeft_snelheid = "TRUE AIRSPEED (derived)" in df_anim.columns
        heeft_tijd     = "Time (secs)" in df_anim.columns

        # Bouw frames: elk frame toont het volledige pad t/m punt i,
        # plus een grotere marker op het huidige punt
        frames = []
        for i in range(1, len(lats) + 1):
            # Hover-tekst voor huidig punt
            hover_parts = [f"<b>{gekozen_naam}</b>"]
            if heeft_tijd:
                t = df_anim["Time (secs)"].iloc[i - 1]
                hover_parts.append(f"Tijd: {int(t)} sec")
            if heeft_hoogte:
                h = df_anim["[3d Altitude M]"].iloc[i - 1]
                hover_parts.append(f"Hoogte: {h:.0f} m")
            if heeft_snelheid:
                s = df_anim["TRUE AIRSPEED (derived)"].iloc[i - 1] * KNOTS_TO_KMH
                hover_parts.append(f"Snelheid: {s:.1f} km/h")
            hover_tekst = "<br>".join(hover_parts) + "<extra></extra>"

            frame_data = [
                # Staart: volledig afgelegde route
                go.Scattermapbox(
                    lat=lats[:i],
                    lon=lons[:i],
                    mode="lines",
                    line=dict(width=2, color=kleur_anim),
                    hoverinfo="skip",
                    showlegend=False,
                ),
                # Huidig punt: groot marker
                go.Scattermapbox(
                    lat=[lats[i - 1]],
                    lon=[lons[i - 1]],
                    mode="markers",
                    marker=dict(size=14, color=kleur_anim, symbol="circle"),
                    name=gekozen_naam,
                    hovertemplate=hover_tekst,
                    showlegend=False,
                ),
            ]
            frames.append(go.Frame(data=frame_data, name=str(i)))

        # Beginframe: alleen startpunt
        fig_anim = go.Figure(
            data=[
                go.Scattermapbox(
                    lat=[lats[0]],
                    lon=[lons[0]],
                    mode="lines",
                    line=dict(width=2, color=kleur_anim),
                    hoverinfo="skip",
                    showlegend=False,
                ),
                go.Scattermapbox(
                    lat=[lats[0]],
                    lon=[lons[0]],
                    mode="markers",
                    marker=dict(size=14, color=kleur_anim, symbol="circle"),
                    name=gekozen_naam,
                    showlegend=False,
                ),
            ],
            frames=frames,
        )

        fig_anim.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=46.0, lon=3.5),
                zoom=4,
            ),
            updatemenus=[
                dict(
                    type="buttons",
                    showactive=False,
                    y=0.02,
                    x=0.5,
                    xanchor="center",
                    yanchor="bottom",
                    buttons=[
                        dict(
                            label="▶ Afspelen",
                            method="animate",
                            args=[
                                None,
                                dict(
                                    frame=dict(duration=120, redraw=True),
                                    fromcurrent=True,
                                    transition=dict(duration=0),
                                ),
                            ],
                        ),
                        dict(
                            label="⏸ Pauzeren",
                            method="animate",
                            args=[
                                [None],
                                dict(
                                    frame=dict(duration=0, redraw=False),
                                    mode="immediate",
                                    transition=dict(duration=0),
                                ),
                            ],
                        ),
                    ],
                )
            ],
            sliders=[
                dict(
                    steps=[
                        dict(
                            method="animate",
                            args=[[str(k)], dict(mode="immediate", frame=dict(duration=120, redraw=True), transition=dict(duration=0))],
                            label=str(k),
                        )
                        for k in range(1, len(lats) + 1)
                    ],
                    active=0,
                    y=0,
                    x=0,
                    len=1.0,
                    currentvalue=dict(prefix="Meetpunt: ", visible=True, xanchor="center"),
                    transition=dict(duration=0),
                )
            ],
            margin=dict(l=0, r=0, t=0, b=60),
            height=570,
        )

        st.plotly_chart(fig_anim, use_container_width=True)

st.divider()

######################
### 3. Grafieken    ###
######################

col1, col2 = st.columns(2)

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
