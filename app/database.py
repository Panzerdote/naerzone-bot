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
        
        logger.info(f"🔌 Conectando a Supabase: {self.supabase_url}")
        self.supabase = create_client(self.supabase_url, self.supabase_key)
        logger.info("✅ Conexión a Supabase exitosa")
    
    async def guardar_credenciales(self, guild_id, guild_name, usuario, password):
        """Guarda las credenciales de Naerzone para un servidor"""
        try:
            logger.info(f"💾 Intentando guardar credenciales para guild: {guild_id} - {guild_name}")
            logger.info(f"   Usuario: {usuario}")
            
            if not guild_id:
                logger.error("❌ ERROR CRÍTICO: guild_id está vacío")
                return False
            
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'usuario': usuario,
                'password': password,
                'fecha_creacion': 'now()'
            }
            
            # Verificar si ya existe
            logger.info(f"🔍 Verificando si ya existen credenciales para guild {guild_id}")
            existing = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            
            if existing.data:
                logger.info(f"🔄 Actualizando credenciales existentes para {guild_id}")
                result = self.supabase.table('credenciales').update(data).eq('guild_id', str(guild_id)).execute()
                logger.info(f"✅ Credenciales actualizadas para {guild_name} (ID: {guild_id})")
            else:
                logger.info(f"🆕 Insertando nuevas credenciales para {guild_id}")
                result = self.supabase.table('credenciales').insert(data).execute()
                logger.info(f"✅ Nuevas credenciales guardadas para {guild_name} (ID: {guild_id})")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando credenciales: {e}")
            return False
    
    async def obtener_credenciales(self, guild_id):
        """Obtiene las credenciales de un servidor"""
        try:
            logger.info(f"🔍 Buscando credenciales para guild: {guild_id}")
            
            if not guild_id:
                logger.error("❌ ERROR: guild_id está vacío en obtener_credenciales")
                return None
            
            result = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            
            if result.data:
                logger.info(f"✅ Credenciales encontradas para {guild_id}")
                return result.data[0]
            else:
                logger.warning(f"⚠️ No se encontraron credenciales para {guild_id}")
                return None
        except Exception as e:
            logger.error(f"❌ Error obteniendo credenciales: {e}")
            return None
    
    async def guardar_config(self, guild_id, canal_id, hora, minuto):
        """Guarda la configuración del bot para un servidor"""
        try:
            logger.info(f"⚙️ Guardando configuración para guild: {guild_id}")
            logger.info(f"   Canal: {canal_id}, Hora: {hora}:{minuto}")
            
            if not guild_id:
                logger.error("❌ ERROR CRÍTICO: guild_id está vacío en guardar_config")
                return False
            
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
            logger.info(f"🔍 Buscando configuración para guild: {guild_id}")
            
            if not guild_id:
                logger.error("❌ ERROR: guild_id está vacío en obtener_config")
                return None
            
            result = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            
            if result.data:
                logger.info(f"✅ Configuración encontrada para {guild_id}")
                return result.data[0]
            else:
                logger.warning(f"⚠️ No se encontró configuración para {guild_id}")
                return None
        except Exception as e:
            logger.error(f"❌ Error obteniendo config: {e}")
            return None
    
    async def obtener_servidores_activos(self):
        """Obtiene todos los servidores activos con sus credenciales y config"""
        try:
            logger.info("🔍 Buscando servidores activos...")
            
            configs = self.supabase.table('configuracion').select('*').eq('activo', True).execute()
            logger.info(f"📊 Configuraciones activas encontradas: {len(configs.data)}")
            
            resultado = []
            for config in configs.data:
                credenciales = await self.obtener_credenciales(config['guild_id'])
                if credenciales:
                    resultado.append({
                        **config,
                        'usuario': credenciales['usuario'],
                        'password': credenciales['password']
                    })
                    logger.info(f"✅ Servidor {config['guild_id']} tiene credenciales")
                else:
                    logger.warning(f"⚠️ Servidor {config['guild_id']} no tiene credenciales")
            
            logger.info(f"📊 Total servidores listos para enviar: {len(resultado)}")
            return resultado
        except Exception as e:
            logger.error(f"❌ Error obteniendo servidores: {e}")
            return []
    
    async def registrar_envio(self, guild_id):
        """Registra que hoy ya se envió la promo"""
        try:
            from datetime import date
            logger.info(f"📝 Registrando envío para {guild_id} - {date.today()}")
            
            data = {
                'guild_id': str(guild_id),
                'fecha': str(date.today())
            }
            self.supabase.table('envios').insert(data).execute()
            logger.info(f"✅ Envío registrado para {guild_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error registrando envio: {e}")
            return False
    
    async def ya_se_envio_hoy(self, guild_id):
        """Verifica si ya se envió hoy"""
        try:
            from datetime import date
            logger.info(f"🔍 Verificando si ya se envió para {guild_id} hoy")
            
            result = self.supabase.table('envios').select('*')\
                .eq('guild_id', str(guild_id))\
                .eq('fecha', str(date.today()))\
                .execute()
            
            ya_envio = len(result.data) > 0
            logger.info(f"📅 Ya se envió hoy: {ya_envio}")
            return ya_envio
        except Exception as e:
            logger.error(f"❌ Error verificando envio: {e}")
            return False
    
    async def eliminar_servidor(self, guild_id):
        """Marca un servidor como inactivo (cuando el bot es expulsado)"""
        try:
            logger.info(f"🗑️ Eliminando servidor {guild_id}")
            self.supabase.table('configuracion').update({'activo': False}).eq('guild_id', str(guild_id)).execute()
            logger.info(f"✅ Servidor {guild_id} marcado como inactivo")
            return True
        except Exception as e:
            logger.error(f"❌ Error eliminando servidor: {e}")
            return False
