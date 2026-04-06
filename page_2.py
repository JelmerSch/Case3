import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os

st.set_page_config(page_title="Vluchtactiviteit & Klimaat", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 1. DATA INLADEN ---
df_airports = pd.read_csv(os.path.join(BASE_DIR, 'airports-extended-clean.csv'), sep=';', decimal=',')
df_schedule = pd.read_csv(
    os.path.join(BASE_DIR, 'schedule_airport.csv'),
    sep=',',
    index_col=0,
    encoding='utf-8-sig'  # fix voor BOM-karakter
)

# --- 2. CO2 CONFIGURATIE ---
LAT_HOME = 47.4647
LON_HOME = 8.5492

co2_factors = {
    'A319': 5.5,
    'A320': 6.0,
    'A321': 6.5,
    'A21N': 5.5,
    'B763': 15.0,
    'A359': 18.0,
}
RADIATIVE_FORCING_INDEX = 2.0

# --- 3. DATA VOORBEREIDEN ---
# Tel het aantal vluchten per luchthaven
flight_counts = df_schedule.groupby('Org/Des').size().reset_index(name='Aantal_Vluchten')

# Haal het meest voorkomende vliegtuigtype per luchthaven op
act_per_airport = (
    df_schedule.groupby('Org/Des')['ACT']
    .agg(lambda x: x.value_counts().index[0])
    .reset_index()
)

# STAP 1: maak df_map aan
df_map = pd.merge(df_airports, flight_counts, left_on='ICAO', right_on='Org/Des', how='inner')

# STAP 2: voeg vliegtuigtype toe aan de al bestaande df_map
df_map = pd.merge(df_map, act_per_airport, left_on='ICAO', right_on='Org/Des', how='left')


# --- 4. CO2 & AFSTAND BEREKENEN ---
def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# Bereken afstand en CO2 factor
df_map['Distance_km'] = haversine_vectorized(LAT_HOME, LON_HOME, df_map['Latitude'], df_map['Longitude'])
df_map['CO2_Factor'] = df_map['ACT'].map(co2_factors).fillna(7.0)

# Berekening per enkele vlucht
df_map['CO2_Emission_kg'] = df_map['Distance_km'] * df_map['CO2_Factor']
df_map['Climate_Impact_CO2e_kg'] = df_map['CO2_Emission_kg'] * RADIATIVE_FORCING_INDEX

# CORRECTIE: Bereken de totale impact van álle vluchten op deze route in Ton (1000 kg)
df_map['Total_Climate_Impact_CO2e_Ton'] = (df_map['Climate_Impact_CO2e_kg'] * df_map['Aantal_Vluchten']) / 1000


# --- 5. DASHBOARD UI ---
st.title("🌍 Wereldwijde Vluchtactiviteit & Klimaatimpact")
st.write("In dit dashboard zie je het vliegschema, de drukste routes en de bijbehorende klimaatimpact.")

# --- BUBBEL DIAGRAM (Alle vluchten) ---
st.header("1. Wereldwijde Vluchtactiviteit")
fig_bubbles = px.scatter_geo(
    df_map,
    lat='Latitude',
    lon='Longitude',
    size='Aantal_Vluchten',
    hover_name='Name',
    color='Aantal_Vluchten',
    color_continuous_scale='Plasma',
    projection="natural earth",
    labels={'Aantal_Vluchten': 'Aantal Vluchten'}
)
st.plotly_chart(fig_bubbles, use_container_width=True)

st.divider()

# --- STAAF DIAGRAM (Top 10 hubs) ---
st.header("2. Top 10 Drukste Luchthavens")
top_10_hubs = df_map.nlargest(10, 'Aantal_Vluchten')

fig_bar = px.bar(
    top_10_hubs, 
    x='Aantal_Vluchten', 
    y='Name', 
    orientation='h', 
    color='Aantal_Vluchten',
    color_continuous_scale='Viridis',
    labels={'Name': 'Luchthaven', 'Aantal_Vluchten': 'Totaal aantal vluchten'}
)
fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# --- KLIMAAT IMPACT SECTIE ---
st.header("🌱 3. Klimaatimpact Analyse (CO2e)")
st.write("Overzicht van de uitstoot per route, meegerekend dat effecten op grote hoogte de impact verdubbelen (Radiative Forcing).")

# KPI's (Voorstel 3)
totale_uitstoot = df_map['Total_Climate_Impact_CO2e_Ton'].sum()
gemiddelde_vlucht = df_map['Climate_Impact_CO2e_kg'].mean()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Totale Netwerk Uitstoot (Ton)", f"{totale_uitstoot:,.0f}".replace(',', '.'))
with col2:
    st.metric("Gem. uitstoot enkele vlucht (Kg)", f"{gemiddelde_vlucht:,.0f}".replace(',', '.'))
with col3:
    bomen_nodig = (totale_uitstoot * 1000) / 20
    st.metric("Bomen nodig voor compensatie", f"{bomen_nodig:,.0f}".replace(',', '.'))

st.write("") # Extra witruimte


    # Staafdiagram meest vervuilende routes (Voorstel 1)
    st.subheader("Top 10 Routes (Totale Uitstoot)")
    top_10_co2 = df_map.nlargest(10, 'Total_Climate_Impact_CO2e_Ton')

    fig_co2_bar = px.bar(
        top_10_co2, 
        x='Total_Climate_Impact_CO2e_Ton', 
        y='Name', 
        orientation='h', 
        color='Total_Climate_Impact_CO2e_Ton',
        color_continuous_scale='Reds',
        labels={'Name': 'Luchthaven', 'Total_Climate_Impact_CO2e_Ton': 'CO2e (Ton)'}
    )
    fig_co2_bar.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_co2_bar, use_container_width=True)


    # Treemap per land (Voorstel 2)
    st.subheader("Uitstootverdeling Wereldwijd")
    # Zorg dat lege landen de grafiek niet breken
    df_tree = df_map.dropna(subset=['Country'])
    
    fig_tree = px.treemap(
        df_tree,
        path=[px.Constant("Wereldwijd"), 'Country', 'Name'],
        values='Total_Climate_Impact_CO2e_Ton',
        color='Total_Climate_Impact_CO2e_Ton',
        color_continuous_scale='YlOrRd'
    )
    fig_tree.update_traces(root_color="lightgrey")
    fig_tree.update_layout(margin = dict(t=25, l=10, r=10, b=10))
    st.plotly_chart(fig_tree, use_container_width=True)








