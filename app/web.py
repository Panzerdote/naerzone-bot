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

# ==================== FUNCIONES AUXILIARES ====================

def verificar_credenciales_naerzone(usuario, password):
    """Verifica credenciales con Naerzone"""
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
        
        intents = discord.Intents.default()
        intents.guilds = True
        client = discord.Client(intents=intents)
        
        await client.login(BOT_TOKEN)
        
        # Intentar obtener el servidor desde caché primero
        guild = client.get_guild(int(guild_id))
        
        # Si no está en caché, usar fetch_guild con with_counts para forzar carga de canales
        if not guild:
            logger.info(f"⚠️ {guild_id} no está en caché, usando fetch_guild")
            guild = await client.fetch_guild(int(guild_id), with_counts=True)
        
        if not guild:
            logger.error(f"❌ No se pudo obtener el gremio {guild_id}")
            await client.close()
            return []
        
        logger.info(f"✅ Gremio obtenido: {guild.name} (ID: {guild.id})")
        
        # Listar todos los canales (para depuración)
        logger.info(f"📋 Canales en el gremio (todos los tipos):")
        canales_texto = []
        for canal in guild.channels:
            logger.info(f"   - #{canal.name} (ID: {canal.id}, Tipo: {canal.type})")
            if isinstance(canal, discord.TextChannel):
                canales_texto.append({
                    'id': str(canal.id),
                    'name': canal.name,
                    'position': canal.position
                })
        
        await client.close()
        
        if not canales_texto:
            logger.warning(f"⚠️ No se encontraron canales de texto en el servidor {guild.name}")
        else:
            logger.info(f"✅ Total canales de texto: {len(canales_texto)}")
        
        # Ordenar por posición
        canales_texto.sort(key=lambda x: x['position'])
        return canales_texto
        
    except discord.LoginFailure:
        logger.error("❌ Token de Discord inválido. Verifica DISCORD_TOKEN en las variables de entorno.")
        return []
    except discord.Forbidden:
        logger.error(f"❌ El bot no tiene permisos para ver los canales del servidor {guild_id}")
        return []
    except discord.NotFound:
        logger.error(f"❌ El servidor {guild_id} no existe o el bot no está en él")
        return []
    except Exception as e:
        logger.error(f"❌ Error general obteniendo canales: {e}")
        return []

# ==================== INICIALIZACIÓN DE RUTAS API ====================

def init_api_routes(app):
    
    @app.route('/api/verificar-credenciales', methods=['POST'])
    def api_verificar():
        """Verifica credenciales de Naerzone"""
        data = request.json
        usuario = data.get('usuario')
        password = data.get('password')
        if not usuario or not password:
            return jsonify({'valido': False, 'error': 'Faltan datos'})
        valido = verificar_credenciales_naerzone(usuario, password)
        return jsonify({'valido': valido})
    
    @app.route('/api/guardar-credenciales', methods=['POST'])
    def api_guardar_credenciales():
        """Guarda credenciales en Supabase"""
        data = request.json
        guild_id = data.get('guild_id')
        guild_name = data.get('guild_name', 'Servidor')
        usuario = data.get('usuario')
        password = data.get('password')
        
        if not guild_id or not usuario:
            return jsonify({'exito': False, 'error': 'Faltan datos'})
        
        # Si hay password, verificamos
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
        """Guarda configuración del bot"""
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
        
        if not canales:
            logger.warning(f"⚠️ No se obtuvieron canales para {guild_id}. Verifica que el bot esté en el servidor y tenga permisos.")
            return jsonify({'canales': [], 'advertencia': 'No se pudieron cargar los canales. Asegúrate de que el bot esté en el servidor y tenga permisos.'})
        
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
