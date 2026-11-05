"""
Module de gestion de la base de données
Supporte SQLite (dev) et PostgreSQL (production)
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional, Any, List, Tuple
from contextlib import contextmanager

# Détecte si PostgreSQL est disponible
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

# Détermine le type de base de données à utiliser
DATABASE_URL = os.getenv('DATABASE_URL')
USE_POSTGRES = DATABASE_URL and POSTGRES_AVAILABLE

class DatabaseConnection:
    """Gestionnaire de connexion unifié pour SQLite et PostgreSQL"""
    
    @staticmethod
    @contextmanager
    def get_connection():
        """Contexte manager pour obtenir une connexion à la base de données"""
        if USE_POSTGRES:
            # PostgreSQL
            conn = psycopg2.connect(DATABASE_URL)
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
        else:
            # SQLite
            conn = sqlite3.connect('learning_streak.db')
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise e
            finally:
                conn.close()
    
    @staticmethod
    def get_placeholder():
        """Retourne le placeholder approprié pour les requêtes paramétrées"""
        return '%s' if USE_POSTGRES else '?'

def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    placeholder = DatabaseConnection.get_placeholder()
    
    with DatabaseConnection.get_connection() as conn:
        c = conn.cursor()
        
        if USE_POSTGRES:
            # PostgreSQL - Table des utilisateurs
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                total_points INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                last_log_date TEXT,
                created_at TEXT,
                interests TEXT
            )''')
            
            # PostgreSQL - Table des logs d'apprentissage
            c.execute('''CREATE TABLE IF NOT EXISTS learning_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                subject TEXT,
                description TEXT,
                duration INTEGER,
                log_date TEXT,
                points_earned INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')
            
            # PostgreSQL - Table des badges
            c.execute('''CREATE TABLE IF NOT EXISTS badges (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                badge_name TEXT,
                badge_description TEXT,
                earned_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')
            
            # PostgreSQL - Table des défis du jour
            c.execute('''CREATE TABLE IF NOT EXISTS daily_challenges (
                id SERIAL PRIMARY KEY,
                challenge_text TEXT,
                category TEXT,
                date TEXT,
                user_id BIGINT
            )''')
            # Migration : ajoute user_id si la table existait sans
            c.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'daily_challenges' AND column_name = 'user_id'
            """)
            if not c.fetchone():
                c.execute('ALTER TABLE daily_challenges ADD COLUMN user_id BIGINT')
            
            # PostgreSQL - Table des résultats de quiz
            c.execute('''CREATE TABLE IF NOT EXISTS quiz_results (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                category TEXT,
                score INTEGER,
                total_questions INTEGER,
                points_earned INTEGER,
                quiz_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')

            # PostgreSQL - Questions maîtrisées (anti-répétition quiz)
            c.execute('''CREATE TABLE IF NOT EXISTS quiz_mastered_questions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                topic TEXT,
                question_text TEXT,
                mastered_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')

            # PostgreSQL - Table des suggestions
            c.execute('''CREATE TABLE IF NOT EXISTS suggestions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT,
                subject TEXT,
                suggested_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')

            # PostgreSQL - Questions utilisateurs (Aide)
            c.execute('''CREATE TABLE IF NOT EXISTS help_questions (
                id SERIAL PRIMARY KEY,
                username TEXT,
                question TEXT,
                submitted_at TEXT
            )''')

            # PostgreSQL - Migration colonnes auth + profil
            for col, col_type in [('email', 'TEXT'), ('password_hash', 'TEXT'), ('google_id', 'TEXT'), ('profile', 'TEXT')]:
                c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name=%s", (col,))
                if not c.fetchone():
                    c.execute(f'ALTER TABLE users ADD COLUMN {col} {col_type}')

            # PostgreSQL - Migration colonne kind sur suggestions
            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name='suggestions' AND column_name='kind'")
            if not c.fetchone():
                c.execute("ALTER TABLE suggestions ADD COLUMN kind TEXT DEFAULT 'topic'")
        else:
            # SQLite - Table des utilisateurs
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                total_points INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                last_log_date TEXT,
                created_at TEXT,
                interests TEXT
            )''')
            
            # SQLite - Table des logs d'apprentissage
            c.execute('''CREATE TABLE IF NOT EXISTS learning_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subject TEXT,
                description TEXT,
                duration INTEGER,
                log_date TEXT,
                points_earned INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')
            
            # SQLite - Table des badges
            c.execute('''CREATE TABLE IF NOT EXISTS badges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                badge_name TEXT,
                badge_description TEXT,
                earned_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')
            
            # SQLite - Table des défis du jour
            c.execute('''CREATE TABLE IF NOT EXISTS daily_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge_text TEXT,
                category TEXT,
                date TEXT,
                user_id INTEGER
            )''')
            # Migration : ajoute user_id si la table existait sans
            c.execute("PRAGMA table_info(daily_challenges)")
            columns = [row[1] for row in c.fetchall()]
            if 'user_id' not in columns:
                c.execute('ALTER TABLE daily_challenges ADD COLUMN user_id INTEGER')
            
            # SQLite - Table des résultats de quiz
            c.execute('''CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                category TEXT,
                score INTEGER,
                total_questions INTEGER,
                points_earned INTEGER,
                quiz_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')

            # SQLite - Questions maîtrisées (anti-répétition quiz)
            c.execute('''CREATE TABLE IF NOT EXISTS quiz_mastered_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                topic TEXT,
                question_text TEXT,
                mastered_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')

            # SQLite - Table des suggestions
            c.execute('''CREATE TABLE IF NOT EXISTS suggestions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subject TEXT,
                suggested_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )''')

            # SQLite - Questions utilisateurs (Aide)
            c.execute('''CREATE TABLE IF NOT EXISTS help_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                question TEXT,
                submitted_at TEXT
            )''')

            # SQLite - Migration colonnes auth + profil
            c.execute("PRAGMA table_info(users)")
            user_cols = [row[1] for row in c.fetchall()]
            for col, col_type in [('email', 'TEXT'), ('password_hash', 'TEXT'), ('google_id', 'TEXT'), ('profile', 'TEXT')]:
                if col not in user_cols:
                    c.execute(f'ALTER TABLE users ADD COLUMN {col} {col_type}')

            # SQLite - Migration colonne kind sur suggestions
            c.execute("PRAGMA table_info(suggestions)")
            sugg_cols = [row[1] for row in c.fetchall()]
            if 'kind' not in sugg_cols:
                c.execute("ALTER TABLE suggestions ADD COLUMN kind TEXT DEFAULT 'topic'")

        conn.commit()
    
    print(f"[OK] Base de donnees initialisee ({'PostgreSQL' if USE_POSTGRES else 'SQLite'})")

def execute_query(query: str, params: Tuple = (), fetch_one: bool = False, 
                  fetch_all: bool = False) -> Optional[Any]:
    """
    Exécute une requête SQL avec les paramètres appropriés
    
    Args:
        query: Requête SQL (utiliser {ph} comme placeholder)
        params: Paramètres de la requête
        fetch_one: Si True, retourne une seule ligne
        fetch_all: Si True, retourne toutes les lignes
    
    Returns:
        Résultat de la requête ou None
    """
    # Remplace les placeholders
    ph = DatabaseConnection.get_placeholder()
    query = query.replace('{ph}', ph)
    
    with DatabaseConnection.get_connection() as conn:
        c = conn.cursor()
        c.execute(query, params)
        
        if fetch_one:
            result = c.fetchone()
            # Convertit Row en tuple pour compatibilité
            if result and hasattr(result, 'keys'):
                return tuple(result)
            return result
        elif fetch_all:
            results = c.fetchall()
            # Convertit Rows en tuples pour compatibilité
            if results and hasattr(results[0], 'keys'):
                return [tuple(row) for row in results]
            return results
        
        return None

def execute_insert(query: str, params: Tuple = ()) -> Optional[int]:
    """
    Exécute une requête INSERT et retourne l'ID inséré
    
    Args:
        query: Requête SQL INSERT
        params: Paramètres de la requête
    
    Returns:
        ID de la ligne insérée ou None
    """
    ph = DatabaseConnection.get_placeholder()
    query = query.replace('{ph}', ph)
    
    with DatabaseConnection.get_connection() as conn:
        c = conn.cursor()
        c.execute(query, params)
        
        if USE_POSTGRES:
            # PostgreSQL retourne l'ID avec RETURNING
            if 'RETURNING' in query.upper():
                return c.fetchone()[0]
            return c.lastrowid if hasattr(c, 'lastrowid') else None
        else:
            # SQLite
            return c.lastrowid

# Fonctions utilitaires pour les opérations courantes

def get_user(user_id: int) -> Optional[Tuple]:
    """Récupère les infos d'un utilisateur"""
    return execute_query(
        'SELECT * FROM users WHERE user_id = {ph}',
        (user_id,),
        fetch_one=True
    )

def create_user(user_id: int, username: str, created_at: str,
                email: str = None, password_hash: str = None, google_id: str = None):
    """Crée un nouvel utilisateur"""
    execute_query(
        '''INSERT INTO users (user_id, username, created_at, interests, email, password_hash, google_id)
           VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})''',
        (user_id, username, created_at, '[]', email, password_hash, google_id)
    )

def get_user_by_email(email: str) -> Optional[Tuple]:
    """Récupère un utilisateur par son email"""
    return execute_query('SELECT * FROM users WHERE email = {ph}', (email.lower(),), fetch_one=True)

def get_user_by_google_id(google_id: str) -> Optional[Tuple]:
    """Récupère un utilisateur par son Google ID"""
    return execute_query('SELECT * FROM users WHERE google_id = {ph}', (google_id,), fetch_one=True)

def set_user_google_id(user_id: int, google_id: str):
    """Associe un Google ID à un utilisateur existant"""
    execute_query('UPDATE users SET google_id = {ph} WHERE user_id = {ph}', (google_id, user_id))

def update_user_streak(user_id: int, current_streak: int, longest_streak: int, last_log_date: str):
    """Met à jour le streak d'un utilisateur"""
    execute_query(
        '''UPDATE users SET current_streak = {ph}, longest_streak = {ph}, last_log_date = {ph}
           WHERE user_id = {ph}''',
        (current_streak, longest_streak, last_log_date, user_id)
    )

def update_user_points(user_id: int, total_points: int, level: int):
    """Met à jour les points et le niveau d'un utilisateur"""
    execute_query(
        '''UPDATE users SET total_points = {ph}, level = {ph} WHERE user_id = {ph}''',
        (total_points, level, user_id)
    )

def insert_learning_log(user_id: int, subject: str, description: str, 
                        duration: int, log_date: str, points_earned: int):
    """Insère un log d'apprentissage"""
    execute_query(
        '''INSERT INTO learning_logs (user_id, subject, description, duration, log_date, points_earned)
           VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})''',
        (user_id, subject, description, duration, log_date, points_earned)
    )

def insert_badge(user_id: int, badge_name: str, badge_description: str, earned_date: str):
    """Insère un nouveau badge"""
    execute_query(
        '''INSERT INTO badges (user_id, badge_name, badge_description, earned_date)
           VALUES ({ph}, {ph}, {ph}, {ph})''',
        (user_id, badge_name, badge_description, earned_date)
    )

def get_user_badges(user_id: int) -> List[str]:
    """Récupère la liste des badges d'un utilisateur"""
    results = execute_query(
        'SELECT badge_name FROM badges WHERE user_id = {ph}',
        (user_id,),
        fetch_all=True
    )
    return [row[0] for row in results] if results else []

def count_user_logs(user_id: int) -> int:
    """Compte le nombre total de logs d'un utilisateur"""
    result = execute_query(
        'SELECT COUNT(*) FROM learning_logs WHERE user_id = {ph}',
        (user_id,),
        fetch_one=True
    )
    return result[0] if result else 0

def count_unique_subjects(user_id: int) -> int:
    """Compte le nombre de sujets uniques étudiés par un utilisateur"""
    result = execute_query(
        'SELECT COUNT(DISTINCT subject) FROM learning_logs WHERE user_id = {ph}',
        (user_id,),
        fetch_one=True
    )
    return result[0] if result else 0

def get_daily_challenge(date: str, user_id: int) -> Optional[Tuple]:
    """Récupère le défi du jour pour un utilisateur"""
    return execute_query(
        'SELECT challenge_text, category FROM daily_challenges WHERE date = {ph} AND user_id = {ph}',
        (date, user_id),
        fetch_one=True
    )

def insert_daily_challenge(challenge_text: str, category: str, date: str, user_id: int):
    """Insère un défi du jour pour un utilisateur"""
    execute_query(
        'INSERT INTO daily_challenges (challenge_text, category, date, user_id) VALUES ({ph}, {ph}, {ph}, {ph})',
        (challenge_text, category, date, user_id)
    )

def get_recent_challenge_topics(user_id: int, limit: int = 7) -> List[str]:
    """Récupère les catégories des derniers défis d'un utilisateur pour éviter les répétitions"""
    results = execute_query(
        'SELECT category FROM daily_challenges WHERE user_id = {ph} ORDER BY date DESC LIMIT {ph}',
        (user_id, limit),
        fetch_all=True
    )
    return [row[0] for row in results] if results else []

def update_user_interests(user_id: int, interests_json: str):
    """Met à jour les centres d'intérêt d'un utilisateur"""
    execute_query(
        'UPDATE users SET interests = {ph} WHERE user_id = {ph}',
        (interests_json, user_id)
    )

def get_user_profile(user_id: int) -> Optional[str]:
    """Récupère le profil JSON d'un utilisateur"""
    row = execute_query(
        'SELECT profile FROM users WHERE user_id = {ph}',
        (user_id,), fetch_one=True
    )
    return row[0] if row and row[0] else None

def update_user_profile(user_id: int, profile_json: str):
    """Met à jour le profil JSON d'un utilisateur"""
    execute_query(
        'UPDATE users SET profile = {ph} WHERE user_id = {ph}',
        (profile_json, user_id)
    )

def insert_suggestion(user_id: int, subject: str, suggested_date: str, kind: str = 'topic'):
    """Enregistre une suggestion proposée à l'utilisateur (kind : 'topic' ou 'idea')"""
    execute_query(
        'INSERT INTO suggestions (user_id, subject, suggested_date, kind) VALUES ({ph}, {ph}, {ph}, {ph})',
        (user_id, subject, suggested_date, kind)
    )

def get_recent_suggestions(user_id: int, limit: int = 10, kind: str = 'topic') -> List[str]:
    """Récupère les dernières suggestions proposées à l'utilisateur pour un type donné"""
    results = execute_query(
        'SELECT subject FROM suggestions WHERE user_id = {ph} AND kind = {ph} ORDER BY suggested_date DESC LIMIT {ph}',
        (user_id, kind, limit),
        fetch_all=True
    )
    return [row[0] for row in results] if results else []

def insert_help_question(username: str, question: str):
    """Enregistre une question posée par un utilisateur depuis l'onglet Aide"""
    execute_query(
        'INSERT INTO help_questions (username, question, submitted_at) VALUES ({ph}, {ph}, {ph})',
        (username, question, datetime.now().isoformat())
    )

def get_mastered_questions(user_id: int, topic: str, limit: int = 15) -> List[str]:
    """Récupère les questions déjà maîtrisées par l'utilisateur pour un sujet donné"""
    results = execute_query(
        'SELECT question_text FROM quiz_mastered_questions WHERE user_id = {ph} AND topic = {ph} ORDER BY mastered_at DESC LIMIT {ph}',
        (user_id, topic, limit),
        fetch_all=True
    )
    return [row[0] for row in results] if results else []

def insert_mastered_questions(user_id: int, topic: str, questions: List[str]):
    """Enregistre les questions répondues correctement pour éviter les répétitions futures"""
    now = datetime.now().isoformat()
    for question_text in questions:
        existing = execute_query(
            'SELECT id FROM quiz_mastered_questions WHERE user_id = {ph} AND topic = {ph} AND question_text = {ph}',
            (user_id, topic, question_text),
            fetch_one=True
        )
        if not existing:
            execute_query(
                'INSERT INTO quiz_mastered_questions (user_id, topic, question_text, mastered_at) VALUES ({ph}, {ph}, {ph}, {ph})',
                (user_id, topic, question_text, now)
            )
