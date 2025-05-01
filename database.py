import sqlite3
from datetime import datetime, timedelta
import random
from typing import Optional, Dict, List, Union

class DatabaseError(Exception):
    """Classe de base pour les erreurs de base de données"""
    pass

class IntegrityError(DatabaseError):
    """Erreur d'intégrité de la base de données"""
    pass

class NotFoundError(DatabaseError):
    """Erreur lorsque l'élément recherché n'existe pas"""
    pass

class UserManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.create_users_table()

    def create_users_table(self) -> None:
        """Crée la table des utilisateurs si elle n'existe pas"""
        try:
            with self.conn:
                self.conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CHECK (role IN ('user', 'admin', 'manager'))
                )
                ''')
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la création de la table users: {str(e)}")

    def add_user(self, username: str, email: str, password_hash: str, role: str = 'user') -> Optional[int]:
        """
        Ajoute un nouvel utilisateur
        Retourne l'ID de l'utilisateur ou None en cas d'échec
        """
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, ?)
                ''', (username, email, password_hash, role))
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise IntegrityError(f"Nom d'utilisateur ou email déjà existant: {str(e)}")
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de l'ajout de l'utilisateur: {str(e)}")

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Récupère un utilisateur par son nom d'utilisateur"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username=?', (username,))
            user = cursor.fetchone()
            
            if user:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, user))
            return None
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération de l'utilisateur: {str(e)}")

    def verify_user(self, username: str, password_hash: str) -> Optional[Dict]:
        """Vérifie les identifiants de l'utilisateur"""
        user = self.get_user_by_username(username)
        if user and user['password_hash'] == password_hash:
            return user
        return None


class BankDatabase:
    def __init__(self, db_name: str = "bank_database.db"):
        """Initialise la connexion à la base de données et crée les tables"""
        try:
            self.conn = sqlite3.connect(db_name)
            self.conn.row_factory = sqlite3.Row  # Pour accéder aux colonnes par nom
            self.create_tables()
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur de connexion à la base de données: {str(e)}")

    def create_tables(self) -> None:
        """Crée toutes les tables nécessaires"""
        try:
            with self.conn:
                # Table Clients
                self.conn.execute('''
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    email TEXT UNIQUE,
                    phone TEXT,
                    type TEXT CHECK(type IN ('Particulier', 'Entreprise', 'Association')),
                    status TEXT CHECK(status IN ('Actif', 'Inactif', 'En attente')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # Table IBAN
                self.conn.execute('''
                CREATE TABLE IF NOT EXISTS ibans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    iban TEXT UNIQUE NOT NULL,
                    currency TEXT CHECK(currency IN ('EUR', 'USD', 'GBP')),
                    type TEXT CHECK(type IN ('Courant', 'Epargne', 'Entreprise')),
                    balance REAL DEFAULT 0 CHECK(balance >= 0),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
                )
                ''')
                
                # Table Transactions
                self.conn.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    iban_id INTEGER NOT NULL,
                    client_id INTEGER NOT NULL,
                    type TEXT CHECK(type IN ('Dépôt', 'Retrait', 'Virement', 'Prélèvement')),
                    amount REAL NOT NULL CHECK(amount > 0),
                    description TEXT,
                    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (iban_id) REFERENCES ibans (id),
                    FOREIGN KEY (client_id) REFERENCES clients (id)
                )
                ''')
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la création des tables: {str(e)}")

    # ===== Méthodes pour les clients =====
    def add_client(self, first_name: str, last_name: str, email: str, phone: str, 
                  client_type: str, status: str) -> int:
        """Ajoute un nouveau client et retourne son ID"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                INSERT INTO clients (first_name, last_name, email, phone, type, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, email, phone, client_type, status))
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise IntegrityError(f"Email déjà existant: {str(e)}")
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de l'ajout du client: {str(e)}")

    def update_client(self, client_id: int, first_name: str, last_name: str, email: str, 
                     phone: str, client_type: str, status: str) -> None:
        """Met à jour les informations d'un client"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                UPDATE clients 
                SET first_name=?, last_name=?, email=?, phone=?, type=?, status=?
                WHERE id=?
                ''', (first_name, last_name, email, phone, client_type, status, client_id))
                
                if cursor.rowcount == 0:
                    raise NotFoundError(f"Client avec ID {client_id} non trouvé")
        except sqlite3.IntegrityError as e:
            raise IntegrityError(f"Email déjà existant: {str(e)}")
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la mise à jour du client: {str(e)}")

    def get_client_by_id(self, client_id: int) -> Optional[Dict]:
        """Récupère un client par son ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM clients WHERE id=?', (client_id,))
            client = cursor.fetchone()
            
            if client:
                return dict(client)
            return None
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération du client: {str(e)}")

    def get_all_clients(self) -> List[Dict]:
        """Récupère tous les clients triés par nom"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM clients ORDER BY last_name, first_name')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des clients: {str(e)}")

    def count_active_clients(self) -> int:
        """Compte le nombre de clients actifs"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM clients WHERE status="Actif"')
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors du comptage des clients actifs: {str(e)}")

    def get_clients_by_type(self) -> List[tuple]:
        """Retourne le nombre de clients par type"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT type, COUNT(*) as count FROM clients GROUP BY type')
            return cursor.fetchall()
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des clients par type: {str(e)}")

    # ===== Méthodes pour les IBAN =====
    def add_iban(self, client_id: int, iban: str, currency: str, 
                account_type: str, balance: float = 0) -> int:
        """Ajoute un nouveau compte IBAN et retourne son ID"""
        try:
            with self.conn:
                cursor = self.conn.cursor()
                # Vérifie que le client existe
                if not self.get_client_by_id(client_id):
                    raise NotFoundError(f"Client avec ID {client_id} non trouvé")
                
                cursor.execute('''
                INSERT INTO ibans (client_id, iban, currency, type, balance)
                VALUES (?, ?, ?, ?, ?)
                ''', (client_id, iban, currency, account_type, balance))
                return cursor.lastrowid
        except sqlite3.IntegrityError as e:
            raise IntegrityError(f"IBAN déjà existant: {str(e)}")
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de l'ajout de l'IBAN: {str(e)}")

    def get_iban_by_id(self, iban_id: int) -> Optional[Dict]:
        """Récupère un compte IBAN par son ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM ibans WHERE id=?', (iban_id,))
            iban = cursor.fetchone()
            return dict(iban) if iban else None
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération de l'IBAN: {str(e)}")

    def get_ibans_by_client(self, client_id: int) -> List[Dict]:
        """Récupère tous les IBAN d'un client"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT * FROM ibans WHERE client_id=?', (client_id,))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des IBANs: {str(e)}")

    def get_all_ibans(self) -> List[Dict]:
        """Récupère tous les IBAN avec les infos clients"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT i.*, c.first_name, c.last_name 
            FROM ibans i
            JOIN clients c ON i.client_id = c.id
            ''')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des IBANs: {str(e)}")

    # ===== Méthodes pour les transactions =====
    def _execute_transaction(self, iban_id: int, amount: float, 
                           transaction_type: str, description: str) -> None:
        """Méthode interne pour exécuter une transaction"""
        if amount <= 0:
            raise ValueError("Le montant doit être positif")
            
        cursor = self.conn.cursor()
        
        # Récupère le client_id et vérifie le solde pour les retraits
        cursor.execute('SELECT client_id, balance FROM ibans WHERE id=?', (iban_id,))
        result = cursor.fetchone()
        
        if not result:
            raise NotFoundError(f"IBAN avec ID {iban_id} non trouvé")
            
        client_id, balance = result['client_id'], result['balance']
        
        if transaction_type == 'Retrait' and balance < amount:
            raise ValueError("Solde insuffisant pour ce retrait")
        
        # Ajoute la transaction
        cursor.execute('''
        INSERT INTO transactions (iban_id, client_id, type, amount, description)
        VALUES (?, ?, ?, ?, ?)
        ''', (iban_id, client_id, transaction_type, amount, description))
        
        # Met à jour le solde
        if transaction_type == 'Dépôt':
            cursor.execute('UPDATE ibans SET balance = balance + ? WHERE id=?', (amount, iban_id))
        else:
            cursor.execute('UPDATE ibans SET balance = balance - ? WHERE id=?', (amount, iban_id))

    def deposit(self, iban_id: int, amount: float, description: str = "") -> None:
        """Effectue un dépôt sur un compte"""
        try:
            with self.conn:
                self._execute_transaction(iban_id, amount, 'Dépôt', description)
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors du dépôt: {str(e)}")

    def withdraw(self, iban_id: int, amount: float, description: str = "") -> None:
        """Effectue un retrait sur un compte"""
        try:
            with self.conn:
                self._execute_transaction(iban_id, amount, 'Retrait', description)
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors du retrait: {str(e)}")

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Dict]:
        """Récupère une transaction par son ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT t.*, i.iban, c.first_name, c.last_name
            FROM transactions t
            JOIN ibans i ON t.iban_id = i.id
            JOIN clients c ON t.client_id = c.id
            WHERE t.id=?
            ''', (transaction_id,))
            transaction = cursor.fetchone()
            return dict(transaction) if transaction else None
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération de la transaction: {str(e)}")

    def get_all_transactions(self) -> List[Dict]:
        """Récupère toutes les transactions"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT t.*, i.iban, c.first_name, c.last_name
            FROM transactions t
            JOIN ibans i ON t.iban_id = i.id
            JOIN clients c ON t.client_id = c.id
            ORDER BY t.date DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des transactions: {str(e)}")

    def get_recent_transactions(self, limit: int = 5) -> List[Dict]:
        """Récupère les transactions récentes"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT t.*, i.iban, c.first_name, c.last_name
            FROM transactions t
            JOIN ibans i ON t.iban_id = i.id
            JOIN clients c ON t.client_id = c.id
            ORDER BY t.date DESC
            LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des transactions récentes: {str(e)}")

    def count_daily_transactions(self) -> int:
        """Compte les transactions du jour"""
        try:
            cursor = self.conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*) FROM transactions WHERE date(date) = date(?)', (today,))
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors du comptage des transactions journalières: {str(e)}")

    def get_last_week_transactions(self) -> Dict[str, List]:
        """Récupère les statistiques des transactions de la semaine"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)
            
            dates = []
            deposits = []
            withdrawals = []
            
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                cursor = self.conn.cursor()
                
                # Dépôts
                cursor.execute('''
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE type='Dépôt' AND date(date) = date(?)
                ''', (date_str,))
                deposit = cursor.fetchone()[0]
                
                # Retraits
                cursor.execute('''
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE type='Retrait' AND date(date) = date(?)
                ''', (date_str,))
                withdrawal = cursor.fetchone()[0]
                
                dates.append(date_str)
                deposits.append(deposit)
                withdrawals.append(withdrawal)
                
                current_date += timedelta(days=1)
            
            return {
                'date': dates,
                'deposit': deposits,
                'withdrawal': withdrawals
            }
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des stats hebdomadaires: {str(e)}")

    def total_deposits(self) -> float:
        """Retourne le total des dépôts"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type="Dépôt"')
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors du calcul des dépôts totaux: {str(e)}")

    def total_withdrawals(self) -> float:
        """Retourne le total des retraits"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type="Retrait"')
            return cursor.fetchone()[0]
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors du calcul des retraits totaux: {str(e)}")

    def close(self) -> None:
        """Ferme la connexion à la base de données"""
        try:
            self.conn.close()
        except sqlite3.Error as e:
            raise DatabaseError(f"Erreur lors de la fermeture de la connexion: {str(e)}")

    def __enter__(self):
        """Permet d'utiliser la classe avec un contexte 'with'"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme la connexion à la fin du contexte"""
        self.close()