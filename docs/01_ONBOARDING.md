# Guía de Inicio y Onboarding

Bienvenido al equipo de rag_fds. Este documento detalla los pasos necesarios para configurar tu entorno local y conectarlo con la infraestructura en la nube.

## 1. Clonar el Repositorio

Clona el proyecto en tu máquina local y accede al directorio principal:

```bash
git clone git@github.com:jpospinalo/fds.git
cd fds
```

## 2. Desplegar la Infraestructura (AWS)

La plataforma utiliza servicios de AWS distribuidos. La creación de estos recursos (S3, EC2, Security Groups) está automatizada mediante scripts de Infrastructure as Code (IaC).

1. Abre tu terminal configurada con AWS CLI o accede a AWS CloudShell.
2. Ejecuta el script de infraestructura:

```bash
chmod +x scripts/setup_aws.sh
./scripts/setup_aws.sh
```

Al finalizar, el script mostrará en pantalla un resumen con el nombre del bucket S3, la IP de la EC2. Guarda estos datos para los siguientes pasos.

>[!NOTE]
>Si quieres dejar todo en la nube para trabajar y que todos puedan ver lo que has hecho consulta la [Guía de configuracion de entorno Cloud 9](./C9_CREATION.md)

## 3. Configurar ChromaDB en EC2 (Motor Vectorial)
Nuestra arquitectura aloja la base de datos vectorial en la instancia EC2 para separar la carga de trabajo. Debes inicializar este servicio remoto antes de levantar el backend local.

1. Conéctate a tu instancia EC2 recién creada mediante SSH:

```bash
ssh -i "tu-llave.pem" ubuntu@<EC2_IP>
```

2. Crea el archivo de instalación dentro de la instancia EC2:

```bash
nano setup_chromadb.sh
```

3. Abre el archivo scripts/setup_chromadb.sh de tu repositorio local, copia todo su contenido y pégalo en la terminal del EC2. Guarda los cambios (Ctrl+O, luego Enter) y sal del editor (Ctrl+X).

4. Otorga permisos de ejecución y lanza el instalador:

```bash
chmod +x setup_chromadb.sh
./setup_chromadb.sh
```
Al finalizar, el script creará un servicio systemd y ChromaDB quedará ejecutándose en segundo plano en el puerto 4000. Puedes verificarlo corriendo: curl http://localhost:4000/api/v2/heartbeat.

## 4. Configurar las Variables de Entorno

Por motivos de seguridad, las credenciales no se incluyen en el repositorio. Crea un archivo llamado `.env` en la raíz del proyecto (`rag_fds/.env`) y define la siguiente estructura. 

>[!NOTE]
>Si aún no tienes configurados los servicios de Azure OpenAI, consulta la [Guía de Configuración de Azure Embeddings](./05_AZURE_EMBEDDINGS.md) antes de continuar.

```env
# Credenciales de AWS
AWS_ACCESS_KEY_ID=tu_access_key_aqui
AWS_SECRET_ACCESS_KEY=tu_secret_key_aqui
AWS_SESSION_TOKEN=tu_token_key_aqui
AWS_REGION=us-east-1

# Credenciales LLM
GEMINI_API_KEY = tu_api_key_aqui

# Configuración del Bucket y Rutas (Arquitectura Medallón)
S3_BUCKET_NAME=tu_bucket_aqui
S3_PREFIX_DOCS=bronze/docs/
S3_PREFIX_BRONCE=bronze/processed/
S3_PREFIX_SILVER=silver/
S3_PREFIX_GOLD=gold/
S3_PREFIX_QUARANTINE=Quarantine/

# ----------------------------------------
# SELECTOR DE PROVEEDOR RAG
# Opciones: azure | ollama
# ----------------------------------------
EMBEDDINGS_PROVIDER=ollama

# ----------------------------------------
# Configuración Ollama (Si usas proveedor local)
# ----------------------------------------
OLLAMA_BASE_URL=tu_end_point_aqui
OLLAMA_EMBEDDINGS_MODEL=tu_modelo_aqui

# Azure OpenAI
AZURE_OPENAI_API_KEY=tu_api_key_aqui
AZURE_OPENAI_ENDPOINT=tu_end_point_aqui
AZURE_OPENAI_API_VERSION=tu_version_aqui
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=tu_modelo_aqui

# CHROMA KEYS
CHROMA_SERVER_HOST=IP_del_servidor
CHROMA_SERVER_PORT=puerto_del_chroma

VITE_API_URL=http://<DNS_PUBLICO_C9 o localhost>:8000 
```

## 5. Configurar el Entorno Virtual (Backend Local)

Para ejecutar el motor RAG y la API de manera local (para pruebas y desarrollo), es necesario configurar un entorno de Python aislado.

**En sistemas basados en Unix (Mac/Linux):**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r apps/api_backend/requirements_api.txt
```

**En sistemas Windows:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r apps/api_backend/requirements_api.txt
```

## 6. Ejecución del Servidor Local

Con el entorno virtual activado y tu archivo `.env` configurado, ejecuta el backend utilizando el comando para nuestra arquitectura monorepo:

```bash
python -m uvicorn api_backend.main:app --reload --port 8000 --host 0.0.0.0 --app-dir apps
```

Si la consola muestra `Application startup complete`, el servidor estará operativo. Puedes acceder a la documentación interactiva de la API en `http://localhost:8000/api/docs` o `http://<DNS_PUBLICO_C9>:8000/api/docs`.

## 7. Ejecución de la Aplicación Web (Frontend SPA)

El frontend está construido sobre una arquitectura SPA moderna con React, Vite y TypeScript. Para levantar la interfaz gráfica y conectarla con la API local, sigue estos pasos:

### Paso 7.1: Configurar el entorno del Frontend

Crea un archivo de configuración específico para las variables del cliente web dentro de la carpeta del frontend:

Archivo: apps/frontend/.env

```env
# URL de conexión a la API local expuesta al navegador
VITE_API_URL=http://<localhost o DNS_PUBLICO_C9>:8000

```

### Paso 7.2: Instalación y Ejecución

Abre una **nueva terminal** (manteniendo el servidor backend corriendo en la ventana anterior) y ejecuta los siguientes comandos para instalar dependencias y levantar el servidor de desarrollo:

```bash
# Navegar al directorio del frontend
cd apps/frontend

# Instalar los paquetes de Node
npm install

# Levantar el servidor de desarrollo en caliente
npm run dev

```

La consola te indicará una URL local (generalmente `http://localhost:5173`). Abre esa dirección en tu navegador para interactuar con la plataforma de manera visual

Si estas en el entorno de c9 para acceder a este en ves de localhost es (`http://DNS_PUBLICO_C9:5173`). Abre esa dirección en tu navegador para interactuar con la plataforma de manera visual