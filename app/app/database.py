# app/database.py
import os
from supabase import create_client
import logging

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.supabase_url = os.environ.get('SUPABASE_URL')
        self.supabase_key = os.environ.get('SUPABASE_KEY')
        
        if not self.supabase_url or not self.supabase_key:
            logger.error("❌ Faltan SUPABASE_URL o SUPABASE_KEY")
            raise Exception("Supabase no configurado")
        
        self.supabase = create_client(self.supabase_url, self.supabase_key)
        self._init_tables()
    
    def _init_tables(self):
        """Crea las tablas si no existen"""
        try:
            # Tabla de usuarios de Naerzone (cada servidor tiene sus credenciales)
            self.supabase.table('credenciales').select('*').limit(1).execute()
        except:
            logger.info("Creando tablas en Supabase...")
            # Las tablas se crean manualmente desde el SQL que te daré después
    
    async def guardar_credenciales(self, guild_id, guild_name, usuario, password):
        """Guarda las credenciales de Naerzone para un servidor"""
        try:
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'usuario': usuario,
                'password': password,  # IMPORTANTE: En producción, esto debería estar encriptado
                'fecha_creacion': 'now()'
            }
            
            # Verificar si ya existe
            existing = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            
            if existing.data:
                # Actualizar
                self.supabase.table('credenciales').update(data).eq('guild_id', str(guild_id)).execute()
            else:
                # Insertar
                self.supabase.table('credenciales').insert(data).execute()
            
            logger.info(f"✅ Credenciales guardadas para {guild_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando credenciales: {e}")
            return False
    
    async def obtener_credenciales(self, guild_id):
        """Obtiene las credenciales de un servidor"""
        try:
            result = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error obteniendo credenciales: {e}")
            return None
    
    async def guardar_config(self, guild_id, canal_id, hora, minuto):
        """Guarda la configuración del bot para un servidor"""
        try:
            data = {
                'guild_id': str(guild_id),
                'canal_id': str(canal_id),
                'hora_envio': hora,
                'minuto_envio': minuto,
                'activo': True
            }
            
            existing = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            
            if existing.data:
                self.supabase.table('configuracion').update(data).eq('guild_id', str(guild_id)).execute()
            else:
                self.supabase.table('configuracion').insert(data).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error guardando config: {e}")
            return False
    
    async def obtener_config(self, guild_id):
        """Obtiene la configuración de un servidor"""
        try:
            result = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error obteniendo config: {e}")
            return None
    
    async def obtener_servidores_activos(self):
        """Obtiene todos los servidores activos con sus credenciales y config"""
        try:
            # Obtener servidores con configuración
            configs = self.supabase.table('configuracion').select('*').eq('activo', True).execute()
            
            resultado = []
            for config in configs.data:
                credenciales = await self.obtener_credenciales(config['guild_id'])
                if credenciales:
                    resultado.append({
                        **config,
                        'usuario': credenciales['usuario'],
                        'password': credenciales['password']
                    })
            
            return resultado
        except Exception as e:
            logger.error(f"Error obteniendo servidores: {e}")
            return []
    
    async def registrar_envio(self, guild_id):
        """Registra que hoy ya se envió la promo"""
        try:
            from datetime import date
            data = {
                'guild_id': str(guild_id),
                'fecha': str(date.today())
            }
            self.supabase.table('envios').insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Error registrando envio: {e}")
            return False
    
    async def ya_se_envio_hoy(self, guild_id):
        """Verifica si ya se envió hoy"""
        try:
            from datetime import date
            result = self.supabase.table('envios').select('*')\
                .eq('guild_id', str(guild_id))\
                .eq('fecha', str(date.today()))\
                .execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error verificando envio: {e}")
            return False