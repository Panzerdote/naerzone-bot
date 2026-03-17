# app/database.py
import os
from supabase import create_client
import logging
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)

# Clave de encriptación (EN UN ENTORNO REAL, USA UNA VARIABLE DE ENTORNO)
# Esta clave debe ser secreta y NO SUBIRSE A GITHUB.
# Por ahora la generamos así, pero deberías guardarla en os.environ.
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    # Si no existe en entorno, generamos una (SOLO PARA DESARROLLO)
    # En producción, DEBES definir ENCRYPTION_KEY en las variables de Render.
    ENCRYPTION_KEY = Fernet.generate_key()
    logger.warning("⚠️ Usando clave de encriptación generada. Define ENCRYPTION_KEY en producción.")
cipher = Fernet(ENCRYPTION_KEY)

def encrypt_password(password: str) -> str:
    """Encripta una contraseña"""
    return cipher.encrypt(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    """Desencripta una contraseña"""
    return cipher.decrypt(encrypted_password.encode()).decode()

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
            
            # Encriptar la contraseña ANTES de guardarla
            encrypted_pass = encrypt_password(password)
            
            data = {
                'guild_id': str(guild_id),
                'guild_name': guild_name,
                'usuario': usuario,
                'password': encrypted_pass
            }
            
            existing = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            
            if existing.data:
                self.supabase.table('credenciales').update(data).eq('guild_id', str(guild_id)).execute()
                logger.info(f"✅ Credenciales actualizadas para {guild_id}")
            else:
                self.supabase.table('credenciales').insert(data).execute()
                logger.info(f"✅ Credenciales insertadas para {guild_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error guardando credenciales: {e}")
            return False
    
    async def obtener_credenciales(self, guild_id):
        try:
            if not guild_id:
                return None
            result = self.supabase.table('credenciales').select('*').eq('guild_id', str(guild_id)).execute()
            if result.data:
                cred = result.data[0]
                # Desencriptar la contraseña al obtenerla
                try:
                    cred['password'] = decrypt_password(cred['password'])
                except Exception as e:
                    logger.error(f"Error desencriptando contraseña para {guild_id}: {e}")
                    # Si falla la desencriptación, devolvemos None o la contraseña encriptada?
                    # Mejor devolvemos None para que falle el login y no use una contraseña corrupta.
                    return None
                return cred
            return None
        except Exception as e:
            logger.error(f"Error obteniendo credenciales: {e}")
            return None
    
    # ... (el resto de funciones: guardar_config, obtener_config, etc. deben quedar IGUAL que antes) ...
    # Asegúrate de copiar el resto de funciones desde tu archivo original.
    # Por espacio, no las repito aquí, pero deben estar completas.
    
    async def guardar_config(self, guild_id, canal_id, canal_nombre, hora, minuto, mensaje=None):
        # ... (tu código original, sin cambios) ...
        pass
    
    async def obtener_config(self, guild_id):
        # ... (tu código original, sin cambios) ...
        pass
    
    async def agregar_servidor_bot(self, guild_id, guild_name):
        # ... (tu código original, sin cambios) ...
        pass
    
    async def eliminar_servidor_bot(self, guild_id):
        # ... (tu código original, sin cambios) ...
        pass
    
    async def obtener_servidores_bot(self):
        # ... (tu código original, sin cambios) ...
        return []
    
    async def obtener_servidores_activos(self):
        # ... (tu código original, sin cambios) ...
        return []
    
    async def registrar_envio(self, guild_id):
        # ... (tu código original, sin cambios) ...
        pass
    
    async def ya_se_envio_hoy(self, guild_id):
        # ... (tu código original, sin cambios) ...
        return False
    
    async def eliminar_todo_servidor(self, guild_id):
        # ... (tu código original, sin cambios) ...
        pass
