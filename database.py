from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

# Connexion à la base de données et création de la table si nécessaire
def init_db():
    conn = sqlite3.connect("community.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        sponsor_id INTEGER,
        balance REAL DEFAULT 0,  -- Ajout de la balance
        profile_pic TEXT,  -- Ajout du chemin de la photo de profil
        level INTEGER DEFAULT 1,  -- Ajout du niveau dans la communauté
        FOREIGN KEY (sponsor_id) REFERENCES users (id)
    )
    """)
    conn.commit()
    conn.close()

# Fonction pour ajouter un utilisateur
def add_user(name, email, password, sponsor_id=None):
    conn = sqlite3.connect("community.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO users (name, email, password, sponsor_id)
        VALUES (?, ?, ?, ?)
        """, (name, email, password, sponsor_id))
        conn.commit()
    except sqlite3.IntegrityError:
        return False  # L'utilisateur existe déjà
    finally:
        conn.close()
    return True

# Fonction pour récupérer le nom du parrain
def get_sponsor_name(sponsor_id):
    conn = sqlite3.connect("community.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users WHERE id = ?", (sponsor_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else "Inconnu"

# Route d'inscription
@app.route('/register', methods=['GET', 'POST'])
def register():
    sponsor_id = request.args.get('sponsor_id')  # Récupérer l'ID du parrain depuis l'URL
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        sponsor_id = sponsor_id if sponsor_id else None  # Si aucun sponsor n'est passé, utiliser None
        if add_user(name, email, password, sponsor_id):
            return redirect(url_for('home'))  # Rediriger vers la page d'accueil après l'inscription
        else:
            return "Erreur lors de l'inscription. Veuillez réessayer."

    return render_template('register.html', sponsor_id=sponsor_id)

# Page d'accueil
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    init_db()  # Initialiser la base de données et les tables
    app.run(debug=True)    