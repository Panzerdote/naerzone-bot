from flask import Flask, jsonify, render_template, redirect, request, session, url_for
from threading import Thread
import logging
import os
import time
import secrets
from requests_oauthlib import OAuth2Session
from datetime import datetime
import pytz
import asyncio
from waitress import serve

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

chile_tz = pytz.timezone('America/Santiago')

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

bot = None

def obtener_datos_servidor(guild_id):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        db = Database()
        credenciales = loop.run_until_complete(db.obtener_credenciales(guild_id))
        config = loop.run_until_complete(db.obtener_config(guild_id))
        loop.close()
        return credenciales, config
    except Exception as e:
        logger.error(f"Error obteniendo datos: {e}")
        return None, None

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()}), 200

@app.route('/ping')
def ping():
    return "pong", 200

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
        callback_url = request.url.replace('http://', 'https://')
        discord = OAuth2Session(
            DISCORD_CLIENT_ID,
            state=session.get('oauth_state'),
            redirect_uri=DISCORD_REDIRECT_URI
        )
        token = discord.fetch_token(
            DISCORD_TOKEN_URL,
            client_secret=DISCORD_CLIENT_SECRET,
            authorization_response=callback_url
        )
        session['oauth_token'] = token
        user_response = discord.get(DISCORD_USER_URL)
        session['user'] = user_response.json()
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"Error en callback: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

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
        logger.error(f"Error en dashboard: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/guild/<guild_id>')
def guild_config(guild_id):
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

@app.context_processor
def utility_processor():
    def now():
        return datetime.now(chile_tz)
    return dict(now=now)

@app.route('/')
def home():
    try:
        user = session.get('user')
        return render_template('index.html', user=user)
    except Exception as e:
        logger.error(f"Error en home: {e}")
        return jsonify({"error": str(e)}), 500

def run():
    port = int(os.environ.get("PORT", 10000))
    serve(app, host='0.0.0.0', port=port, threads=4)

def keep_alive(bot_instance=None):
    global bot
    if bot_instance:
        bot = bot_instance
    thread = Thread(target=run, daemon=True)
    thread.start()
    logger.info("✅ Servidor web iniciado")
    return thread
