import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

# Pagina configuratie
st.set_page_config(page_title="Airport Insights Dashboard", layout="wide")

# Functie om data in te laden (gecached voor snelheid)
@st.cache_data
def load_data():
    base_dir = os.path.dirname(__file__)

    airports = pd.read_csv(os.path.join(base_dir, 'airports-extended-clean.csv'), sep=';', decimal=',')
    schedule = pd.read_csv(os.path.join(base_dir, 'schedule_airport.csv'))

    # Latitude/Longitude regels weg — decimal=',' doet dit al bij het inladen

    schedule['Scheduled_DT'] = pd.to_datetime(schedule['STD'] + ' ' + schedule['STA_STD_ltc'], dayfirst=True)
    schedule['Actual_DT'] = pd.to_datetime(schedule['STD'] + ' ' + schedule['ATA_ATD_ltc'], dayfirst=True)
    schedule['Delay_min'] = (schedule['Actual_DT'] - schedule['Scheduled_DT']).dt.total_seconds() / 60

    df = schedule.merge(airports[['ICAO', 'Name', 'City', 'Country']],
                        left_on='Org/Des', right_on='ICAO', how='left')

    df['Month_str'] = df['Scheduled_DT'].dt.to_period('M').astype(str)
    df['Day_of_Week'] = df['Scheduled_DT'].dt.day_name()

    return df

# Data laden
df = load_data()

# --- STREAMLIT UI ---
st.title("✈️ Airport Operations & Insights Dashboard")
st.markdown("Dit dashboard geeft inzicht in vluchtvolumes, bestemmingen en vertragingen op basis van de verstrekte data.")

# Sidebar filters
st.sidebar.header("Filters")
selected_country = st.sidebar.multiselect("Selecteer Landen", options=df['Country'].unique(), default=None)

if selected_country:
    display_df = df[df['Country'].isin(selected_country)]
else:
    display_df = df

# Key Metrics
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Totaal aantal vluchten", len(display_df))
with col2:
    avg_delay = display_df[display_df['Delay_min'] > 0]['Delay_min'].mean()
    st.metric("Gem. Vertraging", f"{avg_delay:.1f} min")
with col3:
    st.metric("Unieke Bestemmingen", display_df['Org/Des'].nunique())
with col4:
    most_common_ac = display_df['ACT'].mode()[0]
    st.metric("Meest gebruikt toestel", most_common_ac)

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Volumes", "⏰ Vertragingen", "🛩️ Vloot & Bestemmingen"])

with tab1:
    st.header("Vluchtvolumes")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Volume per Maand")
        fig_vol = plt.figure(figsize=(10, 5))
        monthly_data = display_df.groupby('Month_str').size()
        plt.plot(monthly_data.index, monthly_data.values, marker='o', color='teal')
        plt.xticks(rotation=45)
        plt.ylabel("Aantal vluchten")
        st.pyplot(fig_vol)

    with col_b:
        st.subheader("Volume per Dag")
        fig_day = plt.figure(figsize=(10, 5))
        
        order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        nl_order = ['maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag', 'zondag']

        translation = dict(zip(order, nl_order))
        
        day_data = display_df['Day_of_Week'].value_counts().reindex(order)
        day_data.index = day_data.index.map(translation)
        
        sns.barplot(x=day_data.index, y=day_data.values, palette='coolwarm')
        plt.xticks(rotation=45)
        plt.xlabel("Dag van de week")
        st.pyplot(fig_day)

with tab2:
    st.header("Vertragingsanalyse")
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Verdeling van Vertragingen (tot 120 min)")
        fig_hist = plt.figure(figsize=(10, 4))
        sns.histplot(
        display_df[(display_df['Delay_min'] > 0) & (display_df['Delay_min'] < 120)]['Delay_min'],
        bins=40, kde=True, color='purple')
        plt.xlabel("Minuten te laat")
        plt.ylabel("Aantal")
        st.pyplot(fig_hist)

    # FIX 2: dubbele/drievoudige st.subheader regels verwijderd, enkel één gehouden
    with col_b:
        st.subheader("Gemiddelde Vertraging per Bestemming")
        delay_dest = (
        display_df[display_df['Delay_min'] > 0]
        .groupby('Name')['Delay_min']
        .mean()
        .sort_values(ascending=False)
        .head(10)
        )
        fig_dest = plt.figure(figsize=(10, 4))
        sns.barplot(x=delay_dest.values, y=delay_dest.index, palette='Reds_r')
        plt.xlabel("Gem. vertraging (min)")
        plt.ylabel("")
        st.pyplot(fig_dest)

    st.subheader("Gemiddelde Vertraging per Dag van de Week")
    order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    delay_day = (
        display_df[display_df['Delay_min'] > 0]
        .groupby('Day_of_Week')['Delay_min']
        .mean()
        .reindex(order)
    )
    fig_day2 = plt.figure(figsize=(10, 4))
    sns.barplot(x=delay_day.index, y=delay_day.values, palette='coolwarm')
    plt.xticks(rotation=45)
    plt.ylabel("Gem. vertraging (min)")
    plt.xlabel("Dag van de week")
    st.pyplot(fig_day2)

with tab3:

    
    st.header("Vloot & Bestemmingen")
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("Top 10 Bestemmingen")
        top_dest = display_df['Name'].value_counts().head(10)
        fig_top = plt.figure(figsize=(10, 5))
        sns.barplot(x=top_dest.values, y=top_dest.index, palette='Blues_r')
        plt.xlabel("Aantal vluchten")
        plt.ylabel("")
        st.pyplot(fig_top)

    with col_b: 
        st.subheader("Vlootsamenstelling")
        fleet = display_df['ACT'].value_counts().head(10)
        fig_fleet = plt.figure(figsize=(10, 5))
        sns.barplot(x=fleet.values, y=fleet.index, palette='Greens_r')
        plt.xlabel("Aantal vluchten")
        plt.ylabel("type vliegtuig")
        st.pyplot(fig_fleet)
