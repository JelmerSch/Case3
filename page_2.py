import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
!pip install plotly



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
fig = px.scatter_geo(
    df_map,
    lat='Latitude',
    lon='Longitude',
    size='FLT',               # Grootte op basis van aantal vluchten
    hover_name='Name',        # Toon naam van vliegveld bij hover
    color='FLT',              # Kleur op basis van drukte
    projection="natural earth",
    title='Drukte op luchthavens op basis van vliegschema'
)

fig.show()


