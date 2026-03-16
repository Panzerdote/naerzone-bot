# ==================== PATCH DE AUDIOOP (DEBE IR AL PRINCIPIO) ====================
# Este parche debe ejecutarse ANTES de que cualquier otro módulo intente importar audioop
import os
import sys
import types

# Configurar variables de entorno para deshabilitar voice (opcional pero recomendado)
os.environ["DISCORD_NO_VOICE"] = "true"
os.environ["DISCORD_VOICE_DISABLED"] = "true"

# Crear un mock completo de audioop si no existe
if 'audioop' not in sys.modules:
    audioop_mock = types.ModuleType('audioop')
    
    def dummy_func(*args, **kwargs):
        if args and len(args) > 0 and isinstance(args[0], bytes):
            return args[0]
        return b''
    
    # Lista completa de funciones que audioop solía tener
    for func_name in ['add', 'mul', 'lin2lin', 'ratecv', 'tomono', 'tostereo',
                      'findfactor', 'findfit', 'findmax', 'getsample',
                      'lin2adpcm', 'lin2alaw', 'lin2ulaw', 'adpcm2lin',
                      'alaw2lin', 'ulaw2lin', 'reverse', 'cross', 'bias',
                      'downsample', 'find']:
        setattr(audioop_mock, func_name, dummy_func)
    
    sys.modules['audioop'] = audioop_mock
    print("✅ Parche de audioop aplicado correctamente en main.py")
# =================================================================================

import logging
import requests
import re
import json
import asyncio
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pytz
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== RESTO DE IMPORTACIONES ====================
import sys
import os
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from keep_alive import keep_alive, app
from web import init_api_routes
init_api_routes(app)
logger.info("✅ Rutas API conectadas correctamente")

# Importar database
from database import Database

# URLs fijas
LOGIN_URL = "https://naerzone.com/start.php?login=ini"
CANJES_URL = "https://naerzone.com/canjes/canjes-reino.php?r=t"
BASE_URL = "https://naerzone.com"
IMAGEN_PROMO = "https://naerzone.com/image/canjes/gear-landing-25.jpg"

# Headers para simular navegador
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://naerzone.com/login.php',
    'X-Requested-With': 'XMLHttpRequest'
}

# Zona horaria Chile
chile_tz = pytz.timezone('America/Santiago')

# ==================== FUNCIONES DE WEB SCRAPING ====================
def extraer_icono_wowhead(wowhead_url):
    """Extractor de icono de WoWhead"""
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

def login_web(usuario, password):
    """Login con credenciales específicas"""
    try:
        session = requests.Session()
        session.get('https://naerzone.com/login.php', headers=HEADERS, timeout=10)
        payload = {'nombre': usuario, 'password': password}
        response = session.post(LOGIN_URL, data=payload, headers=HEADERS, timeout=10)
        if response.text == "OK":
            return session, True
        else:
            return None, False
    except Exception as e:
        logger.error(f"Error en login: {e}")
        return None, False

def extraer_promocion(session):
    """Extrae la promoción usando una sesión específica"""
    try:
        headers_canjes = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://naerzone.com/',
        }
        
        r = session.get(CANJES_URL, headers=headers_canjes, timeout=15)
        
        if r.status_code != 200:
            return None
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Buscar el div de promoción diaria
        promo_div = soup.find('div', class_='gear-store-sidebar')
        
        if not promo_div or not promo_div.find('a', href=re.compile(r'wowhead')):
            return None

        p = PromocionDiaria()
        
        # 1. Nombre del producto
        nombre_tag = promo_div.find('h3')
        if nombre_tag:
            p.nombre = nombre_tag.text.strip()

        # 2. Precio con descuento
        precio_tag = promo_div.find('span', class_='account-id')
        if precio_tag:
            texto = precio_tag.text.strip()
            match = re.search(r'(\d+)\s*créditos', texto)
            if match:
                p.precio_oferta = match.group(1)
            
            desc = precio_tag.find('font', color='green')
            if desc:
                p.descuento = desc.text.strip()

        # 3. Precio original
        orig_tag = promo_div.find('span', class_='account-region')
        if orig_tag:
            texto = orig_tag.text.strip()
            match = re.search(r'(\d+)\s*créditos', texto)
            if match:
                p.precio_original = match.group(1)

        # 4. Enlace a Wowhead
        wow_link = promo_div.find('a', href=re.compile(r'wowhead'))
        if wow_link and wow_link.get('href'):
            p.url_wowhead = wow_link['href']
            p.icono_url = extraer_icono_wowhead(p.url_wowhead)

        # 5. Enlace al producto
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
# ================================================================

# ==================== CLASE PROMOCION ====================
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
        """Formato original del mensaje"""
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
        
        # Calcular próximo envío (hora por defecto 22:00)
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
# ========================================================

# ==================== BOT DE DISCORD ====================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class NaerzoneBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="n!", intents=intents, help_command=None)
        self.db = Database()
        self.tareas_programadas = {}  # Diccionario para almacenar tareas programadas
    
    async def setup_hook(self):
        await self.add_cog(ConfigCog(self))
    
    async def on_ready(self):
        logger.info(f'🤖 Bot {self.user} conectado a Discord!')
        await self.change_presence(activity=discord.Game(name="n!comandos | Ofertas Naerzone"))
        # Iniciar tarea de programación
        self.loop.create_task(self.programar_envios())
    
    async def on_guild_join(self, guild):
        """Cuando el bot entra a un servidor nuevo"""
        logger.info(f"✅ Bot añadido al servidor: {guild.name} ({guild.id})")
        await self.db.agregar_servidor_bot(guild.id, guild.name)
        
        # Buscar canal adecuado
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
                    "**IMPORTANTE:** Para funcionar, necesito tus credenciales de Naerzone.\n\n"
                    "🌐 **Ve a la web de configuración:**\n"
                    f"```\n{base_url}\n```\n\n"
                    "📝 **Pasos:**\n"
                    "1️⃣ Ve a la web y haz clic en 'Dashboard'\n"
                    "2️⃣ Inicia sesión con Discord\n"
                    "3️⃣ Selecciona este servidor y configura:\n"
                    "   • Credenciales de Naerzone\n"
                    "   • Canal de envío\n"
                    "   • Hora de envío\n"
                    "   • Mensaje personalizado (opcional)\n\n"
                    "📌 **Comandos disponibles:**\n"
                    "`n!comandos` - Ver todos los comandos\n"
                    "`n!promo` - Ver oferta manualmente"
                ),
                color=0x5865F2
            )
            await canal.send(embed=embed)
    
    async def on_guild_remove(self, guild):
        """Cuando el bot es expulsado de un servidor"""
        logger.info(f"👋 Bot eliminado del servidor: {guild.name} ({guild.id})")
        await self.db.eliminar_servidor_bot(guild.id)
    
    async def enviar_promocion_servidor(self, guild_id, canal_id, credenciales, config):
        """Envía la promoción usando las credenciales y configuración del servidor"""
        try:
            guild = self.get_guild(int(guild_id))
            if not guild:
                logger.error(f"❌ No se encontró el servidor {guild_id}")
                return
            
            canal = guild.get_channel(int(canal_id))
            if not canal:
                logger.error(f"❌ No se encontró el canal {canal_id} en {guild_id}")
                return
            
            # Verificar permisos
            if not canal.permissions_for(guild.me).send_messages:
                logger.error(f"❌ No tengo permisos en {canal.name}")
                return
            
            # Verificar si ya se envió hoy
            if await self.db.ya_se_envio_hoy(guild_id):
                logger.info(f"⏭️ {guild.name} ya recibió la promo hoy")
                return
            
            # Hacer login con las credenciales del servidor
            session, success = login_web(credenciales['usuario'], credenciales['password'])
            if not success:
                logger.error(f"❌ Login fallido para {guild.name}")
                await canal.send("⚠️ **Error:** No se pudo iniciar sesión en Naerzone con tus credenciales. Por favor, verifica tu usuario y contraseña en la web de configuración.")
                return
            
            # Obtener promoción
            promo = extraer_promocion(session)
            if not promo:
                logger.error(f"❌ No se pudo obtener promoción para {guild.name}")
                return
            
            # Usar mensaje personalizado si existe
            mensaje = config.get('mensaje_personalizado') or "@everyone atentos que tenemos promo, joder."
            await canal.send(mensaje)
            await canal.send(embed=promo.formatear_mensaje(), view=promo.crear_botones())
            
            # Registrar envío
            await self.db.registrar_envio(guild_id)
            logger.info(f"✅ Promo enviada a {guild.name}")
            
        except Exception as e:
            logger.error(f"Error enviando a {guild_id}: {e}")
    
    async def programar_envios(self):
        """Programa los envíos para todos los servidores"""
        await self.wait_until_ready()
        logger.info("📅 Iniciando programación de envíos...")
        
        while not self.is_closed():
            try:
                servidores = await self.db.obtener_servidores_activos()
                logger.info(f"📊 Servidores activos encontrados: {len(servidores)}")
                
                for servidor in servidores:
                    try:
                        ahora = datetime.now(chile_tz)
                        
                        proximo = ahora.replace(
                            hour=servidor.get('hora_envio', 22),
                            minute=servidor.get('minuto_envio', 0),
                            second=0, microsecond=0
                        )
                        
                        if ahora >= proximo:
                            proximo += timedelta(days=1)
                        
                        espera = (proximo - ahora).total_seconds()
                        logger.info(f"   {servidor.get('guild_name', 'Desconocido')}: próximo envío en {espera/3600:.1f}h")
                        
                        if espera < 86400 and espera > 0:
                            task_id = f"{servidor['guild_id']}_{proximo.strftime('%Y%m%d')}"
                            
                            if task_id not in self.tareas_programadas:
                                async def enviar_con_espera(gid, cid, creds, config, delay, tid):
                                    await asyncio.sleep(delay)
                                    await self.enviar_promocion_servidor(gid, cid, creds, config)
                                    if tid in self.tareas_programadas:
                                        del self.tareas_programadas[tid]
                                
                                self.tareas_programadas[task_id] = asyncio.create_task(
                                    enviar_con_espera(
                                        servidor['guild_id'],
                                        servidor['canal_id'],
                                        servidor,
                                        servidor,
                                        espera,
                                        task_id
                                    )
                                )
                                logger.info(f"   ✅ Tarea programada: {task_id}")
                    
                    except Exception as e:
                        logger.error(f"Error programando servidor {servidor.get('guild_id')}: {e}")
                
                # Esperar 1 hora antes de reprogramar
                await asyncio.sleep(3600)
                
            except Exception as e:
                logger.error(f"Error general en programación: {e}")
                await asyncio.sleep(60)

# ==================== COGS ====================
class ConfigCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.group(name="config", invoke_without_command=True)
    async def config(self, ctx):
        """Muestra la configuración actual"""
        config_db = await self.bot.db.obtener_config(ctx.guild.id)
        credenciales = await self.bot.db.obtener_credenciales(ctx.guild.id)
        
        if not config_db or not credenciales:
            await ctx.send("❌ Este servidor no está configurado. Ve a la web para configurar tus credenciales primero.")
            return
        
        embed = discord.Embed(
            title="⚙️ Configuración del Bot",
            color=0x5865F2
        )
        embed.add_field(name="📢 Canal", value=f"<#{config_db['canal_id']}>", inline=False)
        embed.add_field(name="⏰ Hora", value=f"{config_db['hora_envio']:02d}:{config_db['minuto_envio']:02d}", inline=True)
        embed.add_field(name="👤 Usuario Naerzone", value=credenciales['usuario'], inline=True)
        if config_db.get('mensaje_personalizado'):
            embed.add_field(name="💬 Mensaje personalizado", value=config_db['mensaje_personalizado'], inline=False)
        
        await ctx.send(embed=embed)
    
    @config.command(name="canal")
    async def config_canal(self, ctx, canal: discord.TextChannel):
        """Configura el canal para las ofertas"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Solo administradores pueden usar este comando")
            return
        
        credenciales = await self.bot.db.obtener_credenciales(ctx.guild.id)
        if not credenciales:
            await ctx.send("❌ Primero debes configurar tus credenciales en la web.")
            return
        
        config = await self.bot.db.obtener_config(ctx.guild.id) or {}
        
        await self.bot.db.guardar_config(
            ctx.guild.id,
            canal.id,
            canal.name,
            config.get('hora_envio', 22),
            config.get('minuto_envio', 0),
            config.get('mensaje_personalizado')
        )
        
        await ctx.send(f"✅ Canal configurado: {canal.mention}")
    
    @config.command(name="hora")
    async def config_hora(self, ctx, hora: int, minuto: int):
        """Configura la hora de envío"""
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Solo administradores")
            return
        
        if hora < 0 or hora > 23 or minuto < 0 or minuto > 59:
            await ctx.send("❌ Hora inválida. Usa formato 24h (0-23 horas, 0-59 minutos)")
            return
        
        config = await self.bot.db.obtener_config(ctx.guild.id)
        if not config:
            await ctx.send("❌ Primero configura el canal usando `n!config canal #canal`")
            return
        
        await self.bot.db.guardar_config(
            ctx.guild.id,
            config['canal_id'],
            config.get('canal_nombre', ''),
            hora,
            minuto,
            config.get('mensaje_personalizado')
        )
        
        await ctx.send(f"✅ Hora configurada: {hora:02d}:{minuto:02d}")
    
    @commands.command(name="promo")
    async def promo(self, ctx):
        """Muestra la oferta del día (sin @everyone)"""
        credenciales = await self.bot.db.obtener_credenciales(ctx.guild.id)
        if not credenciales:
            await ctx.send("❌ Primero configura tus credenciales en la web")
            return
        
        session, success = login_web(credenciales['usuario'], credenciales['password'])
        if not success:
            await ctx.send("❌ Error de login con tus credenciales. Verifica en la web.")
            return
        
        promo = extraer_promocion(session)
        if promo:
            await ctx.send(embed=promo.formatear_mensaje(), view=promo.crear_botones())
        else:
            await ctx.send("❌ No se pudo obtener la promoción de Naerzone")
    
    @commands.command(name="comandos")
    async def comandos(self, ctx):
        """Muestra la lista de comandos disponibles"""
        embed = discord.Embed(
            title="📚 Comandos del Bot",
            description="Bot de ofertas diarias de Naerzone",
            color=0x5865F2
        )
        
        embed.add_field(
            name="⚙️ Configuración (Admin)",
            value="`n!config` - Ver configuración actual\n"
                  "`n!config canal #canal` - Elegir canal de ofertas\n"
                  "`n!config hora HH MM` - Ajustar hora de envío",
            inline=False
        )
        
        embed.add_field(
            name="🛒 Promociones",
            value="`n!promo` - Ver oferta del día (manual)",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Información",
            value="`n!comandos` - Mostrar esta ayuda",
            inline=False
        )
        
        embed.set_footer(text="Creado para la comunidad de Naerzone")
        
        await ctx.send(embed=embed)
# ========================================================

# ==================== INICIO DEL BOT ====================
if __name__ == "__main__":
    # Verificar token
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        logger.error("❌ FALTA DISCORD_TOKEN en variables de entorno")
        sys.exit(1)
    
    logger.info("🚀 Iniciando bot de Discord...")
    bot = NaerzoneBot()
    
    # Pasar el bot a keep_alive ANTES de iniciar (para reprogramación)
    from keep_alive import keep_alive
    keep_alive(bot)
    
    logger.info("🤖 Conectando bot a Discord...")
    bot.run(token)
# ========================================================
