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
                logger.error("❌ guild_id vacío")
                return False
            
            existing = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'usuario': usuario,
            }
            
            if password:
                data['password'] = password
            
            if existing.data:
                self.supabase.table('credenciales').update(data).eq('guild_id', str(guild_id)).execute()
                logger.info(f"✅ Credenciales actualizadas para {guild_id}")
            else:
                data['password'] = password
                self.supabase.table('credenciales').insert(data).execute()
                logger.info(f"✅ Credenciales insertadas para {guild_id}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando credenciales: {e}")
            return False
    
    async def obtener_credenciales(self, guild_id):
        try:
            if not guild_id:
                return None
            result = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Error obteniendo credenciales: {e}")
            return None
    
    # ========== CONFIGURACIÓN ==========
    async def guardar_config(self, guild_id, canal_id, canal_nombre, hora, minuto, mensaje_personalizado=None):
        try:
            logger.info(f"⚙️ Guardando configuración para guild: {guild_id}")
            logger.info(f"   Canal: {canal_nombre} ({canal_id}), Hora: {hora}:{minuto}")
            
            if not guild_id or not canal_id:
                logger.error("❌ Faltan datos")
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
            
            if mensaje_personalizado and mensaje_personalizado.strip():
                data['mensaje_personalizado'] = mensaje_personalizado.strip()
            
            existing = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            
            try:
                if existing.data:
                    self.supabase.table('configuracion').update(data).eq('guild_id', str(guild_id)).execute()
                    logger.info(f"✅ Configuración actualizada para {guild_id}")
                else:
                    self.supabase.table('configuracion').insert(data).execute()
                    logger.info(f"✅ Nueva configuración guardada para {guild_id}")
                return True
            except Exception as e:
                if 'mensaje_personalizado' in str(e):
                    logger.warning("⚠️ Columna mensaje_personalizado no existe, guardando sin ella")
                    if 'mensaje_personalizado' in data:
                        del data['mensaje_personalizado']
                    if existing.data:
                        self.supabase.table('configuracion').update(data).eq('guild_id', str(guild_id)).execute()
                    else:
                        self.supabase.table('configuracion').insert(data).execute()
                    return True
                else:
                    raise e
        except Exception as e:
            logger.error(f"❌ Error guardando configuración: {e}")
            return False
    
    async def obtener_config(self, guild_id):
        try:
            if not guild_id:
                return None
            result = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Error obteniendo configuración: {e}")
            return None
    
    # ========== SERVIDORES DONDE ESTÁ EL BOT (NUEVO) ==========
    async def agregar_servidor_bot(self, guild_id, guild_name):
        """Registra un servidor donde el bot ha sido invitado"""
        try:
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'joined_at': 'now()'
            }
            # Usar upsert para evitar duplicados
            self.supabase.table('bot_guilds').upsert(data, on_conflict='guild_id').execute()
            logger.info(f"✅ Servidor {guild_name} ({guild_id}) registrado en bot_guilds")
            return True
        except Exception as e:
            logger.error(f"❌ Error registrando servidor del bot: {e}")
            return False
    
    async def eliminar_servidor_bot(self, guild_id):
        """Elimina un servidor cuando el bot es expulsado"""
        try:
            self.supabase.table('bot_guilds').delete().eq('guild_id', str(guild_id)).execute()
            logger.info(f"✅ Servidor {guild_id} eliminado de bot_guilds")
            return True
        except Exception as e:
            logger.error(f"❌ Error eliminando servidor del bot: {e}")
            return False
    
    async def obtener_servidores_bot(self):
        """Devuelve lista de guild_id donde el bot está presente"""
        try:
            result = self.supabase.table('bot_guilds').select('guild_id').execute()
            return [r['guild_id'] for r in result.data]
        except Exception as e:
            logger.error(f"❌ Error obteniendo servidores del bot: {e}")
            return []
    
    # ========== SERVIDORES ACTIVOS (para envíos) ==========
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
            logger.error(f"❌ Error obteniendo servidores activos: {e}")
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
            logger.error(f"❌ Error registrando envío: {e}")
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
            logger.error(f"❌ Error verificando envío: {e}")
            return False
