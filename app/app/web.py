# app/web.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import threading
import logging
import os
import secrets
from database import Database
import requests

logger = logging.getLogger(__name__)

# Crear app Flask
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
app.secret_key = secrets.token_hex(16)

# Base de datos
db = Database()

# URLs de Naerzone para verificación
LOGIN_URL = "https://naerzone.com/start.php?login=ini"
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://naerzone.com/login.php',
}

def verificar_credenciales_naerzone(usuario, password):
    """Verifica si las credenciales son válidas en Naerzone"""
    try:
        session_naer = requests.Session()
        session_naer.get('https://naerzone.com/login.php', headers=HEADERS, timeout=10)
        payload = {'nombre': usuario, 'password': password}
        response = session_naer.post(LOGIN_URL, data=payload, headers=HEADERS, timeout=10)
        return response.text == "OK"
    except:
        return False

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/login/<guild_id>')
def login_page(guild_id):
    """Página de login para un servidor específico"""
    return render_template('login.html', guild_id=guild_id)

@app.route('/api/verificar-credenciales', methods=['POST'])
def api_verificar():
    """API para verificar credenciales"""
    data = request.json
    usuario = data.get('usuario')
    password = data.get('password')
    
    if verificar_credenciales_naerzone(usuario, password):
        return jsonify({'valido': True})
    else:
        return jsonify({'valido': False, 'error': 'Credenciales inválidas'})

@app.route('/api/guardar-credenciales', methods=['POST'])
def api_guardar():
    """Guarda las credenciales en la base de datos"""
    data = request.json
    guild_id = data.get('guild_id')
    guild_name = data.get('guild_name', 'Servidor Desconocido')
    usuario = data.get('usuario')
    password = data.get('password')
    
    # Verificar nuevamente por seguridad
    if not verificar_credenciales_naerzone(usuario, password):
        return jsonify({'exito': False, 'error': 'Credenciales inválidas'})
    
    # Guardar en Supabase
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    resultado = loop.run_until_complete(
        db.guardar_credenciales(guild_id, guild_name, usuario, password)
    )
    loop.close()
    
    if resultado:
        return jsonify({'exito': True})
    else:
        return jsonify({'exito': False, 'error': 'Error guardando en base de datos'})

@app.route('/dashboard/<guild_id>')
def dashboard(guild_id):
    """Dashboard de configuración"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    credenciales = loop.run_until_complete(db.obtener_credenciales(guild_id))
    config = loop.run_until_complete(db.obtener_config(guild_id))
    loop.close()
    
    if not credenciales:
        return redirect(url_for('login_page', guild_id=guild_id))
    
    return render_template('dashboard.html', 
                         guild_id=guild_id,
                         credenciales=credenciales,
                         config=config)

@app.route('/api/guardar-config', methods=['POST'])
def api_guardar_config():
    """Guarda la configuración del bot"""
    data = request.json
    guild_id = data.get('guild_id')
    canal_id = data.get('canal_id')
    hora = data.get('hora', 22)
    minuto = data.get('minuto', 0)
    
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    resultado = loop.run_until_complete(
        db.guardar_config(guild_id, canal_id, hora, minuto)
    )
    loop.close()
    
    return jsonify({'exito': resultado})

def run_flask():
    """Ejecuta el servidor Flask"""
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

def start_web_server():
    """Inicia el servidor web en un thread separado"""
    thread = threading.Thread(target=run_flask, daemon=True)
    thread.start()
    logger.info(f"🌐 Servidor web iniciado en puerto {os.environ.get('PORT', 8080)}")