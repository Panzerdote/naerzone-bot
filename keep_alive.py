# keep_alive.py
from flask import Flask, jsonify, render_template, redirect, request, session, url_for
from threading import Thread
import logging
import os
import time
import requests
import secrets
from requests_oauthlib import OAuth2Session

# === SOLUCIÓN PARA OAUTH2 EN RENDER ===
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Permite HTTP internamente
# ======================================

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de Discord OAuth
DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '')
DISCORD_REDIRECT_URI = os.environ.get('RENDER_EXTERNAL_URL', 'https://naerzone-bot.onrender.com') + '/callback'
DISCORD_API_BASE = 'https://discord.com/api'
DISCORD_TOKEN_URL = DISCORD_API_BASE + '/oauth2/token'
DISCORD_AUTH_URL = DISCORD_API_BASE + '/oauth2/authorize'
DISCORD_USER_URL = DISCORD_API_BASE + '/users/@me'
DISCORD_GUILDS_URL = DISCORD_API_BASE + '/users/@me/guilds'

# Crear aplicación Flask
app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# ==================== RUTAS PARA HEALTH CHECKS ====================
@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200

@app.route('/ping')
def ping():
    return "pong", 200

# ==================== RUTAS DE AUTENTICACIÓN ====================
@app.route('/login')
def login():
    """Inicia el flujo de login con Discord"""
    discord = OAuth2Session(
        DISCORD_CLIENT_ID,
        redirect_uri=DISCORD_REDIRECT_URI,
        scope=['identify', 'guilds']
    )
    authorization_url, state = discord.authorization_url(DISCORD_AUTH_URL)
    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/callback')
def callback():
    """Callback después de autorizar en Discord"""
    try:
        discord = OAuth2Session(
            DISCORD_CLIENT_ID,
            state=session.get('oauth_state'),
            redirect_uri=DISCORD_REDIRECT_URI
        )
        token = discord.fetch_token(
            DISCORD_TOKEN_URL,
            client_secret=DISCORD_CLIENT_SECRET,
            authorization_response=request.url
        )
        session['oauth_token'] = token
        
        # Obtener información del usuario
        user_response = discord.get(DISCORD_USER_URL)
        user_data = user_response.json()
        session['user'] = user_data
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"Error en callback: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    """Cierra sesión"""
    session.clear()
    return redirect(url_for('home'))

# ==================== RUTAS DEL DASHBOARD ====================
@app.route('/dashboard')
def dashboard():
    """Dashboard principal con lista de servidores"""
    if 'oauth_token' not in session:
        return redirect(url_for('home'))
    
    try:
        token = session['oauth_token']
        discord = OAuth2Session(DISCORD_CLIENT_ID, token=token)
        
        guilds_response = discord.get(DISCORD_GUILDS_URL)
        user_guilds = guilds_response.json()
        
        admin_guilds = [g for g in user_guilds if (int(g['permissions']) & 0x8) == 0x8]
        
        return render_template('dashboard.html', 
                             user=session['user'],
                             guilds=admin_guilds)
    except Exception as e:
        logger.error(f"Error en dashboard: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/guild/<guild_id>')
def guild_config(guild_id):
    """Página de configuración para un servidor específico"""
    if 'oauth_token' not in session:
        return redirect(url_for('home'))
    
    return render_template('guild_config.html', 
                         guild_id=guild_id,
                         guild_name=request.args.get('name', 'Servidor'))

# ==================== RUTAS DE API ====================
@app.route('/api/user/guilds')
def api_user_guilds():
    """API para obtener servidores del usuario"""
    if 'oauth_token' not in session:
        return jsonify({"error": "No autenticado"}), 401
    
    try:
        token = session['oauth_token']
        discord = OAuth2Session(DISCORD_CLIENT_ID, token=token)
        guilds_response = discord.get(DISCORD_GUILDS_URL)
        return jsonify(guilds_response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== RUTAS WEB ORIGINALES ====================
@app.route('/')
def home():
    """Página principal"""
    try:
        user = session.get('user')
        return render_template('index.html', user=user)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/login/<guild_id>')
def login_page(guild_id):
    """Página de login legacy (por compatibilidad)"""
    try:
        return render_template('login.html', guild_id=guild_id)
    except Exception as e:
        return f"Error: {e}", 500

def run():
    """Ejecuta el servidor Flask"""
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Servidor web en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    """Inicia el servidor web en un thread separado"""
    try:
        thread = Thread(target=run, daemon=True)
        thread.start()
        logger.info("✅ Thread del servidor web iniciado")
        return thread
    except Exception as e:
        logger.error(f"❌ Error iniciando servidor web: {e}")
        return None
