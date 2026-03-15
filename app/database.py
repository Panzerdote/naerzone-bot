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
            logger.error("Faltan SUPABASE_URL o SUPABASE_KEY")
            raise Exception("Supabase no configurado")
        
        self.supabase = create_client(self.supabase_url, self.supabase_key)
        logger.info("✅ Conectado a Supabase")
    
    async def guardar_credenciales(self, guild_id, guild_name, usuario, password):
        try:
            if not guild_id:
                logger.error("guild_id vacío")
                return False
            
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'usuario': usuario,
                'password': password
            }
            
            existing = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            
            if existing.data:
                self.supabase.table('credenciales').update(data).eq('guild_id', str(guild_id)).execute()
                logger.info(f"Actualizado {guild_id}")
            else:
                self.supabase.table('credenciales').insert(data).execute()
                logger.info(f"Insertado {guild_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error guardando: {e}")
            return False
    
    async def obtener_credenciales(self, guild_id):
        try:
            if not guild_id:
                return None
            
            result = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error obteniendo: {e}")
            return None
    
    async def guardar_config(self, guild_id, canal_id, canal_nombre, hora, minuto, mensaje_personalizado=None):
        """Guarda la configuración del bot para un servidor"""
        try:
            logger.info(f"⚙️ Guardando configuración para guild: {guild_id}")
            logger.info(f"   Canal: {canal_nombre} ({canal_id}), Hora: {hora}:{minuto}")
            
            if not guild_id:
                logger.error("❌ ERROR: guild_id está vacío")
                return False
            
            data = {
                'guild_id': str(guild_id),
                'canal_id': str(canal_id),
                'canal_nombre': canal_nombre,
                'hora_envio': hora,
                'minuto_envio': minuto,
                'mensaje_personalizado': mensaje_personalizado,
                'activo': True,
                'fecha_actualizacion': 'now()'
            }
            
            existing = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            
            if existing.data:
                self.supabase.table('configuracion').update(data).eq('guild_id', str(guild_id)).execute()
                logger.info(f"✅ Configuración actualizada para {guild_id}")
            else:
                self.supabase.table('configuracion').insert(data).execute()
                logger.info(f"✅ Nueva configuración guardada para {guild_id}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando config: {e}")
            return False
    
    async def obtener_config(self, guild_id):
        """Obtiene la configuración de un servidor"""
        try:
            if not guild_id:
                return None
            
            result = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error obteniendo config: {e}")
            return None
    
    async def obtener_servidores_activos(self):
        """Obtiene todos los servidores activos con sus credenciales y config"""
        try:
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
        try:
            from datetime import date
            data = {
                'guild_id': str(guild_id),
                'fecha': str(date.today())
            }
            self.supabase.table('envios').insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    async def ya_se_envio_hoy(self, guild_id):
        try:
            from datetime import date
            result = self.supabase.table('envios').select('*')\
                .eq('guild_id', str(guild_id))\
                .eq('fecha', str(date.today()))\
                .execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
