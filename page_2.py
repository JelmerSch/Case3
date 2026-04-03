import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px




# 1. Laad de vliegvelden (let op de puntkomma en de komma als decimaal)
df_airports = pd.read_csv('airports-extended-clean.csv', sep=';', decimal=',')

# 2. Laad de vluchten
df_schedule = pd.read_csv('schedule_airport.csv')

# 3. Tel het aantal vluchten per vliegveld (kolom 'Org/Des')
flight_counts = df_schedule.groupby('Org/Des').size().reset_index(name='FLT')

# 4. Voeg de data samen
# We koppelen 'ICAO' uit het vliegveld-bestand aan 'Org/Des' uit de tellingen
df_map = pd.merge(df_airports, flight_counts, left_on='ICAO', right_on='Org/Des', how='inner')

# 5. Maak het bubbeldiagram
fig = px.bar(
    top_10_hubs, 
    x='Aantal_Vluchten',       # GEFIXT: underscore toegevoegd
    y='Name', 
    orientation='h', 
    title='Top 10 Drukste Luchthavens',
    # In de labels kun je WEL spaties gebruiken voor de weergave
    labels={'Name': 'Luchthaven', 'Aantal_Vluchten': 'Totaal aantal vluchten'},
    color='Aantal_Vluchten',   # GEFIXT: underscore toegevoegd
    color_continuous_scale='Viridis'
)

fig.show()

st.divider()

# Een staaf diagram van de 10 drukste luchthavens

df_airports = pd.read_csv('airports-extended-clean.csv', sep=';', decimal=',')
df_schedule = pd.read_csv('schedule_airport.csv')

# 2 aantal vluchten per luchthaven
flight_counts = df_schedule.groupby('Org/Des').size().reset_index(name='Aantal_Vluchten')

# 3. koppelen aan vliegvelden
df_hubs = pd.merge(flight_counts, df_airports, left_on='Org/Des', right_on='ICAO', how='inner')

# 4. Top 10 drukste luchthavens
top_10_hubs = df_hubs.nlargest(10, 'Aantal_Vluchten')   

# 5. Staafdiagram maken
fig = px.bar(
    top_10_hubs, 
    x='Aantal_Vluchten', 
    y='Name',            # De naam van het vliegveld op de y-as
    orientation='h',      # Horizontaal diagram voor betere leesbaarheid van namen
    title='Top 10 Drukste Luchthavens',
    labels={'Name': 'Luchthaven', 'Aantal Vluchten': 'Totaal aantal vluchten'},
    color='Aantal Vluchten',
    color_continuous_scale='Viridis'
)

# Zorg dat de drukste bovenaan staat
fig.update_layout(yaxis={'categoryorder':'total ascending'})

# 6. Weergeven in Streamlit
st.title("Luchtvaart Dashboard")
st.plotly_chart(fig, use_container_width=True)


