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
        """Guarda o actualiza credenciales"""
        try:
            if not guild_id:
                logger.error("❌ guild_id vacío")
                return False
            
            # Verificar si ya existe
            existing = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'usuario': usuario,
            }
            
            # Solo actualizar password si se proporciona uno nuevo
            if password:
                data['password'] = password
            
            if existing.data:
                # Actualizar existente
                self.supabase.table('credenciales').update(data).eq('guild_id', str(guild_id)).execute()
                logger.info(f"✅ Credenciales actualizadas para {guild_id}")
            else:
                # Insertar nuevo
                data['password'] = password  # password es obligatorio para nuevo
                self.supabase.table('credenciales').insert(data).execute()
                logger.info(f"✅ Credenciales insertadas para {guild_id}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error guardando credenciales: {e}")
            return False
    
    async def obtener_credenciales(self, guild_id):
        """Obtiene credenciales de un servidor"""
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
        """Guarda la configuración del bot para un servidor"""
        try:
            logger.info(f"⚙️ Guardando configuración para guild: {guild_id}")
            logger.info(f"   Canal: {canal_nombre} ({canal_id}), Hora: {hora}:{minuto}")
            
            if not guild_id:
                logger.error("❌ ERROR: guild_id está vacío")
                return False
            
            if not canal_id:
                logger.error("❌ ERROR: canal_id está vacío")
                return False
            
            # Validar hora
            try:
                hora = int(hora)
                minuto = int(minuto)
                if hora < 0 or hora > 23 or minuto < 0 or minuto > 59:
                    logger.error(f"❌ Hora inválida: {hora}:{minuto}")
                    return False
            except:
                logger.error("❌ Hora no es número válido")
                return False
            
            # Construir datos base
            data = {
                'guild_id': str(guild_id),
                'canal_id': str(canal_id),
                'canal_nombre': canal_nombre,
                'hora_envio': hora,
                'minuto_envio': minuto,
                'activo': True,
                'fecha_actualizacion': 'now()'
            }
            
            # Añadir mensaje_personalizado solo si tiene valor
            if mensaje_personalizado is not None and mensaje_personalizado.strip():
                data['mensaje_personalizado'] = mensaje_personalizado.strip()
            
            # Verificar si ya existe
            existing = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            
            try:
                if existing.data:
                    # Actualizar existente
                    result = self.supabase.table('configuracion').update(data).eq('guild_id', str(guild_id)).execute()
                    logger.info(f"✅ Configuración actualizada para {guild_id}")
                else:
                    # Insertar nuevo
                    result = self.supabase.table('configuracion').insert(data).execute()
                    logger.info(f"✅ Nueva configuración guardada para {guild_id}")
                
                return True
                
            except Exception as e:
                # Si el error es por columna mensaje_personalizado, intentar sin ella
                if 'mensaje_personalizado' in str(e):
                    logger.warning("⚠️ La columna mensaje_personalizado no existe, guardando sin ella")
                    
                    # Quitar mensaje_personalizado del data
                    if 'mensaje_personalizado' in data:
                        del data['mensaje_personalizado']
                    
                    if existing.data:
                        self.supabase.table('configuracion').update(data).eq('guild_id', str(guild_id)).execute()
                    else:
                        self.supabase.table('configuracion').insert(data).execute()
                    
                    logger.info("✅ Configuración guardada sin mensaje personalizado")
                    return True
                else:
                    # Otro tipo de error
                    logger.error(f"❌ Error en Supabase: {e}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Error general guardando configuración: {e}")
            return False
    
    async def obtener_config(self, guild_id):
        """Obtiene la configuración de un servidor"""
        try:
            if not guild_id:
                return None
            
            result = self.supabase.table('configuracion').select('*').eq('guild_id', str(guild_id)).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Error obteniendo configuración: {e}")
            return None
    
    # ========== SERVIDORES ACTIVOS ==========
    async def obtener_servidores_activos(self):
        """Obtiene servidores con credenciales y configuración"""
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
        """Registra que hoy ya se envió"""
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
        """Verifica si ya se envió hoy"""
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
