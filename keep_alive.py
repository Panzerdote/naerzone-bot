# keep_alive.py
from flask import Flask, jsonify
from threading import Thread
import logging
import os
import time
import requests

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear aplicación Flask
app = Flask(__name__)

@app.route('/')
def home():
    """Página principal - health check básico"""
    return jsonify({
        "status": "online",
        "service": "Naerzone Bot",
        "message": "✅ Bot activo y funcionando"
    }), 200

@app.route('/health')
def health():
    """Endpoint detallado para health checks"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time(),
        "uptime": "Funcionando 24/7"
    }), 200

@app.route('/ping')
def ping():
    """Endpoint simple para mantener vivo"""
    return "pong", 200

def run():
    """Ejecuta el servidor Flask en el puerto correcto"""
    # Render asigna el puerto automáticamente en la variable PORT
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"🌐 Iniciando servidor web en puerto {port}")
    
    # Ejecutar Flask
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

def keep_alive():
    """Inicia el servidor web en un thread separado"""
    try:
        # Crear y iniciar thread para Flask
        flask_thread = Thread(target=run, daemon=True)
        flask_thread.start()
        logger.info("✅ Thread del servidor web iniciado correctamente")
        return flask_thread
    except Exception as e:
        logger.error(f"❌ Error iniciando servidor web: {e}")
        return None

# Para pruebas locales (si ejecutas este archivo directamente)
if __name__ == "__main__":
    logger.info("🚀 Iniciando servidor web en modo local...")
    run()