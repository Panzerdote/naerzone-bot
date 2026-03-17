from flask import request, jsonify
import logging
from database import Database
import requests
import asyncio
import discord
import os
from datetime import datetime
import pytz
from bs4 import BeautifulSoup  # <--- NUEVO
import re  # <--- NUEVO
import time  # <--- NUEVO

logger = logging.getLogger(__name__)
db = Database()

LOGIN_URL = "https://naerzone.com/start.php?login=ini"
CANJES_URL = "https://naerzone.com/canjes/canjes-reino.php?r=t"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://naerzone.com/login.php',
}

BOT_TOKEN = os.environ.get('DISCORD_TOKEN')
chile_tz = pytz.timezone('America/Santiago')

def verificar_credenciales_naerzone(usuario, password):
    """
    Copia EXACTA de tu código de Colab que SÍ funciona
    """
    try:
        session = requests.Session()
        
        # Headers IDÉNTICOS a tu Colab
        headers_login = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://naerzone.com/login.php',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        # PASO 1: Obtener cookies iniciales (IGUAL que Colab)
        session.get('https://naerzone.com/login.php', headers=headers_login, timeout=10)
        
        # PASO 2: Enviar credenciales (IGUAL que Colab)
        payload = {'nombre': usuario, 'password': password}
        response = session.post(LOGIN_URL, data=payload, headers=headers_login, timeout=10)
        
        # Verificar respuesta (IGUAL que Colab)
        if response.text != "OK":
            logger.warning(f"❌ Login falló para {usuario}: {response.text}")
            return False
            
        logger.info(f"✅ Login OK para {usuario}, accediendo a canjes...")
        
        # PASO 3: Acceder a página de canjes (IGUAL que Colab)
        headers_canjes = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://naerzone.com/',
        }
        
        # Pequeña pausa para evitar rate limiting
        time.sleep(1)
        
        canjes_response = session.get(CANJES_URL, headers=headers_canjes, timeout=15)
        
        # PASO 4: Verificar que la página se cargó correctamente (IGUAL que Colab)
        if canjes_response.status_code == 200:
            # Analizar con BeautifulSoup como en tu Colab
            soup = BeautifulSoup(canjes_response.text, 'html.parser')
            
            # Buscar el div de promoción diaria
            promocion = soup.find('div', class_='gear-store-sidebar')
            
            # Verificar que contiene enlace a wowhead (señal de que es la página correcta)
            if promocion and promocion.find('a', href=re.compile(r'wowhead')):
                logger.info(f"✅ ¡Verificación COMPLETA exitosa para {usuario}!")
                return True
            else:
                logger.warning(f"⚠️ Login OK pero no se encontró promoción para {usuario}")
                # Verificar si nos redirigió a login
                if "login" in canjes_response.url.lower():
                    logger.warning(f"⚠️ Redirigido a login: {canjes_response.url}")
                return False
        else:
            logger.warning(f"⚠️ No se pudo acceder a canjes: código {canjes_response.status_code}")
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"⏰ Timeout verificando credenciales para {usuario}")
        return False
    except Exception as e:
        logger.error(f"❌ Error verificando credenciales: {e}")
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
        if not usuario or not password:
            return jsonify({'valido': False, 'error': 'Faltan datos'})
        
        logger.info(f"🔐 Verificando credenciales para usuario: {usuario}")
        valido = verificar_credenciales_naerzone(usuario, password)
        
        if valido:
            logger.info(f"✅ Credenciales VÁLIDAS para {usuario}")
        else:
            logger.warning(f"❌ Credenciales INVÁLIDAS para {usuario}")
            
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
        
        # Verificar credenciales solo si se proporcionó nueva contraseña
        if password:
            logger.info(f"🔐 Verificando credenciales NUEVAS para {usuario} en guild {guild_id}")
            if not verificar_credenciales_naerzone(usuario, password):
                logger.warning(f"❌ Credenciales inválidas para {usuario} en guild {guild_id}")
                return jsonify({'exito': False, 'error': 'Credenciales inválidas'})
            logger.info(f"✅ Credenciales válidas para {usuario}, guardando...")
        else:
            logger.info(f"ℹ️ Guardando credenciales SIN cambiar contraseña para {usuario}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        resultado = loop.run_until_complete(
            db.guardar_credenciales(guild_id, guild_name, usuario, password)
        )
        loop.close()
        
        if resultado:
            logger.info(f"✅ Credenciales guardadas exitosamente para guild {guild_id}")
        else:
            logger.error(f"❌ Error al guardar credenciales para guild {guild_id}")
            
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
    
    # ========== RUTA DE DEPURACIÓN TEMPORAL ==========
    @app.route('/api/test-login/<usuario>/<password>', methods=['GET'])
    def test_login(usuario, password):
        """Ruta TEMPORAL para probar login manualmente"""
        resultado = verificar_credenciales_naerzone(usuario, password)
        return jsonify({
            'usuario': usuario,
            'resultado': resultado,
            'mensaje': '✅ Funciona' if resultado else '❌ Falló'
        })
    # =================================================
