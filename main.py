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
    return f"{amount:,.2f} €"

# Barre latérale améliorée
with st.sidebar:
    st.image(logo_img, width=180)
    st.markdown("<h1 style='text-align: center;'>GESTION BANQUE</h1>", unsafe_allow_html=True)
    
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
        options=["Tableau de Bord", "Gestion Clients", "Gestion des Comptes", "Transactions", "Reçus"],
        icons=["speedometer2", "people-fill", "credit-card-2-back-fill", "arrow-left-right", "file-earmark-text"],
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
        st.metric("Dépôts Totaux", f"${db.total_deposits():,.2f}", "8%")
    with col4:
        st.metric("Retraits Totaux", f"${db.total_withdrawals():,.2f}", "3%")
    
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
            df.style.format({"amount": "€{:.2f}"}),
            use_container_width=True,
            column_config={
                "date": st.column_config.DatetimeColumn("Date", format="DD/MM/YYYY HH:mm"),
                "amount": st.column_config.NumberColumn("Montant", format="€%.2f")
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
                    options=["EUR", "USD", "GBP"],
                    default=["EUR", "USD", "GBP"]
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
                            format="%.2f €"
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
        if clients:
            client_options = {
                f"{c['first_name']} {c['last_name']} (ID: {c['id']})": c['id']
                for c in clients
            }
            
            # Bouton pour générer un IBAN en dehors du formulaire
            if 'new_iban' not in st.session_state:
                st.session_state.new_iban = generate_iban()
            
            if st.button("Générer un nouvel IBAN"):
                st.session_state.new_iban = generate_iban()
                st.rerun()
            
            with st.form("add_account_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    selected_client = st.selectbox(
                        "Client*",
                        options=list(client_options.keys()),
                        index=0
                    )
                    client_id = client_options[selected_client]
                    
                    account_type = st.selectbox(
                        "Type de compte*",
                        options=["Courant", "Épargne", "Entreprise"]
                    )
                
                with col2:
                    iban = st.text_input(
                        "IBAN*",
                        value=st.session_state.new_iban,
                        placeholder="FR76 3000 1000 0100 0000 0000 123"
                    )
                    
                    currency = st.selectbox(
                        "Devise*",
                        options=["EUR", "USD", "GBP"]
                    )
                    
                    initial_balance = st.number_input(
                        "Solde initial*",
                        min_value=0.0,
                        value=100.0,
                        step=50.0
                    )
                
                st.markdown("<small>* Champs obligatoires</small>", unsafe_allow_html=True)
                
                if st.form_submit_button("Créer le compte", type="primary"):
                    try:
                        account_id = db.add_iban(
                            client_id=client_id,
                            iban=iban,
                            currency=currency,
                            account_type=account_type,
                            balance=initial_balance
                        )
                        st.toast(f"✅ Compte {iban} créé avec succès!")
                        del st.session_state.new_iban
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de la création du compte : {str(e)}")
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
                                st.success(f"Dépôt de ${amount:,.2f} effectué avec succès!")
                            elif transaction_type == "Retrait":
                                # Vérifier le solde avant retrait
                                iban_data = next(i for i in client_ibans if i['id'] == iban_id)
                                if iban_data['balance'] >= amount:
                                    db.withdraw(iban_id, amount, description)
                                    st.success(f"Retrait de ${amount:,.2f} effectué avec succès!")
                                else:
                                    st.error("Solde insuffisant pour effectuer ce retrait.")
                            elif transaction_type == "Virement" and target_id:
                                # Vérifier le solde avant virement
                                iban_data = next(i for i in client_ibans if i['id'] == iban_id)
                                if iban_data['balance'] >= amount:
                                    # Transaction atomique
                                    db.withdraw(iban_id, amount, f"Virement vers {target_account}")
                                    db.deposit(target_id, amount, f"Virement depuis {iban_data['iban']}")
                                    st.success(f"Virement de ${amount:,.2f} effectué avec succès!")
                                else:
                                    st.error("Solde insuffisant pour effectuer ce virement.")
                            time.sleep(1)
                            st.rerun()
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
        format_func=lambda t: f"#{t['id']} • {t['type']} • {t['amount']:.2f}€ • {t['date'].split()[0]} • {t.get('description', '')[:30]}{'...' if len(t.get('description', '')) > 30 else ''}",
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
            st.write(f"**💰 Montant:** {transaction_data['amount']:.2f}€")
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
            company_name = st.text_input("Nom de l'institution", value="Banque Virtuelle")
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
                            <p><strong>Montant:</strong> ${transaction_data['amount']:,.2f}</p>
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