# keep_alive.py
from flask import Flask, jsonify, render_template
from threading import Thread
import logging
import os
import time

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear aplicación Flask
app = Flask(__name__, 
            template_folder='templates',  # Carpeta de templates
            static_folder='static')       # Carpeta para CSS (si existe)

# ==================== RUTAS PARA HEALTH CHECKS ====================
@app.route('/health')
def health():
    """Endpoint para health checks de Render"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time()
    }), 200

@app.route('/ping')
def ping():
    """Endpoint simple para mantener vivo"""
    return "pong", 200

# ==================== RUTAS DE LA WEB ====================
@app.route('/')
def home():
    """Página principal - AHORA SIRVE HTML"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error cargando index.html: {e}")
        return jsonify({
            "error": "Error cargando la página",
            "message": str(e)
        }), 500

@app.route('/login/<guild_id>')
def login_page(guild_id):
    """Página de login para un servidor específico"""
    try:
        return render_template('login.html', guild_id=guild_id)
    except Exception as e:
        logger.error(f"Error cargando login.html: {e}")
        return f"Error: {e}", 500

@app.route('/dashboard/<guild_id>')
def dashboard_page(guild_id):
    """Dashboard de configuración"""
    try:
        return render_template('dashboard.html', guild_id=guild_id)
    except Exception as e:
        logger.error(f"Error cargando dashboard.html: {e}")
        return f"Error: {e}", 500

# ==================== API ENDPOINTS ====================
# Aquí van las rutas de API que estaban en web.py
# Las importamos desde web.py para no duplicar código

def run():
    """Ejecuta el servidor Flask"""
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Servidor web iniciado en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    """Inicia el servidor web en un thread separado"""
    try:
        flask_thread = Thread(target=run, daemon=True)
        flask_thread.start()
        logger.info("✅ Thread del servidor web iniciado")
        return flask_thread
    except Exception as e:
        logger.error(f"❌ Error iniciando servidor web: {e}")
        return None
