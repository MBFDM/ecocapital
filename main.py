import time
from auth import check_authentication
import streamlit as st

check_authentication()

# Vérification de l'authentification
check_authentication()

# Ajoutez ceci au début de votre script
st.session_state.setdefault('force_refresh', True)

if st.session_state.force_refresh:
    time.sleep(0.1)  # Pause minimale
    st.session_state.force_refresh = False
    st.rerun()  # Force le rechargement propre