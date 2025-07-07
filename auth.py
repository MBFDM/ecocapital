"""
Application de Gestion Administrateur avec Streamlit (version MySQL)

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
import re
import PyPDF2
from PIL import Image, ImageFilter
from docx import Document
from fpdf import FPDF
import mysql.connector
import pdfplumber
import qrcode
import streamlit as st
from datetime import datetime
import pandas as pd
import hashlib
import time
from typing import List, Dict, Optional
import streamlit as st
from streamlit_option_menu import option_menu
import plotly.express as px
from database import BankDatabase
from receipt_generator import generate_receipt_pdf
from faker import Faker
import base64
import os
from datetime import datetime, timedelta
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from streamlit.components.v1 import html
import extra_streamlit_components as stx
from streamlit.components.v1 import html
# from streamlit_extras.notification_box import notification
from streamlit_extras.let_it_rain import rain
from streamlit_extras.stylable_container import stylable_container
from streamlit_extras.switch_page_button import switch_page
from streamlit_extras.colored_header import colored_header
from streamlit_extras.add_vertical_space import add_vertical_space
from streamlit_extras.dataframe_explorer import dataframe_explorer
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.toggle_switch import st_toggle_switch
import bcrypt
import secrets
import string

# Configuration MySQL
MYSQL_CONFIG = {
    'host': 'db-mav-1.cdeaqqe46t76.eu-north-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'Frz5E1LTv49J7xF6MQleP0hgrYrCO3ybyHpJujA',
    'database': 'ecocapital',
    'port': 3306,
}

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================
# STYLE ET THÈME PERSONNALISÉ
# =============================================
def set_custom_theme():
    st.markdown(f"""
    <style>
        /* Couleurs principales */
        :root {{
            --primary: #3498db;
            --secondary: #2ecc71;
            --accent: #e74c3c;
            --dark: #2c3e50;
            --light: #ecf0f1;
            --background: #f9f9f9;
        }}
        
        /* Style général */
        .stApp {{
            background-color: var(--background);
            color: var(--dark);
        }}
        
        /* En-têtes */
        h1, h2, h3, h4, h5, h6 {{
            color: var(--dark) !important;
            border-bottom: 2px solid var(--primary);
            padding-bottom: 0.3em;
        }}
        
        /* Sidebar */
        [data-testid="stSidebar"] {{
            background: linear-gradient(135deg, var(--dark), #34495e) !important;
            color: white !important;
        }}
        
        /* Boutons */
        .stButton>button {{
            background-color: var(--primary) !important;
            color: white !important;
            border-radius: 8px !important;
            transition: all 0.3s ease !important;
            border: none !important;
        }}
        
        .stButton>button:hover {{
            background-color: #2980b9 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
        }}
        
        /* Cartes */
        .card {{
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            padding: 1.5em;
            margin-bottom: 1em;
            transition: all 0.3s ease;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.15);
        }}
        
        /* Tableaux */
        .stDataFrame {{
            border-radius: 10px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
        }}
        
        /* Onglets */
        .stTabs [role="tablist"] {{
            background: transparent !important;
        }}
        
        .stTabs [role="tab"] {{
            color: var(--dark) !important;
            border-radius: 8px 8px 0 0 !important;
            transition: all 0.3s ease !important;
        }}
        
        .stTabs [role="tab"][aria-selected="true"] {{
            background: var(--primary) !important;
            color: white !important;
        }}
        
        /* Animation pour les notifications */
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .notification {{
            animation: fadeIn 0.5s ease-out;
        }}
        
        /* Effet de chargement */
        @keyframes pulse {{
            0% {{ opacity: 0.6; }}
            50% {{ opacity: 1; }}
            100% {{ opacity: 0.6; }}
        }}
        
        .stSpinner>div>div {{
            background-color: var(--primary) !important;
            animation: pulse 1.5s infinite ease-in-out;
        }}
    </style>
    """, unsafe_allow_html=True)

# =============================================
# 2. CLASSES DE GESTION DE BASE DE DONNÉES
# =============================================

class EnhancedUserManager:
    """Gestionnaire complet des utilisateurs et de l'administration"""
    
    def __init__(self, conn: mysql.connector.MySQLConnection):
        """Initialise la connexion et crée les tables"""
        self.conn = conn
        self._create_tables()

    def _create_tables(self):
        """Crée les tables nécessaires dans la base de données"""
        with self.conn.cursor() as cursor:
            try:
                # Table des utilisateurs
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) DEFAULT 'user',
                    status VARCHAR(50) DEFAULT 'active',
                    last_login TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CONSTRAINT chk_role CHECK (role IN ('user', 'manager', 'admin')),
                    CONSTRAINT chk_status CHECK (status IN ('active', 'inactive', 'suspended'))
                )''')

                # Table des demandes admin
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_requests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    justification TEXT,
                    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(50) DEFAULT 'pending',
                    approved_by INT,
                    FOREIGN KEY (approved_by) REFERENCES users (id)
                )''')

                # Table des logs d'activité
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    action VARCHAR(255) NOT NULL,
                    details TEXT,
                    ip_address VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )''')
                
                self.conn.commit()
            except mysql.connector.Error as err:
                logger.error(f"Erreur lors de la création des tables: {err}")
                raise

    # Méthodes de gestion des utilisateurs
    def add_user(self, username: str, email: str, password_hash: str, role: str = 'user') -> int:
        """Ajoute un nouvel utilisateur à la base de données"""
        try:
            with self.conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (%s, %s, %s, %s)
                ''', (username, email, password_hash, role))
                self.conn.commit()
                return cursor.lastrowid
        except mysql.connector.Error as e:
            raise mysql.connector.Error(f"Erreur MySQL: {str(e)}")

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Récupère un utilisateur par son nom d'utilisateur"""
        with self.conn.cursor(dictionary=True) as cursor:
            cursor.execute('SELECT * FROM users WHERE username=%s', (username,))
            return cursor.fetchone()
    
    def get_all_users(self) -> List[Dict]:
        """Récupère tous les utilisateurs"""
        with self.conn.cursor(dictionary=True) as cursor:
            cursor.execute('SELECT * FROM users ORDER BY username')
            return cursor.fetchall()

    def update_user_role(self, user_id: int, new_role: str) -> None:
        """Met à jour le rôle d'un utilisateur"""
        with self.conn.cursor() as cursor:
            cursor.execute(
                'UPDATE users SET role=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s',
                (new_role, user_id))
            self.conn.commit()

    def update_user_status(self, user_id: int, new_status: str) -> None:
        """Met à jour le statut d'un utilisateur"""
        with self.conn.cursor() as cursor:
            cursor.execute(
                'UPDATE users SET status=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s',
                (new_status, user_id))
            self.conn.commit()

    def count_active_users(self) -> int:
        """Compte les utilisateurs actifs"""
        with self.conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM users WHERE status="active"')
            return cursor.fetchone()[0]

    def log_activity(self, user_id: int, action: str, details: str = "", ip_address: str = "") -> None:
        """Enregistre une activité utilisateur"""
        with self.conn.cursor() as cursor:
            cursor.execute('''
            INSERT INTO activity_logs (user_id, action, details, ip_address)
            VALUES (%s, %s, %s, %s)
            ''', (user_id, action, details, ip_address))
            self.conn.commit()

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
            query += ' AND DATE(l.created_at) = DATE(%s)'
            params.append(date_filter)
        
        if user_id:
            query += ' AND l.user_id = %s'
            params.append(user_id)
        
        query += ' ORDER BY l.created_at DESC'
        
        with self.conn.cursor(dictionary=True) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    # Méthodes de gestion des comptes admin
    def create_admin_account(self, username: str, email: str, password: str, justification: str = "") -> bool:
        """Crée un compte administrateur immédiatement"""
        try:
            with self.conn.cursor() as cursor:
                password_hash = hash_password(password)
                cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (%s, %s, %s, 'admin')
                ''', (username, email, password_hash))
                self.conn.commit()
                return True
        except mysql.connector.Error as e:
            st.error(f"Erreur lors de la création du compte admin: {str(e)}")
            return False

    def request_admin_account(self, username: str, email: str, password: str, justification: str) -> bool:
        """Enregistre une demande de création de compte admin"""
        try:
            with self.conn.cursor() as cursor:
                password_hash = hash_password(password)
                cursor.execute('''
                INSERT INTO admin_requests (username, email, password_hash, justification)
                VALUES (%s, %s, %s, %s)
                ''', (username, email, password_hash, justification))
                self.conn.commit()
                return True
        except mysql.connector.Error as e:
            st.error(f"Erreur lors de la demande de compte admin: {str(e)}")
            return False

    def get_pending_admin_requests(self) -> List[Dict]:
        """Récupère les demandes de compte admin en attente"""
        with self.conn.cursor(dictionary=True) as cursor:
            cursor.execute('SELECT * FROM admin_requests WHERE status="pending"')
            return cursor.fetchall()

    def approve_admin_request(self, request_id: int, approved_by: int) -> bool:
        """Approuve une demande de compte admin"""
        try:
            with self.conn.cursor(dictionary=True) as cursor:
                cursor.execute('SELECT * FROM admin_requests WHERE id=%s', (request_id,))
                request = cursor.fetchone()
                
                if request:
                    cursor.execute('''
                    INSERT INTO users (username, email, password_hash, role)
                    VALUES (%s, %s, %s, 'admin')
                    ''', (request['username'], request['email'], request['password_hash']))
                    
                    cursor.execute('''
                    UPDATE admin_requests 
                    SET status="approved", approved_by=%s
                    WHERE id=%s
                    ''', (approved_by, request_id))
                    self.conn.commit()
                    return True
                return False
        except mysql.connector.Error as e:
            st.error(f"Erreur lors de l'approbation: {str(e)}")
            return False

# =============================================
# 3. FONCTIONS UTILITAIRES
# =============================================

def hash_password(password: str) -> str:
    """Hash un mot de passe avec SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_db_connection() -> mysql.connector.MySQLConnection:
    """Établit une connexion à la base de données MySQL"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        return conn
    except mysql.connector.Error as err:
        logger.error(f"Erreur de connexion à MySQL: {err}")
        raise

def init_session():
    """Initialise les variables de session"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None

def get_last_activity(user_manager: EnhancedUserManager) -> str:
    """Récupère la dernière activité enregistrée"""
    logs = user_manager.get_activity_logs()
    return logs[0]['created_at'].strftime('%Y-%m-%d %H:%M') if logs else "Aucune"


def generate_secure_token(length=32):
    """Génère un token sécurisé pour les sessions"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def hash_password_secure(password: str) -> str:
    """Hash un mot de passe avec bcrypt (plus sécurisé que SHA-256)"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(hashed_password: str, input_password: str) -> bool:
    """Vérifie un mot de passe contre son hash (support bcrypt et legacy SHA-256)"""
    try:
        # Essayer d'abord avec bcrypt
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
            return bcrypt.checkpw(input_password.encode('utf-8'), hashed_password.encode('utf-8'))
        
        # Fallback pour l'ancien système SHA-256
        return hashed_password == hash_password(input_password)
    except Exception as e:
        logger.error(f"Erreur de vérification de mot de passe: {str(e)}")
        return False

def check_csrf():
    """Protection contre les attaques CSRF"""
    if 'csrf_token' not in st.session_state:
        st.session_state.csrf_token = generate_secure_token()
    
    if st.query_params.get('csrf_token'):
        if st.query_params['csrf_token'] != st.session_state.csrf_token:
            st.error("Token de sécurité invalide. Veuillez rafraîchir la page.")
            st.stop()

def migrate_password_hash(conn, user_id, plain_password):
    """Migre un hash SHA-256 vers bcrypt"""
    try:
        new_hash = hash_password_secure(plain_password)
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE users SET password_hash=%s WHERE id=%s",
                (new_hash, user_id)
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erreur migration hash: {str(e)}")
        return False

# =============================================
# 3. COMPOSANTS UI AMÉLIORÉS
# =============================================
def show_notification(message, notification_type="success", duration=3000):
    """Affiche une notification stylisée"""
    colors = {
        "success": "#2ecc71",
        "error": "#e74c3c",
        "warning": "#f39c12",
        "info": "#3498db"
    }
    
    notification_html = f"""
    <div class="notification" style="
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px;
        background: {colors[notification_type]};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        z-index: 1000;
        display: flex;
        align-items: center;
        animation: fadeIn 0.5s ease-out;
    ">
        <span style="margin-right: 10px;">{message}</span>
    </div>
    <script>
        setTimeout(function() {{
            document.querySelector('.notification').style.animation = 'fadeOut 0.5s ease-out';
            setTimeout(function() {{
                document.querySelector('.notification').remove();
            }}, 500);
        }}, {duration});
    </script>
    <style>
        @keyframes fadeOut {{
            from {{ opacity: 1; transform: translateY(0); }}
            to {{ opacity: 0; transform: translateY(-20px); }}
        }}
    </style>
    """
    
    st.components.v1.html(notification_html, height=0)

def animated_rain_effect():
    """Effet de pluie animé pour les succès"""
    rain(
        emoji="💰",
        font_size=20,
        falling_speed=5,
        animation_length=1,
    )

def loading_spinner_with_message(message):
    """Spinner de chargement avec message"""
    with st.spinner(message):
        time.sleep(1.5)

# =============================================
# STYLE ET THEME PERSONNALISE
# =============================================
def load_css():
    st.markdown("""
    <style>
        :root {
            --primary: #4a6fa5;
            --secondary: #166088;
            --accent: #4fc3f7;
            --success: #4caf50;
            --warning: #ff9800;
            --danger: #f44336;
            --light: #f8f9fa;
            --dark: #212529;
        }
        
        /* Animation d'entrée */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .animated {
            animation: fadeIn 0.5s ease-out forwards;
        }
        
        /* Boutons améliorés */
        .stButton>button {
            border-radius: 8px;
            transition: all 0.3s;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        /* Cartes */
        .card {
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            background: white;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transition: all 0.3s;
            border-left: 4px solid var(--primary);
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 16px rgba(0,0,0,0.15);
        }
        
        /* Onglets */
        .stTabs [role="tablist"] {
            gap: 5px;
        }
        
        .stTabs [role="tab"] {
            border-radius: 8px 8px 0 0 !important;
            padding: 10px 20px !important;
            transition: all 0.3s;
        }
        
        .stTabs [role="tab"][aria-selected="true"] {
            background: var(--primary) !important;
            color: white !important;
            font-weight: bold;
        }
        
        /* Formulaire */
        .stTextInput>div>div>input, 
        .stTextArea>div>div>textarea,
        .stNumberInput>div>div>input,
        .stSelectbox>div>div>select {
            border-radius: 8px !important;
            padding: 10px !important;
        }
        
        /* Notification */
        .notification {
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
        }
        
        .notification-success {
            background: #e8f5e9;
            border-left: 4px solid var(--success);
        }
        
        .notification-error {
            background: #ffebee;
            border-left: 4px solid var(--danger);
        }
        
        .notification-warning {
            background: #fff8e1;
            border-left: 4px solid var(--warning);
        }
        
        /* Effet de chargement */
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .loader {
            border: 4px solid #f3f3f3;
            border-top: 4px solid var(--primary);
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }
    </style>
    """, unsafe_allow_html=True)


# =============================================
# 4. PAGES DE L'INTERFACE UTILISATEUR
# =============================================
def login_page():
    """Page de connexion avec design amélioré"""
    st.title("🔐 Connexion")
    
    # Effet de fond animé
    st.markdown("""
    <style>
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        .login-container {
            background: linear-gradient(-45deg, #ee7752, #e73c7e, #23a6d5, #23d5ab);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            padding: 2em;
            border-radius: 15px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
            color: white;
        }
    </style>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur", placeholder="Entrez votre identifiant")
            password = st.text_input("Mot de passe", type="password", placeholder="Entrez votre mot de passe")
            
            cols = st.columns([1, 1, 2])
            with cols[0]:
                login_btn = st.form_submit_button("Se connecter", type="primary")
            
            if login_btn:
                try:
                    conn = get_db_connection()
                    user_manager = EnhancedUserManager(conn)
                    user = user_manager.get_user_by_username(username)
                    
                    if user and verify_password(user['password_hash'], password):
                        # Création de la session sécurisée
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.session_token = generate_secure_token()
                        st.session_state.last_activity = datetime.now()
                        
                        # Journalisation
                        user_manager.log_activity(
                            user['id'],
                            "Connexion réussie",
                            f"Connexion depuis {st.experimental_get_query_params().get('client_ip', [''])[0]}",
                            ip_address=st.query_params.get('client_ip', '')
                        )
                        
                        # Notification et redirection
                        show_notification("Connexion réussie! Redirection en cours...", "success")
                        animated_rain_effect()
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        show_notification("Identifiants incorrects", "error")
                        logger.warning(f"Tentative de connexion échouée pour l'utilisateur: {username}")
                
                except Exception as e:
                    show_notification(f"Erreur de connexion: {str(e)}", "error")
                    logger.error(f"Erreur de connexion: {str(e)}")
                finally:
                    if 'conn' in locals():
                        conn.close()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Section d'aide
        with st.expander("🔍 Aide à la connexion", expanded=False):
            st.info("""
            - Utilisez votre nom d'utilisateur et mot de passe fournis par l'administrateur
            - Le système est sensible à la casse (majuscules/minuscules)
            - Après 3 tentatives échouées, votre compte sera temporairement bloqué
            """)

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
            st.write(f"**Date:** {req['request_date'].strftime('%Y-%m-%d %H:%M')}")
            st.write(f"**Justification:** {req['justification']}")
            
            if st.button(f"Approuver {req['username']}", key=f"approve_{req['id']}"):
                if user_manager.approve_admin_request(req['id'], st.session_state.user['id']):
                    st.success("Demande approuvée!")
                    time.sleep(2)
                    st.rerun()

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
                    except mysql.connector.Error as e:
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
            "Date": log['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
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
            st.success("Paramètres système mis à jour!")


def admin_dashboard():
    """Tableau de bord admin avec nouveau design"""
    st.set_page_config(
        page_title="GESTION BANQUE",
        page_icon="assets/logo.png",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    load_css()
    
    # Sidebar stylisée
    with st.sidebar:
        st.image("assets/logo.png", width=150)
        st.markdown(f"<h3 style='text-align: center; color: #4a6fa5;'>{st.session_state.user['username']}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='text-align: center; color: #666;'>{st.session_state.user['role'].capitalize()}</p>", unsafe_allow_html=True)
        
        add_vertical_space(2)
        
        # Menu de navigation
        selected = option_menu(
            menu_title=None,
            options=["Tableau de bord", "Utilisateurs", "Activités", "Paramètres"],
            icons=["speedometer2", "people-fill", "activity", "gear"],
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "#f8f9fa"},
                "icon": {"color": "#4a6fa5", "font-size": "16px"}, 
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "5px 0",
                    "border-radius": "8px",
                    "padding": "10px 15px",
                },
                "nav-link-selected": {
                    "background-color": "#4a6fa5",
                    "color": "white",
                },
            }
        )
        
        add_vertical_space(2)
        
        if st.button("🚪 Déconnexion", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            show_notification("Déconnexion réussie", "success", "👋")
            time.sleep(1)
            st.rerun()
    
    # Contenu principal
    st.markdown(f"<h1 style='color: #4a6fa5;'>Tableau de bord Administrateur</h1>", unsafe_allow_html=True)
    
    try:
        conn = get_db_connection()
        user_manager = EnhancedUserManager(conn)
        
        cols = st.columns(4)
        with cols[0]:
            st.metric(label="👥 Utilisateurs actifs", value=user_manager.count_active_users())
        with cols[1]:
            st.metric(label="🕒 Dernière activité", value=get_last_activity(user_manager))
        with cols[2]:
            st.metric(label="📊 Actions aujourd'hui", value=len(user_manager.get_activity_logs(date_filter=datetime.now().date())))
        with cols[3]:
            st.metric(label="⏳ Demandes en attente", value=len(user_manager.get_pending_admin_requests()))

        style_metric_cards()
        
        # Graphiques avec Plotly
        st.markdown("## Activité récente")
        logs = user_manager.get_activity_logs()
        if logs:
            df_logs = pd.DataFrame(logs)
            df_logs['date'] = pd.to_datetime(df_logs['created_at']).dt.date
            
            # Graphique d'activité
            fig = px.bar(
                df_logs.groupby(['date', 'action']).size().reset_index(name='count'),
                x='date',
                y='count',
                color='action',
                title="Activité par jour",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig, use_container_width=True)

        # Onglets
        tab1, tab2, tab3 = st.tabs(["👥 Gestion Utilisateurs", "📊 Activités", "⚙ Paramètres"])
        
        with tab1:
            show_user_management(user_manager)
        
        with tab2:
            show_activity_logs(user_manager)
        
        with tab3:
            show_system_settings()
        
        
        # Dernières activités
        #st.markdown("## Dernières activités")
        #if logs:
        #    with st.expander("Voir les dernières activités", expanded=True):
        #        st.dataframe(
        #            df_logs.head(10),
        #            use_container_width=True,
        #            hide_index=True,
        #            column_config={
        #                "created_at": st.column_config.DatetimeColumn("Date"),
        #                "action": "Action",
        #                "username": "Utilisateur",
        #                "details": "Détails"
        #            }
        #        )
        
    except Exception as e:
        show_notification(f"Erreur: {str(e)}", "error", "❌")
    finally:
        if 'conn' in locals():
            conn.close()


def check_authentication(required_role: str = None) -> None:
    """
    Vérifie si l'utilisateur est authentifié et a le rôle requis
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
    """Point d'entrée principal avec animations"""
    init_session()
    
    # Vérifie si les tables existent, sinon les crée
    try:
        conn = get_db_connection()
        user_manager = EnhancedUserManager(conn)
        conn.close()
    except Exception as e:
        logger.error(f"Erreur initiale: {str(e)}")
        show_notification(f"Erreur de connexion à la base de données: {str(e)}", "error", "❌")

    check_authentication()

def show_admin_dashboard():
    """Page de tableau de bord pour les utilisateurs non admin"""
    # Configuration de la page
    st.set_page_config(
        page_title="GESTION BANQUE",
        page_icon="assets/logo.png",
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
                    "Date": log['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
                    "Action": log['action'],
                    "Détails": log.get('details', '')
                } for log in logs]))
            else:
                st.info("Aucune activité récente")

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
                options=["Tableau de Bord", "Gestion Clients", "Gestion des Comptes", "Gestion AVI", "Transactions", "Reçus", "Reçus RIB", "Générateur"],
                icons=["speedometer2", "people-fill", "credit-card-2-back-fill", "arrow-left-right", "file-earmark-text", "file-earmark-pdf", "file-earmark-check", "file-earmark-check"],
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
            
            tab1, tab2, tab3  = st.tabs(["📋 Liste des Comptes", "➕ Associer un Compte", "📤 Importer des Comptes"])
            
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
                            options=["XAF", "USD", "EUR"],
                            default=["XAF", "USD", "EUR"]
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
            
                # Dans la section "Associer un Nouveau Compte", modifiez le code comme suit :

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
                    
                    # Affichage et édition des données générées
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
                        
                        # Formulaire d'édition des informations bancaires
                        with st.expander("✏️ Modifier les informations bancaires", expanded=False):
                            cols = st.columns(2)
                            with cols[0]:
                                acc['bank_name'] = st.text_input(
                                    "Banque*",
                                    value=acc['bank_name']
                                )
                                acc['bank_code'] = st.text_input(
                                    "Code Banque*",
                                    value=acc['bank_code'],
                                    max_chars=5
                                )
                                acc['branch_code'] = st.text_input(
                                    "Code Guichet*",
                                    value=acc['branch_code'],
                                    max_chars=5
                                )
                                acc['account_number'] = st.text_input(
                                    "Numéro de compte*",
                                    value=acc['account_number'],
                                    max_chars=11
                                )
                                acc['rib_key'] = st.text_input(
                                    "Clé RIB*",
                                    value=acc['rib_key'],
                                    max_chars=2
                                )
                            
                            with cols[1]:
                                acc['iban'] = st.text_input(
                                    "IBAN*",
                                    value=acc['iban'],
                                    max_chars=27
                                )
                                acc['bic'] = st.text_input(
                                    "BIC/SWIFT*",
                                    value=acc['bic'],
                                    max_chars=11
                                )
                        
                        # Formulaire complémentaire
                        with st.form("account_details_form"):
                            account_type = st.selectbox(
                                "Type de compte*",
                                options=["Courant", "Épargne", "Entreprise"]
                            )
                            
                            currency = st.selectbox(
                                "Devise*",
                                options=["XAF", "USD", "EUR"],
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
                                    
                                    # Validation des données
                                    if not all([full_account_data['bank_code'], full_account_data['branch_code'], 
                                            full_account_data['account_number'], full_account_data['rib_key'],
                                            full_account_data['iban'], full_account_data['bic']]):
                                        st.error("Tous les champs bancaires doivent être remplis")
                                    else:
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
                    
                with tab3:
                    st.subheader("📤 Importer des Comptes depuis Excel")
                    
                    # Création dynamique du modèle Excel
                    def generate_template():
                        output = BytesIO()
                        writer = pd.ExcelWriter(output, engine='xlsxwriter')
                        
                        # Création d'un DataFrame exemple
                        sample_data = {
                            'client_id': [1, 2],
                            'bank_name': ['Ma Banque', 'Autre Banque'],
                            'bank_code': ['12345', '67890'],
                            'branch_code': ['12345', '67890'],
                            'account_number': ['12345678901', '98765432109'],
                            'rib_key': ['12', '34'],
                            'iban': ['FR7612345123451234567890112', 'FR769876543219876543210934'],
                            'bic': ['ABCDEFGH', 'IJKLMNOP'],
                            'type': ['Courant', 'Épargne'],
                            'currency': ['XAF', 'EUR'],
                            'balance': [1000.00, 5000.00],
                            'status': ['ACTIF', 'ACTIF']
                        }
                        df = pd.DataFrame(sample_data)
                        
                        # Écriture dans le fichier Excel
                        df.to_excel(writer, index=False, sheet_name='Comptes')
                        writer.close()
                        return output.getvalue()
                    
                    # Téléchargement du modèle
                    st.markdown("### Télécharger le modèle")
                    st.download_button(
                        label="📥 Télécharger le modèle Excel",
                        data=generate_template(),
                        file_name="modele_import_comptes.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    # Upload du fichier
                    st.markdown("### Importer un fichier Excel")
                    uploaded_file = st.file_uploader(
                        "Choisir un fichier Excel", 
                        type=["xlsx", "xls"],
                        accept_multiple_files=False
                    )
                    
                    if uploaded_file is not None:
                        try:
                            # Lecture du fichier Excel
                            df = pd.read_excel(uploaded_file)
                            
                            # Vérification des colonnes obligatoires
                            required_columns = ['client_id', 'bank_name', 'bank_code', 'branch_code', 
                                            'account_number', 'rib_key', 'iban', 'bic', 
                                            'type', 'currency', 'balance']
                            
                            missing_cols = [col for col in required_columns if col not in df.columns]
                            if missing_cols:
                                st.error(f"Colonnes manquantes dans le fichier: {', '.join(missing_cols)}")
                            else:
                                # Aperçu des données
                                st.markdown("### Aperçu des données à importer")
                                st.dataframe(df.head(3))
                                
                                # Options d'importation
                                with st.expander("Options d'importation", expanded=True):
                                    col1, col2 = st.columns(2)
                                    with col1:
                                        update_existing = st.checkbox(
                                            "Mettre à jour les comptes existants",
                                            value=False,
                                            help="Si coché, les comptes existants avec le même IBAN seront mis à jour"
                                        )
                                    with col2:
                                        skip_errors = st.checkbox(
                                            "Ignorer les erreurs",
                                            value=True,
                                            help="Si coché, les lignes avec erreurs seront ignorées"
                                        )
                                
                                # Bouton d'importation
                                if st.button("⚡ Importer les comptes", type="primary"):
                                    progress_bar = st.progress(0)
                                    status_text = st.empty()
                                    imported_count = 0
                                    updated_count = 0
                                    error_count = 0
                                    
                                    for i, row in df.iterrows():
                                        try:
                                            # Préparation des données
                                            account_data = {
                                                "client_id": int(row['client_id']),
                                                "bank_name": str(row['bank_name']),
                                                "bank_code": str(row['bank_code']),
                                                "branch_code": str(row['branch_code']),
                                                "account_number": str(row['account_number']),
                                                "rib_key": str(row['rib_key']),
                                                "iban": str(row['iban']).replace(" ", "").upper(),
                                                "bic": str(row['bic']).upper(),
                                                "type": str(row['type']),
                                                "currency": str(row['currency']),
                                                "balance": float(row['balance']),
                                                "status": str(row.get('status', 'ACTIF')),
                                                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                            }
                                            
                                            # Vérification de l'existence du compte
                                            existing_account = db.get_account_by_iban(account_data['iban'])
                                            
                                            if existing_account:
                                                if update_existing:
                                                    db.update_account(existing_account['id'], account_data)
                                                    updated_count += 1
                                                else:
                                                    st.warning(f"Le compte avec IBAN {account_data['iban']} existe déjà (ignoré)")
                                                    error_count += 1
                                                    continue
                                            else:
                                                db.add_account(account_data)
                                                imported_count += 1
                                            
                                            progress_bar.progress((i + 1) / len(df))
                                            status_text.text(f"Import en cours... {i + 1}/{len(df)} lignes traitées")
                                            
                                        except Exception as e:
                                            error_count += 1
                                            if not skip_errors:
                                                st.error(f"Erreur ligne {i + 2}: {str(e)}")
                                                break
                                            continue
                                    
                                    # Résumé de l'import
                                    st.success(f"""Import terminé!
                                    - {imported_count} nouveaux comptes
                                    - {updated_count} comptes mis à jour
                                    - {error_count} erreurs""")
                                    
                                    # Rafraîchir l'affichage
                                    st.rerun()
                                    
                        except Exception as e:
                            st.error(f"Erreur lors de la lecture du fichier: {str(e)}")
       

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
                    # Convertir les dates en strings pour le formatage
                    df = pd.DataFrame(transactions)
                    df['date_str'] = df['date'].dt.strftime('%Y-%m-%d %H:%M')  # Conversion datetime -> string
                    
                    # Utiliser la colonne convertie pour l'affichage
                    selected_transaction = st.selectbox(
                        "Sélectionner une transaction",
                        options=df.to_dict('records'),
                        format_func=lambda t: f"#{t['id']} • {t['type']} • {t['amount']:.2f}XAF • {t['date_str']} • {t.get('description', '')[:30]}"
                    )
                    
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
                    transactions = db.get_all_transactions()
                    transactions_count = len(transactions) if transactions else 0
                    st.metric("💸 Transactions éligibles", transactions_count)
            
            if not transactions:
                st.warning("Aucune transaction disponible pour générer un reçu.")
                st.stop()
            
            # Conversion des dates en format string pour l'affichage
            df_transactions = pd.DataFrame(transactions)
            df_transactions['date_str'] = df_transactions['date'].dt.strftime('%Y-%m-%d %H:%M')
            
            # Barre de recherche améliorée
            search_cols = st.columns([4, 1])
            with search_cols[0]:
                search_query = st.text_input("🔍 Rechercher une transaction", "", 
                                        placeholder="ID, montant, type...")
            with search_cols[1]:
                transaction_type_filter = st.selectbox("Filtrer", ["Tous"] + list(set(t['type'] for t in transactions)))
            
            # Filtrage des transactions
            filtered_transactions = df_transactions.to_dict('records')
            if search_query:
                filtered_transactions = [t for t in filtered_transactions if search_query.lower() in str(t).lower()]
            if transaction_type_filter != "Tous":
                filtered_transactions = [t for t in filtered_transactions if t['type'] == transaction_type_filter]
            
            if not filtered_transactions:
                st.warning("Aucune transaction ne correspond aux critères de recherche.")
                st.stop()
            
            # Sélecteur de transaction amélioré
            selected_transaction = st.selectbox(
                "Choisir une transaction à documenter",
                options=filtered_transactions,
                format_func=lambda t: f"#{t['id']} • {t['type']} • {t['amount']:.2f}XAF • {t['date_str']} • {t.get('description', '')[:30]}{'...' if len(t.get('description', '')) > 30 else ''}",
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
                    st.write(f"**📅 Date:** {transaction_data['date_str']}")  # Utilisation de la version string
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
                    try:
                        # Sauvegarde temporaire du logo
                        logo_path = None
                        if company_logo:
                            logo_path = f"temp_logo_{transaction_data['id']}.png"
                            with open(logo_path, "wb") as f:
                                f.write(company_logo.getbuffer())
                        
                        # Gestion robuste des différents formats de date
                        date_value = transaction_data['date']
                        
                        if isinstance(date_value, pd.Timestamp):
                            formatted_date = date_value.strftime('%d/%m/%Y %H:%M')
                        elif isinstance(date_value, datetime.datetime):
                            formatted_date = date_value.strftime('%d/%m/%Y %H:%M')
                        elif isinstance(date_value, str):
                            try:
                                # Essayer de parser si c'est une string
                                parsed_date = datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                                formatted_date = parsed_date.strftime('%d/%m/%Y %H:%M')
                            except ValueError:
                                # Si le parsing échoue, utiliser la valeur directement
                                formatted_date = date_value
                        else:
                            formatted_date = "Date non disponible"
                        
                        # Création d'une copie des données avec la date formatée
                        receipt_data = {
                            **transaction_data,
                            'date_str': formatted_date,
                            'formatted_amount': f"{transaction_data['amount']:,.2f} XAF"
                        }
                        
                        # Génération du PDF
                        pdf_path = generate_receipt_pdf(
                            transaction_data=receipt_data,
                            client_data=client_data,
                            iban_data=iban_data,
                            company_name=company_name,
                            logo_path=logo_path,
                            receipt_title=receipt_title,
                            additional_notes=additional_notes,
                            include_signature=include_signature,
                            include_qr=include_qr
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
                                        <p><strong>Montant:</strong> {receipt_data['formatted_amount']}</p>
                                        <p><strong>Date:</strong> {formatted_date}</p>
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
                    
                    except Exception as e:
                        st.error(f"Erreur lors de la génération du reçu: {str(e)}")
                        if logo_path and os.path.exists(logo_path):
                            os.remove(logo_path)

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
                avis = db.get_all_avis()
                
                if avi_data:
                    selected_avi = st.selectbox(
                        "Choisir une attestation à générer",
                        options=[f"{a['reference']} - {a['nom_complet']}" for a in avis],
                        index=0
                    )
                    
                    reference = selected_avi.split(" - ")[0]
                    avi_data = db.get_avi_by_reference(reference)
                    
                    if st.button("Générer l'Attestation PDF", type="primary"):
                        with st.spinner("Génération en cours..."):
                            try:                          
                                # Création du PDF
                                pdf = FPDF()
                                pdf.add_page()

                                def montant_en_lettres(montant):
                                    """Convertit un montant numérique en lettres françaises avec devise"""
                                    from num2words import num2words
                                    
                                    partie_entiere = int(montant)
                                    partie_decimale = int(round((montant - partie_entiere) * 100))
                                    
                                    texte = num2words(partie_entiere, lang='fr')
                                    
                                    # Ajout de la devise
                                    if partie_entiere > 1:
                                        texte += " francs CFA"
                                    else:
                                        texte += " franc CFA"
                                    
                                    # Gestion des décimales si nécessaire
                                    if partie_decimale > 0:
                                        texte += " et " + num2words(partie_decimale, lang='fr') + " centimes"
                                    
                                    return texte.capitalize()
                                
                                # ---- Ajout des logos floutés en arrière-plan ----
                                try:
                                    logo_path = "assets/logo.png"
                                    img = Image.open(logo_path)
                                    
                                    # Créer une version avec opacité réduite
                                    if img.mode != 'RGBA':
                                        img = img.convert('RGBA')
                                    
                                    data = img.getdata()
                                    new_data = []
                                    for item in data:
                                        new_data.append((item[0], item[1], item[2], int(item[3] * 0.2)))  # 30% opacity
                                    img.putdata(new_data)
                                    
                                    # Convertir en format utilisable par FPDF
                                    temp_logo = BytesIO()
                                    img.save(temp_logo, format='PNG')
                                    temp_logo.seek(0)
                                    
                                    for position in [(30, 30), (120, 200), (50, 300), (100, 100)]:
                                        pdf.image(temp_logo, x=position[0], y=position[1], w=100)
                                        
                                except Exception as e:
                                    st.warning(f"Logo non trouvé ou erreur de traitement: {str(e)}")
                                
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
                                pdf.cell(45, 5, "NUMERO COMPTE : ", 0, 0)
                                pdf.set_font('Arial', '', 12)
                                pdf.cell(0, 5, avi_data['numero_compte'], 0, 1)
                                
                                pdf.set_font('Arial', 'B', 12)
                                pdf.cell(20, 5, "Devise :", 0, 0)
                                pdf.set_font('Arial', '', 12)
                                pdf.cell(0, 5, avi_data['devise'], 0, 1)
                                pdf.ln(5)
                                
                                # ---- Détails du virement ----
                                details = [
                                    f"Il est l'ordonnateur d'un virement irrévocable et permanent d'un montant total de {avi_data['montant']:,.2f} FCFA",
                                    f"({montant_en_lettres(avi_data['montant'])}), équivalant actuellement à {avi_data['montant']/650:,.2f} euros,",
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
                                pdf.cell(16, 5, "IBAN :", 0, 0)
                                pdf.set_font('Arial', '', 12)
                                pdf.cell(0, 5, avi_data['iban'], 0, 1)
                                
                                pdf.set_font('Arial', 'B', 12)
                                pdf.cell(16, 5, "BIC :", 0, 0)
                                pdf.set_font('Arial', '', 12)
                                pdf.cell(0, 5, avi_data['bic'], 0, 1)
                                pdf.ln(10)
                                
                                # ---- Clause de validation ----
                                pdf.cell(0, 5, "En foi de quoi, cette attestation lui est délivrée pour servir et valoir ce que de droit.", 0, 1)
                                pdf.ln(10)
                                
                                # ---- Date et signature ----
                                pdf.cell(0, 5, f"Fait à Brazzaville, le {datetime.now().strftime('%d %B %Y')}", 0, 1, 'R')
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
                                    pdf.cell(1, 4.5, line, 0, 2, 'L')
                                
                                # ---- QR Code ----
                                qr_data = {
                                    "Référence": avi_data['reference'],
                                    "Nom": avi_data['nom_complet'],
                                    "Code Banque": avi_data['code_banque'],
                                    "Numéro Compte": avi_data['numero_compte'],
                                    #"IBAN": avi_data['iban'],
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
                                
                                pdf.image(img_bytes, x=150, y=pdf.get_y()-40, w=40)
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

                                def show_pdf(file_path):
                                    try:
                                        with st.spinner("Chargement du document..."):
                                            with open(file_path, "rb") as f:
                                                base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                                            
                                            container = st.container(border=True)
                                            with container:
                                                st.markdown(f"""
                                                <div style="height: 600px; overflow: auto;">
                                                    <object 
                                                        data="data:application/pdf;base64,{base64_pdf}"
                                                        type="application/pdf"
                                                        width="100%" 
                                                        height="100%"
                                                        style="border: none;"
                                                    >
                                                        <p>Votre navigateur ne supporte pas l'affichage direct de PDF. 
                                                        <a href="data:application/pdf;base64,{base64_pdf}" download="document.pdf">Télécharger le PDF</a></p>
                                                    </object>
                                                </div>
                                                """, unsafe_allow_html=True)
                                    except Exception as e:
                                        st.error(f"Erreur lors du chargement du PDF: {str(e)}")
                                        st.error("Solution alternative :")
                                        with open(file_path, "rb") as f:
                                            st.download_button(
                                                "⬇️ Télécharger le document PDF",
                                                data=f,
                                                file_name="document.pdf",
                                                mime="application/pdf"
                                            )
                                
                                show_pdf(output_path)
                                
                            except Exception as e:
                                st.error(f"❌ Erreur lors de la génération: {str(e)}")
                                st.exception(e)
                        
            # Fonctions utilitaires (à mettre AVANT le with tab5)
            def extract_between(text, start, end):
                """Extrait le texte entre deux chaînes"""
                start_idx = text.find(start)
                if start_idx == -1: return None
                start_idx += len(start)
                end_idx = text.find(end, start_idx)
                return text[start_idx:end_idx].strip() if end_idx != -1 else None

            def extract_regex(text, pattern):
                """Extrait avec une expression régulière"""
                match = re.search(pattern, text)
                return match.group(1).strip() if match else None

            def generate_qr_code(data, fill_color="#000000", back_color="#FFFFFF", size=100):
                """Génère un QR code"""
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=4,
                )
                qr.add_data(data)
                qr.make(fit=True)
                return qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGB')

            def add_qr_to_pdf(pdf_file, qr_img, position="Bas droite"):
                """Ajoute un QR code au PDF original"""
                temp_qr = BytesIO()
                qr_img.save(temp_qr, format="PNG")
                temp_qr.seek(0)
                
                # Lire le PDF original
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                pdf_writer = PyPDF2.PdfWriter()
                
                # Créer un calque avec le QR code
                packet = BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)
                
                # Positions ajustées pour ne pas dépasser des marges
                pos_map = {
                    "Bas droite": (450, 60),
                    "Bas gauche": (30, 30),
                    "Haut droite": (letter[0] - 120, letter[1] - 120),
                    "Haut gauche": (30, letter[1] - 120),
                    "Centre": ((letter[0] - 100)/2, (letter[1] - 100)/2)
                }
                
                x, y = pos_map.get(position, pos_map["Bas droite"])
                
                # Dessiner le QR code sur le calque
                can.drawImage(ImageReader(temp_qr), x, y, width=100, height=100, mask='auto')
                can.save()
                
                # Fusionner le calque avec chaque page du PDF original
                packet.seek(0)
                qr_pdf = PyPDF2.PdfReader(packet)
                
                for page in pdf_reader.pages:
                    # Créer une nouvelle page avec le contenu original
                    new_page = page
                    
                    # Fusionner avec le calque QR code
                    new_page.merge_page(qr_pdf.pages[0])
                    pdf_writer.add_page(new_page)
                
                # Sauvegarder le résultat
                output = BytesIO()
                pdf_writer.write(output)
                output.seek(0)
                return output

            def show_pdf(file):
                """Affiche un PDF dans l'interface"""
                if hasattr(file, 'read'):
                    file.seek(0)
                    pdf_bytes = file.read()
                else:
                    with open(file, "rb") as f:
                        pdf_bytes = f.read()
                
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                
                pdf_display = f"""
                <div style="height: 600px; overflow: auto; margin: 1rem 0; border: 1px solid #ddd; border-radius: 8px;">
                    <embed
                        src="data:application/pdf;base64,{base64_pdf}"
                        type="application/pdf"
                        width="100%"
                        height="100%"
                        style="border: none;"
                    >
                </div>
                """
                st.markdown(pdf_display, unsafe_allow_html=True)

            def convert_word_to_pdf(word_file):
                """Convertit un fichier Word en PDF"""
                try:
                    # Lire le fichier Word
                    doc = Document(word_file)
                    
                    # Créer un fichier PDF temporaire
                    temp_pdf = BytesIO()
                    
                    # Convertir en PDF
                    doc.save(temp_pdf)
                    temp_pdf.seek(0)
                    
                    return temp_pdf
                except Exception as e:
                    st.error(f"Erreur lors de la conversion Word en PDF: {str(e)}")
                    return None

            # Maintenant le code de l'onglet
            with tab5:
                st.subheader("📤 Importer Word/PDF et Ajouter QR Code")
                
                uploaded_file = st.file_uploader("Choisir un fichier Word ou PDF", type=["docx", "pdf"], key="file_uploader")
                
                if uploaded_file is not None:
                    try:
                        # Convertir en PDF si c'est un fichier Word
                        if uploaded_file.name.endswith('.docx'):
                            with st.spinner("Conversion du Word en PDF..."):
                                pdf_file = convert_word_to_pdf(uploaded_file)
                                if pdf_file is None:
                                    st.error("Échec de la conversion Word en PDF")
                                    st.stop()
                        else:
                            pdf_file = uploaded_file
                        
                        # Extraire le texte du PDF
                        with st.spinner("Analyse du PDF en cours..."):
                            pdf_text = ""
                            with pdfplumber.open(pdf_file) as pdf:
                                for page in pdf.pages:
                                    pdf_text += page.extract_text() + "\n"

                            extracted_data = {
                                'nom': extract_between(pdf_text, "Nous certifions par la présente que", "détient un compte"),
                                'code_banque': extract_regex(pdf_text, r"CODE BANQUE : (\d+)"),
                                'numero_compte': extract_regex(pdf_text, r"NUMERO DE COMPTE : ([^\n]+)"),
                                'devise': extract_regex(pdf_text, r"Devise : ([^\n]+)"),
                                'iban': extract_regex(pdf_text, r"IBAN: ([^\n]+)"),
                                'bic': extract_regex(pdf_text, r"BIC: ([^\n]+)"),
                                'montant': extract_regex(pdf_text, r"montant total de ([^\n]+ FCFA)")
                            }

                        with st.expander("🔍 Données extraites", expanded=True):
                            st.json({k: v for k, v in extracted_data.items() if v})

                        qr_content = "\n".join([f"{k}: {v}" for k, v in extracted_data.items() if v])
                        
                        # Variables pour stocker le résultat
                        if 'modified_pdf' not in st.session_state:
                            st.session_state.modified_pdf = None
                        
                        with st.form("qr_settings"):
                            st.subheader("⚙️ Paramètres du QR Code")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                qr_position = st.selectbox("Position", ["Bas droite", "Bas gauche", "Haut droite", "Haut gauche"], index=0)
                                qr_size = st.slider("Taille (px)", 50, 150, 80)
                            
                            with col2:
                                qr_color = st.color_picker("Couleur", "#000000")
                                bg_color = st.color_picker("Fond", "#FFFFFF")
                            
                            # Modifiez la partie génération du QR code dans votre onglet tab5 comme suit :
                            if st.form_submit_button("🔄 Générer le PDF avec QR Code"):
                                with st.spinner("Création du nouveau PDF..."):
                                    try:
                                        # Vérification et préparation des données pour le QR code
                                        if not qr_content:
                                            st.warning("Aucune donnée extraite - Utilisation des informations basiques")
                                            qr_content = f"Document: {uploaded_file.name}\nDate: {datetime.now().strftime('%Y-%m-%d')}"
                                        else:
                                            # Formatage avancé des données
                                            qr_content = "=== INFORMATIONS DOCUMENT ===\n" + qr_content
                                        
                                        # Debug: afficher le contenu qui sera encodé
                                        st.session_state.qr_debug_content = qr_content
                                        st.write(f"Données à encoder dans le QR code ({(len(qr_content))} caractères):")
                                        st.code(qr_content[:200] + ("..." if len(qr_content) > 200 else ""))
                                        
                                        # Génération robuste du QR code
                                        qr = qrcode.QRCode(
                                            version=None,  # Auto-détection de la version
                                            error_correction=qrcode.constants.ERROR_CORRECT_H,
                                            box_size=8,  # Meilleure résolution
                                            border=2,
                                        )
                                        
                                        # Encodage des données
                                        qr.add_data(qr_content)
                                        qr.make(fit=True)
                                        
                                        # Création de l'image avec vérification
                                        qr_img = qr.make_image(fill_color=qr_color, back_color=bg_color).convert('RGB')
                                        
                                        # Vérification visuelle immédiate
                                        with st.expander("Aperçu du QR Code", expanded=True):
                                            st.image(qr_img, caption="QR Code généré", width=200)
                                        
                                        # Insertion dans le PDF
                                        output_pdf = add_qr_to_pdf(pdf_file, qr_img, position=qr_position)
                                        st.session_state.modified_pdf = output_pdf
                                        st.success("✅ PDF généré avec succès!")
                                        
                                    except Exception as e:
                                        st.error(f"❌ Erreur lors de la génération: {str(e)}")
                                        # Création d'un QR code d'erreur comme fallback
                                        error_qr = qrcode.make(f"ERREUR: {str(e)}")
                                        st.session_state.modified_pdf = add_qr_to_pdf(pdf_file, error_qr, position=qr_position)
                        
                        # Section de téléchargement et prévisualisation (HORS DU FORMULAIRE)
                        if st.session_state.modified_pdf:
                            col1, col2 = st.columns(2)
                            with col1:
                                # Bouton de téléchargement
                                st.download_button(
                                    "💾 Télécharger",
                                    data=st.session_state.modified_pdf,
                                    file_name="document_avec_qr.pdf",
                                    mime="application/pdf"
                                )
                            
                            with col2:
                                if st.button("👁️ Aperçu"):
                                    show_pdf(st.session_state.modified_pdf)
                            
                            # Affichage automatique
                            st.subheader("📄 Aperçu du document final")
                            show_pdf(st.session_state.modified_pdf)
                        
                        # Aperçu du document original
                        st.subheader("📄 Aperçu du document original")
                        show_pdf(pdf_file)

                    except Exception as e:
                        st.error(f"Erreur lors du traitement: {str(e)}")

        elif selected == "Générateur":
            st.title("📑 Générateur QR")
            
            # Correction: Utiliser st.tabs() correctement et créer un seul onglet
            tab1, = st.tabs(["📤 Importer PDF"])  # Notez la virgule après tab1 pour unpack le tuple
            
            # Fonctions utilitaires
            def extract_between_1(text, start, end):
                """Extrait le texte entre deux chaînes"""
                start_idx = text.find(start)
                if start_idx == -1: return None
                start_idx += len(start)
                end_idx = text.find(end, start_idx)
                return text[start_idx:end_idx].strip() if end_idx != -1 else None

            def extract_regex_1(text, pattern):
                """Extrait avec une expression régulière"""
                match = re.search(pattern, text)
                return match.group(1).strip() if match else None

            def generate_qr_code_1(data, fill_color="#000000", back_color="#FFFFFF", size=100):
                """Génère un QR code"""
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=4,
                )
                qr.add_data(data)
                qr.make(fit=True)
                return qr.make_image(fill_color=fill_color, back_color=back_color).convert('RGB')

            def add_qr_to_pdf_1(pdf_file, qr_img, position="Bas droite"):
                """Ajoute un QR code au PDF original"""
                temp_qr = BytesIO()
                qr_img.save(temp_qr, format="PNG")
                temp_qr.seek(0)
                
                # Lire le PDF original
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                pdf_writer = PyPDF2.PdfWriter()
                
                # Créer un calque avec le QR code
                packet = BytesIO()
                can = canvas.Canvas(packet, pagesize=letter)
                
                # Positions ajustées pour ne pas dépasser des marges
                pos_map = {
                    "Bas droite": (450, 60),
                    "Bas gauche": (30, 30),
                    "Haut droite": (500, (letter[1])/2),
                    "Haut gauche": (30, letter[1] - 120),
                    "Centre": ((letter[0] - 100)/2, (letter[1] - 100)/2)
                }
                
                x, y = pos_map.get(position, pos_map["Haut droite"])
                
                # Dessiner le QR code sur le calque
                can.drawImage(ImageReader(temp_qr), x, y, width=100, height=100, mask='auto')
                can.save()
                
                # Fusionner le calque avec chaque page du PDF original
                packet.seek(0)
                qr_pdf = PyPDF2.PdfReader(packet)
                
                for page in pdf_reader.pages:
                    # Créer une nouvelle page avec le contenu original
                    new_page = page
                    
                    # Fusionner avec le calque QR code
                    new_page.merge_page(qr_pdf.pages[0])
                    pdf_writer.add_page(new_page)
                
                # Sauvegarder le résultat
                output = BytesIO()
                pdf_writer.write(output)
                output.seek(0)
                return output

            def show_pdf_1(file):
                """Affiche un PDF dans l'interface"""
                if hasattr(file, 'read'):
                    file.seek(0)
                    pdf_bytes = file.read()
                else:
                    with open(file, "rb") as f:
                        pdf_bytes = f.read()
                
                base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                
                pdf_display = f"""
                <div style="height: 600px; overflow: auto; margin: 1rem 0; border: 1px solid #ddd; border-radius: 8px;">
                    <embed
                        src="data:application/pdf;base64,{base64_pdf}"
                        type="application/pdf"
                        width="100%"
                        height="100%"
                        style="border: none;"
                    >
                </div>
                """
                st.markdown(pdf_display, unsafe_allow_html=True)

            def convert_word_to_pdf_1(word_file):
                """Convertit un fichier Word en PDF"""
                try:
                    # Lire le fichier Word
                    doc = Document(word_file)
                    
                    # Créer un fichier PDF temporaire
                    temp_pdf = BytesIO()
                    
                    # Convertir en PDF
                    doc.save(temp_pdf)
                    temp_pdf.seek(0)
                    
                    return temp_pdf
                except Exception as e:
                    st.error(f"Erreur lors de la conversion Word en PDF: {str(e)}")
                    return None

            # Maintenant le code de l'onglet
            with tab1:  # Maintenant cela fonctionne car tab1 est un seul onglet
                st.subheader("📤 Importer Word/PDF et Ajouter QR Code")
                
                uploaded_file = st.file_uploader("Choisir un fichier Word ou PDF", type=["docx", "pdf"], key="file_uploader")
                
                if uploaded_file is not None:
                    try:
                        # Convertir en PDF si c'est un fichier Word
                        if uploaded_file.name.endswith('.docx'):
                            with st.spinner("Conversion du Word en PDF..."):
                                pdf_file = convert_word_to_pdf_1(uploaded_file)
                                if pdf_file is None:
                                    st.error("Échec de la conversion Word en PDF")
                                    st.stop()
                        else:
                            pdf_file = uploaded_file
                        
                        # Extraire le texte du PDF
                        with st.spinner("Analyse du PDF en cours..."):
                            pdf_text = ""
                            with pdfplumber.open(pdf_file) as pdf:
                                for page in pdf.pages:
                                    pdf_text += page.extract_text() + "\n"

                            extracted_data = {
                                'Client': extract_regex_1(pdf_text, r"Client : ([^\n]+)"),
                                'Période': extract_regex_1(pdf_text, r"Période : (\d+)"),
                                'Compte N°': extract_regex_1(pdf_text, r"Compte N° : ([^\n]+)"),
                                'devise': extract_regex_1(pdf_text, r"Devise : ([^\n]+)"),
                                'Type de Compte': extract_regex_1(pdf_text, r"Type de Compte : ([^\n]+)"),
                                'Bénéficiaire': extract_regex_1(pdf_text, r"Bénéficiaire : ([^\n]+)"),
                                'montant': extract_regex_1(pdf_text, r"Montant : ([^\n]+)")
                            }

                        with st.expander("🔍 Données extraites", expanded=True):
                            st.json({k: v for k, v in extracted_data.items() if v})

                        qr_content = "\n".join([f"{k}: {v}" for k, v in extracted_data.items() if v])
                        
                        # Variables pour stocker le résultat
                        if 'modified_pdf' not in st.session_state:
                            st.session_state.modified_pdf = None
                        
                        with st.form("qr_settings"):
                            st.subheader("⚙️ Paramètres du QR Code")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                qr_position = st.selectbox("Position", ["Bas droite", "Bas gauche", "Haut droite", "Haut gauche"], index=0)
                                qr_size = st.slider("Taille (px)", 50, 150, 80)
                            
                            with col2:
                                qr_color = st.color_picker("Couleur", "#000000")
                                bg_color = st.color_picker("Fond", "#FFFFFF")
                            
                            # Modifiez la partie génération du QR code dans votre onglet tab5 comme suit :
                            if st.form_submit_button("🔄 Générer le PDF avec QR Code"):
                                with st.spinner("Création du nouveau PDF..."):
                                    try:
                                        # Vérification et préparation des données pour le QR code
                                        if not qr_content:
                                            st.warning("Aucune donnée extraite - Utilisation des informations basiques")
                                            qr_content = f"Document: {uploaded_file.name}\nDate: {datetime.now().strftime('%Y-%m-%d')}"
                                        else:
                                            # Formatage avancé des données
                                            qr_content = "=== INFORMATIONS DOCUMENT ===\n" + qr_content
                                        
                                        # Debug: afficher le contenu qui sera encodé
                                        st.session_state.qr_debug_content = qr_content
                                        st.write(f"Données à encoder dans le QR code ({(len(qr_content))} caractères):")
                                        st.code(qr_content[:200] + ("..." if len(qr_content) > 200 else ""))
                                        
                                        # Génération robuste du QR code
                                        qr = qrcode.QRCode(
                                            version=None,  # Auto-détection de la version
                                            error_correction=qrcode.constants.ERROR_CORRECT_H,
                                            box_size=8,  # Meilleure résolution
                                            border=2,
                                        )
                                        
                                        # Encodage des données
                                        qr.add_data(qr_content)
                                        qr.make(fit=True)
                                        
                                        # Création de l'image avec vérification
                                        qr_img = qr.make_image(fill_color=qr_color, back_color=bg_color).convert('RGB')
                                        
                                        # Vérification visuelle immédiate
                                        with st.expander("Aperçu du QR Code", expanded=True):
                                            st.image(qr_img, caption="QR Code généré", width=200)
                                        
                                        # Insertion dans le PDF
                                        output_pdf = add_qr_to_pdf_1(pdf_file, qr_img, position=qr_position)
                                        st.session_state.modified_pdf = output_pdf
                                        st.success("✅ PDF généré avec succès!")
                                        
                                    except Exception as e:
                                        st.error(f"❌ Erreur lors de la génération: {str(e)}")
                                        # Création d'un QR code d'erreur comme fallback
                                        error_qr = qrcode.make(f"ERREUR: {str(e)}")
                                        st.session_state.modified_pdf = add_qr_to_pdf_1(pdf_file, error_qr, position=qr_position)
                        
                        # Section de téléchargement et prévisualisation (HORS DU FORMULAIRE)
                        if st.session_state.modified_pdf:
                            col1, col2 = st.columns(2)
                            with col1:
                                # Bouton de téléchargement
                                st.download_button(
                                    "💾 Télécharger",
                                    data=st.session_state.modified_pdf,
                                    file_name="document_avec_qr.pdf",
                                    mime="application/pdf"
                                )
                            
                            with col2:
                                if st.button("👁️ Aperçu"):
                                    show_pdf_1(st.session_state.modified_pdf)
                            
                            # Affichage automatique
                            st.subheader("📄 Aperçu du document final")
                            show_pdf_1(st.session_state.modified_pdf)
                        
                        # Aperçu du document original
                        st.subheader("📄 Aperçu du document original")
                        show_pdf_1(pdf_file)

                    except Exception as e:
                        st.error(f"Erreur lors du traitement: {str(e)}")
            
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()