import logging
import os
import mysql.connector
from datetime import datetime, timedelta
import random
from typing import Optional, Dict, List, Union
from venv import logger

from jsonschema import ValidationError

class DatabaseError(Exception):
    """Classe de base pour les erreurs de base de données"""
    pass

class IntegrityError(DatabaseError):
    """Erreur d'intégrité de la base de données"""
    pass

class NotFoundError(DatabaseError):
    """Erreur lorsque l'élément recherché n'existe pas"""
    pass


class BankDatabase:
    def __init__(self, host: str = "db-mav-1.cdeaqqe46t76.eu-north-1.rds.amazonaws.com", user: str = "admin", 
                 password: str = "Frz5E1LTv49J7xF6MQleP0hgrYrCO3ybyHpJujA", database: str = "ecocapital"):
        """Initialise la connexion à la base de données MySQL et met à jour les tables"""
        logging.basicConfig(filename='database.log', level=logging.INFO)
        try:
            self.conn = mysql.connector.connect(
                host=host,
                user=user,
                password=password,
                database=database
            )
            self.create_tables()
            self.update_database_schema()
            logging.info(f"Connexion à la base de données MySQL: {database}")
        except mysql.connector.Error as e:
            logger.error(f"Erreur de connexion: {str(e)}")
            raise DatabaseError(f"Erreur de connexion à la base de données: {str(e)}")

    # Dictionnaire des banques avec leurs codes et BIC
    BANK_DATA = {
        "Digital Financial Service": {"code": "30001", "bic": "UNAFCGCG"},
        "UBA": {"code": "30004", "bic": "UNAFCGCG"},
        #"ECOBANK": {"code": "30006", "bic": "ECOCCGCG"},
        #"Société Générale": {"code": "30003", "bic": "SOGEFRPP"}
    }
    
    def generate_account_number(self, bank_name="Digital Financial Service"):
        """Génère un numéro de compte complet avec clé RIB"""
        bank_info = self.BANK_DATA.get(bank_name, self.BANK_DATA["Digital Financial Service"])
        code_banque = bank_info["code"]
        code_guichet = f"{random.randint(0, 99999):05d}"
        num_compte = f"{random.randint(0, 99999999999):011d}"
        
        # Calcul de la clé RIB (formule bancaire française)
        rib_key = 97 - (
            (89 * int(code_banque) + 15 * int(code_guichet) + 3 * int(num_compte)) % 97
        )
        
        return {
            "full_account": f"{code_banque}{code_guichet}{num_compte}{rib_key:02d}",
            "bank_code": code_banque,
            "branch_code": code_guichet,
            "account_number": num_compte,
            "rib_key": f"{rib_key:02d}",
            "bic": bank_info["bic"],
            "bank_name": bank_name
        }

    def get_account_by_iban_1(self, iban):
        """Récupère un compte par son IBAN"""
        query = "SELECT * FROM accounts WHERE iban = %s"
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(query, (iban,))
        return cursor.fetchone()

    def generate_iban(self, bank_name="Digital Financial Service"):
        """Génère un IBAN valide à partir des données bancaires"""
        account_data = self.generate_account_number(bank_name)
        country_code = "CG"
        check_digits = "42"  # Pour la France
        
        # Construction du BBAN (Basic Bank Account Number)
        bban = (
            f"{account_data['bank_code']}"
            f"{account_data['branch_code']}"
            f"{account_data['account_number']}"
            f"{account_data['rib_key']}"
        )
        
        return {
            "iban": f"{country_code}{check_digits}{bban}",
            **account_data
        }
    
    def backup_database(self, backup_path: str) -> None:
        """Crée une sauvegarde de la base de données"""
        try:
            # MySQL doesn't have a built-in backup like SQLite, so we'll dump the database
            import subprocess
            command = f"mysqldump -u {self.conn.user} -p{self.conn.password} {self.conn.database} > {backup_path}"
            subprocess.run(command, shell=True, check=True)
            logger.info(f"Sauvegarde créée: {backup_path}")
        except Exception as e:
            logger.error(f"Erreur de sauvegarde: {str(e)}")
            raise DatabaseError(f"Erreur de sauvegarde: {str(e)}")
        
    def check_integrity(self):
        """Vérifie l'intégrité de la base de données"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("CHECK TABLE ibans, clients, transactions, avis")
            result = cursor.fetchall()
            logging.info(f"Vérification d'intégrité: {result}")
            return result
        except mysql.connector.Error as e:
            logging.error(f"Erreur de vérification d'intégrité: {str(e)}")
            raise DatabaseError(f"Erreur de vérification d'intégrité: {str(e)}")

    def update_database_schema(self) -> None:
        """Met à jour le schéma de la base de données existante"""
        try:
            cursor = self.conn.cursor()
            
            # Vérifier et ajouter les colonnes manquantes dans la table ibans
            cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'ibans'
            """, (self.conn.database,))
            columns = [column[0] for column in cursor.fetchall()]
            
            # Ajoutez les colonnes manquantes
            if 'bank_name' not in columns:
                cursor.execute("ALTER TABLE ibans ADD COLUMN bank_name VARCHAR(255)")
            
            if 'bank_code' not in columns:
                cursor.execute("ALTER TABLE ibans ADD COLUMN bank_code VARCHAR(50)")
                
            if 'bic' not in columns:
                cursor.execute("ALTER TABLE ibans ADD COLUMN bic VARCHAR(20)")
                
            if 'rib_key' not in columns:
                cursor.execute("ALTER TABLE ibans ADD COLUMN rib_key VARCHAR(10)")
                
            if 'account_number' not in columns:
                cursor.execute("ALTER TABLE ibans ADD COLUMN account_number VARCHAR(50)")
                
            if 'branch_code' not in columns:
                cursor.execute("ALTER TABLE ibans ADD COLUMN branch_code VARCHAR(50)")
                
            # Vérifier et ajouter les colonnes manquantes dans la table avis
            cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'avis'
            """, (self.conn.database,))
            columns = [column[0] for column in cursor.fetchall()]
            
            if 'date_expiration' not in columns:
                cursor.execute("ALTER TABLE avis ADD COLUMN date_expiration DATE")
                
            if 'commentaires' not in columns:
                cursor.execute("ALTER TABLE avis ADD COLUMN commentaires TEXT")
                
            self.conn.commit()
                    
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la mise à jour du schéma: {str(e)}")


    def add_account(self, account_data: dict) -> int:
        """Ajoute un compte bancaire avec toutes les informations requises"""
        try:
            required_fields = ['client_id', 'iban', 'bank_name', 'bank_code', 'bic',
                            'rib_key', 'account_number', 'branch_code', 'currency', 'type']
            for field in required_fields:
                if field not in account_data:
                    raise ValueError(f"Champ manquant: {field}")

            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO ibans 
            (client_id, iban, currency, type, balance, bank_name, bank_code, 
            bic, rib_key, account_number, branch_code)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                account_data['client_id'],
                account_data['iban'],
                account_data['currency'],
                account_data['type'],
                account_data.get('balance', 0),
                account_data['bank_name'],
                account_data['bank_code'],
                account_data['bic'],
                account_data['rib_key'],
                account_data['account_number'],
                account_data['branch_code']
            ))
            self.conn.commit()
            return cursor.lastrowid
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur MySQL: {str(e)}")

    def update_account(self, account_id, account_data):
        """Met à jour un compte existant"""
        query = """
        UPDATE accounts 
        SET bank_name = %s, bank_code = %s, branch_code = %s, 
            account_number = %s, rib_key = %s, iban = %s, 
            bic = %s, type = %s, currency = %s, balance = %s, 
            status = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """
        params = (
            account_data['bank_name'], account_data['bank_code'],
            account_data['branch_code'], account_data['account_number'],
            account_data['rib_key'], account_data['iban'],
            account_data['bic'], account_data['type'],
            account_data['currency'], account_data['balance'],
            account_data['status'], account_id
        )
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()

    def search_accounts(self, client_query: str = None, iban_query: str = None,
                   min_balance: float = None, max_balance: float = None) -> List[Dict]:
        """
        Recherche avancée de comptes avec plusieurs critères
        Args:
            client_query: Terme de recherche pour le nom du client
            iban_query: Terme de recherche pour l'IBAN
            min_balance: Solde minimum
            max_balance: Solde maximum
        Returns:
            List[Dict]: Liste des comptes correspondants
        """
        try:
            cursor = self.conn.cursor(dictionary=True)
            
            # Construction dynamique de la requête SQL
            query = '''
            SELECT 
                i.id,
                i.iban,
                i.currency,
                i.type,
                i.balance,
                i.bank_name,
                c.first_name,
                c.last_name,
                c.email,
                c.phone
            FROM ibans i
            JOIN clients c ON i.client_id = c.id
            WHERE 1=1
            '''
            
            params = []
            
            # Filtre par nom/prénom client
            if client_query and client_query.strip():
                query += '''
                AND (c.first_name LIKE %s OR c.last_name LIKE %s)
                '''
                search_term = f"%{client_query.strip()}%"
                params.extend([search_term, search_term])
            
            # Filtre par IBAN
            if iban_query and iban_query.strip():
                query += '''
                AND i.iban LIKE %s
                '''
                params.append(f"%{iban_query.strip()}%")
            
            # Filtre par solde
            if min_balance is not None:
                query += '''
                AND i.balance >= %s
                '''
                params.append(min_balance)
            
            if max_balance is not None:
                query += '''
                AND i.balance <= %s
                '''
                params.append(max_balance)
            
            # Exécution de la requête
            cursor.execute(query, params)
            
            # Formatage des résultats
            accounts = []
            for row in cursor.fetchall():
                account = dict(row)
                account['client_name'] = f"{account['first_name']} {account['last_name']}"
                account['formatted_iban'] = ' '.join(
                    [account['iban'][i:i+4] for i in range(0, len(account['iban']), 4)]
                )
                accounts.append(account)
            
            return accounts
            
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la recherche de comptes: {str(e)}")
        
    def generate_rib_receipt(self, iban: str, output_path: str = None) -> str:
        """
        Génère un reçu RIB (Relevé d'Identité Bancaire) au format PDF avec design amélioré
        Args:
            iban: IBAN du compte
            output_path: Chemin de sortie du fichier PDF (optionnel)
        Returns:
            str: Chemin du fichier généré
        """
        try:
            # Récupération des données du compte
            account_data = self.get_account_by_iban(iban)
            if not account_data:
                raise NotFoundError(f"Aucun compte trouvé avec l'IBAN {iban}")
            
            from fpdf import FPDF
            from datetime import datetime
            import os

            # Configuration du PDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            # ---- En-tête avec logo ----
            try:
                # Ajoutez votre logo (remplacez par le chemin correct)
                pdf.image("assets/logo.png", x=10, y=8, w=30)
            except:
                pass  # Continue si le logo n'est pas trouvé
            
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "RELEVE DE COMPTE", 0, 1, 'C')
            
            # Référence du document
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(0, 5, f"REF: RIB-{datetime.now().strftime('%Y%m%d')}-{iban[-4:]}", 0, 1, 'C')
            pdf.ln(10)
            
            # ---- Informations Banque ----
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, "Informations Comptes", 0, 1, 'L', True)
            
            pdf.set_font("Arial", '', 10)
            bank_info = [
                ("Structure Financière", "Eco Capital"),
                #("Nom", account_data['bank_name']),
                ("BIC/SWIFT", account_data['bic']),
                ("Adresse", "1636 Boulevard Dénis SASSOU NGUESSO, Brazzaville, Congo"),
                ("Téléphone", "+242 06 113 5605"),
                ("Email", "contacts@ecocapitale.com")
            ]
            
            for label, value in bank_info:
                pdf.cell(40, 6, f"{label} :", 0, 0)
                pdf.cell(0, 6, value, 0, 1)
            pdf.ln(5)
            
            # ---- Informations Client ----
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, "Informations Client", 0, 1, 'L', True)
            
            pdf.set_font("Arial", '', 10)
            client_info = [
                ("Nom", f"{account_data['first_name']} {account_data['last_name']}"),
                ("Email", account_data.get('email', 'Non renseigné')),
                ("Téléphone", account_data.get('phone', 'Non renseigné')),
                ("Type Client", account_data.get('client_type', 'Particulier'))
            ]
            
            for label, value in client_info:
                pdf.cell(40, 6, f"{label} :", 0, 0)
                pdf.cell(0, 6, value, 0, 1)
            pdf.ln(5)
            
            # ---- Détails du Compte ----
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 8, "Détails du Compte", 0, 1, 'L', True)
            
            # Tableau des informations
            pdf.set_fill_color(220, 230, 242)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(70, 8, "Champ", 1, 0, 'C', True)
            pdf.cell(70, 8, "Valeur", 1, 0, 'C', True)
            pdf.cell(50, 8, "Autre", 1, 1, 'C', True)
            
            pdf.set_font("Arial", '', 10)
            account_details = [
                ("Code Banque", account_data['bank_code'], ""),
                ("Code Guichet", account_data['branch_code'], ""),
                ("Numéro Compte", account_data['account_number'], ""),
                ("Clé RIB", account_data['rib_key'], ""),
                ("IBAN", account_data['iban'], ""),
                ("Type Compte", account_data['type'], ""),
                ("Devise", account_data['currency'], ""),
                ("Solde Actuel", f"{account_data.get('balance', 0):,.2f}", account_data['currency'])
            ]
            
            for field, value, extra in account_details:
                pdf.cell(70, 8, field, 1, 0)
                pdf.cell(70, 8, value, 1, 0)
                pdf.cell(50, 8, extra, 1, 1)
            pdf.ln(10)
            
            # ---- QR Code ----
            try:
                import qrcode
                from io import BytesIO
                
                qr_data = {
                    "IBAN": account_data['iban'],
                    "Nom": f"{account_data['first_name']} {account_data['last_name']}",
                    "BIC": account_data['bic'],
                    "Banque": account_data['bank_name'],
                    "Date": datetime.now().strftime('%d/%m/%Y')
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
                pdf.image(img_bytes, x=150, y=pdf.get_y()+10, w=40)

            except ImportError:
                pass
            
            # ---- Pied de page ----
            pdf.set_y(-20)
            pdf.set_font("Arial", 'I', 8)
            pdf.cell(0, 5, f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", 0, 0, 'C')
            
            # ---- Sauvegarde ----
            if not output_path:
                os.makedirs("rib_documents", exist_ok=True)
                output_path = f"rib_documents/RIB_{account_data['iban']}.pdf"
            
            pdf.output(output_path)
            return output_path
            
        except Exception as e:
            raise DatabaseError(f"Erreur lors de la génération du RIB: {str(e)}")

    def create_tables(self) -> None:
        """Crée toutes les tables nécessaires avec les colonnes requises"""
        try:
            cursor = self.conn.cursor()
            
            # Table Clients
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id INT AUTO_INCREMENT PRIMARY KEY,
                first_name VARCHAR(255) NOT NULL,
                last_name VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE,
                phone VARCHAR(50),
                type ENUM('Particulier', 'Entreprise', 'VIP'),
                status ENUM('Actif', 'Inactif', 'En attente'),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            # Table IBAN avec toutes les colonnes nécessaires
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS ibans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                client_id INT NOT NULL,
                iban VARCHAR(50) UNIQUE NOT NULL,
                currency ENUM('EUR', 'USD', 'GBP', 'XAF'),
                type ENUM('Courant', 'Épargne', 'Entreprise'),
                balance DECIMAL(15,2) DEFAULT 0 CHECK (balance >= 0),
                bank_name VARCHAR(255) NOT NULL,
                bank_code VARCHAR(50) NOT NULL,
                bic VARCHAR(20) NOT NULL,
                rib_key VARCHAR(10) NOT NULL,
                account_number VARCHAR(50) NOT NULL,
                branch_code VARCHAR(50) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients (id) ON DELETE CASCADE
            )
            ''')
            
            # Table Transactions
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                iban_id INT NOT NULL,
                client_id INT NOT NULL,
                type ENUM('Dépôt', 'Retrait', 'Virement', 'Prélèvement'),
                amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),
                description TEXT,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (iban_id) REFERENCES ibans (id),
                FOREIGN KEY (client_id) REFERENCES clients (id)
            )
            ''')

            # Table AVI
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS avis (
                id INT AUTO_INCREMENT PRIMARY KEY,
                reference VARCHAR(50) UNIQUE NOT NULL,
                nom_complet VARCHAR(255) NOT NULL,
                code_banque VARCHAR(50) NOT NULL,
                numero_compte VARCHAR(50) NOT NULL,
                devise ENUM('XAF', 'EUR', 'USD') NOT NULL,
                iban VARCHAR(50) NOT NULL,
                bic VARCHAR(20) NOT NULL,
                montant DECIMAL(15,2) NOT NULL,
                date_creation DATE NOT NULL,
                date_expiration DATE,
                statut ENUM('Etudiant', 'Fonctionnaire') NOT NULL,
                commentaires TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            self.conn.commit()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la création des tables: {str(e)}")
        
    def get_avi_by_id(self, avi_id: int) -> Optional[Dict]:
        """Récupère une AVI par son ID"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM avis WHERE id=%s', (avi_id,))
            avi = cursor.fetchone()
            return avi
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération de l'AVI: {str(e)}")

    def get_avi_by_reference(self, reference: str) -> Optional[Dict]:
        """Récupère une AVI par sa référence"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('''
            SELECT 
                a.*,
                i.bank_name,
                i.bank_code,
                i.branch_code,
                i.account_number,
                i.rib_key
            FROM avis a
            LEFT JOIN ibans i ON a.iban = i.iban
            WHERE a.reference = %s
            ''', (reference,))
            
            return cursor.fetchone()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération de l'AVI par référence: {str(e)}")

    def get_all_avis(self, with_details: bool = False) -> List[Dict]:
        """
        Récupère toutes les attestations AVI
        Args:
            with_details: Si True, tente de joindre les tables clients et ibans
        Returns:
            Liste des AVI sous forme de dictionnaires
        """
        try:
            cursor = self.conn.cursor(dictionary=True)
            
            if with_details:
                cursor.execute('''
                SELECT 
                    a.*,
                    i.bank_name,
                    i.bank_code,
                    i.branch_code,
                    i.account_number,
                    i.rib_key
                FROM avis a
                LEFT JOIN ibans i ON a.iban = i.iban
                ORDER BY a.date_creation DESC
                ''')
            else:
                cursor.execute('SELECT * FROM avis ORDER BY date_creation DESC')
                
            return cursor.fetchall()
            
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des AVI: {str(e)}")

    def update_avi(self, reference: str, updated_data: Dict) -> bool:
        """Met à jour une AVI existante en utilisant sa référence"""
        try:
            allowed_fields = {
                'nom_complet', 'code_banque', 'numero_compte', 'devise',
                'iban', 'bic', 'montant', 'date_creation', 'date_expiration', 'statut'
            }
            
            update_fields = {k: v for k, v in updated_data.items() if k in allowed_fields}
            
            if not update_fields:
                raise ValueError("Aucun champ valide à mettre à jour")
            
            cursor = self.conn.cursor()
            
            set_clause = ', '.join([f"{field}=%s" for field in update_fields])
            values = list(update_fields.values())
            values.append(reference)
            
            cursor.execute(f'''
            UPDATE avis
            SET {set_clause}
            WHERE reference=%s
            ''', values)
            
            self.conn.commit()
            return cursor.rowcount > 0
                
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la mise à jour de l'AVI: {str(e)}")

    def add_avi(self, avi_data: Dict) -> int:
        """Ajoute une nouvelle attestation AVI et retourne son ID"""
        try:
            required_fields = [
                'nom_complet', 'code_banque', 'numero_compte', 'devise',
                'iban', 'bic', 'montant', 'date_creation', 'statut'
            ]
            
            for field in required_fields:
                if field not in avi_data:
                    raise ValueError(f"Champ manquant: {field}")

            # Générer une référence unique
            reference = f"AVI-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
            
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO avis (
                reference, nom_complet, code_banque, numero_compte, devise,
                iban, bic, montant, date_creation, date_expiration,
                statut, commentaires
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                reference,
                avi_data['nom_complet'],
                avi_data['code_banque'],
                avi_data['numero_compte'],
                avi_data['devise'],
                avi_data['iban'],
                avi_data['bic'],
                avi_data['montant'],
                avi_data['date_creation'],
                avi_data.get('date_expiration'),
                avi_data['statut'],
                avi_data.get('commentaires')
            ))
            self.conn.commit()
            return cursor.lastrowid
        except mysql.connector.IntegrityError as e:
            raise IntegrityError(f"Erreur d'intégrité lors de l'ajout de l'AVI: {str(e)}")
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur MySQL lors de l'ajout de l'AVI: {str(e)}")

    def search_avis(self, search_term: str = None, statut: str = None) -> List[Dict]:
        """
        Recherche des AVI avec filtres optionnels
        Args:
            search_term: Terme de recherche pour référence, nom, IBAN, etc.
            statut: Filtre par statut (Etudiant, Fonctionnaire)
        Returns:
            Liste des AVI correspondantes sous forme de dictionnaires
        """
        try:
            cursor = self.conn.cursor(dictionary=True)
            query = 'SELECT * FROM avis WHERE 1=1'
            params = []
            
            if search_term:
                query += '''
                AND (reference LIKE %s OR 
                    nom_complet LIKE %s OR 
                    iban LIKE %s OR 
                    code_banque LIKE %s OR 
                    numero_compte LIKE %s)
                '''
                search_param = f"%{search_term}%"
                params.extend([search_param]*5)
                
            if statut:
                query += ' AND statut = %s'
                params.append(statut)
                
            query += ' ORDER BY date_creation DESC'
            
            cursor.execute(query, params)
            return cursor.fetchall()
            
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la recherche d'AVI: {str(e)}")


    # ===== Méthodes pour les clients =====
    def add_client(self, first_name: str, last_name: str, email: str, phone: str, 
                  client_type: str, status: str) -> int:
        """Ajoute un nouveau client et retourne son ID"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO clients (first_name, last_name, email, phone, type, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ''', (first_name, last_name, email, phone, client_type, status))
            self.conn.commit()
            return cursor.lastrowid
        except mysql.connector.IntegrityError as e:
            raise IntegrityError(f"Email déjà existant: {str(e)}")
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de l'ajout du client: {str(e)}")

    def update_client(self, client_id: int, first_name: str, last_name: str, email: str, 
                     phone: str, client_type: str, status: str) -> None:
        """Met à jour les informations d'un client"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            UPDATE clients 
            SET first_name=%s, last_name=%s, email=%s, phone=%s, type=%s, status=%s
            WHERE id=%s
            ''', (first_name, last_name, email, phone, client_type, status, client_id))
            
            self.conn.commit()
            if cursor.rowcount == 0:
                raise NotFoundError(f"Client avec ID {client_id} non trouvé")
        except mysql.connector.IntegrityError as e:
            raise IntegrityError(f"Email déjà existant: {str(e)}")
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la mise à jour du client: {str(e)}")

    def get_client_by_id(self, client_id: int) -> Optional[Dict]:
        """Récupère un client par son ID"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM clients WHERE id=%s', (client_id,))
            return cursor.fetchone()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération du client: {str(e)}")

    def get_all_clients(self) -> List[Dict]:
        """Récupère tous les clients triés par nom"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM clients ORDER BY last_name, first_name')
            return cursor.fetchall()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des clients: {str(e)}")

    def count_active_clients(self) -> int:
        """Compte le nombre de clients actifs"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM clients WHERE status="Actif"')
            return cursor.fetchone()[0]
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors du comptage des clients actifs: {str(e)}")

    def get_clients_by_type(self) -> List[tuple]:
        """Retourne le nombre de clients par type"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT type, COUNT(*) as count FROM clients GROUP BY type')
            return cursor.fetchall()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des clients par type: {str(e)}")

    # ===== Méthodes pour les IBAN =====
    def add_iban(self, client_id: int, iban: str, currency: str, 
                account_type: str, balance: float = 0) -> int:
        """Ajoute un nouveau compte IBAN et retourne son ID"""
        try:
            cursor = self.conn.cursor()
            # Vérifie que le client existe
            if not self.get_client_by_id(client_id):
                raise NotFoundError(f"Client avec ID {client_id} non trouvé")
            
            cursor.execute('''
            INSERT INTO ibans (client_id, iban, currency, type, balance)
            VALUES (%s, %s, %s, %s, %s)
            ''', (client_id, iban, currency, account_type, balance))
            self.conn.commit()
            return cursor.lastrowid
        except mysql.connector.IntegrityError as e:
            raise IntegrityError(f"IBAN déjà existant: {str(e)}")
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de l'ajout de l'IBAN: {str(e)}")

    def get_iban_by_id(self, iban_id: int) -> Optional[Dict]:
        """Récupère un compte IBAN par son ID"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM ibans WHERE id=%s', (iban_id,))
            return cursor.fetchone()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération de l'IBAN: {str(e)}")

    def get_ibans_by_client(self, client_id: int) -> List[Dict]:
        """Récupère tous les IBAN d'un client"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM ibans WHERE client_id=%s', (client_id,))
            return cursor.fetchall()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des IBANs: {str(e)}")

    def get_account_by_iban(self, iban: str) -> Optional[Dict]:
        """Récupère les détails complets d'un compte par son IBAN"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('''
            SELECT 
                i.*, 
                c.first_name, 
                c.last_name,
                c.email,
                c.phone,
                c.type as client_type
            FROM ibans i
            JOIN clients c ON i.client_id = c.id
            WHERE i.iban = %s
            ''', (iban,))
            
            return cursor.fetchone()
            
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération du compte par IBAN: {str(e)}")

    def get_all_ibans(self) -> List[Dict]:
        """Récupère tous les IBAN avec les infos clients"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('''
            SELECT i.*, c.first_name, c.last_name 
            FROM ibans i
            JOIN clients c ON i.client_id = c.id
            ''')
            return cursor.fetchall()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des IBANs: {str(e)}")

    # ===== Méthodes pour les transactions =====
    def _execute_transaction(self, iban_id: int, amount: float, 
                           transaction_type: str, description: str) -> None:
        """Méthode interne pour exécuter une transaction"""
        if amount <= 0:
            raise ValueError("Le montant doit être positif")
            
        cursor = self.conn.cursor(dictionary=True)
        
        # Récupère le client_id et vérifie le solde pour les retraits
        cursor.execute('SELECT client_id, balance FROM ibans WHERE id=%s', (iban_id,))
        result = cursor.fetchone()
        
        if not result:
            raise NotFoundError(f"IBAN avec ID {iban_id} non trouvé")
            
        client_id, balance = result['client_id'], result['balance']
        
        if transaction_type == 'Retrait' and balance < amount:
            raise ValueError("Solde insuffisant pour ce retrait")
        
        # Ajoute la transaction
        cursor.execute('''
        INSERT INTO transactions (iban_id, client_id, type, amount, description)
        VALUES (%s, %s, %s, %s, %s)
        ''', (iban_id, client_id, transaction_type, amount, description))
        
        # Met à jour le solde
        if transaction_type == 'Dépôt':
            cursor.execute('UPDATE ibans SET balance = balance + %s WHERE id=%s', (amount, iban_id))
        else:
            cursor.execute('UPDATE ibans SET balance = balance - %s WHERE id=%s', (amount, iban_id))

    def deposit(self, iban_id: int, amount: float, description: str = "") -> None:
        """Effectue un dépôt sur un compte"""
        try:
            cursor = self.conn.cursor()
            self._execute_transaction(iban_id, amount, 'Dépôt', description)
            self.conn.commit()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors du dépôt: {str(e)}")

    def withdraw(self, iban_id: int, amount: float, description: str = "") -> None:
        """Effectue un retrait sur un compte"""
        try:
            cursor = self.conn.cursor()
            self._execute_transaction(iban_id, amount, 'Retrait', description)
            self.conn.commit()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors du retrait: {str(e)}")

    def get_transaction_by_id(self, transaction_id: int) -> Optional[Dict]:
        """Récupère une transaction par son ID"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('''
            SELECT t.*, i.iban, c.first_name, c.last_name
            FROM transactions t
            JOIN ibans i ON t.iban_id = i.id
            JOIN clients c ON t.client_id = c.id
            WHERE t.id=%s
            ''', (transaction_id,))
            return cursor.fetchone()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération de la transaction: {str(e)}")

    def get_all_transactions(self) -> List[Dict]:
        """Récupère toutes les transactions"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('''
            SELECT t.*, i.iban, c.first_name, c.last_name
            FROM transactions t
            JOIN ibans i ON t.iban_id = i.id
            JOIN clients c ON t.client_id = c.id
            ORDER BY t.date DESC
            ''')
            return cursor.fetchall()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des transactions: {str(e)}")

    def get_recent_transactions(self, limit: int = 5) -> List[Dict]:
        """Récupère les transactions récentes"""
        try:
            cursor = self.conn.cursor(dictionary=True)
            cursor.execute('''
            SELECT t.*, i.iban, c.first_name, c.last_name
            FROM transactions t
            JOIN ibans i ON t.iban_id = i.id
            JOIN clients c ON t.client_id = c.id
            ORDER BY t.date DESC
            LIMIT %s
            ''', (limit,))
            return cursor.fetchall()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des transactions récentes: {str(e)}")

    def count_daily_transactions(self) -> int:
        """Compte les transactions du jour"""
        try:
            cursor = self.conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('SELECT COUNT(*) FROM transactions WHERE DATE(date) = DATE(%s)', (today,))
            return cursor.fetchone()[0]
        except mysql.connector.Error as e:
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
                WHERE type='Dépôt' AND DATE(date) = DATE(%s)
                ''', (date_str,))
                deposit = cursor.fetchone()[0]
                
                # Retraits
                cursor.execute('''
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE type='Retrait' AND DATE(date) = DATE(%s)
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
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la récupération des stats hebdomadaires: {str(e)}")

    def total_deposits(self) -> float:
        """Retourne le total des dépôts"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type="Dépôt"')
            return cursor.fetchone()[0]
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors du calcul des dépôts totaux: {str(e)}")

    def total_withdrawals(self) -> float:
        """Retourne le total des retraits"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type="Retrait"')
            return cursor.fetchone()[0]
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors du calcul des retraits totaux: {str(e)}")

    def close(self) -> None:
        """Ferme la connexion à la base de données"""
        try:
            self.conn.close()
        except mysql.connector.Error as e:
            raise DatabaseError(f"Erreur lors de la fermeture de la connexion: {str(e)}")

    def __enter__(self):
        """Permet d'utiliser la classe avec un contexte 'with'"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferme la connexion à la fin du contexte"""
        self.close()