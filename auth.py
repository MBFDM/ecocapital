"""
Application de Gestion Administrateur avec Streamlit

Structure:
1. Imports et configuration
2. Classes de gestion de base de données
3. Fonctions utilitaires
4. Pages de l'interface utilisateur
5. Fonction principale
"""

# =============================================
# 1. IMPORTS ET CONFIGURATION
# =============================================
from io import BytesIO
import logging
import PyPDF2
from fpdf import FPDF
import qrcode
import streamlit as st
from datetime import datetime
import pandas as pd
import sqlite3
import hashlib
import time
from typing import List, Dict, Optional
from sqlite3 import DatabaseError
import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
import plotly.express as px
from database import BankDatabase
from receipt_generator import generate_receipt_pdf
from faker import Faker
import time
import base64
import os
from datetime import datetime, timedelta
from PIL import Image
import PyPDF2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import base64
import qrcode
from io import BytesIO
import os
import PyPDF2
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import base64
import qrcode
from io import BytesIO

# Configuration de la base de données
DATABASE_NAME = "bank_database.db"

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================
# 2. CLASSES DE GESTION DE BASE DE DONNÉES
# =============================================

class EnhancedUserManager:
    """Gestionnaire complet des utilisateurs et de l'administration"""
    
    def __init__(self, conn: sqlite3.Connection):
        """Initialise la connexion et crée les tables"""
        self.conn = conn
        self._create_tables()

    def _create_tables(self):
        """Crée les tables nécessaires dans la base de données"""
        with self.conn:
            # Table des utilisateurs
            self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                status TEXT DEFAULT 'active',
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (role IN ('user', 'manager', 'admin')),
                CHECK (status IN ('active', 'inactive', 'suspended'))
            )''')

            # Table des demandes admin
            self.conn.execute('''
            CREATE TABLE IF NOT EXISTS admin_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                justification TEXT,
                request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                approved_by INTEGER,
                FOREIGN KEY (approved_by) REFERENCES users (id)
            )''')

            # Table des logs d'activité
            self.conn.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )''')

    # Méthodes de gestion des utilisateurs
    def add_user(self, username: str, email: str, password_hash: str, role: str = 'user') -> int:
        """Ajoute un nouvel utilisateur à la base de données"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                ''', (username, email, password_hash, role))
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise sqlite3.IntegrityError(f"Erreur d'intégrité: {str(e)}")

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Récupère un utilisateur par son nom d'utilisateur"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username=?', (username,))
        user = cursor.fetchone()
        return dict(user) if user else None
    
    def get_all_users(self) -> List[Dict]:
        """Récupère tous les utilisateurs"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users ORDER BY username')
        return [dict(row) for row in cursor.fetchall()]

    def update_user_role(self, user_id: int, new_role: str) -> None:
        """Met à jour le rôle d'un utilisateur"""
        with self.conn:
            self.conn.execute(
                'UPDATE users SET role=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (new_role, user_id))

    def update_user_status(self, user_id: int, new_status: str) -> None:
        """Met à jour le statut d'un utilisateur"""
        with self.conn:
            self.conn.execute(
                'UPDATE users SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (new_status, user_id))

    def count_active_users(self) -> int:
        """Compte les utilisateurs actifs"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users WHERE status="active"')
        return cursor.fetchone()[0]

    def log_activity(self, user_id: int, action: str, details: str = "", ip_address: str = "") -> None:
        """Enregistre une activité utilisateur"""
        with self.conn:
            self.conn.execute('''
            INSERT INTO activity_logs (user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
            ''', (user_id, action, details, ip_address))

    def get_activity_logs(self, date_filter: str = None, user_id: int = None) -> List[Dict]:
        """Récupère les logs d'activité avec filtres"""
        query = '''
        SELECT l.*, u.username 
        FROM activity_logs l
        JOIN users u ON l.user_id = u.id
        WHERE 1=1
        '''
        params = []
        
        if date_filter:
            query += ' AND date(l.created_at) = date(?)'
            params.append(date_filter)
        
        if user_id:
            query += ' AND l.user_id = ?'
            params.append(user_id)
        
        query += ' ORDER BY l.created_at DESC'
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # Méthodes de gestion des comptes admin
    def create_admin_account(self, username: str, email: str, password: str, justification: str = "") -> bool:
        """Crée un compte administrateur immédiatement"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                password_hash = hash_password(password)
                cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, 'admin')
                ''', (username, email, password_hash))
                return True
        except sqlite3.Error as e:
            st.error(f"Erreur lors de la création du compte admin: {str(e)}")
            return False

    def request_admin_account(self, username: str, email: str, password: str, justification: str) -> bool:
        """Enregistre une demande de création de compte admin"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                password_hash = hash_password(password)
                cursor.execute('''
                INSERT INTO admin_requests (username, email, password_hash, justification)
                VALUES (?, ?, ?, ?)
                ''', (username, email, password_hash, justification))
                return True
        except sqlite3.Error as e:
            st.error(f"Erreur lors de la demande de compte admin: {str(e)}")
            return False

    def get_pending_admin_requests(self) -> List[Dict]:
        """Récupère les demandes de compte admin en attente"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM admin_requests WHERE status="pending"')
        return [dict(row) for row in cursor.fetchall()]

    def approve_admin_request(self, request_id: int, approved_by: int) -> bool:
        """Approuve une demande de compte admin"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('SELECT * FROM admin_requests WHERE id=?', (request_id,))
                request = cursor.fetchone()
                
                if request:
                    cursor.execute('''
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (?, ?, ?, 'admin')
                    ''', (request['username'], request['email'], request['password_hash']))
                    
                    cursor.execute('''
                    UPDATE admin_requests 
                    SET status="approved", approved_by=?
                    WHERE id=?
                    ''', (approved_by, request_id))
                    return True
                return False
        except sqlite3.Error as e:
            st.error(f"Erreur lors de l'approbation: {str(e)}")
            return False

    # Autres méthodes de gestion
    def update_user_role(self, user_id: int, new_role: str) -> None:
        """Met à jour le rôle d'un utilisateur"""
        with self.conn:
            self.conn.execute(
                'UPDATE users SET role=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (new_role, user_id))

    def log_activity(self, user_id: int, action: str, details: str = "", ip_address: str = "") -> None:
        """Enregistre une activité utilisateur"""
        with self.conn:
            self.conn.execute('''
            INSERT INTO activity_logs (user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
            ''', (user_id, action, details, ip_address))

    def get_activity_logs(self, date_filter: str = None, user_id: int = None) -> List[Dict]:
        """Récupère les logs d'activité avec filtres"""
        query = '''
        SELECT l.*, u.username 
        FROM activity_logs l
        JOIN users u ON l.user_id = u.id
        WHERE 1=1
        '''
        params = []
        
        if date_filter:
            query += ' AND date(l.created_at) = date(?)'
            params.append(date_filter)
        
        if user_id:
            query += ' AND l.user_id = ?'
            params.append(user_id)
        
        query += ' ORDER BY l.created_at DESC'
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

# =============================================
# 3. FONCTIONS UTILITAIRES
# =============================================

def hash_password(password: str) -> str:
    """Hash un mot de passe avec SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection() -> sqlite3.Connection:
    """Établit une connexion à la base de données"""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn

def init_session():
    """Initialise les variables de session"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None

def get_last_activity(user_manager: EnhancedUserManager) -> str:
    """Récupère la dernière activité enregistrée"""
    logs = user_manager.get_activity_logs()
    return logs[0]['created_at'][:16] if logs else "Aucune"

# =============================================
# 4. PAGES DE L'INTERFACE UTILISATEUR
# =============================================

def login_page():
    """Affiche la page de connexion"""
    st.title("🔐 Connexion ")
    
    with st.form("login_form"):
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        
        if st.form_submit_button("Se connecter"):
            try:
                conn = get_db_connection()
                user_manager = EnhancedUserManager(conn)
                user = user_manager.get_user_by_username(username)
                
                if user and user['password_hash'] == hash_password(password):
                    st.session_state.authenticated = True
                    st.session_state.user = dict(user)
                    st.success("Connexion réussie!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Identifiants incorrects")
            except Exception as e:
                st.error(f"Erreur de connexion: {str(e)}")
            finally:
                if 'conn' in locals():
                    conn.close()

def initial_admin_setup():
    """Page de configuration initiale du premier admin"""
    st.title("🔧 Configuration Initiale")
    st.warning("Aucun compte administrateur trouvé. Créez le compte administrateur initial.")
    
    with st.form("initial_admin_form"):
        username = st.text_input("Nom d'utilisateur admin*")
        email = st.text_input("Email admin*")
        password = st.text_input("Mot de passe*", type="password")
        confirm_password = st.text_input("Confirmer le mot de passe*", type="password")
        
        if st.form_submit_button("Créer le compte admin"):
            if password != confirm_password:
                st.error("Les mots de passe ne correspondent pas")
            elif not all([username, email, password]):
                st.error("Tous les champs obligatoires (*) doivent être remplis")
            else:
                conn = get_db_connection()
                user_manager = EnhancedUserManager(conn)
                
                if user_manager.create_admin_account(username, email, password):
                    st.success("Compte admin créé! Redirection...")
                    time.sleep(2)
                    st.session_state.authenticated = True
                    st.session_state.user = {
                        'username': username,
                        'email': email,
                        'role': 'admin'
                    }
                    st.rerun()
                conn.close()

def admin_request_page():
    """Page pour demander un compte admin"""
    st.title("👑 Demande de Compte Admin")
    
    with st.form("admin_request_form"):
        st.info("Remplissez ce formulaire pour demander un compte administrateur.")
        
        username = st.text_input("Nom d'utilisateur*")
        email = st.text_input("Email*")
        password = st.text_input("Mot de passe*", type="password")
        confirm_password = st.text_input("Confirmer le mot de passe*", type="password")
        justification = st.text_area("Justification*")
        
        if st.form_submit_button("Soumettre la demande"):
            if password != confirm_password:
                st.error("Les mots de passe ne correspondent pas")
            elif not all([username, email, password, justification]):
                st.error("Tous les champs obligatoires (*) doivent être remplis")
            else:
                conn = get_db_connection()
                user_manager = EnhancedUserManager(conn)
                
                if user_manager.request_admin_account(username, email, password, justification):
                    st.success("Demande envoyée! Un admin examinera votre demande.")
                    time.sleep(3)
                    st.rerun()
                conn.close()

def admin_approval_page(user_manager: EnhancedUserManager):
    """Page d'approbation des demandes admin"""
    st.header("📋 Demandes Admin en Attente")
    
    requests = user_manager.get_pending_admin_requests()
    
    if not requests:
        st.info("Aucune demande en attente")
        return
    
    for req in requests:
        with st.expander(f"Demande de {req['username']}"):
            st.write(f"**Email:** {req['email']}")
            st.write(f"**Date:** {req['request_date']}")
            st.write(f"**Justification:** {req['justification']}")
            
            if st.button(f"Approuver {req['username']}", key=f"approve_{req['id']}"):
                if user_manager.approve_admin_request(req['id'], st.session_state.user['id']):
                    st.success("Demande approuvée!")
                    time.sleep(2)
                    st.rerun()

def get_last_activity(user_manager: EnhancedUserManager) -> str:
    """Récupère la dernière activité"""
    logs = user_manager.get_activity_logs()
    return logs[0]['created_at'][:16] if logs else "Aucune"

def show_user_management(user_manager: EnhancedUserManager):
    """Affiche l'interface de gestion des utilisateurs"""
    st.header("Gestion des Utilisateurs")
    
    # Création d'utilisateur
    with st.expander("➕ Créer un nouvel utilisateur", expanded=False):
        with st.form("create_user_form"):
            cols = st.columns(2)
            with cols[0]:
                new_username = st.text_input("Nom d'utilisateur*")
                new_email = st.text_input("Email*")
            with cols[1]:
                new_password = st.text_input("Mot de passe*", type="password")
                new_role = st.selectbox("Rôle*", ["user", "manager", "admin"])
            
            if st.form_submit_button("Créer l'utilisateur"):
                if not all([new_username, new_email, new_password]):
                    st.error("Tous les champs sont obligatoires")
                else:
                    try:
                        hashed_pwd = hash_password(new_password)
                        user_id = user_manager.add_user(new_username, new_email, hashed_pwd, new_role)
                        user_manager.log_activity(
                            st.session_state.user['id'], 
                            "Création utilisateur",
                            f"Nouvel utilisateur: {new_username} (ID:{user_id})"
                        )
                        st.success(f"Utilisateur {new_username} créé avec succès!")
                    except sqlite3.IntegrityError as e:
                        st.error(str(e))
    
    # Liste et édition des utilisateurs
    st.subheader("Liste des Utilisateurs")
    users = user_manager.get_all_users()
    
    if users:
        df = pd.DataFrame(users)
        
        # Colonnes à afficher
        cols_to_show = ['id', 'username', 'email', 'role', 'status', 'last_login', 'created_at']
        
        # Éditeur de données
        edited_df = st.data_editor(
            df[cols_to_show],
            disabled=["id", "created_at", "last_login"],
            column_config={
                "created_at": st.column_config.DatetimeColumn("Créé le"),
                "last_login": st.column_config.DatetimeColumn("Dernière connexion"),
                "role": st.column_config.SelectboxColumn(
                    "Rôle",
                    options=["user", "manager", "admin"]
                ),
                "status": st.column_config.SelectboxColumn(
                    "Statut",
                    options=["active", "inactive", "suspended"]
                )
            },
            hide_index=True,
            use_container_width=True
        )
        
        if st.button("💾 Enregistrer les modifications"):
            # Comparaison pour détecter les changements
            original_df = df[cols_to_show].set_index('id')
            edited_df = edited_df.set_index('id')
            
            for user_id in original_df.index:
                original = original_df.loc[user_id]
                edited = edited_df.loc[user_id]
                
                # Vérifier les changements de rôle
                if original['role'] != edited['role']:
                    user_manager.update_user_role(user_id, edited['role'])
                    user_manager.log_activity(
                        st.session_state.user['id'],
                        "Modification rôle",
                        f"Utilisateur ID:{user_id} nouveau rôle: {edited['role']}"
                    )
                
                # Vérifier les changements de statut
                if original['status'] != edited['status']:
                    user_manager.update_user_status(user_id, edited['status'])
                    user_manager.log_activity(
                        st.session_state.user['id'],
                        "Modification statut",
                        f"Utilisateur ID:{user_id} nouveau statut: {edited['status']}"
                    )
            
            st.success("Modifications enregistrées!")
            st.rerun()
    else:
        st.info("Aucun utilisateur trouvé")

def show_activity_logs(user_manager: EnhancedUserManager):
    """Affiche les logs d'activité"""
    st.header("Journal des Activités")
    
    # Filtres
    with st.expander("🔍 Filtres", expanded=True):
        cols = st.columns(3)
        with cols[0]:
            date_filter = st.date_input("Date", value=datetime.now().date())
        with cols[1]:
            user_filter = st.selectbox(
                "Utilisateur",
                ["Tous"] + [u['username'] for u in user_manager.get_all_users()]
            )
        with cols[2]:
            action_filter = st.text_input("Action contenant")
    
    # Récupération des logs
    logs = user_manager.get_activity_logs(
        date_filter=str(date_filter),
        user_id=None if user_filter == "Tous" else next(
            u['id'] for u in user_manager.get_all_users() if u['username'] == user_filter
        )
    )
    
    # Filtrage supplémentaire
    if action_filter:
        logs = [log for log in logs if action_filter.lower() in log['action'].lower()]
    
    # Affichage
    if logs:
        # Formatage des données pour l'affichage
        log_data = [{
            "Date": log['created_at'][:19],
            "Utilisateur": log['username'],
            "Action": log['action'],
            "Détails": log.get('details', ''),
            "IP": log.get('ip_address', '')
        } for log in logs]
        
        st.dataframe(
            pd.DataFrame(log_data),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Date": st.column_config.DatetimeColumn("Date/heure"),
                "Détails": st.column_config.TextColumn("Détails", width="large")
            }
        )
        
        # Bouton d'export
        csv = pd.DataFrame(log_data).to_csv(index=False).encode('utf-8')
        st.download_button(
            "📤 Exporter en CSV",
            data=csv,
            file_name=f"logs_activite_{date_filter}.csv",
            mime="text/csv"
        )
    else:
        st.info("Aucune activité trouvée pour ces critères")

def show_system_settings():
    """Affiche les paramètres système"""
    st.header("Paramètres Système")
    
    with st.form("system_settings"):
        maintenance_mode = st.checkbox("Mode maintenance")
        log_level = st.selectbox(
            "Niveau de log",
            ["DEBUG", "INFO", "WARNING", "ERROR"],
            index=1
        )
        max_file_size = st.number_input(
            "Taille maximale des fichiers (MB)",
            min_value=1,
            value=10
        )
        
        if st.form_submit_button("Enregistrer les paramètres"):
            # Ici vous pourriez sauvegarder dans un fichier de config ou une table dédiée
            st.success("Paramètres système mis à jour!")


def admin_dashboard():
    """Tableau de bord principal de l'administrateur"""
    # Configuration de la page
    st.set_page_config(
        page_title="GESTION BANQUE",
        page_icon="🏦",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    def load_image(image_path):
        return Image.open(image_path)

    logo_img = load_image("assets/logo.png")
    
    # Barre latérale
    with st.sidebar:
        st.image(logo_img, width=20, use_column_width=True)
        st.markdown(f"### {st.session_state.user['username']}")
        st.markdown(f"*Rôle: {st.session_state.user['role']}*")
        
        if st.button("🔄 Rafraîchir"):
            st.rerun()
            
        if st.button("🚪 Déconnexion"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()
    
    # Contenu principal
    st.title("🏛 Tableau de bord Administrateur")
    
    try:
        conn = get_db_connection()
        user_manager = EnhancedUserManager(conn)
        
        # Métriques
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Utilisateurs actifs", user_manager.count_active_users())
        with col2:
            st.metric("Dernière activité", get_last_activity(user_manager))
        with col3:
            st.metric("Actions aujourd'hui", len(user_manager.get_activity_logs(date_filter=datetime.now().date())))
        
        # Onglets
        tab1, tab2, tab3 = st.tabs(["👥 Gestion Utilisateurs", "📊 Activités", "⚙ Paramètres"])
        
        with tab1:
            show_user_management(user_manager)
        
        with tab2:
            show_activity_logs(user_manager)
        
        with tab3:
            show_system_settings()
    
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()


def check_authentication(required_role: str = None) -> None:
    """
    Vérifie si l'utilisateur est authentifié et a le rôle requis
    Args:
        required_role: Rôle requis pour accéder à la page (optionnel)
    """

    # Vérifie si un admin existe
    conn = get_db_connection()
    user_manager = EnhancedUserManager(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    admin_count = cursor.fetchone()[0]
    conn.close()

    # Initialise l'état de session si nécessaire
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    
    # Redirige vers la page d'authentification si non connecté
    if admin_count == 0:
        initial_admin_setup()
    elif not st.session_state['authenticated']:
        login_page()
        st.stop()
    else:
        user_role = st.session_state.user.get('role')
        if user_role == 'admin':
            admin_dashboard()
            st.stop()
        else: 
            if user_role == 'manager' or user_role == 'user':
                show_admin_dashboard()
                st.stop()
    
    # Vérifie les autorisations si un rôle est requis
    if required_role and st.session_state.get('role') != required_role:
        st.error("Vous n'avez pas les permissions nécessaires pour accéder à cette page")
        logger.warning(
            f"Tentative d'accès non autorisé par {st.session_state['username']} "
            f"(requiert: {required_role})"
        )
        

def logout() -> None:
    """
    Déconnecte l'utilisateur et nettoie la session
    """
    username = st.session_state.get('username', 'Inconnu')
    st.session_state.clear()
    logger.info(f"Utilisateur {username} déconnecté")
    st.rerun()

# =============================================
# 5. FONCTION PRINCIPALE
# =============================================

def main():
    """Point d'entrée principal de l'application"""
    init_session()

    check_authentication()

 
def show_admin_dashboard():
    """Page de tableau de bord pour les utilisateurs non admin"""
    # Configuration de la page
    st.set_page_config(
        page_title="GESTION BANQUE",
        page_icon="🏦",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Chargement des styles CSS et des assets
    def load_css(file_name):
        with open(file_name) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

    def load_image(image_path):
        return Image.open(image_path)

    load_css("assets/styles.css")
    logo_img = load_image("assets/logo.png")
    
    # Barre latérale
    with st.sidebar:
        st.image(logo_img, width=20, use_column_width=True)
        st.markdown("<h1 style='text-align: center;'>Digital Financial Service</h1>", unsafe_allow_html=True)
        st.markdown(f"### {st.session_state.user['username']}")
        st.markdown(f"*Rôle: {st.session_state.user['role'].capitalize()}*")
        
        if st.button("🔄 Rafraîchir"):
            st.rerun()
            
        if st.button("🚪 Déconnexion"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()
    
    # Contenu principal en fonction du rôle
    st.title(f"🏠 Tableau de bord {st.session_state.user['role'].capitalize()}")
    
    try:
        conn = get_db_connection()
        user_manager = EnhancedUserManager(conn)
        
        # Contenu différent selon le rôle
        if st.session_state.user['role'] == 'manager':
            # Tableau de bord manager
            st.subheader("Fonctionnalités Manager")
            st.write("Vous avez accès aux fonctionnalités de gestion limitées.")
            
            # Exemple de fonctionnalité manager
            with st.expander("📊 Statistiques"):
                st.metric("Utilisateurs actifs", user_manager.count_active_users())
                st.write(f"Dernière activité système: {get_last_activity(user_manager)}")
                
        else:
            # Tableau de bord utilisateur standard
            st.subheader("Votre Espace Personnel")
            st.write("Bienvenue dans votre espace utilisateur.")
            
            # Exemple de fonctionnalité utilisateur
            with st.expander("📝 Mon Profil"):
                user = user_manager.get_user_by_username(st.session_state.user['username'])
                st.write(f"**Nom d'utilisateur:** {user['username']}")
                st.write(f"**Email:** {user['email']}")
                st.write(f"**Dernière connexion:** {user['last_login'] or 'Jamais'}")
                
        # Fonctionnalités communes à tous les utilisateurs non-admin
        with st.expander("📋 Mes Activités"):
            logs = user_manager.get_activity_logs(user_id=st.session_state.user['id'])
            if logs:
                st.dataframe(pd.DataFrame([{
                    "Date": log['created_at'],
                    "Action": log['action'],
                    "Détails": log.get('details', '')
                } for log in logs]))
            else:
                st.info("Aucune activité récente")

        # Ajoutez ceci au début de votre script
        st.session_state.setdefault('force_refresh', True)

        if st.session_state.force_refresh:
            time.sleep(0.1)  # Pause minimale
            st.session_state.force_refresh = False
            st.rerun()  # Force le rechargement propre

        # Initialisation des composants
        db = BankDatabase()
        fake = Faker()

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
            
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Liste des AVI", "➕ Ajouter AVI", "✏️ Modifier AVI", "🖨 Générer AVI", "📤 Importer PDF"])
            
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
                                    # Création du PDF
                                    pdf = FPDF()
                                    pdf.add_page()
                                    
                                    # ---- En-tête ----
                                    pdf.set_font('Arial', 'B', 16)
                                    pdf.cell(0, 30, 'ATTESTATION DE VIREMENT IRREVOCABLE', 0, 1, 'C')
                                    
                                    # Référence du document
                                    pdf.set_font('Arial', 'B', 10)
                                    pdf.cell(0, 0, f"DGF/EC-{avi_data['reference']}", 0, 1, 'C')
                                    pdf.ln(10)
                                    
                                    # ---- Logo et entête ----
                                    try:
                                        pdf.image("assets/logo.png", x=10, y=10, w=30)
                                    except:
                                        pass  # Continue sans logo si non trouvé
                                    
                                    # Fonction pour texte justifié
                                    def justified_text(text, line_height=5):
                                        lines = text.split('\n')
                                        for line in lines:
                                            if line.strip() == "":
                                                pdf.ln(line_height)
                                            else:
                                                pdf.multi_cell(0, line_height, line, 0, 'J')

                                    # ---- Corps du document ----
                                    pdf.set_font('Arial', '', 12)
                                    intro = [
                                        "Nous soussignés, Eco Capital (E.C), établissement de microfinance agréé pour exercer des",
                                        "activités bancaires en République du Congo conformément au décret n°7236/MEFB-CAB du",
                                        "15 novembre 2007, après avis conforme de la COBAC D-2007/2018, déclarons avoir notre",
                                        "siège au n°1636 Boulevard Denis Sassou Nguesso, Batignol Brazzaville.",
                                        "",
                                        "Représenté par son Directeur Général, Monsieur ILOKO Charmant.",
                                        "",
                                        f"Nous certifions par la présente que Monsieur/Madame {avi_data['nom_complet']}",
                                        "détient un compte courant enregistré dans nos livres avec les caractéristiques suivantes :",
                                        ""
                                    ]
                                    
                                    for line in intro:
                                        pdf.cell(0, 5, line, 0, 2)
                                    
                                    # Informations bancaires en gras
                                    pdf.set_font('Arial', 'B', 12)
                                    pdf.cell(40, 5, "CODE BANQUE :", 0, 0)
                                    pdf.set_font('Arial', '', 12)
                                    pdf.cell(0, 5, avi_data['code_banque'], 0, 1)
                                    
                                    pdf.set_font('Arial', 'B', 12)
                                    pdf.cell(40, 5, "NUMERO COMPTE : ", 0, 0)
                                    pdf.set_font('Arial', '', 12)
                                    pdf.cell(0, 5, avi_data['numero_compte'], 0, 1)
                                    
                                    pdf.set_font('Arial', 'B', 12)
                                    pdf.cell(40, 5, "Devise :", 0, 0)
                                    pdf.set_font('Arial', '', 12)
                                    pdf.cell(0, 5, avi_data['devise'], 0, 1)
                                    pdf.ln(5)
                                    
                                    # ---- Détails du virement ----
                                    details = [
                                        f"Il est l'ordonnateur d'un virement irrévocable et permanent d'un montant total de {avi_data['montant']:,.2f} FCFA",
                                        f"(cinq millions de francs CFA), équivalant actuellement à {avi_data['montant']/650:,.2f} euros,",
                                        "destiné à couvrir les frais liés à ses études en France.",
                                        "",
                                        "Il est précisé que ce compte demeurera bloqué jusqu'à la présentation, par le donneur",
                                        "d'ordre, de ses nouvelles coordonnées bancaires ouvertes en France.",
                                        "",
                                        "À défaut, les fonds ne pourront être remis à sa disposition qu'après présentation de son",
                                        "passeport attestant d'un refus de visa. Toutefois, nous autorisons le donneur d'ordre, à",
                                        "toutes fins utiles, à utiliser notre compte ouvert auprès de United Bank for Africa (UBA).",
                                        ""
                                    ]
                                    
                                    for line in details:
                                        pdf.cell(0, 5, line, 0, 1)
                                    
                                    # ---- Coordonnées bancaires ----
                                    pdf.set_font('Arial', 'B', 12)
                                    pdf.cell(40, 5, "IBAN:", 0, 0)
                                    pdf.set_font('Arial', '', 12)
                                    pdf.cell(0, 5, avi_data['iban'], 0, 1)
                                    
                                    pdf.set_font('Arial', 'B', 12)
                                    pdf.cell(40, 5, "BIC:", 0, 0)
                                    pdf.set_font('Arial', '', 12)
                                    pdf.cell(0, 5, avi_data['bic'], 0, 1)
                                    pdf.ln(10)
                                    
                                    # ---- Clause de validation ----
                                    pdf.cell(0, 5, "En foi de quoi, cette attestation lui est délivrée pour servir et valoir ce que de droit.", 0, 1)
                                    pdf.ln(10)
                                    
                                    # ---- Date et signature ----
                                    pdf.cell(1, 5, f"Fait à Brazzaville, le {datetime.now().strftime('%d %B %Y')}", 0, 1)
                                    pdf.ln(5)
                                    
                                    pdf.cell(0, 5, "Rubain MOUNGALA", 0, 1)
                                    pdf.set_font('Arial', 'B', 12)
                                    pdf.cell(0, 5, "Directeur de la Gestion Financière", 0, 1)
                                    pdf.ln(15)
                                    
                                    # ---- Pied de page ----
                                    footer = [
                                        "Eco capital Sarl",
                                        "Société a responsabilité limité au capital de 60.000.000 XAF",
                                        "Siège social : 1636 Boulevard Denis Sassou Nguesso Brazzaville",
                                        "Contact: 00242 06 931 31 06 /04 001 79 40",
                                        "Web : www.ecocapitale.com mail : contacts@ecocapitale.com",
                                        "RCCM N°CG/BZV/B12-00320NIU N°M24000000665934H",
                                        "Brazzaville République du Congo"
                                    ]
                                    
                                    pdf.set_font('Arial', 'I', 10)
                                    for line in footer:
                                        pdf.cell(0, 4, line, 0, 1, 'C')
                                    
                                    # ---- QR Code ----
                                    qr_data = {
                                        "Référence": avi_data['reference'],
                                        "Nom": avi_data['nom_complet'],
                                        "Code Banque": avi_data['code_banque'],
                                        "Numéro Compte": avi_data['numero_compte'],
                                        "IBAN": avi_data['iban'],
                                        "BIC": avi_data['bic'],
                                        "Montant": f"{avi_data['montant']:,.2f} FCFA",
                                        "Date Création": avi_data['date_creation']
                                    }
                                    
                                    qr = qrcode.QRCode(
                                        version=1,
                                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                                        box_size=3,
                                        border=2,
                                    )
                                    
                                    qr.add_data(qr_data)
                                    qr.make(fit=True)
                                    
                                    img = qr.make_image(fill_color="black", back_color="white")
                                    img_bytes = BytesIO()
                                    img.save(img_bytes, format='PNG')
                                    img_bytes.seek(0)
                                    
                                    pdf.image(img_bytes, x=150, y=pdf.get_y()-65, w=40)
                                    pdf.ln(20)
                                    
                                    # ---- Sauvegarde du fichier ----
                                    os.makedirs("avi_documents", exist_ok=True)
                                    output_path = f"avi_documents/AVI_{avi_data['reference']}.pdf"
                                    pdf.output(output_path)
                                    
                                    # ---- Affichage et téléchargement ----
                                    st.success("✅ Attestation générée avec succès!")
                                    
                                    # Colonnes pour les boutons et la prévisualisation
                                    col1, col2 = st.columns([1, 3])
                                    
                                    with col1:
                                        # Bouton de téléchargement
                                        with open(output_path, "rb") as f:
                                            st.download_button(
                                                "⬇️ Télécharger l'AVI",
                                                data=f,
                                                file_name=f"AVI_{avi_data['reference']}.pdf",
                                                mime="application/pdf",
                                                use_container_width=True
                                            )
                                    
                                    with col2:
                                        # Bouton pour afficher la prévisualisation
                                        if st.button("👁️ Aperçu du document", use_container_width=True):
                                            # Affichage du PDF dans l'interface
                                            with open(output_path, "rb") as f:
                                                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                                                pdf_display = f"""
                                                <div style="height: 600px; overflow: auto;">
                                                    <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="100%" type="application/pdf"></iframe>
                                                </div>
                                                """
                                                st.markdown(pdf_display, unsafe_allow_html=True)
                                    
                                    # Afficher automatiquement la prévisualisation
                                    with open(output_path, "rb") as f:
                                        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                                        pdf_display = f"""
                                        <div style="height: 600px; overflow: auto; margin-top: 20px; border: 1px solid #ddd; border-radius: 5px;">
                                            <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="100%" type="application/pdf"></iframe>
                                        </div>
                                        """
                                        st.markdown(pdf_display, unsafe_allow_html=True)
                                    
                                except Exception as e:
                                    st.error(f"❌ Erreur lors de la génération: {str(e)}")
                                    st.exception(e)
    

            with tab5:
                st.subheader("Importer et Modifier un PDF")
                
                # Section d'import de fichier
                uploaded_file = st.file_uploader("Choisir un fichier PDF", type="pdf")
                
                if uploaded_file is not None:
                    # Afficher le PDF importé
                    st.success("Fichier importé avec succès!")
                    
                    # Afficher la prévisualisation du PDF
                    base64_pdf = base64.b64encode(uploaded_file.read()).decode('utf-8')
                    pdf_display = f"""
                    <div style="height: 500px; overflow: auto; margin-bottom: 20px; border: 1px solid #ddd; border-radius: 5px;">
                        <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="100%" type="application/pdf"></iframe>
                    </div>
                    """
                    st.markdown(pdf_display, unsafe_allow_html=True)
                    
                    # Réinitialiser le pointeur du fichier pour le réutiliser
                    uploaded_file.seek(0)
                    
                    # Section pour générer le QR code
                    st.subheader("Ajouter un QR Code au PDF")
                    
                    # Formulaire pour les données du QR code
                    with st.form("qr_data_form"):
                        qr_content = st.text_area("Contenu du QR Code", 
                                                value="Référence: \nNom: \nCode Banque: \nMontant: \nDate: ",
                                                height=150)
                        
                        qr_position = st.selectbox("Position du QR Code", 
                                                ["En bas à droite", "En bas à gauche", "En haut à droite", "En haut à gauche"])
                        
                        qr_size = st.slider("Taille du QR Code", 50, 200, 100)
                        
                        submitted = st.form_submit_button("Générer QR Code")
                    
                    # Section pour afficher le résultat et télécharger (en dehors du form)
                    if submitted:
                        try:
                            # Créer le QR code
                            qr = qrcode.QRCode(
                                version=1,
                                error_correction=qrcode.constants.ERROR_CORRECT_L,
                                box_size=10,
                                border=4,
                            )
                            qr.add_data(qr_content)
                            qr.make(fit=True)
                            
                            img = qr.make_image(fill_color="black", back_color="white")
                            
                            # Sauvegarder l'image temporairement
                            temp_qr_path = "temp_qr.png"
                            img.save(temp_qr_path)
                            
                            # Charger le PDF existant
                            pdf_reader = PyPDF2.PdfReader(uploaded_file)
                            pdf_writer = PyPDF2.PdfWriter()
                            
                            # Ajouter toutes les pages au writer
                            for page_num in range(len(pdf_reader.pages)):
                                page = pdf_reader.pages[page_num]
                                pdf_writer.add_page(page)
                            
                            # Créer un nouveau PDF avec le QR code
                            packet = BytesIO()
                            can = canvas.Canvas(packet, pagesize=letter)
                            
                            # Déterminer la position du QR code
                            if qr_position == "En bas à droite":
                                x = 450
                                y = 50
                            elif qr_position == "En bas à gauche":
                                x = 50
                                y = 50
                            elif qr_position == "En haut à droite":
                                x = 450
                                y = 700
                            else:  # En haut à gauche
                                x = 50
                                y = 700
                            
                            # Dessiner le QR code à partir du fichier temporaire
                            can.drawImage(temp_qr_path, x, y, width=qr_size, height=qr_size)
                            can.save()
                            
                            # Fusionner avec le PDF original
                            packet.seek(0)
                            new_pdf = PyPDF2.PdfReader(packet)
                            
                            # Ajouter le QR code à chaque page
                            for page_num in range(len(pdf_writer.pages)):
                                page = pdf_writer.pages[page_num]
                                page.merge_page(new_pdf.pages[0])
                            
                            # Sauvegarder le résultat
                            output_path = "modified_pdf_with_qr.pdf"
                            with open(output_path, "wb") as output_file:
                                pdf_writer.write(output_file)
                            
                            # Supprimer le fichier temporaire
                            os.remove(temp_qr_path)
                            
                            st.success("QR code ajouté au PDF avec succès!")
                            
                            # Afficher le résultat
                            with open(output_path, "rb") as f:
                                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                                pdf_display = f"""
                                <div style="height: 500px; overflow: auto; margin-top: 20px; border: 1px solid #ddd; border-radius: 5px;">
                                    <iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="100%" type="application/pdf"></iframe>
                                </div>
                                """
                                st.markdown(pdf_display, unsafe_allow_html=True)
                            
                            # Bouton de téléchargement (en dehors du form)
                            with open(output_path, "rb") as f:
                                st.download_button(
                                    "⬇️ Télécharger le PDF modifié",
                                    data=f,
                                    file_name="document_avec_qr.pdf",
                                    mime="application/pdf"
                                )
                        
                        except Exception as e:
                            st.error(f"Erreur lors de l'ajout du QR code: {str(e)}")
                            if os.path.exists(temp_qr_path):
                                os.remove(temp_qr_path)
            
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()