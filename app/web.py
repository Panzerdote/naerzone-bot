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
        
        # Configurar intents básicos
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        # Iniciar sesión
        await client.login(BOT_TOKEN)
        
        # Obtener el servidor
        try:
            guild = await client.fetch_guild(int(guild_id))
        except Exception as e:
            logger.error(f"❌ No se pudo obtener el servidor {guild_id}: {e}")
            await client.close()
            return []
        
        # Recopilar canales de texto
        canales = []
        for canal in guild.channels:
            if isinstance(canal, discord.TextChannel):
                canales.append({
                    'id': str(canal.id),
                    'name': canal.name,
                    'position': canal.position
                })
                logger.info(f"   - Canal encontrado: #{canal.name} ({canal.id})")
        
        # Cerrar sesión
        await client.close()
        
        # Ordenar por posición
        canales.sort(key=lambda x: x['position'])
        logger.info(f"✅ Total canales obtenidos para {guild_id}: {len(canales)}")
        
        return canales
        
    except discord.LoginFailure:
        logger.error("❌ Token de Discord inválido")
        return []
    except Exception as e:
        logger.error(f"❌ Error general obteniendo canales: {e}")
        return []

# ==================== INICIALIZACIÓN DE RUTAS API ====================

def init_api_routes(app):
    
    @app.route('/api/verificar-credenciales', methods=['POST'])
    def api_verificar():
        """Verifica credenciales de Naerzone"""
        try:
            data = request.json
            usuario = data.get('usuario')
            password = data.get('password')
            
            if not usuario or not password:
                return jsonify({'valido': False, 'error': 'Faltan datos'})
            
            if verificar_credenciales_naerzone(usuario, password):
                return jsonify({'valido': True})
            return jsonify({'valido': False, 'error': 'Credenciales inválidas'})
        except Exception as e:
            logger.error(f"Error en api_verificar: {e}")
            return jsonify({'valido': False, 'error': str(e)}), 500
    
    @app.route('/api/guardar-credenciales', methods=['POST'])
    def api_guardar_credenciales():
        """Guarda credenciales en Supabase"""
        try:
            data = request.json
            guild_id = data.get('guild_id')
            guild_name = data.get('guild_name', 'Servidor')
            usuario = data.get('usuario')
            password = data.get('password')
            
            if not guild_id:
                return jsonify({'exito': False, 'error': 'Falta guild_id'})
            
            if not usuario:
                return jsonify({'exito': False, 'error': 'Falta usuario'})
            
            # Si hay password nueva, verificamos
            if password:
                if not verificar_credenciales_naerzone(usuario, password):
                    return jsonify({'exito': False, 'error': 'Credenciales inválidas'})
            
            # Guardar en base de datos
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            resultado = loop.run_until_complete(
                db.guardar_credenciales(guild_id, guild_name, usuario, password)
            )
            loop.close()
            
            return jsonify({'exito': resultado})
        except Exception as e:
            logger.error(f"Error en api_guardar_credenciales: {e}")
            return jsonify({'exito': False, 'error': str(e)}), 500
    
    @app.route('/api/guardar-config', methods=['POST'])
    def api_guardar_config():
        """Guarda configuración del bot"""
        try:
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
                    return jsonify({'exito': False, 'error': 'Hora inválida (debe ser 0-23 y 0-59)'})
            except ValueError:
                return jsonify({'exito': False, 'error': 'Hora debe ser número'})
            
            # Guardar en base de datos
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            resultado = loop.run_until_complete(
                db.guardar_config(guild_id, canal_id, canal_nombre, hora, minuto, mensaje)
            )
            loop.close()
            
            return jsonify({'exito': resultado})
        except Exception as e:
            logger.error(f"Error en api_guardar_config: {e}")
            return jsonify({'exito': False, 'error': str(e)}), 500
    
    @app.route('/api/obtener-config', methods=['GET'])
    def api_obtener_config():
        """Obtiene configuración de un servidor"""
        try:
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
        except Exception as e:
            logger.error(f"Error en api_obtener_config: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/canales/<guild_id>', methods=['GET'])
    def api_canales(guild_id):
        """API para obtener canales de un servidor"""
        try:
            if not guild_id:
                return jsonify({'error': 'Falta guild_id'}), 400
            
            logger.info(f"📡 Solicitando canales para guild: {guild_id}")
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            canales = loop.run_until_complete(obtener_canales_discord(guild_id))
            loop.close()
            
            return jsonify({'canales': canales})
        except Exception as e:
            logger.error(f"Error en api_canales: {e}")
            return jsonify({'error': str(e), 'canales': []}), 500
    
    @app.route('/api/test-canales/<guild_id>', methods=['GET'])
    def api_test_canales(guild_id):
        """Endpoint de prueba para verificar la conexión con Discord"""
        try:
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
        except Exception as e:
            return jsonify({'error': str(e)}), 500
