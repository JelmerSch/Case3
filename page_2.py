import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import os

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


# Nu werkt dit wel:
df_map['CO2_Factor'] = df_map['ACT'].map(co2_factors).fillna(7.0)


# Koppel de tellingen aan de vliegveld-informatie (naam, lat, lon)
# We gebruiken 'inner' om alleen vliegvelden te tonen die in het schema staan
df_map = pd.merge(df_airports, flight_counts, left_on='ICAO', right_on='Org/Des', how='inner')

# --- 3. BUBBEL DIAGRAM (Alle vluchten) ---
st.title("Wereldwijde Vluchtactiviteit")
st.write("In dit overzicht zie je alle luchthavens uit het vliegschema.")

fig_bubbles = px.scatter_geo(
    df_map,
    lat='Latitude',
    lon='Longitude',
    size='Aantal_Vluchten',
    hover_name='Name',
    color='Aantal_Vluchten',
    color_continuous_scale='Plasma',
    projection="natural earth",
    title='Alle vluchten per luchthaven',
    labels={'Aantal_Vluchten': 'Aantal Vluchten'}
)

st.plotly_chart(fig_bubbles, use_container_width=True)

st.divider() # Een lijn tussen de twee grafieken

# --- 4. STAAF DIAGRAM (Top 10 hubs) ---
st.header("Top 10 Drukste Luchthavens")

# Filter de top 10 uit de al bestaande df_map
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

# Zorg dat de grootste staaf bovenaan staat
fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})

st.plotly_chart(fig_bar, use_container_width=True)


st.divider()

# 1. Thuisbasis coördinaten (Zürich - LSZH)
LAT_HOME = 47.4647
LON_HOME = 8.5492

# 2. CO2 factoren dictionary (kg per km per vliegtuig)
co2_factors = {
    'A319': 5.5,
    'A320': 6.0,
    'A321': 6.5,
    'A21N': 5.5,
    'B763': 15.0,
    'A359': 18.0,
}

RADIATIVE_FORCING_INDEX = 2.0

# 3. Haversine functie
def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# 4. Bereken afstand en CO2 op df_map
df_map['Distance_km'] = haversine_vectorized(LAT_HOME, LON_HOME, df_map['Latitude'], df_map['Longitude'])
df_map['CO2_Factor'] = df_map['ACT'].map(co2_factors).fillna(7.0)
df_map['CO2_Emission_kg'] = df_map['Distance_km'] * df_map['CO2_Factor']
df_map['Climate_Impact_CO2e_kg'] = df_map['CO2_Emission_kg'] * RADIATIVE_FORCING_INDEX



# Map de factoren, vul onbekende types met een gemiddelde (bijv. 7.0 kg/km)
display_df['CO2_Factor'] = display_df['ACT'].map(co2_factors).fillna(7.0)

# 3. Bereken de klimaatimpact
RADIATIVE_FORCING_INDEX = 2.0 # Verdubbelaar voor de impact op grote hoogte

# Absolute CO2 in kg
display_df['CO2_Emission_kg'] = display_df['Distance_km'] * display_df['CO2_Factor']

# Totale klimaatimpact (CO2e)
display_df['Climate_Impact_CO2e_kg'] = display_df['CO2_Emission_kg'] * RADIATIVE_FORCING_INDEX






