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
        logger.info("✅ Conectado a Supabase")
    
    # ========== CREDENCIALES ==========
    async def guardar_credenciales(self, guild_id, guild_name, usuario, password):
        try:
            if not guild_id:
                return False
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'usuario': usuario,
            }
            if password:
                data['password'] = password
            existing = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            if existing.data:
                self.supabase.table('credenciales').update(data).eq('guild_id', str(guild_id)).execute()
            else:
                data['password'] = password
                self.supabase.table('credenciales').insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Error guardando credenciales: {e}")
            return False
    
    async def obtener_credenciales(self, guild_id):
        try:
            if not guild_id:
                return None
            result = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error obteniendo credenciales: {e}")
            return None
    
    # ========== CONFIGURACIÓN ==========
    async def guardar_config(self, guild_id, canal_id, canal_nombre, hora, minuto, mensaje=None):
        try:
            if not guild_id or not canal_id:
                return False
            data = {
                'guild_id': str(guild_id),
                'canal_id': str(canal_id),
                'canal_nombre': canal_nombre,
                'hora_envio': hora,
                'minuto_envio': minuto,
                'activo': True,
                'fecha_actualizacion': 'now()'
            }
            if mensaje:
                data['mensaje_personalizado'] = mensaje
            existing = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            if existing.data:
                self.supabase.table('configuracion').update(data).eq('guild_id', str(guild_id)).execute()
            else:
                self.supabase.table('configuracion').insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False
    
    async def obtener_config(self, guild_id):
        try:
            if not guild_id:
                return None
            result = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Error obteniendo configuración: {e}")
            return None
    
    # ========== SERVIDORES DEL BOT ==========
    async def agregar_servidor_bot(self, guild_id, guild_name):
        try:
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'joined_at': 'now()'
            }
            self.supabase.table('bot_guilds').upsert(data, on_conflict='guild_id').execute()
            return True
        except Exception as e:
            logger.error(f"Error agregando servidor: {e}")
            return False
    
    async def eliminar_servidor_bot(self, guild_id):
        try:
            self.supabase.table('bot_guilds').delete().eq('guild_id', str(guild_id)).execute()
            return True
        except Exception as e:
            logger.error(f"Error eliminando servidor: {e}")
            return False
    
    async def obtener_servidores_bot(self):
        try:
            result = self.supabase.table('bot_guilds').select('guild_id').execute()
            return [r['guild_id'] for r in result.data]
        except Exception as e:
            logger.error(f"Error obteniendo servidores: {e}")
            return []
    
    # ========== SERVIDORES ACTIVOS ==========
    async def obtener_servidores_activos(self):
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
            logger.error(f"Error obteniendo servidores activos: {e}")
            return []
    
    # ========== ENVÍOS ==========
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
            logger.error(f"Error registrando envío: {e}")
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
            logger.error(f"Error verificando envío: {e}")
            return False
    
    # ========== NUEVA FUNCIÓN: ELIMINAR TODO ==========
    async def eliminar_todo_servidor(self, guild_id):
        """Elimina TODOS los datos de un servidor (credenciales, config, envios)"""
        try:
            logger.info(f"🗑️ Eliminando todos los datos del servidor {guild_id}")
            
            # Eliminar en orden (primero las que tienen dependencias)
            self.supabase.table('envios').delete().eq('guild_id', str(guild_id)).execute()
            self.supabase.table('configuracion').delete().eq('guild_id', str(guild_id)).execute()
            self.supabase.table('credenciales').delete().eq('guild_id', str(guild_id)).execute()
            
            logger.info(f"✅ Datos eliminados para {guild_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error eliminando datos: {e}")
            return False
