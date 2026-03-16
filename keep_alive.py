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
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://naerzone.com/login.php',
}

BOT_TOKEN = os.environ.get('DISCORD_TOKEN')
chile_tz = pytz.timezone('America/Santiago')

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
        intents.guilds = True
        client = discord.Client(intents=intents)
        
        await client.login(BOT_TOKEN)
        
        guild = await client.fetch_guild(int(guild_id))
        if not guild:
            logger.error(f"❌ No se pudo obtener el gremio {guild_id}")
            await client.close()
            return []
        
        logger.info(f"✅ Gremio obtenido: {guild.name} (ID: {guild.id})")
        
        logger.info(f"📡 Solicitando canales vía fetch_channels()...")
        canales = await guild.fetch_channels()
        
        logger.info(f"📋 Canales encontrados: {len(canales)}")
        
        canales_texto = []
        for canal in canales:
            if isinstance(canal, discord.TextChannel):
                canales_texto.append({
                    'id': str(canal.id),
                    'name': canal.name,
                    'position': canal.position
                })
                logger.info(f"   - #{canal.name} (ID: {canal.id}, Tipo: {canal.type})")
        
        await client.close()
        
        if not canales_texto:
            logger.warning(f"⚠️ No se encontraron canales de texto en el servidor {guild.name}")
        else:
            logger.info(f"✅ Total canales de texto: {len(canales_texto)}")
        
        canales_texto.sort(key=lambda x: x['position'])
        return canales_texto
        
    except discord.Forbidden:
        logger.error(f"❌ El bot no tiene permisos para ver los canales del servidor {guild_id}")
        return []
    except discord.NotFound:
        logger.error(f"❌ El servidor {guild_id} no existe o el bot no está en él")
        return []
    except discord.LoginFailure:
        logger.error("❌ Token de Discord inválido")
        return []
    except Exception as e:
        logger.error(f"❌ Error general obteniendo canales: {e}")
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
        hora = data.get('hora', 22)
        minuto = data.get('minuto', 0)
        mensaje = data.get('mensaje_personalizado')
        
        hora_actual = datetime.now(chile_tz).strftime('%H:%M:%S')
        logger.info(f"🔥🔥🔥 RECIBIDA PETICIÓN DE GUARDAR CONFIG a las {hora_actual} para guild {guild_id}")
        logger.info(f"   Datos: canal={canal_id}, hora={hora}:{minuto}, mensaje={mensaje}")
        
        if not guild_id or not canal_id:
            logger.error("❌ Faltan datos obligatorios")
            return jsonify({'exito': False, 'error': 'Faltan datos'})
        
        try:
            hora = int(hora)
            minuto = int(minuto)
            if hora < 0 or hora > 23 or minuto < 0 or minuto > 59:
                logger.error(f"❌ Hora inválida: {hora}:{minuto}")
                return jsonify({'exito': False, 'error': 'Hora inválida'})
        except:
            logger.error(f"❌ Hora no numérica: {hora}:{minuto}")
            return jsonify({'exito': False, 'error': 'Hora inválida'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        logger.info("💾 Guardando en base de datos...")
        resultado = loop.run_until_complete(
            db.guardar_config(guild_id, canal_id, '', hora, minuto, mensaje)
        )
        
        if resultado:
            logger.info(f"✅✅✅ Configuración GUARDADA CORRECTAMENTE para {guild_id}")
            try:
                from keep_alive import reprogramar_servidor
                logger.info(f"🔄 LLAMANDO A reprogramar_servidor({guild_id})...")
                loop.run_until_complete(reprogramar_servidor(guild_id))
                logger.info(f"🔄✅ reprogramar_servidor ejecutado correctamente")
            except Exception as e:
                logger.error(f"❌❌❌ Error reprogramando: {e}")
        else:
            logger.error(f"❌❌❌ Falló el guardado en base de datos para {guild_id}")
        
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
        
        if not canales:
            return jsonify({'canales': [], 'advertencia': 'No se pudieron cargar los canales. Verifica permisos.'})
        
        return jsonify({'canales': canales})
    
    @app.route('/api/test-canales/<guild_id>', methods=['GET'])
    def api_test_canales(guild_id):
        return jsonify({
            'guild_id': guild_id,
            'token_presente': bool(BOT_TOKEN),
            'token_preview': BOT_TOKEN[:10] + '...' if BOT_TOKEN else None
        })
