import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- 1. DATA INLADEN ---
# We laden de data één keer in voor de hele pagina
df_airports = pd.read_csv('airports-extended-clean.csv', sep=';', decimal=',')
df_schedule = pd.read_csv('schedule_airport.csv')

# --- 2. DATA VOORBEREIDEN ---
# Tel het aantal vluchten per ICAO code
flight_counts = df_schedule.groupby('Org/Des').size().reset_index(name='Aantal_Vluchten')

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


# 1. Definieer de coördinaten van de thuisbasis (Zürich - LSZH)
LAT_HOME = 47.4647
LON_HOME = 8.5492

# Functie om afstand in kilometers te berekenen (Haversine)
def haversine_vectorized(lat1, lon1, lat2, lon2):
    R = 6371.0 # Straal van de aarde in km
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# Pas toe op je dataset (ervan uitgaande dat je display_df al hebt)
display_df['Distance_km'] = haversine_vectorized(LAT_HOME, LON_HOME, display_df['Latitude'], display_df['Longitude'])

# 2. Maak een simpele dictionary voor CO2 uitstoot (kg per km per vliegtuig)
# Let op: Dit zijn ruwe schattingen voor het hele vliegtuig, niet per passagier!
# Je kunt deze lijst uitbreiden op basis van de unieke waarden in df['ACT'].unique()
co2_factors = {
    'A319': 5.5,   # Narrow-body
    'A320': 6.0,
    'A321': 6.5,
    'A21N': 5.5,   # A321 Neo (zuiniger)
    'B763': 15.0,  # Wide-body (ouder)
    'A359': 18.0,  # Wide-body (groot)
    # Voeg een standaardwaarde toe voor onbekende types
}

# Map de factoren, vul onbekende types met een gemiddelde (bijv. 7.0 kg/km)
display_df['CO2_Factor'] = display_df['ACT'].map(co2_factors).fillna(7.0)

# 3. Bereken de klimaatimpact
RADIATIVE_FORCING_INDEX = 2.0 # Verdubbelaar voor de impact op grote hoogte

# Absolute CO2 in kg
display_df['CO2_Emission_kg'] = display_df['Distance_km'] * display_df['CO2_Factor']

# Totale klimaatimpact (CO2e)
display_df['Climate_Impact_CO2e_kg'] = display_df['CO2_Emission_kg'] * RADIATIVE_FORCING_INDEX




