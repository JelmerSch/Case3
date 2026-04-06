import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os
import datetime

st.set_page_config(page_title="Vluchtactiviteit & Klimaat", layout="wide")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# --- 1. DATA INLADEN ---
@st.cache_data
def load_data():
    df_airports = pd.read_csv(os.path.join(BASE_DIR, 'airports-extended-clean.csv'), sep=';', decimal=',')
    
    # Let op: index_col=0 is hier weggehaald!
    df_schedule = pd.read_csv(
        os.path.join(BASE_DIR, 'schedule_airport.csv'),
        sep=',',
        encoding='utf-8-sig'  
    )
    
    # Nu kan Pandas de kolom 'STD' wel gewoon vinden
    df_schedule['Datum'] = pd.to_datetime(df_schedule['STD'], dayfirst=True).dt.date
    
    return df_airports, df_schedule


df_airports, df_schedule = load_data()

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

# --- 3. SIDEBAR & TIJDFILTER ---
st.sidebar.header("⚙️ Filters")

min_datum = df_schedule['Datum'].min()
max_datum = df_schedule['Datum'].max()

geselecteerde_periode = st.sidebar.slider(
    "Selecteer Periode",
    min_value=min_datum,
    max_value=max_datum,
    value=(min_datum, max_datum),
    format="DD-MM-YYYY"
)

# Filter de schedule data op basis van de slider
mask = (df_schedule['Datum'] >= geselecteerde_periode[0]) & (df_schedule['Datum'] <= geselecteerde_periode[1])
df_schedule_filtered = df_schedule[mask]


# --- 4. DATA VOORBEREIDEN (Gefilterd) ---
if df_schedule_filtered.empty:
    st.warning("Er zijn geen vluchten gevonden in deze geselecteerde periode.")
    st.stop() # Stop met renderen als er geen data is

# Tel het aantal vluchten per luchthaven (nu gebaseerd op de gefilterde data)
flight_counts = df_schedule_filtered.groupby('Org/Des').size().reset_index(name='Aantal_Vluchten')

# Haal het meest voorkomende vliegtuigtype per luchthaven op
act_per_airport = (
    df_schedule_filtered.groupby('Org/Des')['ACT']
    .agg(lambda x: x.value_counts().index[0])
    .reset_index()
)

# Maak df_map aan
df_map = pd.merge(df_airports, flight_counts, left_on='ICAO', right_on='Org/Des', how='inner')
df_map = pd.merge(df_map, act_per_airport, left_on='ICAO', right_on='Org/Des', how='left')


# --- 5. CO2 & AFSTAND BEREKENEN ---
def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

df_map['Distance_km'] = haversine_vectorized(LAT_HOME, LON_HOME, df_map['Latitude'], df_map['Longitude'])
df_map['CO2_Factor'] = df_map['ACT'].map(co2_factors).fillna(7.0)
df_map['CO2_Emission_kg'] = df_map['Distance_km'] * df_map['CO2_Factor']
df_map['Climate_Impact_CO2e_kg'] = df_map['CO2_Emission_kg'] * RADIATIVE_FORCING_INDEX
df_map['Total_Climate_Impact_CO2e_Ton'] = (df_map['Climate_Impact_CO2e_kg'] * df_map['Aantal_Vluchten']) / 1000


# --- 6. DASHBOARD UI ---
st.title("🌍 Wereldwijde Vluchtactiviteit & Klimaatimpact")
st.write(f"In dit dashboard zie je gegevens voor de periode: **{geselecteerde_periode[0].strftime('%d-%m-%Y')} tot {geselecteerde_periode[1].strftime('%d-%m-%Y')}**")

# --- BUBBEL DIAGRAM ---
st.header("1. Wereldwijde Vluchtactiviteit")
fig_bubbles = px.scatter_geo(
    df_map, lat='Latitude', lon='Longitude', size='Aantal_Vluchten',
    hover_name='Name', color='Aantal_Vluchten', color_continuous_scale='Plasma',
    projection="natural earth", labels={'Aantal_Vluchten': 'Aantal Vluchten'}
)
st.plotly_chart(fig_bubbles, use_container_width=True)

st.divider()

# --- STAAF DIAGRAM (Top 10 hubs) ---
st.header("2. Top 10 Drukste Luchthavens")
top_10_hubs = df_map.nlargest(10, 'Aantal_Vluchten')

fig_bar = px.bar(
    top_10_hubs, x='Aantal_Vluchten', y='Name', orientation='h', 
    color='Aantal_Vluchten', color_continuous_scale='Viridis',
    labels={'Name': 'Luchthaven', 'Aantal_Vluchten': 'Totaal aantal vluchten'}
)
fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# --- KLIMAAT IMPACT SECTIE ---
st.header("🌱 3. Klimaatimpact Analyse (CO2e)")
st.write("Overzicht van de uitstoot per route, meegerekend dat effecten op grote hoogte de impact verdubbelen (Radiative Forcing).")

# KPI's
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

st.write("") 

# Hier staan de grafieken nu recht onder elkaar in plaats van in kolommen

# Staafdiagram meest vervuilende routes 
st.subheader("Top 10 Routes (Totale Uitstoot)")
top_10_co2 = df_map.nlargest(10, 'Total_Climate_Impact_CO2e_Ton')

fig_co2_bar = px.bar(
    top_10_co2, x='Total_Climate_Impact_CO2e_Ton', y='Name', orientation='h', 
    color='Total_Climate_Impact_CO2e_Ton', color_continuous_scale='Reds',
    labels={'Name': 'Luchthaven', 'Total_Climate_Impact_CO2e_Ton': 'CO2e (Ton)'}
)
fig_co2_bar.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_co2_bar, use_container_width=True)

st.write("") # Beetje extra ruimte ertussen

# Treemap per land 
st.subheader("Uitstootverdeling Wereldwijd")
df_tree = df_map.dropna(subset=['Country'])

fig_tree = px.treemap(
    df_tree, path=[px.Constant("Wereldwijd"), 'Country', 'Name'],
    values='Total_Climate_Impact_CO2e_Ton', color='Total_Climate_Impact_CO2e_Ton',
    color_continuous_scale='YlOrRd'
)
fig_tree.update_traces(root_color="lightgrey")
fig_tree.update_layout(margin=dict(t=25, l=10, r=10, b=10))
st.plotly_chart(fig_tree, use_container_width=True)





