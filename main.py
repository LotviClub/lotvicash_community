from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import paypalrestsdk
from flask_bcrypt import Bcrypt

# Initialisation de l'application Flask
app = Flask(__name__)
app.secret_key = 'votre_cle_secrete'  # Clé secrète pour sécuriser les sessions
bcrypt = Bcrypt(app)

# Configuration de l'API PayPal
paypalrestsdk.configure({
    "mode": "sandbox",  # Changez en "live" pour production
    "client_id": "AYYX3uQeSQTOcZNOy0nGQz2_5Cp0haCILGH7Xvx90Uh4izRzpUtRf6ok1QDSojdwU-yED7lIecCH5jR5",  # Remplacez avec votre Client ID
    "client_secret": "EIT3UYWHHZDL3eLNAb7MDjS8_gvAbRqTxedCYND9CMybd5L_8m7yzZ1dihepqM95yQJUDylvyq80sF4u"  # Remplacez avec votre Secret Key
})

# ==========================================================
# INITIALISATION DE LA BASE DE DONNÉES
# ==========================================================
def init_db():
    """Créer la table des utilisateurs si elle n'existe pas"""   
conn = sqlite3.connect("community.db")
cursor = conn.cursor()
cursor.execute("DROP TABLE IF EXISTS users;")
cursor.execute("""
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    sponsor_id INTEGER,
    balance REAL DEFAULT 0,
    profile_pic TEXT,
    level INTEGER DEFAULT 1,
    subscription_type TEXT,
    paid BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (sponsor_id) REFERENCES users (id)
)
""")
conn.commit()
conn.close()
# ==========================================================
# ROUTES PRINCIPALES
# ==========================================================

@app.route('/')
def index():
    """Page d'accueil"""
    return render_template("index.html")


@app.route('/select_subscription', methods=['GET', 'POST'])
def select_subscription():
    """Permet à l'utilisateur de choisir un type d'abonnement"""
    if "user_id" in session:
        return redirect(url_for('dashboard'))  # Rediriger si déjà connecté

    if request.method == 'POST':
        subscription_type = request.form.get('subscription_type')
        return redirect(url_for('register', subscription_type=subscription_type))

    return render_template('select_subscription.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Inscription de l'utilisateur"""
    subscription_type = request.args.get('subscription_type')  # Abonnement choisi

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Hasher le mot de passe avant de l'enregistrer
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        if add_user(name, email, hashed_password, subscription_type):
            return redirect(url_for('paypal_payment', subscription_type=subscription_type))  # Rediriger vers le paiement
        else:
            return "Erreur : cet email est déjà utilisé."

    return render_template('register.html', subscription_type=subscription_type)

# Route de connexion
@app.route('/login', methods=['GET', 'POST'])
def login():
    if "user_id" in session:
        return redirect(url_for('dashboard'))  # Si l'utilisateur est déjà connecté, redirigez vers le tableau de bord

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = check_user(email, password)  # Vérifier les informations de l'utilisateur
        if user:
            session['user_id'] = user[0]  # Sauvegarder l'ID utilisateur dans la session
            return redirect(url_for('dashboard'))  # Rediriger vers le tableau de bord
        else:
            return "Email ou mot de passe incorrect. Essayez à nouveau."

    return render_template('login.html')  # Si GET, afficher le formulaire de connexion
    
# Page de tableau de bord
@app.route('/dashboard')
def dashboard():
    if "user_id" not in session:
        return redirect(url_for('login'))  # Si l'utilisateur n'est pas connecté, le rediriger vers la connexion

    user_id = session['user_id']
    conn = sqlite3.connect("community.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, balance, level FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()
    conn.close()

    if user_data:
        user_name, user_balance, user_level = user_data
        return render_template('dashboard.html', user_name=user_name, user_balance=user_balance, user_level=user_level)
    else:
        return "Utilisateur introuvable"

#logout
@app.route("/logout")
def logout():
    """Déconnexion de l'utilisateur"""
    session.clear()
    return redirect(url_for("login"))

# ==========================================================
# ROUTES DE PAIEMENT
# ==========================================================

@app.route('/paypal_payment', methods=['GET', 'POST'])
def paypal_payment():
    """Gérer le paiement avec PayPal"""
    if request.method == 'POST':
        # Créer un paiement
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "redirect_urls": {
                "return_url": url_for('payment_success', _external=True),
                "cancel_url": url_for('payment_cancel', _external=True)
            },
            "transactions": [{
                "amount": {"total": "200.00", "currency": "USD"},
                "description": "Abonnement LotviCash Community"
            }]
        })

        if payment.create():
            for link in payment.links:
                if link.rel == "approval_url":
                    return redirect(link.href)
        else:
            return "Une erreur s'est produite lors de la création du paiement."

    return render_template('payment.html')


@app.route('/payment_success')
def payment_success():
    """Traitement après un paiement réussi"""
    payment_id = request.args.get('paymentId')
    payer_id = request.args.get('PayerID')
    payment = paypalrestsdk.Payment.find(payment_id)

    if payment.execute({"payer_id": payer_id}):
        # Mettre à jour le statut de paiement dans la base de données
        user_id = session.get('user_id')
        if user_id:
            update_subscription(user_id, "premium")  # Exemple de mise à jour
        return redirect(url_for("dashboard"))
    else:
        return "Le paiement a échoué."


@app.route('/payment_cancel')
def payment_cancel():
    """Traitement après une annulation de paiement"""
    return "Le paiement a été annulé."

# ==========================================================
# FONCTIONS UTILES
# ==========================================================

def add_user(name, email, password, subscription_type, sponsor_id=None):
    """Ajouter un nouvel utilisateur à la base de données"""
    conn = sqlite3.connect("community.db")
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO users (name, email, password, subscription_type, sponsor_id)
        VALUES (?, ?, ?, ?, ?)
        """, (name, email, password, subscription_type, sponsor_id))
        conn.commit()
    except sqlite3.IntegrityError:
        return False  # Email déjà utilisé
    finally:
        conn.close()
    return True


def update_subscription(user_id, subscription_type):
    """Mettre à jour l'abonnement d'un utilisateur"""
    conn = sqlite3.connect("community.db")
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE users 
    SET subscription_type = ?, paid = TRUE
    WHERE id = ?
    """, (subscription_type, user_id))
    conn.commit()
    conn.close()


def check_user(email, password):
    """Vérifier les informations de connexion"""
    conn = sqlite3.connect("community.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, password FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()

    if result and bcrypt.check_password_hash(result[2], password):
        return result[:2]  # Retourne l'ID et le nom de l'utilisateur
    return None

# ==========================================================
# LANCEMENT DE L'APPLICATION
# ==========================================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)