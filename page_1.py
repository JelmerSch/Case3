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
# TAB 2 — Animatie (2D + 3D sub-tabs)
# ──────────────────────────────────────────────
with tab_animatie:
    st.markdown(
        "Selecteer één vlucht om de animatie te starten. "
        "Het vliegtuigje beweegt over de route en een pijl toont de actuele heading."
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

        heeft_hoogte   = "[3d Altitude M]" in df_anim.columns
        heeft_snelheid = "TRUE AIRSPEED (derived)" in df_anim.columns
        heeft_tijd     = "Time (secs)" in df_anim.columns
        heeft_heading  = "[3d Heading]" in df_anim.columns

        hoogtes = df_anim["[3d Altitude M]"].tolist() if heeft_hoogte else [0] * len(lats)

        # ── hulpfunctie: heading → kleine offset voor pijlpunt ──
        def heading_offset(heading_deg: float, stap: float = 0.015):
            """Geeft (dlat, dlon) voor een pijl in de richting van heading_deg."""
            rad = np.radians(heading_deg)
            dlat = stap * np.cos(rad)
            dlon = stap * np.sin(rad)
            return dlat, dlon

        # ── sub-tabs ──
        sub_2d, sub_3d = st.tabs(["🗺️ 2D animatie", "🏔️ 3D hoogteprofiel"])

        # ══════════════════════════════════════════
        # SUB-TAB A — 2D animatie met heading-pijl
        # ══════════════════════════════════════════
        with sub_2d:
            frames_2d = []
            for i in range(1, len(lats) + 1):
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
                if heeft_heading:
                    hdg = df_anim["[3d Heading]"].iloc[i - 1]
                    hover_parts.append(f"Heading: {hdg:.0f}°")
                hover_tekst = "<br>".join(hover_parts) + "<extra></extra>"

                # Heading-pijl berekenen
                if heeft_heading:
                    hdg_val = pd.to_numeric(
                        df_anim["[3d Heading]"].iloc[i - 1], errors="coerce"
                    )
                    if pd.notna(hdg_val):
                        dlat, dlon = heading_offset(hdg_val)
                        pijl_lats = [lats[i - 1], lats[i - 1] + dlat]
                        pijl_lons = [lons[i - 1], lons[i - 1] + dlon]
                    else:
                        pijl_lats = [lats[i - 1], lats[i - 1]]
                        pijl_lons = [lons[i - 1], lons[i - 1]]
                else:
                    pijl_lats = [lats[i - 1], lats[i - 1]]
                    pijl_lons = [lons[i - 1], lons[i - 1]]

                frame_data = [
                    # Staart
                    go.Scattermapbox(
                        lat=lats[:i], lon=lons[:i],
                        mode="lines",
                        line=dict(width=2, color=kleur_anim),
                        hoverinfo="skip", showlegend=False,
                    ),
                    # Vliegtuig-positie
                    go.Scattermapbox(
                        lat=[lats[i - 1]], lon=[lons[i - 1]],
                        mode="markers",
                        marker=dict(size=14, color=kleur_anim, symbol="airport"),
                        name=gekozen_naam,
                        hovertemplate=hover_tekst,
                        showlegend=False,
                    ),
                    # Heading-pijl (oranje, dun)
                    go.Scattermapbox(
                        lat=pijl_lats, lon=pijl_lons,
                        mode="lines",
                        line=dict(width=3, color="#FF6B00"),
                        hoverinfo="skip", showlegend=False,
                    ),
                ]
                frames_2d.append(go.Frame(data=frame_data, name=str(i)))

            fig_2d = go.Figure(
                data=[
                    go.Scattermapbox(lat=[lats[0]], lon=[lons[0]], mode="lines",
                                     line=dict(width=2, color=kleur_anim),
                                     hoverinfo="skip", showlegend=False),
                    go.Scattermapbox(lat=[lats[0]], lon=[lons[0]], mode="markers",
                                     marker=dict(size=14, color=kleur_anim, symbol="airport"),
                                     showlegend=False),
                    go.Scattermapbox(lat=[lats[0], lats[0]], lon=[lons[0], lons[0]],
                                     mode="lines",
                                     line=dict(width=3, color="#FF6B00"),
                                     hoverinfo="skip", showlegend=False),
                ],
                frames=frames_2d,
            )

            fig_2d.update_layout(
                mapbox=dict(
                    style="open-street-map",
                    center=dict(lat=46.0, lon=3.5),
                    zoom=4,
                ),
                updatemenus=[dict(
                    type="buttons", showactive=False,
                    y=0.02, x=0.5, xanchor="center", yanchor="bottom",
                    buttons=[
                        dict(label="▶ Afspelen", method="animate",
                             args=[None, dict(frame=dict(duration=120, redraw=True),
                                              fromcurrent=True,
                                              transition=dict(duration=0))]),
                        dict(label="⏸ Pauzeren", method="animate",
                             args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                mode="immediate",
                                                transition=dict(duration=0))]),
                    ],
                )],
                sliders=[dict(
                    steps=[
                        dict(method="animate",
                             args=[[str(k)], dict(mode="immediate",
                                                  frame=dict(duration=120, redraw=True),
                                                  transition=dict(duration=0))],
                             label=str(k))
                        for k in range(1, len(lats) + 1)
                    ],
                    active=0, y=0, x=0, len=1.0,
                    currentvalue=dict(prefix="Meetpunt: ", visible=True, xanchor="center"),
                    transition=dict(duration=0),
                )],
                margin=dict(l=0, r=0, t=0, b=60),
                height=570,
            )
            st.plotly_chart(fig_2d, use_container_width=True)
            st.caption("🟠 Oranje pijl = actuele vliegrichting (heading)")

        # ══════════════════════════════════════════
        # SUB-TAB B — 3D hoogteprofiel (Scatter3d)
        # ══════════════════════════════════════════
        with sub_3d:
            st.markdown(
                "Interactieve 3D-weergave van de vluchtroute. "
                "De Z-as toont de hoogte in meters. Draaien, zoomen en pannen is mogelijk."
            )

            if not heeft_hoogte:
                st.warning("Geen hoogtekolom ([3d Altitude M]) gevonden voor deze vlucht.")
            else:
                frames_3d = []
                for i in range(1, len(lats) + 1):
                    hover_parts_3d = [f"<b>{gekozen_naam}</b>"]
                    if heeft_tijd:
                        t = df_anim["Time (secs)"].iloc[i - 1]
                        hover_parts_3d.append(f"Tijd: {int(t)} sec")
                    hover_parts_3d.append(f"Hoogte: {hoogtes[i-1]:.0f} m")
                    if heeft_snelheid:
                        s = df_anim["TRUE AIRSPEED (derived)"].iloc[i - 1] * KNOTS_TO_KMH
                        hover_parts_3d.append(f"Snelheid: {s:.1f} km/h")
                    if heeft_heading:
                        hdg = df_anim["[3d Heading]"].iloc[i - 1]
                        hover_parts_3d.append(f"Heading: {hdg:.0f}°")
                    hover_3d = "<br>".join(hover_parts_3d) + "<extra></extra>"

                    frame_data_3d = [
                        # Staart (volledig pad t/m punt i)
                        go.Scatter3d(
                            x=lons[:i], y=lats[:i], z=hoogtes[:i],
                            mode="lines",
                            line=dict(width=4, color=kleur_anim),
                            hoverinfo="skip", showlegend=False,
                        ),
                        # Huidige positie
                        go.Scatter3d(
                            x=[lons[i - 1]], y=[lats[i - 1]], z=[hoogtes[i - 1]],
                            mode="markers",
                            marker=dict(size=8, color="#FF6B00",
                                        symbol="circle",
                                        line=dict(color="white", width=1)),
                            name=gekozen_naam,
                            hovertemplate=hover_3d,
                            showlegend=False,
                        ),
                    ]
                    frames_3d.append(go.Frame(data=frame_data_3d, name=str(i)))

                fig_3d = go.Figure(
                    data=[
                        go.Scatter3d(
                            x=[lons[0]], y=[lats[0]], z=[hoogtes[0]],
                            mode="lines",
                            line=dict(width=4, color=kleur_anim),
                            hoverinfo="skip", showlegend=False,
                        ),
                        go.Scatter3d(
                            x=[lons[0]], y=[lats[0]], z=[hoogtes[0]],
                            mode="markers",
                            marker=dict(size=8, color="#FF6B00",
                                        symbol="circle",
                                        line=dict(color="white", width=1)),
                            showlegend=False,
                        ),
                    ],
                    frames=frames_3d,
                )

                fig_3d.update_layout(
                    scene=dict(
                        xaxis=dict(title="Lengtegraad", showgrid=True, zeroline=False),
                        yaxis=dict(title="Breedtegraad", showgrid=True, zeroline=False),
                        zaxis=dict(title="Hoogte (m)", showgrid=True, zeroline=False),
                        aspectmode="manual",
                        aspectratio=dict(x=1.5, y=1, z=0.5),
                        camera=dict(eye=dict(x=1.5, y=-1.5, z=0.8)),
                    ),
                    updatemenus=[dict(
                        type="buttons", showactive=False,
                        y=0.05, x=0.5, xanchor="center", yanchor="bottom",
                        buttons=[
                            dict(label="▶ Afspelen", method="animate",
                                 args=[None, dict(frame=dict(duration=120, redraw=True),
                                                  fromcurrent=True,
                                                  transition=dict(duration=0))]),
                            dict(label="⏸ Pauzeren", method="animate",
                                 args=[[None], dict(frame=dict(duration=0, redraw=False),
                                                    mode="immediate",
                                                    transition=dict(duration=0))]),
                        ],
                    )],
                    sliders=[dict(
                        steps=[
                            dict(method="animate",
                                 args=[[str(k)], dict(mode="immediate",
                                                      frame=dict(duration=120, redraw=True),
                                                      transition=dict(duration=0))],
                                 label=str(k))
                            for k in range(1, len(lats) + 1)
                        ],
                        active=0, y=0, x=0, len=1.0,
                        currentvalue=dict(prefix="Meetpunt: ", visible=True, xanchor="center"),
                        transition=dict(duration=0),
                    )],
                    margin=dict(l=0, r=0, t=30, b=60),
                    height=580,
                )
                st.plotly_chart(fig_3d, use_container_width=True)
                st.caption("🔵 Lijn = vluchtpad  •  🟠 Punt = huidige positie  •  Draaien: sleep met muis")

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
