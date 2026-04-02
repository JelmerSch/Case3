import streamlit as st
from Startdash import initialize_data

st.set_page_config(layout="wide", page_title="vlucht data analyse")
initialize_data()

dashboard = st.Page("Startdash.py", title="Startpagina",    icon=":material/dashboard:")
page_1    = st.Page("page_1.py",   title="vlucht info",     icon=":material/article:")
page_2    = st.Page("page_2.py",   title="vlucht info 2",   icon=":material/article:")
page_3    = st.Page("page_3.py",   title="vlucht info 3",   icon=":material/article:")

pg = st.navigation([dashboard, page_1, page_2, page_3])
pg.run()
