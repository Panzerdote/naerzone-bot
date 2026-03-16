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
    """Obtiene los canales de texto de un servidor de Discord usando el token del bot"""
    try:
        if not BOT_TOKEN:
            logger.error("❌ No hay token de bot configurado en variables de entorno")
            return []
        
        logger.info(f"🔍 Obteniendo canales para guild: {guild_id}")
        
        # Configurar intents (necesario para acceder a miembros y canales)
        intents = discord.Intents.default()
        intents.guilds = True  # Asegurar que podemos acceder a los gremios
        client = discord.Client(intents=intents)
        
        await client.login(BOT_TOKEN)
        
        try:
            # Intentar obtener el gremio (servidor)
            guild = await client.fetch_guild(int(guild_id))
            if not guild:
                logger.error(f"❌ No se pudo obtener el gremio {guild_id}: fetch_guild devolvió None")
                await client.close()
                return []
            
            logger.info(f"✅ Gremio obtenido: {guild.name} (ID: {guild.id})")
            
            # Obtener canales (puede ser lento, pero necesario)
            # A veces fetch_guild no trae todos los canales, usamos guild.channels después de estar en caché
            # Para asegurar, podemos hacer fetch de los canales explícitamente, pero no hay un método directo.
            # En su lugar, esperamos un poco para que el caché se llene o usamos guild.fetch_channels()
            # Pero discord.py no tiene fetch_channels. Mejor usar guild.channels después de que el bot tenga la información.
            # Una alternativa es usar REST API directamente, pero es más complejo.
            # Asumimos que después de fetch_guild, los canales están disponibles.
            
            canales = []
            for canal in guild.channels:
                if isinstance(canal, discord.TextChannel):
                    canales.append({
                        'id': str(canal.id),
                        'name': canal.name,
                        'position': canal.position
                    })
                    logger.info(f"   - Canal encontrado: #{canal.name} ({canal.id})")
            
            await client.close()
            
            # Ordenar por posición
            canales.sort(key=lambda x: x['position'])
            logger.info(f"✅ Total canales obtenidos: {len(canales)}")
            return canales
            
        except discord.Forbidden:
            logger.error(f"❌ El bot no tiene permisos para ver los canales del servidor {guild_id}")
            await client.close()
            return []
        except discord.NotFound:
            logger.error(f"❌ El servidor {guild_id} no existe o el bot no está en él")
            await client.close()
            return []
        except Exception as e:
            logger.error(f"❌ Error al procesar el servidor {guild_id}: {e}")
            await client.close()
            return []
            
    except discord.LoginFailure:
        logger.error("❌ Token de Discord inválido. Verifica DISCORD_TOKEN en las variables de entorno.")
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
        """API para obtener canales de un servidor"""
        if not guild_id:
            return jsonify({'error': 'Falta guild_id'}), 400
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        canales = loop.run_until_complete(obtener_canales_discord(guild_id))
        loop.close()
        
        # Si no se obtuvieron canales, devolver lista vacía pero con mensaje de advertencia
        if not canales:
            logger.warning(f"⚠️ No se obtuvieron canales para {guild_id}. Verifica que el bot esté en el servidor y tenga permisos.")
            return jsonify({'canales': [], 'advertencia': 'No se pudieron cargar los canales. Asegúrate de que el bot esté en el servidor.'})
        
        return jsonify({'canales': canales})
    
    @app.route('/api/test-canales/<guild_id>', methods=['GET'])
    def api_test_canales(guild_id):
        """Endpoint de prueba para verificar la conexión con Discord"""
        if not BOT_TOKEN:
            return jsonify({
                'error': 'No hay DISCORD_TOKEN configurado',
                'token_presente': False
            }), 400
        
        return jsonify({
            'mensaje': 'Endpoint funcionando',
            'guild_id': guild_id,
            'token_presente': True,
            'token_preview': BOT_TOKEN[:10] + '...' if BOT_TOKEN else None
        })
