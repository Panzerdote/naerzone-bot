from flask import Flask
from threading import Thread
import logging

app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot de Naerzone activo"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
    logging.info("🌐 Servidor web iniciado en puerto 8080")
