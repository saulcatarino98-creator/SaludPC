# Manual de uso de SaludPC

**Versión del manual:** 1.0
**Última actualización:** 9 de noviembre de 2026
**Ámbito:** edición local 0.5.3 y edición empresarial (servidor central 1.0.3 y cliente operario 1.0.2)

## 1. Qué es SaludPC

SaludPC es un programa de **diagnóstico y prevención** para equipos con Windows.
Observa el consumo de CPU, memoria, disco y temperatura, aprende cómo se comporta
cada equipo y avisa cuando algo se sale de lo normal. **No repara nada**: no cambia
configuraciones, no borra archivos, no reinicia servicios y no toma decisiones por
el usuario. Solo informa para que una persona decida.

El programa funciona de dos formas:

- **Edición local:** todo ocurre dentro del equipo. Los datos no salen a Internet.
- **Edición empresarial:** un servidor central recibe reportes de varios equipos y
  el personal de TI los supervisa desde un panel web en la red interna.

## 2. Ediciones y cuándo usar cada una

| Edición | Para quién | Qué incluye | Dónde se guardan los datos |
|---|---|---|---|
| Local | Un usuario, un equipo | Panel de estado, historial, aprendizaje estadístico, avisos | En el mismo equipo |
| Empresarial | Un hospital, sede o área | Servidor central, panel de TI, cliente operario, búsqueda, informes | En el servidor de la organización |

Use la edición local cuando quiera cuidar un equipo sin infraestructura. Use la
edición empresarial cuando TI necesite ver varios equipos desde un solo lugar.

## 3. Antes de instalar

- Windows 10 u 11, preferiblemente 64 bits.
- Permisos de administrador para instalar. La instalación pide **un solo UAC**.
- En la edición empresarial, el servidor y los equipos deben estar en la misma red
  o tener acceso al puerto **8443** del servidor.
- Anote la **IP del servidor** (por ejemplo `192.168.100.4`) y el **puerto**
  (por defecto `8443`). En el cliente se escriben separados: IP en un campo y
  puerto en otro.
- No hace falta crear cuentas, ni iniciar sesión en Internet, ni abrir un botón
  de «iniciar» después de instalar.

## 4. Edición local (usuario final)

### 4.1 Instalación

1. Ejecute el instalador `SaludPC-Setup-0.5.3.exe`.
2. Acepte el aviso de administrador (UAC) y siga el asistente.
3. Al terminar, SaludPC queda funcionando y empieza a tomar muestras solo. No hay
   que abrir nada ni pulsar «iniciar».
4. Si el equipo no tiene sensores o no desea leer temperatura, existe la variante
   **Lite** (`SaludPC-Setup-0.5.3-Lite.exe`). Es la misma aplicación sin lectura de
   sensores.

### 4.2 Primera apertura y aprendizaje

Durante los primeros días el panel muestra **APRENDIENDO**. Eso es normal: el
programa está reuniendo la línea base del equipo. Necesita **300 muestras** (una
por minuto) repartidas en **3 fechas locales distintas**. Mientras tanto no emite
un diagnóstico definitivo.

Cuando termina el aprendizaje, el estado cambia a **Normal**, **Atención** o
**Acción**. La línea base se actualiza al arrancar, al cambiar el día y cada
6 horas.

### 4.3 Estados del panel

| Estado | Significado | Qué hacer |
|---|---|---|
| Aprendiendo | Todavía no hay historia suficiente | Esperar; el sistema ya está midiendo |
| Normal | El comportamiento entra en lo esperado para ese equipo | Nada |
| Atención | Hay una desviación moderada | Revisar el equipo cuando pueda |
| Acción | Hay una desviación importante o sostenida | Revisar el equipo pronto |

Los umbrales no son fijos para todos: se calculan con el percentil 95 y 99 del
propio equipo, con pisos y techos de seguridad. Por eso dos equipos distintos
pueden reaccionar de forma distinta ante el mismo porcentaje de CPU.

### 4.4 Historial y filtros

El historial guarda **90 días** de detalle, con una muestra por minuto. Desde el
panel se puede filtrar por fecha y por estado para ver qué pasó en un día o en una
franja concreta. Los resúmenes diarios se conservan por más tiempo.

### 4.5 Consumo del agente

El propio programa mide su consumo. El panel muestra el promedio móvil de los
últimos 5 minutos y lo actualiza cada 5 segundos. Si el consumo del agente baja de
0.95 % se considera «consumo bajo». Los picos solo se registran como episodio si
duran **5 minutos o más**; si el servicio estuvo detenido más de 15 minutos, el
episodio se descarta.

### 4.6 Ocultar la ventana al iniciar sesión

En el pie del panel está la casilla **«No mostrar esta ventana al iniciar sesión»**.
Si la marca:

- la ventana no aparece al iniciar sesión;
- el programa **sigue midiendo y enviando** en segundo plano;
- puede abrirlo manualmente desde el acceso directo cuando quiera.

Cerrar la ventana con la **X** la oculta, no detiene el monitoreo. Para detenerlo
del todo use **«Salir»**.

### 4.7 Desinstalar

Use **Configuración → Aplicaciones → SaludPC → Desinstalar**, o el acceso directo
de desinstalación del menú Inicio. La desinstalación no envía datos a Internet.

## 5. Edición empresarial: servidor central

### 5.1 Requisitos del servidor

- Un equipo Windows que quede encendido mientras se monitorea.
- IP fija o reservada en la red interna. Ejemplo: `192.168.100.4`.
- Puerto **8443** libre y permitido en el firewall de Windows.
- Espacio en disco suficiente para la base SQLite y los registros.

### 5.2 Instalación del servidor

1. Copie `SaludPC-Servidor-Central-1.0.3.exe` al equipo servidor.
2. Doble clic, acepte el UAC y complete el asistente.
3. El instalador cierra una instancia anterior, copia los archivos e inicia el
   servidor. Si no se inicia solo, abra **SaludPC Servidor Central** desde el
   escritorio o el menú Inicio.
4. La consola muestra la base de datos, el registro y la dirección del panel.
5. Abra en el navegador: `http://IP_DEL_SERVIDOR:8443/`.

Rutas habituales:

| Elemento | Ruta |
|---|---|
| Programa | `C:\Program Files\SaludPC Servidor\` |
| Base de datos | `C:\ProgramData\SaludPC\servidor_central.db` |
| Registro | `C:\ProgramData\SaludPC\servidor.log` |
| Panel | `http://IP_DEL_SERVIDOR:8443/` |

Si el servidor no abre el puerto, revise que no haya otra instancia en ejecución y
que el firewall permita el puerto 8443.

### 5.3 Panel de TI

El panel muestra:

- **Tarjetas de resumen:** total de equipos, normales, atención, requieren acción,
  en aprendizaje y sin reportar.
- **Tabla de equipos:** ID, organización, sede, área, estado, última conexión y
  últimas métricas (CPU, RAM, disco y temperatura).
- **Actualización automática** cada 30 segundos. Se pausa mientras usted escribe
  en el buscador o tiene abierto el cuadro de informes.

### 5.4 Buscar y filtrar

En la parte superior derecha están el **buscador**, el **filtro por estado** y el
botón **Actualizar**:

1. Escriba en el buscador el ID del equipo, la organización, la sede o el área.
   La búsqueda encuentra coincidencias parciales.
2. Elija un estado en la lista: **Todos**, **Normal**, **Atención**,
   **Requiere acción**, **En aprendizaje** o **Sin reportar**.
3. Pulse **Buscar** o presione **Enter**.
4. Pulse **Limpiar** para quitar la búsqueda y el filtro.

Las tarjetas de resumen siempre muestran el panorama general; la tabla muestra
solo los equipos que coinciden con la búsqueda y el filtro. El texto
«Mostrando: N» indica cuántos equipos quedaron visibles.

### 5.5 Actualizar

El botón **↻ Actualizar** está a la derecha, junto al buscador. Fuerza una recarga
inmediata del panel. Aunque no lo pulse, el panel se actualiza solo cada 30
segundos.

### 5.6 Detalle de un equipo

Pulse el ID del equipo en la tabla. El detalle muestra:

- organización, sede y área;
- fecha de inscripción y última conexión;
- estado actual y avance del aprendizaje (muestras y días);
- los últimos 50 reportes con estado, CPU, RAM, disco y temperatura.

Desde esa pantalla puede generar el informe de ese equipo con un solo botón.

### 5.7 Eliminar un equipo

En la columna **Acciones** de la tabla, pulse el icono de papelera. El panel pide
confirmación y elimina el equipo junto con sus reportes y avisos. Esta acción no
se puede deshacer.

Si el equipo vuelve a inscribirse, se crea de nuevo y empieza otra vez su
aprendizaje.

### 5.8 Generar reportes

El botón **📄 Generar reporte** abre un cuadro con tres decisiones:

1. **¿Qué informe necesita?**
   - **Todas las máquinas:** un informe general del estado actual.
   - **Un equipo específico:** elija el equipo en la lista.
2. **Equipo:** se habilita solo cuando eligió «Un equipo específico».
3. **Formato:**
   - **Para imprimir o guardar como PDF:** abre una página limpia.
   - **CSV para Excel:** descarga una hoja de cálculo.

Pulse **Generar**. El informe se abre en una pestaña nueva.

#### 5.8.1 Reporte de todas las máquinas

Incluye:

- fecha y hora de generación;
- resumen por estado;
- tabla con ID, organización, sede, área, estado, última conexión, CPU, RAM,
  disco y temperatura del último reporte.

En la página del informe puede pulsar **🖨 Imprimir / Guardar PDF** o
**⬇ Descargar CSV**.

#### 5.8.2 Reporte de un equipo

Incluye:

- ficha del equipo (ID, organización, sede, área, inscripción, última conexión,
  estado actual y avance del aprendizaje);
- total de reportes, CPU media y máxima, RAM media y máxima, disco medio, primer
  y último reporte;
- historial cronológico con fecha UTC, fecha local, estado, CPU, RAM, disco y
  temperatura.

La página muestra hasta los **últimos 500 reportes** para que sea imprimible. El
**CSV incluye el detalle completo**, sin ese límite.

#### 5.8.3 Formatos y uso práctico

| Formato | Para qué sirve | Cómo se usa |
|---|---|---|
| HTML / impresión | Entregar un informe legible o firmarlo | Pulse Imprimir y elija «Guardar como PDF» |
| CSV | Analizar en Excel, filtrar o archivizar | Se descarga y se abre con Excel |

El CSV usa punto y coma como separador y lleva una marca de codificación para que
Excel reconozca los acentos. Si su Excel no separa las columnas automáticamente,
use **Datos → Texto en columnas** y elija el punto y coma.

## 6. Edición empresarial: cliente operario

### 6.1 Instalación

1. Copie `SaludPC-Cliente-Operario-1.0.2.exe` al equipo que se va a monitorear.
2. Doble clic y acepte el UAC.
3. Deje marcada la tarea **«Iniciar SaludPC automáticamente al iniciar sesión»**.
4. Al terminar, el cliente se abre. Si no hay token, muestra la pantalla de
   inscripción.

El instalador crea un acceso directo de inicio automático con el argumento
`--auto`, que respeta la preferencia de ventana oculta.

### 6.2 Inscripción

Complete:

- **Organización:** por ejemplo `HGO`.
- **Sede:** por ejemplo `Imiem5645`.
- **Área:** por ejemplo `UCIN`.
- **IP del servidor:** por ejemplo `192.168.100.4`. No escriba el puerto aquí.
- **Puerto:** por ejemplo `8443`.

Pulse **Inscribir equipo**. Si todo está bien, el servidor devuelve un token y el
cliente pasa al panel de aprendizaje **sin cerrarse**.

Reglas importantes:

- Un equipo no se puede inscribir dos veces con el mismo ID. Si ya estaba
  inscrito, el servidor devuelve el token existente y el cliente lo recupera.
- El token se guarda en `C:\ProgramData\SaludPC\Cliente\token_equipo.json`.
- La preferencia de ventana se guarda en
  `C:\ProgramData\SaludPC\Cliente\config_cliente.json`.

### 6.3 Panel de aprendizaje

Mientras el servidor no tenga **300 muestras en 3 fechas locales**, el panel
muestra **APRENDIENDO** y el avance real, por ejemplo «1 de 300» y «1 de 3». No
inventa un estado ni adelanta el diagnóstico. Cuando el aprendizaje se completa,
el panel pasa a **Normal**, **Atención** o **Acción**.

El cliente envía una muestra por minuto. La primera se envía de inmediato.

### 6.4 Inicio automático y ventana oculta

En el pie del panel está la casilla **«No mostrar esta ventana al iniciar sesión
(el cliente sigue enviando reportes en segundo plano)»**.

- Si la marca, al iniciar sesión el cliente arranca oculto y sigue enviando.
- Si la desmarca, la ventana aparece al iniciar sesión.
- El acceso directo del escritorio y el del menú Inicio **siempre muestran la
  ventana** cuando se abren a mano.

### 6.5 Cerrar, ocultar y salir

- **X de la ventana:** oculta la ventana; el cliente sigue enviando. La primera
  vez avisa que SaludPC continúa activo.
- **Ocultar:** hace lo mismo, sin diálogo.
- **Salir:** pide confirmación y **detiene el monitoreo**.

Si el equipo se reinicia y el inicio automático está activo, el cliente vuelve a
arrancar solo.

### 6.6 Reabrir cuando ya está oculto

El cliente permite **una sola instancia**. Si la ventana está oculta y usted abre
de nuevo el acceso directo:

1. La segunda apertura no crea otro cliente.
2. Envía la orden `SHOW` a la instancia que ya está trabajando.
3. La ventana existente se muestra.
4. La segunda apertura termina sola.

No se duplican reportes ni se abren dos ventanas.

### 6.7 Equipo ya inscrito o reinstalación

Si reinstala el cliente y el equipo ya estaba inscrito, la inscripción devuelve
el token existente. El cliente lo guarda y continúa. No es necesario borrar el
equipo en el servidor ni crear un ID nuevo, salvo que quiera empezar de cero.

## 7. Privacidad y seguridad

### 7.1 Qué datos se envían

Solo se envían métricas técnicas de una lista cerrada:

- ID del equipo, organización, sede y área;
- CPU, memoria, disco y temperatura;
- estado del agente y fecha del reporte.

**No** se envían nombres de pacientes, documentos, historias clínicas, nombres de
procesos, archivos personales ni el contenido de la pantalla.

### 7.2 Token y firma HMAC

Cada equipo recibe un **token único** al inscribirse. Cada reporte se firma con
**HMAC-SHA256** usando ese token. El servidor rechaza los reportes con firma
inválida. Esto protege la integridad y la autenticidad del reporte.

### 7.3 HTTP y HTTPS

La versión 1.0.3 del servidor usa **HTTP** en el puerto 8443. HMAC evita que un
reporte sea alterado, pero **no cifra** el tráfico. En una red local, alguien con
acceso podría leer las métricas y el token.

Opciones para proteger la conexión, de menor a mayor esfuerzo:

1. **Certificado autofirmado con pinning** (recomendado para el piloto): el
   servidor usa un certificado propio y el cliente valida su huella.
2. **CA interna del hospital:** el servidor recibe un certificado de la CA de la
   organización y los equipos confían en ella.
3. **Proxy inverso Caddy o nginx:** el servidor sigue en HTTP local y el proxy
   termina TLS.
4. **Let's Encrypt:** solo si el servidor tiene un nombre DNS público.
5. **mTLS:** certificado de cliente, además del token.
6. **VPN o red segmentada:** complemento de las anteriores.

Mientras HTTPS no esté implementado, mantenga el servidor en una red interna de
confianza, restrinja el acceso al puerto 8443 y no lo exponga a Internet.

### 7.4 Recomendaciones para el piloto

- Instale el servidor en un equipo con IP fija.
- Permita el puerto 8443 solo en la subred de los equipos monitoreados.
- Use un token por equipo; no comparta tokens.
- Revise el registro `servidor.log` si algo no llega.
- No publique el panel fuera de la red interna.

## 8. Solución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| El cliente no inscribe | IP o puerto incorrectos, servidor apagado o firewall | Verifique IP y puerto, encienda el servidor y permita 8443 |
| «El equipo ya está inscrito» | El ID ya existe en el servidor | El cliente recupera el token solo; si no, revise el ID |
| El panel no muestra un equipo | Aún no llegó el primer reporte o el panel tiene datos viejos | Espere un minuto o pulse Actualizar |
| El equipo sigue en «Aprendiendo» | Faltan muestras o fechas locales | Espere a completar 300 muestras en 3 días |
| No aparece la ventana al iniciar sesión | La casilla de ocultar está marcada | Abra el acceso directo del escritorio o del menú Inicio |
| La segunda apertura no muestra nada | Ya hay una instancia y el socket de control no responde | Cierre el proceso y vuelva a abrir; revise el puerto 8457 |
| El servidor no arranca | Otra instancia ocupa el puerto 8443 | Cierre la instancia anterior o cambie el puerto |
| El CSV se ve en una sola columna | Configuración regional de Excel | Use Datos → Texto en columnas con separador punto y coma |
| El panel no tiene buscador ni informes | Está abierto con una versión anterior | Actualice el servidor a 1.0.3 y recargue con Ctrl+F5 |
| El informe no se abre | El navegador bloqueó la ventana emergente | Permita ventanas emergentes para la dirección del servidor |

## 9. Preguntas frecuentes

**¿SaludPC repara el equipo?**
No. Solo diagnostica y avisa. Las decisiones y las reparaciones las hace una
persona.

**¿Envía datos a Internet?**
La edición local no envía nada a Internet. La edición empresarial envía solo
métricas técnicas al servidor de la organización.

**¿Puedo ocultar la ventana y seguir monitoreando?**
Sí. Marque la casilla de ocultar al iniciar sesión. El cliente sigue enviando. La
X también oculta; «Salir» detiene el monitoreo.

**¿Cuánto tarda el aprendizaje?**
Como mínimo 3 días locales y 300 muestras. Con una muestra por minuto, se cumplen
las 300 muestras en unas 5 horas, pero hacen falta 3 fechas locales distintas.

**¿Qué pasa si el equipo se apaga?**
El cliente se detiene. Al iniciar sesión vuelve a arrancar solo si el inicio
automático está activo. Los reportes que faltan no se inventan.

**¿Puedo generar un informe sin imprimir?**
Sí. Elija el formato CSV para Excel o guarde la página como PDF desde el navegador.

**¿El informe general incluye todos los equipos aunque esté filtrando?**
El informe general incluye todos los equipos inscritos. El filtro de la tabla solo
afecta a lo que ve en pantalla, no al contenido del informe.

**¿Puedo eliminar un equipo y volver a inscribirlo?**
Sí. Al eliminarlo se borran sus reportes y avisos. Al inscribirlo de nuevo empieza
un aprendizaje nuevo.

**¿Qué diferencia hay entre la edición local y la empresarial?**
La local guarda todo en el equipo y usa un baseline estadístico. La empresarial
centraliza los reportes en un servidor y usa un conteo de aprendizaje de 300
muestras y 3 días, con umbrales fijos en el cliente.

## 10. Glosario

| Término | Significado |
|---|---|
| Aprendizaje | Periodo inicial en el que el programa reúne muestras antes de diagnosticar |
| Baseline | Comportamiento habitual del equipo, calculado con su propia historia |
| Muestra | Una lectura de CPU, RAM, disco y temperatura |
| Token | Credencial única de un equipo para autenticarse ante el servidor |
| HMAC-SHA256 | Firma que demuestra que un reporte no fue alterado |
| p95 / p99 | Percentiles usados para separar lo normal de lo anómalo |
| Reporte | Conjunto de métricas que el cliente envía al servidor |
| Informe | Documento generado por el servidor para leer o archivar |

## 11. Anexos

### 11.1 Rutas, puertos y archivos

| Elemento | Valor |
|---|---|
| Puerto del servidor | 8443 (HTTP en la versión 1.0.3) |
| Base del servidor | `C:\ProgramData\SaludPC\servidor_central.db` |
| Registro del servidor | `C:\ProgramData\SaludPC\servidor.log` |
| Configuración del cliente | `C:\ProgramData\SaludPC\Cliente\config_cliente.json` |
| Token del cliente | `C:\ProgramData\SaludPC\Cliente\token_equipo.json` |
| Socket de control del cliente | `127.0.0.1:8457` |
| Muestras para aprender | 300 |
| Fechas locales para aprender | 3 |
| Intervalo de envío | 60 segundos |
| Detalle local | 90 días |
| Actualización del panel | 30 segundos |

### 11.2 API para el personal de TI

| Ruta | Método | Uso |
|---|---|---|
| `/` | GET | Panel de TI |
| `/equipos` | GET | Lista de equipos en JSON; acepta `buscar` y `estado` |
| `/progreso?id=...&token=...` | GET | Avance de aprendizaje de un equipo |
| `/detalle?id=...` | GET | Detalle de un equipo |
| `/informe?tipo=general` | GET | Informe general imprimible |
| `/informe?tipo=general&formato=csv` | GET | Informe general en CSV |
| `/informe?tipo=equipo&id=...` | GET | Informe de un equipo imprimible |
| `/informe?tipo=equipo&id=...&formato=csv` | GET | Informe de un equipo en CSV |
| `/inscribir` | POST | Inscripción de un equipo |
| `/reporte` | POST | Envío de un reporte firmado |
| `/aviso` | POST | Registro de un aviso |
| `/eliminar` | DELETE | Eliminación de un equipo |

### 11.3 Versiones de referencia

| Componente | Versión de este manual |
|---|---|
| Edición local | 0.5.3 |
| Servidor central | 1.0.3 |
| Cliente operario | 1.0.2 |

El cliente 1.0.2 es compatible con el servidor 1.0.3: el protocolo de inscripción,
reportes y progreso no cambió. Las novedades de la versión 1.0.3 son del panel:
búsqueda, filtro por estado, botón de actualización a la derecha y generación de
informes generales y por equipo.

---

**Fin del manual.** Para detalles técnicos, historial de cambios y decisiones de
diseño, consulte `BITACORA.md` y `BITACORA_SaludPC.pdf`.
