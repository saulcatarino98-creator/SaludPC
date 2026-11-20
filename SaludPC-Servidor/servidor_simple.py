#!/usr/bin/env python3
"""
SaludPC Servidor Central - Versión Simple y Funcional
"""

import hashlib
import hmac
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Configuración
PUERTO = 8443
RUTA_DB = "C:\\ProgramData\\SaludPC\\servidor_central.db"
CLAVE_HMAC_ORG = os.environ.get("SALUDP_ORG_KEY", "clave-organizacion-cambiar-en-produccion")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("salud.servidor")

# Crear base de datos
def crear_base():
    os.makedirs(os.path.dirname(RUTA_DB), exist_ok=True)
    conexion = sqlite3.connect(RUTA_DB)
    try:
        conexion.executescript("""
            CREATE TABLE IF NOT EXISTS equipos (
                id_equipo TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                organizacion TEXT NOT NULL,
                sede TEXT,
                area TEXT,
                fecha_inscripcion TEXT NOT NULL,
                ultima_conexion TEXT,
                estado TEXT DEFAULT 'en_aprendizaje'
            );
            CREATE TABLE IF NOT EXISTS reportes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_equipo TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                estado TEXT,
                cpu_load REAL,
                ram_load REAL,
                disk_used_pct REAL,
                cpu_temp REAL,
                firma_hmac TEXT NOT NULL,
                datos_json TEXT,
                FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo)
            );
            CREATE TABLE IF NOT EXISTS avisos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_equipo TEXT NOT NULL,
                estado TEXT NOT NULL,
                mensaje TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (id_equipo) REFERENCES equipos(id_equipo)
            );
        """)
        conexion.commit()
    finally:
        conexion.close()


def generar_token(id_equipo):
    material = f"{id_equipo}|{CLAVE_HMAC_ORG}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


def obtener_token(id_equipo):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        fila = conexion.execute(
            "SELECT token FROM equipos WHERE id_equipo = ?", (id_equipo,)
        ).fetchone()
        return fila[0] if fila else None
    finally:
        conexion.close()


def verificar_firma(datos_json, firma_recibida, token_equipo):
    firma_esperada = hmac.new(
        token_equipo.encode("utf-8"),
        datos_json.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(firma_esperada, firma_recibida)


def listar_equipos():
    conexion = sqlite3.connect(RUTA_DB)
    try:
        return conexion.execute(
            """
            SELECT id_equipo, organizacion, sede, area, estado, ultima_conexion
            FROM equipos
            ORDER BY fecha_inscripcion DESC
            """
        ).fetchall()
    finally:
        conexion.close()


def eliminar_equipo(id_equipo):
    conexion = sqlite3.connect(RUTA_DB)
    try:
        existe = conexion.execute(
            "SELECT 1 FROM equipos WHERE id_equipo = ?", (id_equipo,)
        ).fetchone()
        if existe is None:
            return False
        conexion.execute("DELETE FROM reportes WHERE id_equipo = ?", (id_equipo,))
        conexion.execute("DELETE FROM avisos WHERE id_equipo = ?", (id_equipo,))
        conexion.execute("DELETE FROM equipos WHERE id_equipo = ?", (id_equipo,))
        conexion.commit()
        return True
    finally:
        conexion.close()


class SaludPCHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        log.info("%s - %s" % (self.address_string(), format % args))
    
    def _enviar_json(self, codigo, datos):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(cuerpo)
    
    def _leer_cuerpo(self):
        largo = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(largo).decode('utf-8') if largo > 0 else ""
    
    def do_GET(self):
        """Maneja peticiones GET del panel web y API"""
        try:
            parsed_url = urlparse(self.path)
            ruta = parsed_url.path
            
            if ruta == "/":
                self._pagina_principal()
            elif ruta == "/equipos":
                self._api_equipos()
            else:
                self._enviar_json(404, {"error": "Ruta no encontrada"})
        except Exception as e:
            log.error(f"Error en GET: {e}")
            self._enviar_json(500, {"error": str(e)})
    
    def do_POST(self):
        """Maneja peticiones POST de agentes"""
        try:
            ruta = urlparse(self.path).path
            largo = int(self.headers.get('Content-Length', 0))
            cuerpo = self.rfile.read(largo).decode('utf-8') if largo > 0 else ""
            
            if ruta == "/inscribir":
                self._ruta_inscribir(cuerpo)
            elif ruta == "/reporte":
                self._ruta_reporte(cuerpo)
            elif ruta == "/aviso":
                self._ruta_aviso(cuerpo)
            else:
                self._enviar_json(404, {"error": "Ruta no encontrada"})
        except Exception as e:
            log.error(f"Error en POST: {e}")
            self._enviar_json(500, {"error": str(e)})

    def do_DELETE(self):
        try:
            ruta = urlparse(self.path).path
            cuerpo = self._leer_cuerpo()
            if ruta == "/eliminar":
                self._ruta_eliminar_equipo(cuerpo)
            else:
                self._enviar_json(404, {"error": "Ruta no encontrada"})
        except Exception as e:
            log.error(f"Error en DELETE: {e}")
            self._enviar_json(500, {"error": str(e)})
    
    def _ruta_inscribir(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except (json.JSONDecodeError, TypeError):
            self._enviar_json(400, {"error": "JSON inválido"})
            return
        
        id_equipo = datos.get("id_equipo")
        organizacion = datos.get("organizacion")
        sede = datos.get("sede", "")
        area = datos.get("area", "")
        
        if not id_equipo or not organizacion:
            self._enviar_json(400, {"error": "id_equipo y organizacion son requeridos"})
            return
        
        token_existente = obtener_token(id_equipo)
        if token_existente is not None:
            self._enviar_json(409, {"error": f"Equipo {id_equipo} ya existe", "id_equipo": id_equipo, "token": token_existente})
            return
        
        try:
            token = generar_token(id_equipo)
            ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conexion = sqlite3.connect(RUTA_DB)
            conexion.execute(
                "INSERT INTO equipos (id_equipo, token, organizacion, sede, area, fecha_inscripcion, estado) VALUES (?, ?, ?, ?, ?, ?, 'en_aprendizaje')",
                (id_equipo, token, organizacion, sede, area, ahora)
            )
            conexion.commit()
            conexion.close()
            log.info(f"Equipo inscrito: {id_equipo}")
            self._enviar_json(200, {
                "ok": True,
                "id_equipo": id_equipo,
                "token": token,
                "mensaje": "Equipo inscrito correctamente"
            })
        except Exception as e:
            log.error(f"Error inscribiendo: {e}")
            self._enviar_json(500, {"error": str(e)})

    def _ruta_eliminar_equipo(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except (json.JSONDecodeError, TypeError):
            self._enviar_json(400, {"error": "JSON inválido"})
            return

        id_equipo = datos.get("id_equipo")
        if not id_equipo:
            self._enviar_json(400, {"error": "id_equipo es requerido"})
            return

        if not eliminar_equipo(id_equipo):
            self._enviar_json(404, {"error": "Equipo no encontrado"})
            return

        self._enviar_json(200, {
            "ok": True,
            "id_equipo": id_equipo,
            "mensaje": "Equipo eliminado correctamente",
        })
    
    def _ruta_reporte(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except (json.JSONDecodeError, TypeError):
            self._enviar_json(400, {"error": "JSON inválido"})
            return
        
        id_equipo = datos.get("id_equipo")
        firma_recibida = datos.get("firma_hmac")
        
        if not id_equipo or not firma_recibida:
            self._enviar_json(400, {"error": "id_equipo y firma_hmac requeridos"})
            return
        
        token = obtener_token(id_equipo)
        if token is None:
            self._enviar_json(403, {"error": "Equipo no inscrito"})
            return
        
        datos_sin_firma = dict(datos)
        datos_sin_firma.pop("firma_hmac", None)
        cuerpo_sin_firma = json.dumps(datos_sin_firma, ensure_ascii=False)
        
        if not verificar_firma(cuerpo_sin_firma, firma_recibida, token):
            self._enviar_json(403, {"error": "Firma inválida"})
            return
        
        try:
            ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conexion = sqlite3.connect(RUTA_DB)
            conexion.execute(
                "INSERT INTO reportes (id_equipo, timestamp, estado, cpu_load, ram_load, disk_used_pct, cpu_temp, firma_hmac, datos_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (id_equipo, ahora, datos.get("estado"), datos.get("cpu_load"), datos.get("ram_load"), datos.get("disk_used_pct"), datos.get("cpu_temp"), firma_recibida, json.dumps(datos, ensure_ascii=False))
            )
            conexion.execute("UPDATE equipos SET ultima_conexion = ?, estado = ? WHERE id_equipo = ?", (ahora, datos.get("estado", "desconocido"), id_equipo))
            conexion.commit()
            conexion.close()
            self._enviar_json(200, {"ok": True, "mensaje": "Reporte recibido"})
        except Exception as e:
            log.error(f"Error guardando reporte: {e}")
            self._enviar_json(500, {"error": str(e)})
    
    def _ruta_aviso(self, cuerpo):
        try:
            datos = json.loads(cuerpo)
        except (json.JSONDecodeError, TypeError):
            self._enviar_json(400, {"error": "JSON inválido"})
            return
        
        id_equipo = datos.get("id_equipo")
        estado = datos.get("estado")
        mensaje = datos.get("mensaje", "")
        
        if not id_equipo or not estado:
            self._enviar_json(400, {"error": "id_equipo y estado requeridos"})
            return
        
        token = obtener_token(id_equipo)
        if token is None:
            self._enviar_json(403, {"error": "Equipo no inscrito"})
            return
        
        try:
            conexion = sqlite3.connect(RUTA_DB)
            ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conexion.execute("INSERT INTO avisos (id_equipo, estado, mensaje, timestamp) VALUES (?, ?, ?, ?)", (id_equipo, estado, mensaje, ahora))
            conexion.commit()
            conexion.close()
            self._enviar_json(200, {"ok": True, "mensaje": "Aviso recibido"})
        except Exception as e:
            log.error(f"Error guardando aviso: {e}")
            self._enviar_json(500, {"error": str(e)})

    def _pagina_principal(self):
        """Página principal del panel de TI"""
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>SaludPC Enterprise - Panel de TI</title>
<style>
    body {{ font-family: 'Segoe UI', sans-serif; background: #0E0F13; color: #F2F4F7; margin: 0; padding: 20px; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ color: #3b82f6; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background: #191A20; border-radius: 8px; overflow: hidden; }}
    th {{ background: #3b82f6; color: white; padding: 12px; text-align: left; }}
    td {{ padding: 10px; border-bottom: 1px solid #272832; }}
    .badge {{ padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
    .badge-ok {{ background: #10b981; color: white; }}
    .badge-atencion {{ background: #f59e0b; color: white; }}
    .badge-accion {{ background: #ef4444; color: white; }}
    .badge-aprendizaje {{ background: #6366f1; color: white; }}
    .btn-eliminar {{ background: #ef4444; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; }}
    .btn-eliminar:hover {{ background: #dc2626; }}
    .refresh-btn {{ background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; margin-bottom: 20px; }}
    .refresh-btn:hover {{ background: #2563eb; }}
    .search-box {{ width: 300px; padding: 10px; border-radius: 6px; border: 1px solid #272832; background: #191A20; color: white; margin-bottom: 20px; }}
</style>
</head>
<body>
    <h1>🏥 SaludPC Enterprise - Panel de TI</h1>
    <button class="refresh-btn" onclick="location.reload()">↻ Refrescar</button>
    <input type="text" class="search-box" id="buscar" placeholder="Buscar equipo..." onkeyup="buscar()">
    
    <table>
        <thead>
            <tr>
                <th>ID Equipo</th>
                <th>Organización</th>
                <th>Sede</th>
                <th>Área</th>
                <th>Estado</th>
                <th>Última Conexión</th>
                <th>Acciones</th>
            </tr>
        </thead>
        <tbody id="cuerpoTabla">
            <!-- Los datos se cargan aquí -->
        </tbody>
    </table>
    
    <script>
        function cargarEquipos() {{
            fetch('/equipos')
                .then(r => r.json())
                .then(data => {{
                    const tbody = document.getElementById('cuerpoTabla');
                    tbody.innerHTML = '';
                    data.forEach(eq => {{
                        const fila = document.createElement('tr');
                        fila.innerHTML = `
                            <td>${{eq.id_equipo}}</td>
                            <td>${{eq.organizacion}}</td>
                            <td>${{eq.sede}}</td>
                            <td>${{eq.area}}</td>
                            <td><span class="badge badge-${{eq.estado}}">${{eq.estado}}</span></td>
                            <td>${{eq.ultima_conexion || '—'}}</td>
                            <td><button class="btn-eliminar" onclick="eliminar('${{eq.id_equipo}}')">Eliminar</button></td>
                        `;
                        tbody.appendChild(fila);
                    }});
                }});
        }}
        
        function eliminar(id) {{
            if(confirm('¿Eliminar equipo ' + id + '?')) {{
                fetch('/eliminar', {{
                    method: 'DELETE',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{id_equipo: id}})
                }}).then(r => r.json()).then(data => {{
                    if(data.ok) {{ alert('Eliminado'); location.reload(); }}
                }});
            }}
        }}
        
        function buscar() {{
            const valor = document.getElementById('buscar').value.toLowerCase();
            const filas = document.querySelectorAll('#cuerpoTabla tr');
            filas.forEach(fila => {{
                const texto = fila.textContent.toLowerCase();
                fila.style.display = texto.includes(valor) ? '' : 'none';
            }});
        }}
        
        setInterval(cargarEquipos, 10000);
        cargarEquipos();
    </script>
</body>
</html>"""
        self._enviar_respuesta(200, html, "text/html")
    
    def _enviar_respuesta(self, codigo, datos, tipo_contenido="application/json"):
        cuerpo = datos.encode("utf-8") if isinstance(datos, str) else datos
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo_contenido}; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _api_equipos(self):
        equipos = listar_equipos()
        self._enviar_json(200, [
            {
                "id_equipo": id_equipo,
                "organizacion": organizacion,
                "sede": sede,
                "area": area,
                "estado": estado,
                "ultima_conexion": ultima_conexion,
            }
            for id_equipo, organizacion, sede, area, estado, ultima_conexion in equipos
        ])
    
if __name__ == "__main__":
    crear_base()
    servidor = HTTPServer(("0.0.0.0", PUERTO), SaludPCHandler)
    print(f"Servidor SaludPC iniciado en puerto {PUERTO}")
    print(f"Panel: http://localhost:{PUERTO}/")
    print("Presiona Ctrl+C para detener")
    servidor.serve_forever()