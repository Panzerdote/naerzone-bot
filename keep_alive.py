# keep_alive.py
from flask import Flask
from threading import Thread
import logging
import os

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    """Página principal - health check"""
    return "✅ Bot de Naerzone activo y funcionando", 200

@app.route('/health')
def health():
    """Endpoint para health checks más detallados"""
    return {
        "status": "healthy", 
        "service": "naerzone-bot",
        "message": "Bot operativo"
    }, 200

def run():
    """Ejecuta el servidor Flask en el puerto correcto"""
    port = int(os.environ.get("PORT", 8080))  # Render asigna el puerto automáticamente
    logger.info(f"🌐 Servidor web iniciado en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

def keep_alive():
    """Inicia el servidor web en un thread separado"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
    logger.info("✅ Thread del servidor web iniciado")
