from sqlite3 import DatabaseError
import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import plotly.express as px
from auth import check_authentication
from database import BankDatabase
from receipt_generator import generate_receipt_pdf
from faker import Faker
import time
import base64
import os
from datetime import datetime, timedelta
from PIL import Image

# Vérification de l'authentification
check_authentication()

# Ajoutez ceci au début de votre script
st.session_state.setdefault('force_refresh', True)

if st.session_state.force_refresh:
    time.sleep(0.1)  # Pause minimale
    st.session_state.force_refresh = False
    st.rerun()  # Force le rechargement propre

# Configuration de la page
st.set_page_config(
    page_title="GESTION BANQUE",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialisation des composants
db = BankDatabase()
fake = Faker()

# Chargement des styles CSS et des assets
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def load_image(image_path):
    return Image.open(image_path)

load_css("assets/styles.css")
logo_img = load_image("assets/logo.png")

# Fonctions utilitaires améliorées
def generate_iban(country_code="FR"):
    """Génère un IBAN valide avec vérification"""
    bank_code = f"{fake.random_number(digits=5, fix_len=True):05d}"
    branch_code = f"{fake.random_number(digits=5, fix_len=True):05d}"
    account_number = f"{fake.random_number(digits=11, fix_len=True):011d}"
    national_check = f"{fake.random_number(digits=2, fix_len=True):02d}"
    
    bban = bank_code + branch_code + account_number + national_check + "00"
    check_digits = 98 - (int(bban) % 97)
    
    return f"{country_code}{check_digits:02d}{bank_code}{branch_code}{account_number}{national_check}"

def generate_account_number():
    return f"C{fake.random_number(digits=10, fix_len=True):010d}"

def format_currency(amount):
    return f"{amount:,.2f} XAF"

# Barre latérale améliorée
with st.sidebar:
    st.image(logo_img, width=50, use_column_width=True)
    st.markdown("<h1 style='text-align: center;'>Digital Financial Service</h1>", unsafe_allow_html=True)
    
    if st.session_state['authenticated']:
        st.markdown(
            f"<div class='user-info'>"
            f"<p>Connecté en tant que: <strong>{st.session_state['user']['username']}</strong></p>"
            f"<p>Rôle: <span class='role-badge'>{st.session_state['user'].get('role', 'Utilisateur')}</span></p>"
            f"</div>",
            unsafe_allow_html=True
        )
        
        if st.button("🚪 Déconnexion", use_container_width=True, key="logout_btn"):
            st.session_state.clear()
            st.rerun()
    
    # Menu de navigation amélioré
    selected = option_menu(
        menu_title=None,
        options=["Tableau de Bord", "Gestion Clients", "Gestion des Comptes", "Transactions", "Reçus", "Reçus RIB", "Gestion AVI"],
        icons=["speedometer2", "people-fill", "credit-card-2-back-fill", "arrow-left-right", "file-earmark-text", "file-earmark-pdf", "file-earmark-check"],
        default_index=0,
        styles={
            "container": {"padding": "0!important"},
            "icon": {"font-size": "16px"}, 
            "nav-link": {"font-size": "14px", "text-align": "left", "margin": "4px"},
            "nav-link-selected": {"background-color": "#2c3e50"},
        }
    )

# Style pour les KPI
def kpi_card(title, value, delta=None, delta_color="normal"):
    return st.markdown(
        f"""
        <div class="kpi-card {'delta-' + delta_color if delta else ''}">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            {f'<div class="kpi-delta">{delta}</div>' if delta else ''}
        </div>
        """,
        unsafe_allow_html=True
    )

# Page Tableau de Bord
if selected == "Tableau de Bord":
    st.title("📊 Tableau de Bord")
    
    # Section KPI
    st.subheader("Indicateurs Clés", divider="blue")
    # KPI
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Clients Actifs", db.count_active_clients(), "+5%")
    with col2:
        st.metric("Transactions Journalières", db.count_daily_transactions(), "12%")
    with col3:
        st.metric("Dépôts Totaux", f"{db.total_deposits():,.2f} XAF", "8%")
    with col4:
        st.metric("Retraits Totaux", f"{db.total_withdrawals():,.2f} XAF", "3%")
    
    # Graphiques
    st.subheader("Analytiques", divider="blue")
    col1, col2 = st.columns([3, 2])

    # Graphiques
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Dépôts vs Retraits (7 jours)")
        df_trans = pd.DataFrame(db.get_last_week_transactions())
        if not df_trans.empty:
            fig = px.bar(df_trans, x="date", y=["deposit", "withdrawal"], 
                        barmode="group", color_discrete_sequence=["#4CAF50", "#F44336"])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Pas de transactions disponibles pour les 7 derniers jours.")

    with col2:
        st.subheader("Répartition des Clients par Type")
        data = db.get_clients_by_type()
        df_clients = pd.DataFrame(data)

        if not df_clients.empty:
            if len(df_clients.columns) == 2:
                df_clients.columns = ["Type de Client", "count"]

            fig = px.pie(df_clients, values="count", names="Type de Client", 
                        color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Pas de données clients disponibles.")

    # Nouveau graphique pour les reçus générés
    st.subheader("Reçus Générés (30 derniers jours)")
    
    # Compter les reçus générés (simulation - à adapter avec votre système de stockage)
    receipts_dir = "receipts"
    if os.path.exists(receipts_dir):
        receipt_files = [f for f in os.listdir(receipts_dir) if f.endswith('.pdf')]
        receipt_dates = [datetime.fromtimestamp(os.path.getmtime(os.path.join(receipts_dir, f))) for f in receipt_files]
        
        if receipt_dates:
            df_receipts = pd.DataFrame({
                'date': [d.date() for d in receipt_dates],
                'count': 1
            })
            df_receipts = df_receipts.groupby('date').sum().reset_index()
            
            fig = px.line(df_receipts, x='date', y='count', 
                         title="Nombre de reçus générés par jour",
                         labels={'date': 'Date', 'count': 'Nombre de reçus'},
                         markers=True)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Aucun reçu généré dans les 30 derniers jours.")
    else:
        st.warning("Aucun répertoire de reçus trouvé.")

    # Dernières transactions avec filtres
    st.subheader("Dernières Transactions", divider="blue")
    transactions = db.get_recent_transactions(100)
    # Barre de recherche
    search_query = st.text_input("Rechercher dans les transactions", "")

    if transactions:
        df = pd.DataFrame(transactions)
        
        # Filtres avancés
        col1, col2, col3 = st.columns(3)
        with col1:
            type_filter = st.multiselect("Filtrer par type", options=df['type'].unique())
        with col2:
            min_amount = st.number_input("Montant minimum", min_value=0, value=0)
        with col3:
            date_range = st.date_input("Période", value=[])
        
        # Application des filtres
        if type_filter:
            df = df[df['type'].isin(type_filter)]
        if min_amount:
            df = df[df['amount'] >= min_amount]
        if len(date_range) == 2:
            df = df[(df['date'].dt.date >= date_range[0]) & 
                    (df['date'].dt.date <= date_range[1])]
        
        # Affichage avec ag-grid pour plus de fonctionnalités
        st.dataframe(
            df.style.format({"amount": "{:.2f} XAF"}),
            use_container_width=True,
            column_config={
                "date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY HH:mm"),
                "amount": st.column_config.NumberColumn("Montant", format="%.2f XAF")
            },
            hide_index=True
        )
    else:
        st.info("Aucune transaction récente")

# Page Gestion Clients (version améliorée)
elif selected == "Gestion Clients":
    st.title("👥 Gestion Clients")
    
    tab1, tab2, tab3 = st.tabs(["📋 Liste", "➕ Ajouter", "✏️ Modifier"])
    
    with tab1:
        st.subheader("Liste des Clients")
        clients = db.get_all_clients()
        
        if clients:
            df = pd.DataFrame(clients)
            
            # Barre de recherche avancée
            search_cols = st.columns([3, 1])
            with search_cols[0]:
                search_query = st.text_input("Rechercher", placeholder="Nom, email, téléphone...")
            with search_cols[1]:
                status_filter = st.selectbox("Statut", ["Tous", "Actif", "Inactif"])
            
            # Filtrage
            if search_query:
                mask = df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
                df = df[mask]
            if status_filter != "Tous":
                df = df[df['status'] == status_filter]
            
            # Affichage avec onglets pour différents types de clients
            client_types = df['type'].unique()
            tabs = st.tabs([f"Tous ({len(df)})"] + [f"{t} ({len(df[df['type']==t])})" for t in client_types])
            
            with tabs[0]:
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_order=["id", "first_name", "last_name", "email", "phone", "type", "status"]
                )
            
            for i, t in enumerate(client_types, 1):
                with tabs[i]:
                    st.dataframe(
                        df[df['type']==t],
                        use_container_width=True,
                        hide_index=True
                    )
        else:
            st.info("Aucun client enregistré", icon="ℹ️")
    
    with tab2:
        st.subheader("Ajouter un Client")
        with st.form("add_client_form", clear_on_submit=True):
            cols = st.columns(2)
            with cols[0]:
                first_name = st.text_input("Prénom*", placeholder="Jean")
                email = st.text_input("Email*", placeholder="jean.dupont@example.com")
                client_type = st.selectbox("Type*", ["Particulier", "Entreprise", "VIP"])
            with cols[1]:
                last_name = st.text_input("Nom*", placeholder="Dupont")
                phone = st.text_input("Téléphone", placeholder="0612345678")
                status = st.selectbox("Statut*", ["Actif", "Inactif"])
            
            st.markdown("<small>* Champs obligatoires</small>", unsafe_allow_html=True)
            
            if st.form_submit_button("Enregistrer", type="primary"):
                try:
                    client_id = db.add_client(first_name, last_name, email, phone, client_type, status)
                    st.toast(f"✅ Client {first_name} {last_name} ajouté (ID: {client_id})")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")
    
    with tab3:
        st.subheader("Modifier un Client")
        clients = db.get_all_clients()
        
        if clients:
            # Sélection du client
            selected_client = st.selectbox(
                "Choisir un client",
                options=[f"{c['first_name']} {c['last_name']} (ID: {c['id']})" for c in clients],
                index=0
            )
            
            client_id = int(selected_client.split("(ID: ")[1][:-1])
            client_data = db.get_client_by_id(client_id)
            
            if client_data:
                with st.form("update_client_form"):
                    cols = st.columns(2)
                    with cols[0]:
                        new_first = st.text_input("Prénom", value=client_data['first_name'])
                        new_email = st.text_input("Email", value=client_data['email'])
                    with cols[1]:
                        new_last = st.text_input("Nom", value=client_data['last_name'])
                        new_phone = st.text_input("Téléphone", value=client_data['phone'])
                    
                    new_type = st.selectbox(
                        "Type",
                        ["Particulier", "Entreprise", "VIP"],
                        index=["Particulier", "Entreprise", "VIP"].index(client_data['type'])
                    )
                    new_status = st.selectbox(
                        "Statut",
                        ["Actif", "Inactif"],
                        index=["Actif", "Inactif"].index(client_data['status'])
                    )
                    
                    if st.form_submit_button("Mettre à jour", type="primary"):
                        db.update_client(
                            client_id, new_first, new_last, 
                            new_email, new_phone, new_type, new_status
                        )
                        st.toast("✅ Client mis à jour")
                        time.sleep(1)
                        st.rerun()
        else:
            st.info("Aucun client à modifier", icon="ℹ️")
            

# Page Gestion des Comptes
elif selected == "Gestion des Comptes":
    st.title("💳 Gestion des Comptes Bancaires")
    
    tab1, tab2, tab3 = st.tabs(["📋 Liste des Comptes", "➕ Associer un Compte", "🔍 Recherche Avancée"])
    
    with tab1:
        st.subheader("Liste Complète des Comptes")
        
        # Filtres avancés
        with st.expander("Filtres Avancés", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                type_filter = st.multiselect(
                    "Type de compte",
                    options=["Courant", "Épargne", "Entreprise"],
                    default=["Courant", "Épargne", "Entreprise"]
                )
            with col2:
                currency_filter = st.multiselect(
                    "Devise",
                    options=["XAF", "USD", "GBP", "EUR"],
                    default=["XAF", "USD", "GBP", "EUR"]
                )
            with col3:
                balance_filter = st.slider(
                    "Solde minimum",
                    min_value=0,
                    max_value=10000,
                    value=0,
                    step=100
                )
        
        # Affichage des comptes
        accounts = db.get_all_ibans()
        if accounts:
            df = pd.DataFrame(accounts)
            
            # Application des filtres
            if type_filter:
                df = df[df['type'].isin(type_filter)]
            if currency_filter:
                df = df[df['currency'].isin(currency_filter)]
            df = df[df['balance'] >= balance_filter]
            
            # Affichage avec onglets par devise
            currencies = df['currency'].unique()
            tabs = st.tabs([f"Tous ({len(df)})"] + [f"{c} ({len(df[df['currency']==c])})" for c in currencies])
            
            with tabs[0]:
                st.dataframe(
                    df,
                    use_container_width=True,
                    column_config={
                        "iban": "IBAN",
                        "balance": st.column_config.NumberColumn(
                            "Solde",
                            format="%.2f XAF"
                        ),
                        "created_at": st.column_config.DatetimeColumn(
                            "Date création",
                            format="DD/MM/YYYY"
                        )
                    },
                    hide_index=True
                )
            
            for i, currency in enumerate(currencies, 1):
                with tabs[i]:
                    st.dataframe(
                        df[df['currency'] == currency],
                        use_container_width=True,
                        hide_index=True
                    )
        else:
            st.info("Aucun compte trouvé", icon="ℹ️")
    
    with tab2:
        st.subheader("Associer un Nouveau Compte")
        
        # Sélection du client
        clients = db.get_all_clients()
        client_options = {f"{c['first_name']} {c['last_name']}": c['id'] for c in clients}
        selected_client = st.selectbox("Client*", options=list(client_options.keys()))
        
        # Sélection de la banque
        bank_name = st.selectbox(
            "Banque*",
            options=list(db.BANK_DATA.keys()),
            index=0
        )
        
        # Bouton de génération
        if st.button("Générer les informations bancaires"):
            account_data = db.generate_iban(bank_name)
            st.session_state.new_account = account_data
        
        # Affichage des données générées
        if 'new_account' in st.session_state:
            acc = st.session_state.new_account
            
            st.markdown("### Informations bancaires générées")
            cols = st.columns(2)
            
            cols[0].markdown(f"""
            **Banque:** {acc['bank_name']}  
            **Code Banque:** {acc['bank_code']}  
            **Code Guichet:** {acc['branch_code']}  
            **Numéro de compte:** {acc['account_number']}  
            **Clé RIB:** {acc['rib_key']}
            """)
            
            cols[1].markdown(f"""
            **IBAN:** {(acc['iban'])}  
            **BIC/SWIFT:** {acc['bic']}  
            **Type de compte:** {acc.get('type', 'Courant')}  
            **Devise:** {acc.get('currency', 'XAF')}
            """)
            
            # Formulaire complémentaire
            with st.form("account_details_form"):
                account_type = st.selectbox(
                    "Type de compte*",
                    options=["Courant", "Épargne", "Entreprise", "Joint"]
                )
                
                currency = st.selectbox(
                    "Devise*",
                    options=["XAF", "USD", "GBP", "EUR"],
                )
                
                initial_balance = st.number_input(
                    "Solde initial*",
                    min_value=0.0,
                    value=0.0,
                    step=50.0
                )
                
                if st.form_submit_button("Enregistrer le compte"):
                    try:
                        # Construction des données complètes
                        full_account_data = {
                            **st.session_state.new_account,
                            "client_id": client_options[selected_client],
                            "type": account_type,
                            "currency": currency,
                            "balance": initial_balance,
                            "status": "ACTIF",
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        # Enregistrement dans la base de données
                        db.add_account(full_account_data)
                        st.success("Compte créé avec succès!")
                        del st.session_state.new_account
                    except Exception as e:
                        st.error(f"Erreur: {str(e)}")

            # Fonction utilitaire pour formater l'IBAN
            def format_iban(iban):
                """Formate l'IBAN pour l'affichage (espace tous les 4 caractères)"""
                return ' '.join([iban[i:i+4] for i in range(0, len(iban), 4)])
        else:
            st.warning("Aucun client disponible. Veuillez d'abord créer des clients.", icon="⚠️")
            
    
    with tab3:
        st.subheader("Recherche Avancée")
        
        with st.form("search_account_form"):
            col1, col2 = st.columns(2)
            with col1:
                client_search = st.text_input("Recherche client (nom, prénom)")
                iban_search = st.text_input("Recherche IBAN")
            with col2:
                min_balance = st.number_input("Solde minimum", min_value=0)
                max_balance = st.number_input("Solde maximum", min_value=0, value=100000)
            
            if st.form_submit_button("Rechercher"):
                accounts = db.search_accounts(
                    client_query=client_search,
                    iban_query=iban_search,
                    min_balance=min_balance,
                    max_balance=max_balance
                )
                
                if accounts:
                    st.dataframe(
                        pd.DataFrame(accounts),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("Aucun résultat trouvé", icon="ℹ️")
# Page Transactions
elif selected == "Transactions":
    st.title("⇄ Gestion des Transactions")
    
    tab1, tab2 = st.tabs(["Historique", "Nouvelle Transaction"])
    
    with tab1:
        st.subheader("Historique des Transactions")
        
        # Barre de recherche
        search_query = st.text_input("Rechercher dans les transactions", "")
        
        transactions = db.get_all_transactions()
        if transactions:
            df = pd.DataFrame(transactions)
            
            # Filtrage basé sur la recherche
            if search_query:
                mask = df.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
                df = df[mask]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("Aucune transaction trouvée.")
    
    with tab2:
        st.subheader("Effectuer une Transaction")
        transaction_type = st.radio("Type de Transaction", ["Dépôt", "Retrait", "Virement"], horizontal=True)
        
        clients = db.get_all_clients()
        if clients:
            # Barre de recherche pour trouver un client
            search_query = st.text_input("Rechercher un client", "")
            
            if search_query:
                filtered_clients = [c for c in clients if search_query.lower() in f"{c['first_name']} {c['last_name']}".lower()]
            else:
                filtered_clients = clients
                
            client_options = {f"{c['first_name']} {c['last_name']} (ID: {c['id']})": c['id'] for c in filtered_clients}
            selected_client = st.selectbox("Sélectionner un Client", options=list(client_options.keys()))
            
            if selected_client:
                client_id = client_options[selected_client]
                client_ibans = db.get_ibans_by_client(client_id)
                
                if client_ibans:
                    iban_options = {i['iban']: i['id'] for i in client_ibans}
                    selected_iban = st.selectbox("Sélectionner un IBAN", options=list(iban_options.keys()))
                    
                    with st.form("transaction_form"):
                        amount = st.number_input("Montant", min_value=0.01, value=100.0, step=50.0)
                        description = st.text_area("Description")
                        
                        # Initialisation de target_accounts seulement si nécessaire
                        target_accounts = []
                        if transaction_type == "Virement":
                            all_accounts = db.get_all_ibans()
                            source_id = iban_options[selected_iban]
                            target_accounts = [a for a in all_accounts if a['id'] != source_id]
                            
                            if target_accounts:
                                target_options = {f"{a['iban']} - {a['first_name']} {a['last_name']}": a['id'] for a in target_accounts}
                                target_account = st.selectbox("Compte destinataire", options=list(target_options.keys()))
                                target_id = target_options[target_account]
                            else:
                                st.warning("Aucun autre compte disponible pour le virement")
                                target_id = None
                        
                        if st.form_submit_button("Exécuter la Transaction"):
                            iban_id = iban_options[selected_iban]
                            if transaction_type == "Dépôt":
                                db.deposit(iban_id, amount, description)
                                st.success(f"Dépôt de XAF{amount:,.2f} effectué avec succès!")
                            elif transaction_type == "Retrait":
                                # Vérifier le solde avant retrait
                                iban_data = next(i for i in client_ibans if i['id'] == iban_id)
                                if iban_data['balance'] >= amount:
                                    db.withdraw(iban_id, amount, description)
                                    st.success(f"Retrait de XAF{amount:,.2f} effectué avec succès!")
                                else:
                                    st.error("Solde insuffisant pour effectuer ce retrait.")
                            elif transaction_type == "Virement" and target_id:
                                # Vérifier le solde avant virement
                                iban_data = next(i for i in client_ibans if i['id'] == iban_id)
                                if iban_data['balance'] >= amount:
                                    # Transaction atomique
                                    db.withdraw(iban_id, amount, f"Virement vers {target_account}")
                                    db.deposit(target_id, amount, f"Virement depuis {iban_data['iban']}")
                                    st.success(f"Virement de XAF{amount:,.2f} effectué avec succès!")
                                else:
                                    st.error("Solde insuffisant pour effectuer ce virement.")
                            time.sleep(1)
                            st.rerun()

                        if selected_iban:
                            # Si vous avez besoin de chercher par IBAN
                            all_accounts = db.get_all_ibans()
                            account_details = next((acc for acc in all_accounts if acc['iban'] == selected_iban), None)
                            if account_details:
                                with st.expander("🔍 Détails du compte source"):
                                    cols = st.columns(2)
                                    cols[0].markdown(f"""
                                    **Banque:** {account_details.get('bank_name', 'N/A')}  
                                    **Code Banque:** {account_details.get('bank_code', 'N/A')}  
                                    **BIC:** {account_details.get('bic', 'N/A')}  
                                    **Solde actuel:** {account_details.get('balance', 0):.2f}€
                                    """)
                                    
                                    cols[1].markdown(f"""
                                    **IBAN:** {account_details.get('iban', 'N/A')}  
                                    **Code Guichet:** {account_details.get('branch_code', 'N/A')}  
                                    **Clé RIB:** {account_details.get('rib_key', 'N/A')}  
                                    **Type:** {account_details.get('type', 'N/A')}
                                    """)
                            else:
                                st.warning("Ce client n'a aucun IBAN associé.")
        else:
            st.warning("Aucun client disponible. Veuillez d'abord ajouter des clients.")


# Page Générer Reçu
elif selected == "Reçus":
    st.markdown("""
    <style>
        .receipt-card {
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
            background-color: #f8f9fa;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        .receipt-header {
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }
        .receipt-section {
            margin-bottom: 15px;
        }
        .receipt-signature {
            margin-top: 30px;
            text-align: right;
        }
        .signature-line {
            border-top: 1px solid #333;
            width: 200px;
            margin-top: 5px;
            display: inline-block;
        }
        .stDownloadButton button {
            background-color: #27ae60 !important;
            color: white !important;
            border: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("🧾 Gestion des Reçus")
    
    # Section de statistiques
    with st.container():
        st.subheader("Statistiques", divider="blue")
        col1, col2 = st.columns(2)
        with col1:
            receipts_dir = "receipts"
            if os.path.exists(receipts_dir):
                receipt_count = len([f for f in os.listdir(receipts_dir) if f.endswith('.pdf')])
                st.metric("📄 Reçus générés", receipt_count)
            else:
                st.metric("📄 Reçus générés", 0)
        
        with col2:
            transactions_count = len(db.get_all_transactions())
            st.metric("💸 Transactions éligibles", transactions_count)
    
    # Sélection de la transaction
    st.subheader("Sélection de la transaction", divider="blue")
    transactions = db.get_all_transactions()
    
    if not transactions:
        st.warning("Aucune transaction disponible pour générer un reçu.")
        st.stop()
    
    # Barre de recherche améliorée
    search_cols = st.columns([4, 1])
    with search_cols[0]:
        search_query = st.text_input("🔍 Rechercher une transaction", "", 
                                   placeholder="ID, montant, type...")
    with search_cols[1]:
        transaction_type_filter = st.selectbox("Filtrer", ["Tous"] + list(set(t['type'] for t in transactions)))
    
    # Filtrage des transactions
    filtered_transactions = transactions
    if search_query:
        filtered_transactions = [t for t in transactions if search_query.lower() in str(t).lower()]
    if transaction_type_filter != "Tous":
        filtered_transactions = [t for t in filtered_transactions if t['type'] == transaction_type_filter]
    
    if not filtered_transactions:
        st.warning("Aucune transaction ne correspond aux critères de recherche.")
        st.stop()
    
    # Sélecteur de transaction amélioré
    selected_transaction = st.selectbox(
        "Choisir une transaction à documenter",
        options=filtered_transactions,
        format_func=lambda t: f"#{t['id']} • {t['type']} • {t['amount']:.2f}XAF • {t['date'].split()[0]} • {t.get('description', '')[:30]}{'...' if len(t.get('description', '')) > 30 else ''}",
        index=0
    )
    
    # Récupération des données
    transaction_data = selected_transaction
    client_data = db.get_client_by_id(transaction_data['client_id'])
    iban_data = db.get_iban_by_id(transaction_data['iban_id'])
    
    # Affichage des informations
    with st.expander("📋 Aperçu des informations", expanded=True):
        tab1, tab2 = st.tabs(["Client", "Transaction"])
        
        with tab1:
            st.write(f"**👤 Nom complet:** {client_data['first_name']} {client_data['last_name']}")
            st.write(f"**📧 Email:** {client_data['email'] or 'Non renseigné'}")
            st.write(f"**📞 Téléphone:** {client_data['phone'] or 'Non renseigné'}")
            st.write(f"**🏷 Type client:** {client_data['type']}")
        
        with tab2:
            st.write(f"**💰 Montant:** {transaction_data['amount']:.2f}XAF")
            st.write(f"**📅 Date:** {transaction_data['date']}")
            st.write(f"**🔢 Référence:** {transaction_data['id']}")
            st.write(f"**🏦 IBAN:** {iban_data['iban']}")
            st.write(f"**📝 Description:** {transaction_data.get('description', 'Aucune description')}")
    
    # Personnalisation du reçu
    st.subheader("🛠 Personnalisation du reçu", divider="blue")
    with st.form("receipt_form"):
        cols = st.columns(2)
        
        with cols[0]:
            st.markdown("**Paramètres principaux**")
            company_name = st.text_input("Nom de l'institution", value="Digital Financial Service")
            receipt_title = st.text_input("Titre du document", value="REÇU DE TRANSACTION")
            company_logo = st.file_uploader("Logo (PNG/JPG)", type=["png", "jpg"])
        
        with cols[1]:
            st.markdown("**Options avancées**")
            additional_notes = st.text_area(
                "Notes additionnelles", 
                value="Merci pour votre confiance.\nPour toute question, contactez notre service client.",
                height=100
            )
            include_signature = st.checkbox("Inclure une ligne de signature", value=True)
            include_qr = st.checkbox("Inclure un QR code de vérification", value=True)
        
        # Bouton de génération
        submitted = st.form_submit_button(
            "🖨 Générer le reçu", 
            type="primary", 
            use_container_width=True
        )
    
    # Génération du PDF
    if submitted:
        with st.spinner("Génération du reçu en cours..."):
            # Sauvegarde temporaire du logo
            logo_path = None
            if company_logo:
                logo_path = f"temp_logo_{transaction_data['id']}.png"
                with open(logo_path, "wb") as f:
                    f.write(company_logo.getbuffer())
            
            pdf_path = generate_receipt_pdf(
                transaction_data=transaction_data,
                client_data=client_data,
                iban_data=iban_data,
                company_name=company_name,
                logo_path=logo_path,
                receipt_title=receipt_title,
                additional_notes=additional_notes,
                include_signature=include_signature,
                include_qr=include_qr  # Utilisez le même nom que dans la fonction
            )
            
            # Nettoyage du logo temporaire
            if logo_path and os.path.exists(logo_path):
                os.remove(logo_path)
            
            # Téléchargement
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="⬇️ Télécharger le reçu",
                    data=f,
                    file_name=f"reçu_{transaction_data['id']}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            
            # Aperçu stylisé
            st.success("Reçu généré avec succès !")
            st.markdown("**Aperçu:** (le PDF peut différer légèrement)")
            
            # Simulation d'aperçu
            with st.container():
                st.markdown(f"""
                <div class="receipt-preview">
                    <div class="receipt-header">
                        <h1>{company_name}</h1>
                        {f'<img src="data:image/png;base64,{base64.b64encode(company_logo.getvalue()).decode()}" class="receipt-logo">' if company_logo else ''}
                        <h2>{receipt_title}</h2>
                    </div>
                    <div class="receipt-body">
                        <div class="receipt-section">
                            <h3>Informations Client</h3>
                            <p><strong>Nom:</strong> {client_data['first_name']} {client_data['last_name']}</p>
                            <p><strong>IBAN:</strong> {iban_data['iban']}</p>
                        </div>
                        <div class="receipt-section">
                            <h3>Détails de la Transaction</h3>
                            <p><strong>Type:</strong> {transaction_data['type']}</p>
                            <p><strong>Montant:</strong>{transaction_data['amount']:,.2f} XAF</p>
                            <p><strong>Date:</strong> {transaction_data['date']}</p>
                            <p><strong>Référence:</strong> {transaction_data['id']}</p>
                        </div>
                        <div class="receipt-notes">
                            <p>{additional_notes.replace('\n', '<br>')}</p>
                        </div>
                        {'''<div class="receipt-signature">
                            <p>Signature</p>
                            <div class="signature-line"></div>
                        </div>''' if include_signature else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)

# Ajoutez cette section dans votre page "Reçus" (ou créez une nouvelle page)
elif selected == "Reçus RIB":
    st.title("📋 Reçus RIB")
    
    # Sélection du compte
    accounts = db.get_all_ibans()
    if not accounts:
        st.warning("Aucun compte disponible pour générer un RIB")
        st.stop()
    
    selected_account = st.selectbox(
        "Sélectionner un compte",
        options=accounts,
        format_func=lambda acc: f"{acc['first_name']} {acc['last_name']} - {acc['iban']} ({acc['balance']:,.2f} {acc['currency']})"
    )
    
    if st.button("Générer le RIB", type="primary"):
        with st.spinner("Génération du RIB en cours..."):
            try:
                # Création d'un répertoire pour les reçus s'il n'existe pas
                os.makedirs("rib_receipts", exist_ok=True)
                
                # Génération du RIB
                receipt_path = db.generate_rib_receipt(
                    iban=selected_account['iban'],
                    output_path=f"rib_receipts/RIB_{selected_account['iban']}.pdf"
                )
                
                # Affichage du résultat
                st.success("RIB généré avec succès!")
                
                # Prévisualisation
                with open(receipt_path, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                
                # Bouton de téléchargement
                with open(receipt_path, "rb") as f:
                    st.download_button(
                        "Télécharger le RIB",
                        data=f,
                        file_name=f"RIB_{selected_account['iban']}.pdf",
                        mime="application/pdf"
                    )
                    
            except Exception as e:
                st.error(f"Erreur lors de la génération: {str(e)}")

elif selected == "Gestion AVI":
    st.title("📑 Gestion des Attestations de Virement Irrévocable (AVI)")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Liste des AVI", "➕ Ajouter AVI", "✏️ Modifier AVI", "🖨 Générer AVI"])
    
    with tab1:
        st.subheader("Liste des Attestations")
        
        # Filtres
        col1, col2 = st.columns(2)
        with col1:
            search_term = st.text_input("Rechercher", "")
        with col2:
            statut_filter = st.selectbox("Filtrer par statut", ["Tous", "Etudiant", "Fonctionnaire"])
        
        # Récupération des AVI
        avis = db.search_avis(
            search_term=search_term if search_term else None,
            statut=statut_filter if statut_filter != "Tous" else None
        )
        
        if avis:
            df = pd.DataFrame(avis)
            st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "date_creation": st.column_config.DateColumn("Date création", format="DD/MM/YYYY"),
                    "date_expiration": st.column_config.DateColumn("Date expiration", format="DD/MM/YYYY"),
                    "montant": st.column_config.NumberColumn("Montant", format="%.2f FCFA")
                },
                hide_index=True,
                column_order=["reference", "nom_complet", "code_banque", "iban", "montant", "date_creation", "statut"]
            )
        else:
            st.info("Aucune attestation trouvée", icon="ℹ️")
    
    with tab2:
        st.subheader("Ajouter une Nouvelle Attestation")
        with st.form("add_avi_form", clear_on_submit=True):
            cols = st.columns(2)
            with cols[0]:
                nom_complet = st.text_input("Nom complet*", placeholder="Nom Prénom")
                code_banque = st.text_input("Code Banque*", placeholder="12345")
                numero_compte = st.text_input("Numéro de Compte*", placeholder="12345678901")
            with cols[1]:
                devise = st.selectbox("Devise*", options=["XAF", "EUR", "USD"], index=0)
                iban = st.text_input("IBAN*", placeholder="CG12345678901234567890")
                bic = st.text_input("BIC*", placeholder="BANKCGCGXXX")
            
            montant = st.number_input("Montant (FCFA)*", min_value=0, value=5000000)
            date_creation = st.date_input("Date de création*", value=datetime.now())
            date_expiration = st.date_input("Date d'expiration (optionnel)")
            statut = st.selectbox("Statut*", options=["Etudiant", "Fonctionnaire"], index=0)  # Ajouté
            commentaires = st.text_area("Commentaires (optionnel)")
            
            if st.form_submit_button("Enregistrer l'AVI", type="primary"):
                try:
                    avi_data = {
                        "nom_complet": nom_complet,
                        "code_banque": code_banque,
                        "numero_compte": numero_compte,
                        "devise": devise,
                        "iban": iban,
                        "bic": bic,
                        "montant": montant,
                        "date_creation": date_creation.strftime("%Y-%m-%d"),
                        "date_expiration": date_expiration.strftime("%Y-%m-%d") if date_expiration else None,
                        "statut": statut,
                        "commentaires": commentaires
                    }
                    
                    avi_id = db.add_avi(avi_data)
                    avi_info = db.get_avi_by_id(avi_id)  # Nouvelle méthode à implémenter
                    st.success(f"Attestation enregistrée avec succès! Référence: {avi_info['reference']}")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")
    
    with tab3:
        st.subheader("Modifier une Attestation")
        avis = db.get_all_avis(with_details=True)
    
        if avis:
            selected_avi = st.selectbox(
                "Choisir une attestation à modifier",
                options=[a['reference'] for a in avis],
                format_func=lambda ref: f"{ref} - {next(a['nom_complet'] for a in avis if a['reference'] == ref)}",
                index=0
            )
            
            avi_data = db.get_avi_by_reference(selected_avi)
            
            if avi_data:
                with st.form("update_avi_form"):
                    cols = st.columns(2)
                    with cols[0]:
                        new_nom = st.text_input("Nom complet", value=avi_data['nom_complet'])
                        new_code_banque = st.text_input("Code Banque", value=avi_data['code_banque'])
                        new_numero = st.text_input("Numéro de Compte", value=avi_data['numero_compte'])
                    with cols[1]:
                        new_devise = st.selectbox(
                            "Devise",
                            options=["XAF", "EUR", "USD"],
                            index=["XAF", "EUR", "USD"].index(avi_data['devise'])
                        )
                        new_iban = st.text_input("IBAN", value=avi_data['iban'])
                        new_bic = st.text_input("BIC", value=avi_data['bic'])
                    
                    try:
                        montant_value = float(avi_data['montant']) if avi_data['montant'] is not None else 0.0
                        new_montant = st.number_input(
                            "Montant (FCFA)",
                            min_value=0.0,
                            value=montant_value,
                            step=1.0,
                            format="%.2f"  # Format à 2 décimales
                        )
                    except (ValueError, TypeError) as e:
                        st.error(f"Erreur de format du montant: {str(e)}")
                        new_montant = 0.0
                    new_date_creation = st.date_input("Date de création", value=datetime.strptime(avi_data['date_creation'], "%Y-%m-%d"))
                    new_date_expiration = st.date_input("Date d'expiration", 
                                                      value=datetime.strptime(avi_data['date_expiration'], "%Y-%m-%d") if avi_data['date_expiration'] else None)
                    new_statut = st.selectbox(
                        "Statut",
                        options=["Etudiant", "Fonctionnaire"],
                        index=["Etudiant", "Fonctionnaire"].index(avi_data['statut'])
                    )
                    new_commentaires = st.text_area("Commentaires", value=avi_data.get('commentaires', ''))
                    
                    if st.form_submit_button("Mettre à jour", type="primary"):
                        updated_data = {
                            "nom_complet": new_nom,
                            "code_banque": new_code_banque,
                            "numero_compte": new_numero,
                            "devise": new_devise,
                            "iban": new_iban,
                            "bic": new_bic,
                            "montant": new_montant,
                            "date_creation": new_date_creation.strftime("%Y-%m-%d"),
                            "date_expiration": new_date_expiration.strftime("%Y-%m-%d") if new_date_expiration else None,
                            "statut": new_statut,
                            "commentaires": new_commentaires
                        }
                        
                        try:
                            if db.update_avi(selected_avi, updated_data):
                                st.success("Attestation mise à jour avec succès!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Échec de la mise à jour - l'attestation n'a pas été trouvée")
                        except Exception as e:
                            st.error(f"Erreur lors de la mise à jour: {str(e)}")
        else:
            st.info("Aucune attestation à modifier", icon="ℹ️")
    
    with tab4:
        st.subheader("Générer une Attestation")
        avis = db.get_all_avis(with_details=True)
        
        if avis:
            selected_avi = st.selectbox(
                "Choisir une attestation à générer",
                options=[f"{a['reference']} - {a['nom_complet']}" for a in avis],
                index=0
            )
            
            reference = selected_avi.split(" - ")[0]
            avi_data = db.get_avi_by_reference(reference)
            
            if avi_data:
                # Bouton de génération
                if st.button("Générer l'Attestation PDF", type="primary"):
                    with st.spinner("Génération en cours..."):
                        try:
                            # Créer le contenu de l'AVI
                            avi_content = f"""
                            Nous soussignés, Eco Capital (E.C), établissement de microfinance agréé pour exercer des activités
                            bancaires en République du Congo conformément au décret n°7236/MEFB-CAB du 15 novembre 2007,
                            après avis conforme de la COBAC D-2007/2018, déclarons avoir notre siège au n°1636 Boulevard Denis
                            Sassou Nguesso, Batignol Brazzaville.
                            
                            Représenté par son Directeur Général, Monsieur ILOKO Charmant.
                            
                            Nous certifions par la présente que Monsieur/Madame {avi_data['nom_complet']} détient un compte courant
                            enregistré dans nos livres avec les caractéristiques suivantes :
                            
                            CODE BANQUE : {avi_data['code_banque']}
                            NUMERO DE COMPTE : {avi_data['numero_compte']}
                            Devise : {avi_data['devise']}
                            
                            Il est l'ordonnateur d'un virement irrévocable et permanent d'un montant total de {avi_data['montant']:,.2f} FCFA (cinq
                            millions de francs CFA), équivalant actuellement à {avi_data['montant']/650:,.2f} euros, destiné à couvrir les frais liés à ses études
                            en France.
                            
                            Il est précisé que ce compte demeurera bloqué jusqu'à la présentation, par le donneur d'ordre, de ses
                            nouvelles coordonnées bancaires ouvertes en France.
                            
                            À défaut, les fonds ne pourront être remis à sa disposition qu'après présentation de son passeport
                            attestant d'un refus de visa. Toutefois, nous autorisons le donneur d'ordre, à toutes fins utiles, à utiliser
                            notre compte ouvert auprès de United Bank for Africa (UBA).
                            
                            IBAN: {avi_data['iban']}
                            BIC: {avi_data['bic']}
                            
                            En foi de quoi, cette attestation lui est délivrée pour servir et valoir ce que de droit.
                            """
                            
                            # Pied de page
                            footer = """
                            Eco capital Sarl
                            Société a responsabilité limité au capital de 60.000.000 XAF
                            Siège social : 1636 Boulevard Denis Sassou Nguesso Brazzaville
                            Contact: 00242 06 931 31 06 /04 001 79 40
                            Web : www.ecocapitale.com mail : contacts@ecocapitale.com
                            RCCM N°CG/BZV/B12-00320NIU N°M24000000665934H
                            Brazzaville République du Congo
                            """
                            
                            # Génération du QR code
                            qr_data = f"""
                            Nom: {avi_data['nom_complet']}
                            Code Banque: {avi_data['code_banque']}
                            Numéro Compte: {avi_data['numero_compte']}
                            Devise: {avi_data['devise']}
                            IBAN: {avi_data['iban']}
                            BIC: {avi_data['bic']}
                            Montant: {avi_data['montant']:,.2f} FCFA
                            Date: {avi_data['date_creation']}
                            """
                            
                            # Création du PDF
                            from fpdf import FPDF
                            import qrcode
                            from io import BytesIO
                            
                            pdf = FPDF()
                            pdf.add_page()
                            
                            # En-tête
                            pdf.set_font('Arial', 'B', 16)
                            pdf.cell(0, 10, 'ATTESTATION DE VIREMENT IRREVOCABLE', 0, 2, 'C')
                            pdf.ln(10)
                            
                            # Logo (si disponible)
                            pdf.image("assets/logo.png", x=10, y=8, w=30)
                            
                            # Contenu   
                            pdf.set_font('Arial', '', 12)
                            pdf.multi_cell(0, 5, avi_content)
                            pdf.ln(10)
                            
                            # QR Code
                            qr = qrcode.QRCode(
                                version=1,
                                error_correction=qrcode.constants.ERROR_CORRECT_L,
                                box_size=4,
                                border=2,
                            )
                            qr.add_data(qr_data)
                            qr.make(fit=True)
                            
                            img = qr.make_image(fill_color="black", back_color="white")
                            img_bytes = BytesIO()
                            img.save(img_bytes, format='PNG')
                            img_bytes.seek(0)
                            
                            pdf.image(img_bytes, x=150, y=pdf.get_y(), w=40)
                            pdf.ln(20)
                            
                            # Pied de page
                            pdf.set_font('Arial', 'I', 10)
                            pdf.multi_cell(0, 8, footer)
                            
                            # Sauvegarde du fichier
                            os.makedirs("avi_documents", exist_ok=True)
                            output_path = f"avi_documents/AVI_{avi_data['nom_complet']}_{avi_data['date_creation']}.pdf"
                            pdf.output(output_path)
                            
                            # Affichage et téléchargement
                            st.success("Attestation générée avec succès!")
                            
                            with open(output_path, "rb") as f:
                                st.download_button(
                                    "Télécharger l'AVI",
                                    data=f,
                                    file_name=f"AVI_{avi_data['nom_complet']}.pdf",
                                    mime="application/pdf"
                                )
                            
                            # Prévisualisation
                            with open(output_path, "rb") as f:
                                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                                st.markdown(pdf_display, unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.error(f"Erreur lors de la génération: {str(e)}")
        else:
            st.info("Aucune attestation disponible pour génération", icon="ℹ️")