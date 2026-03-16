# app/web.py
from flask import request, jsonify
import logging
from database import Database
import requests
import asyncio
import discord
import os

logger = logging.getLogger(__name__)
db = Database()

LOGIN_URL = "https://naerzone.com/start.php?login=ini"
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://naerzone.com/login.php',
}

BOT_TOKEN = os.environ.get('DISCORD_TOKEN')

def verificar_credenciales_naerzone(usuario, password):
    try:
        session = requests.Session()
        session.get('https://naerzone.com/login.php', headers=HEADERS, timeout=10)
        payload = {'nombre': usuario, 'password': password}
        response = session.post(LOGIN_URL, data=payload, headers=HEADERS, timeout=10)
        return response.text == "OK"
    except Exception as e:
        logger.error(f"Error verificando credenciales: {e}")
        return False

async def obtener_canales_discord(guild_id):
    try:
        if not BOT_TOKEN:
            logger.error("❌ No hay token de bot configurado")
            return []
        
        logger.info(f"🔍 Obteniendo canales para guild: {guild_id}")
        
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        await client.login(BOT_TOKEN)
        
        try:
            guild = await client.fetch_guild(int(guild_id))
        except Exception as e:
            logger.error(f"❌ No se pudo obtener el servidor {guild_id}: {e}")
            await client.close()
            return []
        
        canales = []
        for canal in guild.channels:
            if isinstance(canal, discord.TextChannel):
                canales.append({
                    'id': str(canal.id),
                    'name': canal.name,
                    'position': canal.position
                })
                logger.info(f"   - Canal: #{canal.name} ({canal.id})")
        
        await client.close()
        canales.sort(key=lambda x: x['position'])
        logger.info(f"✅ Total canales: {len(canales)}")
        return canales
    except discord.LoginFailure:
        logger.error("❌ Token de Discord inválido")
        return []
    except Exception as e:
        logger.error(f"❌ Error obteniendo canales: {e}")
        return []

def init_api_routes(app):
    
    @app.route('/api/verificar-credenciales', methods=['POST'])
    def api_verificar():
        data = request.json
        usuario = data.get('usuario')
        password = data.get('password')
        if not usuario or not password:
            return jsonify({'valido': False, 'error': 'Faltan datos'})
        valido = verificar_credenciales_naerzone(usuario, password)
        return jsonify({'valido': valido})
    
    @app.route('/api/guardar-credenciales', methods=['POST'])
    def api_guardar_credenciales():
        data = request.json
        guild_id = data.get('guild_id')
        guild_name = data.get('guild_name', 'Servidor')
        usuario = data.get('usuario')
        password = data.get('password')
        
        if not guild_id or not usuario:
            return jsonify({'exito': False, 'error': 'Faltan datos'})
        
        if password and not verificar_credenciales_naerzone(usuario, password):
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
        data = request.json
        guild_id = data.get('guild_id')
        canal_id = data.get('canal_id')
        canal_nombre = data.get('canal_nombre', '')
        hora = data.get('hora', 22)
        minuto = data.get('minuto', 0)
        mensaje = data.get('mensaje_personalizado')
        
        if not guild_id or not canal_id:
            return jsonify({'exito': False, 'error': 'Faltan datos'})
        
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
    
    @app.route('/api/canales/<guild_id>', methods=['GET'])
    def api_canales(guild_id):
        if not guild_id:
            return jsonify({'error': 'Falta guild_id'}), 400
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        canales = loop.run_until_complete(obtener_canales_discord(guild_id))
        loop.close()
        
        return jsonify({'canales': canales})
    
    @app.route('/api/test-canales/<guild_id>', methods=['GET'])
    def api_test_canales(guild_id):
        return jsonify({
            'guild_id': guild_id,
            'token_presente': bool(BOT_TOKEN),
            'token_preview': BOT_TOKEN[:10] + '...' if BOT_TOKEN else None
        })
