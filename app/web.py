from flask import request, jsonify
import logging
from database import Database
import asyncio
import discord
import os
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
db = Database()

BOT_TOKEN = os.environ.get('DISCORD_TOKEN')
chile_tz = pytz.timezone('America/Santiago')

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
    
    @app.route('/api/guardar-credenciales', methods=['POST'])
    def api_guardar_credenciales():
        data = request.json
        guild_id = data.get('guild_id')
        guild_name = data.get('guild_name', 'Servidor')
        usuario = data.get('usuario')
        password = data.get('password')
        
        if not guild_id or not usuario:
            return jsonify({'exito': False, 'error': 'Faltan datos'})
        
        # 🎯 YA NO VERIFICAMOS - Solo guardamos
        logger.info(f"📝 Guardando credenciales para {usuario} en guild {guild_id}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        resultado = loop.run_until_complete(
            db.guardar_credenciales(guild_id, guild_name, usuario, password)
        )
        loop.close()
        
        if resultado:
            logger.info(f"✅ Credenciales guardadas para guild {guild_id}")
        else:
            logger.error(f"❌ Error al guardar credenciales para guild {guild_id}")
            
        return jsonify({'exito': resultado, 'mensaje': 'Credenciales guardadas (el bot verificará al usarlas)'})
    
    @app.route('/api/guardar-config', methods=['POST'])
    def api_guardar_config():
        data = request.json
        guild_id = data.get('guild_id')
        canal_id = data.get('canal_id')
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
                    logger.info(f"⚡ Reprogramación enviada para {guild_id}")
                else:
                    logger.warning("⚠️ Bot no disponible")
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
