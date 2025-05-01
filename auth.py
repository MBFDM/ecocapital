import streamlit as st
import hashlib
import logging
from typing import Optional, Dict
from database import BankDatabase, UserManager, DatabaseError, IntegrityError

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AuthError(Exception):
    """Exception personnalisée pour les erreurs d'authentification"""
    pass

def hash_password(password: str) -> str:
    """
    Hash un mot de passe avec SHA-256
    Args:
        password: Mot de passe en clair
    Returns:
        str: Mot de passe hashé
    """
    if not password:
        raise ValueError("Le mot de passe ne peut pas être vide")
    return hashlib.sha256(password.encode()).hexdigest()

def init_db_connection() -> BankDatabase:
    """
    Initialise et retourne une connexion à la base de données
    Returns:
        BankDatabase: Instance de la base de données
    Raises:
        AuthError: Si la connexion échoue
    """
    try:
        db = BankDatabase()
        if not db.conn:
            logger.error("Échec de la connexion à la base de données")
            raise AuthError("Échec de la connexion à la base de données")
        return db
    except DatabaseError as e:
        logger.error(f"Erreur de connexion à la base de données: {str(e)}")
        raise AuthError("Erreur de connexion à la base de données") from e
    except Exception as e:
        logger.error(f"Erreur inattendue lors de la connexion à la base: {str(e)}")
        raise AuthError("Erreur technique") from e

def validate_credentials(username: str, password: str) -> None:
    """
    Valide les identifiants de connexion
    Args:
        username: Nom d'utilisateur
        password: Mot de passe
    Raises:
        ValueError: Si les identifiants sont invalides
    """
    if not username or not password:
        raise ValueError("Le nom d'utilisateur et le mot de passe sont requis")
    if len(username) < 3:
        raise ValueError("Le nom d'utilisateur doit faire au moins 3 caractères")
    if len(password) < 8:
        raise ValueError("Le mot de passe doit faire au moins 8 caractères")

def validate_signup_data(username: str, email: str, password: str, confirm_password: str) -> None:
    """
    Valide les données d'inscription
    Args:
        username: Nom d'utilisateur
        email: Email
        password: Mot de passe
        confirm_password: Confirmation du mot de passe
    Raises:
        ValueError: Si les données sont invalides
    """
    validate_credentials(username, password)
    
    if not email or '@' not in email:
        raise ValueError("Veuillez entrer une adresse email valide")
    if password != confirm_password:
        raise ValueError("Les mots de passe ne correspondent pas")

def show_login_form() -> None:
    """
    Affiche le formulaire de connexion et gère la logique d'authentification
    """
    with st.form("Login", clear_on_submit=True):
        st.subheader("Connexion")
        username = st.text_input("Nom d'utilisateur", key="login_username")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        submit_button = st.form_submit_button("Se connecter")

        if submit_button:
            try:
                validate_credentials(username, password)
                
                db = init_db_connection()
                try:
                    user_manager = UserManager(db.conn)
                    hashed_password = hash_password(password)
                    user = user_manager.verify_user(username, hashed_password)
                    
                    if user:
                        st.session_state.update({
                            'authenticated': True,
                            'user': user,
                            'username': user['username'],
                            'role': user.get('role', 'user')
                        })
                        st.success("Connexion réussie!")
                        logger.info(f"Utilisateur {username} connecté avec succès")
                        st.rerun()
                    else:
                        logger.warning(f"Tentative de connexion échouée pour {username}")
                        st.error("Nom d'utilisateur ou mot de passe incorrect")
                finally:
                    db.close()
                    
            except ValueError as e:
                st.error(str(e))
            except AuthError as e:
                st.error(str(e))
            except Exception as e:
                logger.error(f"Erreur inattendue lors de la connexion: {str(e)}")
                st.error("Une erreur technique est survenue")

def show_signup_form() -> None:
    """
    Affiche le formulaire d'inscription et gère la création de compte
    """
    with st.form("Signup", clear_on_submit=True):
        st.subheader("Créer un compte")
        username = st.text_input("Choisissez un nom d'utilisateur", key="signup_username")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Choisissez un mot de passe", type="password", key="signup_password")
        confirm_password = st.text_input("Confirmez le mot de passe", type="password", key="signup_confirm_password")
        submit_button = st.form_submit_button("S'inscrire")

        if submit_button:
            try:
                validate_signup_data(username, email, password, confirm_password)
                
                db = init_db_connection()
                try:
                    user_manager = UserManager(db.conn)
                    hashed_password = hash_password(password)
                    
                    # Vérifie si l'utilisateur existe déjà
                    if user_manager.get_user_by_username(username):
                        raise IntegrityError("Ce nom d'utilisateur est déjà pris")
                    
                    # Crée le nouvel utilisateur
                    user_id = user_manager.add_user(username, email, hashed_password)
                    
                    if user_id:
                        st.success("Compte créé avec succès! Vous pouvez maintenant vous connecter.")
                        logger.info(f"Nouvel utilisateur créé: {username}")
                    else:
                        raise AuthError("Erreur lors de la création du compte")
                finally:
                    db.close()
                    
            except ValueError as e:
                st.error(str(e))
            except IntegrityError as e:
                st.error(str(e))
            except AuthError as e:
                st.error(str(e))
            except Exception as e:
                logger.error(f"Erreur inattendue lors de l'inscription: {str(e)}")
                st.error("Une erreur technique est survenue")

def show_auth_page() -> None:
    """
    Affiche la page d'authentification avec onglets Connexion/Inscription
    """
    st.title("Authentification")
    tab1, tab2 = st.tabs(["Connexion", "Inscription"])
    
    with tab1:
        show_login_form()
    
    with tab2:
        show_signup_form()

def check_authentication(required_role: str = None) -> None:
    """
    Vérifie si l'utilisateur est authentifié et a le rôle requis
    Args:
        required_role: Rôle requis pour accéder à la page (optionnel)
    """
    # Initialise l'état de session si nécessaire
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    
    # Redirige vers la page d'authentification si non connecté
    if not st.session_state['authenticated']:
        show_auth_page()
        st.stop()
    
    # Vérifie les autorisations si un rôle est requis
    if required_role and st.session_state.get('role') != required_role:
        st.error("Vous n'avez pas les permissions nécessaires pour accéder à cette page")
        logger.warning(
            f"Tentative d'accès non autorisé par {st.session_state['username']} "
            f"(requiert: {required_role})"
        )
        st.stop()

def logout() -> None:
    """
    Déconnecte l'utilisateur et nettoie la session
    """
    username = st.session_state.get('username', 'Inconnu')
    st.session_state.clear()
    logger.info(f"Utilisateur {username} déconnecté")
    st.rerun()

def main() -> None:
    """
    Point d'entrée principal de l'application
    """
    try:
        # Configuration de la page
        st.set_page_config(
            page_title="Tableau de bord bancaire",
            page_icon="🏦",
            layout="wide"
        )
        
        # Vérifie l'authentification
        check_authentication()
        
        # Affiche l'interface principale
        st.title("Tableau de bord bancaire")
        
        # Barre latérale avec infos utilisateur
        with st.sidebar:
            st.write(f"Connecté en tant que **{st.session_state['username']}**")
            if st.button("Déconnexion"):
                logout()
        
        # Contenu principal
        st.write(f"Bienvenue, {st.session_state['user']['username']}!")
        
    except Exception as e:
        logger.error(f"Erreur critique dans l'application: {str(e)}")
        st.error("Une erreur critique est survenue. Veuillez réessayer plus tard.")

if __name__ == "__main__":
    main()