# keep_alive.py
from flask import Flask, jsonify, render_template, redirect, request, session, url_for
from threading import Thread
import logging
import os
import time
import requests
import secrets
from requests_oauthlib import OAuth2Session
from datetime import datetime
import pytz
import asyncio

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://naerzone-bot.onrender.com')
DISCORD_REDIRECT_URI = RENDER_URL + '/callback'
DISCORD_API_BASE = 'https://discord.com/api'
DISCORD_TOKEN_URL = DISCORD_API_BASE + '/oauth2/token'
DISCORD_AUTH_URL = DISCORD_API_BASE + '/oauth2/authorize'
DISCORD_USER_URL = DISCORD_API_BASE + '/users/@me'
DISCORD_GUILDS_URL = DISCORD_API_BASE + '/users/@me/guilds'

from database import Database

app = Flask(__name__, 
            template_folder='templates',
            static_folder='static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# Referencia al bot (se asignará desde main.py)
bot = None

logger.info(f"🔧 Configuración OAuth2: Client ID {DISCORD_CLIENT_ID}")

# ==================== FUNCIÓN AUXILIAR ====================
def obtener_datos_servidor(guild_id):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        db = Database()
        credenciales = loop.run_until_complete(db.obtener_credenciales(guild_id))
        config = loop.run_until_complete(db.obtener_config(guild_id))
        loop.close()
        logger.info(f"📊 Datos obtenidos para {guild_id}: credenciales={'✅' if credenciales else '❌'}, config={'✅' if config else '❌'}")
        return credenciales, config
    except Exception as e:
        logger.error(f"❌ Error obteniendo datos: {e}")
        return None, None

# ==================== FUNCIÓN DE REPROGRAMACIÓN ====================
async def reprogramar_servidor(guild_id):
    """Fuerza la reprogramación de un servidor específico después de guardar configuración"""
    global bot
    if not bot:
        logger.warning("⚠️ Bot no disponible para reprogramar")
        return False
    
    try:
        logger.info(f"🔄 Intentando reprogramar servidor {guild_id}")
        
        # Buscar tarea existente y cancelarla
        tareas_canceladas = 0
        tareas_a_eliminar = []
        
        for task_id, task in bot.tareas_programadas.items():
            if str(guild_id) in task_id:
                logger.info(f"   Cancelando tarea: {task_id}")
                task.cancel()
                tareas_a_eliminar.append(task_id)
                tareas_canceladas += 1
        
        # Eliminar las tareas canceladas del diccionario
        for task_id in tareas_a_eliminar:
            del bot.tareas_programadas[task_id]
        
        logger.info(f"✅ Servidor {guild_id} reprogramado: {tareas_canceladas} tarea(s) cancelada(s)")
        
        # La próxima vez que el loop de programación corra, creará una nueva tarea
        return True
    except Exception as e:
        logger.error(f"❌ Error reprogramando servidor {guild_id}: {e}")
        return False

# ==================== HEALTH CHECKS ====================
@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200

@app.route('/ping')
def ping():
    return "pong", 200

# ==================== AUTENTICACIÓN ====================
@app.route('/login')
def login():
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
        
        user_response = discord.get(DISCORD_USER_URL)
        session['user'] = user_response.json()
        
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"❌ Error en callback: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ==================== DASHBOARD PRINCIPAL ====================
@app.route('/dashboard')
def dashboard():
    if 'oauth_token' not in session:
        return redirect(url_for('home'))
    
    try:
        token = session['oauth_token']
        discord = OAuth2Session(DISCORD_CLIENT_ID, token=token)
        
        guilds_response = discord.get(DISCORD_GUILDS_URL)
        user_guilds = guilds_response.json()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        db = Database()
        bot_guilds_ids = loop.run_until_complete(db.obtener_servidores_bot())
        loop.close()
        
        admin_guilds = []
        for g in user_guilds:
            is_admin = (int(g['permissions']) & 0x8) == 0x8
            if is_admin:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                config = loop.run_until_complete(db.obtener_config(g['id']))
                loop.close()
                
                guild_info = {
                    'id': g['id'],
                    'name': g['name'],
                    'icon': g.get('icon'),
                    'bot_esta': str(g['id']) in bot_guilds_ids,
                    'configurado': config is not None
                }
                admin_guilds.append(guild_info)
        
        return render_template('dashboard.html', 
                             user=session['user'],
                             guilds=admin_guilds)
    except Exception as e:
        logger.error(f"❌ Error en dashboard: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== CONFIGURACIÓN DE SERVIDOR ====================
@app.route('/guild/<guild_id>')
def guild_config(guild_id):
    logger.info(f"⚙️ Accediendo a configuración para guild_id: {guild_id}")
    
    if 'oauth_token' not in session:
        return redirect(url_for('home'))
    
    if not guild_id:
        return "Error: ID de servidor no válido", 400
    
    guild_name = request.args.get('name', 'Servidor')
    credenciales, config = obtener_datos_servidor(guild_id)
    
    return render_template('guild_config.html', 
                         guild_id=guild_id,
                         guild_name=guild_name,
                         credenciales=credenciales,
                         config=config)

# ==================== FILTROS Y CONTEXTO ====================
@app.template_filter('strftime')
def jinja_strftime(date, format):
    return date.strftime(format)

@app.context_processor
def utility_processor():
    def now():
        return datetime.now(pytz.timezone('America/Santiago'))
    return dict(now=now)

# ==================== API ====================
@app.route('/api/user/guilds')
def api_user_guilds():
    if 'oauth_token' not in session:
        return jsonify({"error": "No autenticado"}), 401
    try:
        token = session['oauth_token']
        discord = OAuth2Session(DISCORD_CLIENT_ID, token=token)
        guilds_response = discord.get(DISCORD_GUILDS_URL)
        return jsonify(guilds_response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reprogramar/<guild_id>', methods=['POST'])
def api_reprogramar(guild_id):
    """Endpoint manual para forzar reprogramación (útil para debugging)"""
    if 'oauth_token' not in session:
        return jsonify({"error": "No autenticado"}), 401
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    resultado = loop.run_until_complete(reprogramar_servidor(guild_id))
    loop.close()
    
    return jsonify({"reprogramado": resultado})

# ==================== PÁGINA PRINCIPAL ====================
@app.route('/')
def home():
    try:
        user = session.get('user')
        return render_template('index.html', user=user)
    except Exception as e:
        logger.error(f"❌ Error en home: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/login/<guild_id>')
def login_page(guild_id):
    try:
        return render_template('login.html', guild_id=guild_id)
    except Exception as e:
        return f"Error: {e}", 500

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive(bot_instance=None):
    """Inicia el servidor web y guarda referencia al bot"""
    global bot
    if bot_instance:
        bot = bot_instance
        logger.info("✅ Referencia al bot guardada en keep_alive")
    
    try:
        thread = Thread(target=run, daemon=True)
        thread.start()
        logger.info("✅ Servidor web iniciado")
        return thread
    except Exception as e:
        logger.error(f"❌ Error iniciando servidor: {e}")
        return None
