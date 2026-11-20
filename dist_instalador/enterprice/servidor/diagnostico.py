"""Diagnóstico del servidor central SaludPC."""
import os
import sys
import socket

def probar_puerto(puerto=8443):
    """Verifica si el puerto está disponible."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", puerto))
        s.close()
        print(f"OK: Puerto {puerto} está disponible")
        return True
    except OSError as e:
        print(f"ERROR: Puerto {puerto} ya está en uso o no se puede abrir: {e}")
        return False

def probar_escritura(ruta):
    """Verifica si se puede escribir en la carpeta de datos."""
    try:
        test_file = os.path.join(ruta, "test_write.tmp")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        print(f"OK: Se puede escribir en {ruta}")
        return True
    except Exception as e:
        print(f"ERROR: No se puede escribir en {ruta}: {e}")
        return False

if __name__ == "__main__":
    print("=== Diagnóstico del Servidor Central SaludPC ===\n")
    
    print("1. Verificando puerto 8443...")
    probar_puerto(8443)
    
    print("\n2. Verificando carpeta de datos...")
    import rutas
    print(f"   Carpeta de datos: {rutas.carpeta_datos()}")
    probar_escritura(str(rutas.carpeta_datos()))
    
    print("\n3. Verificando carpeta del servidor...")
    carpeta_servidor = os.path.join(str(rutas.carpeta_datos()), "Servidor")
    print(f"   Carpeta: {carpeta_servidor}")
    probar_escritura(carpeta_servidor)
    
    print("\n=== Diagnóstico completado ===")
