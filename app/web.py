# app/web.py
from flask import request, jsonify
import logging
from database import Database
import requests
import asyncio
import discord
import os
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
db = Database()

LOGIN_URL = "https://naerzone.com/start.php?login=ini"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Origin': 'https://naerzone.com',
    'Referer': 'https://naerzone.com/login.php',
}

BOT_TOKEN = os.environ.get('DISCORD_TOKEN')
chile_tz = pytz.timezone('America/Santiago')

def verificar_credenciales_naerzone(usuario, password):
    """Verifica credenciales con Naerzone - VERSIÓN CON LOGS"""
    try:
        logger.info(f"🔐 VERIFICANDO CREDENCIALES - Usuario: '{usuario}'")
        
        session = requests.Session()
        
        # Paso 1: Obtener cookies
        login_page = session.get('https://naerzone.com/login.php', headers=HEADERS, timeout=10)
        logger.info(f"📡 GET login.php - Status: {login_page.status_code}")
        
        # Paso 2: Enviar credenciales
        payload = {'nombre': usuario, 'password': password}
        logger.info(f"📤 POST a {LOGIN_URL}")
        
        response = session.post(LOGIN_URL, data=payload, headers=HEADERS, timeout=10)
        logger.info(f"📥 Respuesta: '{response.text}' (Status: {response.status_code})")
        
        return response.text == "OK"
        
    except requests.Timeout:
        logger.error("⏰ TIMEOUT - El servidor de Naerzone no respondió")
        return False
    except requests.ConnectionError as e:
        logger.error(f"🔌 ERROR DE CONEXIÓN: {e}")
        return False
    except Exception as e:
        logger.error(f"💥 ERROR INESPERADO: {e}")
        return False

async def obtener_canales_discord(guild_id):
    try:
        if not BOT_TOKEN:
            logger.error("❌ No hay token de bot configurado")
            return []
        logger.info(f"🔍 Obteniendo canales para guild: {guild_id}")
        intents = discord.Intents.default()
        intents.guilds = True
        client = discord.Client(intents=intents)
        await client.login(BOT_TOKEN)
        guild = await client.fetch_guild(int(guild_id))
        if not guild:
            await client.close()
            return []
        canales = await guild.fetch_channels()
        canales_texto = []
        for canal in canales:
            if isinstance(canal, discord.TextChannel):
                canales_texto.append({
                    'id': str(canal.id),
                    'name': canal.name,
                    'position': canal.position
                })
        await client.close()
        canales_texto.sort(key=lambda x: x['position'])
        return canales_texto
    except Exception as e:
        logger.error(f"Error obteniendo canales: {e}")
        return []

def init_api_routes(app):
    
    @app.route('/api/verificar-credenciales', methods=['POST'])
    def api_verificar():
        data = request.json
        usuario = data.get('usuario')
        password = data.get('password')
        
        logger.info(f"📩 API VERIFICAR - Usuario: {usuario}")
        
        if not usuario or not password:
            logger.error("   Faltan datos")
            return jsonify({'valido': False, 'error': 'Faltan datos'})
        
        valido = verificar_credenciales_naerzone(usuario, password)
        logger.info(f"   Resultado: {valido}")
        
        return jsonify({'valido': valido})
    
    @app.route('/api/guardar-credenciales', methods=['POST'])
    def api_guardar_credenciales():
        data = request.json
        guild_id = data.get('guild_id')
        guild_name = data.get('guild_name', 'Servidor')
        usuario = data.get('usuario')
        password = data.get('password')
        
        logger.info(f"📩 API GUARDAR CREDENCIALES - guild: {guild_id}, usuario: {usuario}")
        
        if not guild_id or not usuario:
            return jsonify({'exito': False, 'error': 'Faltan datos'})
        
        # Verificar credenciales con Naerzone
        if password and not verificar_credenciales_naerzone(usuario, password):
            logger.error("   ❌ Credenciales inválidas según Naerzone")
            return jsonify({'exito': False, 'error': 'Credenciales inválidas'})
        
        logger.info("   ✅ Credenciales válidas, guardando en Supabase...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        resultado = loop.run_until_complete(
            db.guardar_credenciales(guild_id, guild_name, usuario, password)
        )
        loop.close()
        
        logger.info(f"   Resultado guardado: {resultado}")
        return jsonify({'exito': resultado})
    
    @app.route('/api/guardar-config', methods=['POST'])
    def api_guardar_config():
        data = request.json
        guild_id = data.get('guild_id')
        canal_id = data.get('canal_id')
        hora = data.get('hora', 22)
        minuto = data.get('minuto', 0)
        mensaje = data.get('mensaje_personalizado')
        
        hora_actual = datetime.now(chile_tz).strftime('%H:%M:%S')
        logger.info(f"🔥 RECIBIDA PETICIÓN DE GUARDAR CONFIG a las {hora_actual} para guild {guild_id}")
        
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
            db.guardar_config(guild_id, canal_id, '', hora, minuto, mensaje)
        )
        
        if resultado:
            logger.info(f"✅ Configuración guardada para {guild_id}")
            try:
                from keep_alive import bot
                if bot:
                    asyncio.run_coroutine_threadsafe(
                        bot.reprogramar_ahora(guild_id),
                        bot.loop
                    )
                    logger.info(f"⚡ Tarea de reprogramación INMEDIATA enviada para {guild_id}")
                else:
                    logger.warning("⚠️ Bot no disponible para reprogramar")
            except Exception as e:
                logger.error(f"❌ Error en reprogramación: {e}")
        else:
            logger.error(f"❌ Falló el guardado para {guild_id}")
        
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
