# app/web.py
from flask import request, jsonify
import logging
from database import Database
import requests
import asyncio
from datetime import datetime
import pytz
import discord
import os

logger = logging.getLogger(__name__)
db = Database()

LOGIN_URL = "https://naerzone.com/start.php?login=ini"
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://naerzone.com/login.php',
}

# Token del bot para consultar canales
BOT_TOKEN = os.environ.get('DISCORD_TOKEN')

def verificar_credenciales_naerzone(usuario, password):
    """Verifica credenciales con Naerzone"""
    try:
        session = requests.Session()
        session.get('https://naerzone.com/login.php', headers=HEADERS, timeout=10)
        payload = {'nombre': usuario, 'password': password}
        response = session.post(LOGIN_URL, data=payload, headers=HEADERS, timeout=10)
        return response.text == "OK"
    except:
        return False

async def obtener_canales_discord(guild_id):
    """Obtiene los canales de texto de un servidor de Discord"""
    try:
        if not BOT_TOKEN:
            logger.error("❌ No hay token de bot configurado")
            return []
        
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        await client.login(BOT_TOKEN)
        guild = await client.fetch_guild(int(guild_id))
        
        canales = []
        for canal in guild.channels:
            if isinstance(canal, discord.TextChannel):
                canales.append({
                    'id': str(canal.id),
                    'name': canal.name,
                    'position': canal.position
                })
        
        await client.close()
        
        # Ordenar por posición
        canales.sort(key=lambda x: x['position'])
        return canales
    except Exception as e:
        logger.error(f"❌ Error obteniendo canales: {e}")
        return []

def init_api_routes(app):
    
    @app.route('/api/verificar-credenciales', methods=['POST'])
    def api_verificar():
        """Verifica credenciales de Naerzone"""
        data = request.json
        usuario = data.get('usuario')
        password = data.get('password')
        
        if verificar_credenciales_naerzone(usuario, password):
            return jsonify({'valido': True})
        return jsonify({'valido': False, 'error': 'Credenciales inválidas'})
    
    @app.route('/api/guardar-credenciales', methods=['POST'])
    def api_guardar_credenciales():
        """Guarda credenciales en Supabase"""
        data = request.json
        guild_id = data.get('guild_id')
        guild_name = data.get('guild_name', 'Servidor')
        usuario = data.get('usuario')
        password = data.get('password')
        
        if not guild_id:
            return jsonify({'exito': False, 'error': 'Falta guild_id'})
        
        # Si hay password, verificamos
        if password:
            if not verificar_credenciales_naerzone(usuario, password):
                return jsonify({'exito': False, 'error': 'Credenciales inválidas'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        resultado = loop.run_until_complete(
            db.guardar_credenciales(guild_id, guild_name, usuario, password)
        )
        loop.close()
        
        return jsonify({'exito': resultado})
    
    @app.route('/api/guardar-config', methods=['POST'])
    def api_guardar_config():
        """Guarda configuración del bot"""
        data = request.json
        guild_id = data.get('guild_id')
        canal_id = data.get('canal_id')
        canal_nombre = data.get('canal_nombre', '')
        hora = data.get('hora', 22)
        minuto = data.get('minuto', 0)
        mensaje = data.get('mensaje_personalizado')
        
        # Validaciones
        if not guild_id:
            return jsonify({'exito': False, 'error': 'Falta guild_id'})
        
        if not canal_id:
            return jsonify({'exito': False, 'error': 'Falta canal_id'})
        
        try:
            hora = int(hora)
            minuto = int(minuto)
            if hora < 0 or hora > 23 or minuto < 0 or minuto > 59:
                return jsonify({'exito': False, 'error': 'Hora inválida'})
        except:
            return jsonify({'exito': False, 'error': 'Hora inválida'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        resultado = loop.run_until_complete(
            db.guardar_config(guild_id, canal_id, canal_nombre, hora, minuto, mensaje)
        )
        loop.close()
        
        return jsonify({'exito': resultado})
    
    @app.route('/api/obtener-config', methods=['GET'])
    def api_obtener_config():
        """Obtiene configuración de un servidor"""
        guild_id = request.args.get('guild_id')
        if not guild_id:
            return jsonify({'error': 'Falta guild_id'}), 400
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        config = loop.run_until_complete(db.obtener_config(guild_id))
        credenciales = loop.run_until_complete(db.obtener_credenciales(guild_id))
        loop.close()
        
        return jsonify({
            'config': config,
            'credenciales': credenciales
        })
    
    @app.route('/api/canales/<guild_id>', methods=['GET'])
    def api_canales(guild_id):
        """API para obtener canales de un servidor"""
        if not guild_id:
            return jsonify({'error': 'Falta guild_id'}), 400
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        canales = loop.run_until_complete(obtener_canales_discord(guild_id))
        loop.close()
        
        return jsonify({'canales': canales})
