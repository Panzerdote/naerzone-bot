# app/main.py

import os
import sys
import types
import logging
import requests
import re
import json
import asyncio
import time  # <--- NUEVO
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pytz
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View

# ==================== CONFIGURACIÓN DE LOGGING ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Silenciar librerías ruidosas
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("discord.client").setLevel(logging.WARNING)
logging.getLogger("discord.gateway").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("waitress").setLevel(logging.ERROR)
# ===================================================================

# ==================== PATCH AUDIOOP ====================
os.environ["DISCORD_NO_VOICE"] = "true"
os.environ["DISCORD_VOICE_DISABLED"] = "true"

if 'audioop' not in sys.modules:
    audioop_mock = types.ModuleType('audioop')
    def dummy_func(*args, **kwargs):
        if args and len(args) > 0 and isinstance(args[0], bytes):
            return args[0]
        return b''
    
    for func_name in ['add', 'mul', 'lin2lin', 'ratecv', 'tomono', 'tostereo',
                      'findfactor', 'findfit', 'findmax', 'getsample',
                      'lin2adpcm', 'lin2alaw', 'lin2ulaw', 'adpcm2lin',
                      'alaw2lin', 'ulaw2lin', 'reverse', 'cross', 'bias',
                      'downsample', 'find']:
        setattr(audioop_mock, func_name, dummy_func)
    
    sys.modules['audioop'] = audioop_mock
    print("✅ Parche de audioop aplicado correctamente")
# ========================================================

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from keep_alive import keep_alive, app
from web import init_api_routes
init_api_routes(app)
from database import Database

LOGIN_URL = "https://naerzone.com/start.php?login=ini"
CANJES_URL = "https://naerzone.com/canjes/canjes-reino.php?r=t"
BASE_URL = "https://naerzone.com"
IMAGEN_PROMO = "https://naerzone.com/image/canjes/gear-landing-25.jpg"

chile_tz = pytz.timezone('America/Santiago')

# ==================== FUNCIÓN DE LOGIN MEJORADA ====================
def login_web(usuario, password):
    """
    Versión mejorada con headers completos para evitar error 415
    """
    try:
        session = requests.Session()
        
        # Headers COMPLETOS que imitan un navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://naerzone.com',
            'Referer': 'https://naerzone.com/login.php',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'Connection': 'keep-alive',
        }
        
        logger.info(f"🔐 Intentando login para usuario: {usuario}")
        
        # PASO 1: Obtener cookies de la página de login
        login_page = session.get('https://naerzone.com/login.php', headers=headers, timeout=10)
        logger.info(f"📌 Página login cargada: {login_page.status_code}")
        
        # Pequeña pausa para simular comportamiento humano
        time.sleep(1)
        
        # PASO 2: Enviar credenciales
        payload = {'nombre': usuario, 'password': password}
        response = session.post(LOGIN_URL, data=payload, headers=headers, timeout=10)
        
        logger.info(f"📌 Respuesta login: '{response.text}'")
        
        if response.text == "OK":
            logger.info(f"✅ Login exitoso para {usuario}")
            return session, True
        else:
            logger.error(f"❌ Login falló para {usuario}: {response.text}")
            return None, False
            
    except requests.exceptions.Timeout:
        logger.error(f"⏰ Timeout en login para {usuario}")
        return None, False
    except Exception as e:
        logger.error(f"❌ Error en login: {e}")
        return None, False
# ====================================================================

def extraer_icono_wowhead(wowhead_url):
    """Extrae el icono de Wowhead"""
    if not wowhead_url or wowhead_url == "#":
        return None
    
    match = re.search(r'item[=/](\d+)', wowhead_url)
    if not match:
        match = re.search(r'/(\d+)[/\-]', wowhead_url)
        if not match:
            return None
    
    item_id = match.group(1)
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(wowhead_url, headers=headers, timeout=15)
        
        if r.status_code != 200:
            return None
        
        patrones = [
            r'WH\.Gatherer\.addData\(\s*\d+\s*,\s*\d+\s*,\s*({.*?})\s*\)\s*;',
            r'new\s+Listview\(\s*\{\s*template:\s*\'item\',.*?data:\s*({.*?})\s*\}\)',
        ]
        
        json_str = None
        for patron in patrones:
            match_json = re.search(patron, r.text, re.DOTALL)
            if match_json:
                json_str = match_json.group(1)
                break
        
        if not json_str:
            return None
        
        datos = json.loads(json_str)
        icon_name = None
        
        if item_id in datos and 'icon' in datos[item_id]:
            icon_name = datos[item_id]['icon']
        else:
            for key, value in datos.items():
                if isinstance(value, dict) and 'icon' in value:
                    icon_name = value['icon']
                    break
        
        if icon_name:
            return f"https://wow.zamimg.com/images/wow/icons/large/{icon_name}.jpg"
        
        return None
    except Exception as e:
        logger.error(f"Error en icono: {e}")
        return None

def extraer_promocion(session):
    """Extrae la promoción diaria de la página de canjes"""
    try:
        headers_canjes = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://naerzone.com/',
        }
        
        r = session.get(CANJES_URL, headers=headers_canjes, timeout=15)
        
        if r.status_code != 200:
            logger.error(f"Error al cargar canjes: {r.status_code}")
            return None
        
        soup = BeautifulSoup(r.text, 'html.parser')
        promo_div = soup.find('div', class_='gear-store-sidebar')
        
        if not promo_div or not promo_div.find('a', href=re.compile(r'wowhead')):
            logger.warning("No se encontró la promoción diaria")
            return None
        
        p = PromocionDiaria()
        
        # Nombre
        nombre_tag = promo_div.find('h3')
        if nombre_tag:
            p.nombre = nombre_tag.text.strip()
        
        # Precio oferta
        precio_tag = promo_div.find('span', class_='account-id')
        if precio_tag:
            texto = precio_tag.text.strip()
            match = re.search(r'(\d+)\s*créditos', texto)
            if match:
                p.precio_oferta = match.group(1)
            
            desc = precio_tag.find('font', color='green')
            if desc:
                p.descuento = desc.text.strip()
        
        # Precio original
        orig_tag = promo_div.find('span', class_='account-region')
        if orig_tag:
            texto = orig_tag.text.strip()
            match = re.search(r'(\d+)\s*créditos', texto)
            if match:
                p.precio_original = match.group(1)
        
        # Links
        wow_link = promo_div.find('a', href=re.compile(r'wowhead'))
        if wow_link and wow_link.get('href'):
            p.url_wowhead = wow_link['href']
            p.icono_url = extraer_icono_wowhead(p.url_wowhead)
        
        prod_link = promo_div.find('a', href=re.compile(r'canjes-producto\.php'))
        if prod_link and prod_link.get('href'):
            href = prod_link['href']
            if href.startswith('/'):
                p.url_producto = BASE_URL + href
            elif href.startswith('..'):
                p.url_producto = BASE_URL + '/canjes/' + href[3:]
            else:
                p.url_producto = BASE_URL + '/canjes/' + href
        
        return p
        
    except Exception as e:
        logger.error(f"Error extrayendo promoción: {e}")
        return None

class PromocionDiaria:
    def __init__(self):
        self.nombre = "Cargando..."
        self.precio_oferta = "?"
        self.precio_original = "?"
        self.descuento = "?"
        self.url_producto = CANJES_URL
        self.url_wowhead = "#"
        self.icono_url = None
        self.fecha = datetime.now(chile_tz)
    
    def formatear_mensaje(self):
        embed = discord.Embed(
            title="Hoy en descuento",
            color=0x5865F2,
            url=self.url_producto
        )
        
        embed.description = f"**{self.nombre}**"
        embed.add_field(name="Precio original", value=f"~~{self.precio_original} créditos~~", inline=False)
        embed.add_field(name="Descuento", value=f"**{self.descuento}**", inline=True)
        embed.add_field(name="Precio con descuento", value=f"**{self.precio_oferta} créditos**", inline=True)
        
        embed.set_image(url=IMAGEN_PROMO)
        
        if self.icono_url:
            embed.set_thumbnail(url=self.icono_url)
        else:
            embed.set_thumbnail(url=IMAGEN_PROMO)
        
        ahora = datetime.now(chile_tz)
        proximo_envio = ahora.replace(hour=22, minute=0, second=0, microsecond=0)
        
        if ahora >= proximo_envio:
            proximo_envio += timedelta(days=1)
        
        resto = proximo_envio - ahora
        horas = int(resto.total_seconds() // 3600)
        minutos = int((resto.total_seconds() % 3600) // 60)
        
        embed.add_field(name="Próximo descuento en:", value=f"**{horas}h {minutos:02d}min**", inline=False)
        embed.set_footer(text=f"Última vez actualizado: {self.fecha.strftime('%d/%m/%Y a las %H:%M')} hrs.")
        
        return embed
    
    def crear_botones(self):
        view = View()
        view.add_item(Button(label="🛒 Tienda", style=discord.ButtonStyle.primary, url=self.url_producto))
        view.add_item(Button(label="🔗 Ver Item", style=discord.ButtonStyle.link, url=self.url_wowhead))
        return view

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class NaerzoneBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="n!", intents=intents, help_command=None)
        self.db = Database()
        self.tareas_programadas = {}
    
    async def setup_hook(self):
        await self.add_cog(ConfigCog(self))
    
    async def rotar_estado(self):
        mensajes = [
            "🛒 Ofertas diarias",
            "⚙️ Configura en la web",
            "🎁 Promo del día",
        ]
        import itertools
        ciclo = itertools.cycle(mensajes)
        
        while not self.is_closed():
            try:
                mensaje = next(ciclo)
                await self.change_presence(activity=discord.Game(name=mensaje))
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error rotando estado: {e}")
                await asyncio.sleep(60)
    
    async def on_ready(self):
        logger.info(f'🤖 Bot {self.user} conectado a Discord!')
        await self.change_presence(activity=discord.Game(name="n!comandos | Ofertas Naerzone"))
        self.loop.create_task(self.rotar_estado())
        self.loop.create_task(self.programar_envios())
    
    async def on_guild_join(self, guild):
        logger.info(f"✅ Bot añadido al servidor: {guild.name} ({guild.id})")
        await self.db.agregar_servidor_bot(guild.id, guild.name)
        
        canal = guild.system_channel or next(
            (ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), 
            None
        )
        
        if canal:
            base_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://naerzone-bot.onrender.com')
            embed = discord.Embed(
                title="🎉 ¡Gracias por invitarme!",
                description=(
                    "Soy el bot de **Ofertas Naerzone**\n\n"
                    "**IMPORTANTE:** Para funcionar, se requieren credenciales de Naerzone.\n"
                    "-# Te aconsejo crear una cuenta exclusivamente para el bot.\n\n"
                    "📝 **Pasos:**\n"
                    "1️⃣ Ve a la web entregada por el autor y haz clic en 'Dashboard'\n"
                    "2️⃣ Inicia sesión con Discord\n"
                    "3️⃣ Selecciona este servidor y configura:\n"
                    "   • Credenciales de Naerzone\n"
                    "   • Canal de envío\n"
                    "   • Hora de envío\n"
                    "   • Mensaje personalizado\n\n"
                    "Con esto ya tienes el bot funcionando!"
                ),
                color=0x5865F2
            )
            await canal.send(embed=embed)
    
    async def on_guild_remove(self, guild):
        logger.info(f"👋 Bot eliminado del servidor: {guild.name} ({guild.id})")
        await self.db.eliminar_servidor_bot(guild.id)
    
    async def reprogramar_ahora(self, guild_id):
        logger.info(f"⚡ REPROGRAMACIÓN INMEDIATA para servidor {guild_id}")
        
        # Cancelar tarea existente
        tareas_a_eliminar = []
        for task_id, task in self.tareas_programadas.items():
            if str(guild_id) in task_id:
                logger.info(f"Cancelando tarea: {task_id}")
                task.cancel()
                tareas_a_eliminar.append(task_id)
        
        for task_id in tareas_a_eliminar:
            if task_id in self.tareas_programadas:
                del self.tareas_programadas[task_id]
        
        # Obtener la nueva configuración
        config = await self.db.obtener_config(guild_id)
        credenciales = await self.db.obtener_credenciales(guild_id)
        
        if not config or not credenciales:
            logger.warning(f"⚠️ No se puede reprogramar {guild_id}: falta configuración")
            return False
        
        # Calcular próximo envío con NUEVA hora
        ahora = datetime.now(chile_tz)
        proximo = ahora.replace(
            hour=config['hora_envio'],
            minute=config['minuto_envio'],
            second=0, microsecond=0
        )
        
        if ahora >= proximo:
            proximo += timedelta(days=1)
        
        espera = (proximo - ahora).total_seconds()
        if espera < 2:
            espera = 2
            logger.info(f"⚠️ Espera muy corta, ajustando a 2 segundos")
        
        logger.info(f"Nueva hora programada: {proximo.strftime('%H:%M')} (en {espera:.1f} segundos)")
        
        task_id = f"{guild_id}_{proximo.strftime('%Y%m%d_%H%M')}"
        
        async def enviar_con_espera(gid, cid, creds, config, delay, tid):
            await asyncio.sleep(delay)
            logger.info(f"⏰ EJECUTANDO ENVÍO PROGRAMADO para {gid}")
            await enviar_oferta_programada(gid, creds, config)
            if tid in self.tareas_programadas:
                del self.tareas_programadas[tid]
        
        task = asyncio.create_task(
            enviar_con_espera(guild_id, config['canal_id'], credenciales, config, espera, task_id)
        )
        self.tareas_programadas[task_id] = task
        return True
    
    async def programar_envios(self):
        await self.wait_until_ready()
        
        while not self.is_closed():
            try:
                logger.info("🔄 Programando envíos...")
                servidores = await self.db.obtener_servidores_activos()
                
                for server in servidores:
                    try:
                        guild = self.get_guild(int(server['guild_id']))
                        if not guild:
                            continue
                        
                        # Calcular próximo envío
                        ahora = datetime.now(chile_tz)
                        proximo = ahora.replace(
                            hour=server['hora_envio'],
                            minute=server['minuto_envio'],
                            second=0, microsecond=0
                        )
                        
                        if ahora >= proximo:
                            proximo += timedelta(days=1)
                        
                        espera = (proximo - ahora).total_seconds()
                        task_id = f"{server['guild_id']}_{proximo.strftime('%Y%m%d_%H%M')}"
                        
                        if task_id not in self.tareas_programadas:
                            logger.info(f"📅 Programando {guild.name} para {proximo.strftime('%H:%M')} (en {espera:.1f}s)")
                            
                            async def enviar_con_espera(gid, creds, config, delay, tid):
                                await asyncio.sleep(delay)
                                await enviar_oferta_programada(gid, creds, config)
                                if tid in self.tareas_programadas:
                                    del self.tareas_programadas[tid]
                            
                            task = asyncio.create_task(
                                enviar_con_espera(server['guild_id'], server, server, espera, task_id)
                            )
                            self.tareas_programadas[task_id] = task
                    
                    except Exception as e:
                        logger.error(f"Error programando {server['guild_id']}: {e}")
                
                await asyncio.sleep(3600)  # Revisar cada hora
                
            except Exception as e:
                logger.error(f"Error en programación: {e}")
                await asyncio.sleep(60)

async def enviar_oferta_programada(guild_id, credenciales, config):
    """Envía la oferta programada a un servidor"""
    try:
        # Intentar login
        session, login_exitoso = login_web(credenciales['usuario'], credenciales['password'])
        
        if not login_exitoso:
            logger.error(f"❌ Login falló para {guild_id} en envío programado")
            # Podrías enviar un mensaje de error al canal
            return
        
        # Extraer promoción
        promo = extraer_promocion(session)
        
        if not promo:
            logger.error(f"❌ No se pudo extraer promoción para {guild_id}")
            return
        
        # Enviar a Discord
        from keep_alive import bot
        if bot:
            guild = bot.get_guild(int(guild_id))
            if guild:
                canal = guild.get_channel(int(config['canal_id']))
                if canal:
                    # Enviar mensaje personalizado si existe
                    if config.get('mensaje_personalizado'):
                        await canal.send(config['mensaje_personalizado'])
                    
                    # Enviar embed
                    await canal.send(embed=promo.formatear_mensaje(), view=promo.crear_botones())
                    
                    # Registrar envío
                    await bot.db.registrar_envio(guild_id)
                    logger.info(f"✅ Oferta enviada a {guild.name}")
        
    except Exception as e:
        logger.error(f"Error en envío programado: {e}")

class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='promo')
    async def promo(self, ctx):
        """Muestra la promoción actual de Naerzone"""
        await ctx.send("🔍 Buscando oferta del día...")
        
        try:
            # Obtener credenciales del servidor
            credenciales = await self.bot.db.obtener_credenciales(str(ctx.guild.id))
            
            if not credenciales:
                await ctx.send("❌ No hay credenciales configuradas para este servidor. Ve al dashboard y configúralas.")
                return
            
            # Intentar login
            session, login_exitoso = login_web(credenciales['usuario'], credenciales['password'])
            
            if not login_exitoso:
                await ctx.send("⚠️ Error: No se pudo iniciar sesión en Naerzone. Verifica tus credenciales.")
                return
            
            # Extraer promoción
            promo = extraer_promocion(session)
            
            if not promo:
                await ctx.send("❌ No se pudo obtener la oferta del día. Intenta más tarde.")
                return
            
            # Enviar embed
            await ctx.send(embed=promo.formatear_mensaje(), view=promo.crear_botones())
            
        except Exception as e:
            logger.error(f"Error en comando promo: {e}")
            await ctx.send("❌ Ocurrió un error al buscar la oferta.")
    
    @commands.command(name='config')
    async def config(self, ctx):
        """Muestra la configuración actual del bot"""
        config = await self.bot.db.obtener_config(str(ctx.guild.id))
        credenciales = await self.bot.db.obtener_credenciales(str(ctx.guild.id))
        
        embed = discord.Embed(
            title="⚙️ Configuración del bot",
            color=0x5865F2
        )
        
        if credenciales:
            embed.add_field(name="Usuario Naerzone", value=credenciales['usuario'], inline=False)
        else:
            embed.add_field(name="Usuario Naerzone", value="❌ No configurado", inline=False)
        
        if config:
            canal = ctx.guild.get_channel(int(config['canal_id']))
            nombre_canal = f"#{canal.name}" if canal else "Canal no encontrado"
            embed.add_field(name="Canal de envío", value=nombre_canal, inline=False)
            embed.add_field(name="Hora de envío", value=f"{config['hora_envio']:02d}:{config['minuto_envio']:02d} hrs", inline=False)
            if config.get('mensaje_personalizado'):
                embed.add_field(name="Mensaje personalizado", value=config['mensaje_personalizado'], inline=False)
        else:
            embed.add_field(name="Canal y hora", value="❌ No configurado", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='comandos', aliases=['help'])
    async def comandos(self, ctx):
        """Muestra la lista de comandos disponibles"""
        embed = discord.Embed(
            title="📋 Comandos de Naerzone Bot",
            description="Prefijo: `n!`",
            color=0x5865F2
        )
        
        embed.add_field(name="🛒 Promociones", value="`n!promo` - Muestra la oferta del día", inline=False)
        embed.add_field(name="⚙️ Configuración", value="`n!config` - Ver configuración actual", inline=False)
        embed.add_field(name="❓ Ayuda", value="`n!comandos` - Muestra esta ayuda", inline=False)
        embed.add_field(name="🌐 Web", value=f"Dashboard: {os.environ.get('RENDER_EXTERNAL_URL', 'https://naerzone-bot.onrender.com')}", inline=False)
        
        await ctx.send(embed=embed)

if __name__ == "__main__":
    bot = NaerzoneBot()
    keep_alive(bot)
    
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        logger.error("❌ No hay DISCORD_TOKEN configurado")
        sys.exit(1)
    
    bot.run(token)
