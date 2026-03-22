
# Pipeline RAG para Fichas de Datos de Seguridad (FDS/SGA)

Este repositorio contiene la arquitectura de datos y los scripts de procesamiento para automatizar la ingesta, extracción y limpieza de Fichas de Datos de Seguridad (FDS) de productos químicos. 

El sistema utiliza una **Arquitectura Medallón** en AWS S3 y un enfoque de extracción híbrido (Expresiones Regulares + Modelos de Lenguaje) para preparar los documentos para un futuro sistema RAG (Retrieval-Augmented Generation).

---

##  Arquitectura de Datos (Medallón)

El almacenamiento está estructurado en un bucket de Amazon S3 con las siguientes capas:

* **1. Origen (`bronze/docs/`)**: Repositorio de los documentos originales en formato PDF.
* **2. Capa Bronce (`bronze/processed/`)**: Almacena "cápsulas" por documento. Cada cápsula contiene el texto extraído en formato Markdown (`.md`) y todas las imágenes/pictogramas (`.jpeg`/`.png`) asociados al documento.
* **3. Capa Silver (`silver/seccion_X/`)**: Contiene fragmentos de texto segmentados por sección (Ej. Sección 1), limpios de ruido visual (etiquetas de paginación, artefactos OCR) y guardados en formato `.jsonl`.
* **4. Cuarentena (`Quarantine/`)**: Archivos que el sistema no pudo procesar por formato ilegible o fallos en la extracción, aislados para revisión manual.

---

### Fases de Procesamiento Actuales

### Fase 1: Ingesta y Creación de Cápsulas (PDF ➔ Bronce)
Script encargado de leer los PDFs originales y transformarlos a texto estructurado.
- **Herramienta principal:** `marker-pdf`.
- **Lógica:** Genera una carpeta única para cada documento dentro de `bronze/processed/`, empaquetando el texto completo en Markdown junto con todos los gráficos extraídos para su uso futuro en modelos de visión.

### Fase 2: Extracción Híbrida y Segmentación (Bronce ➔ Silver)
Script diseñado para aislar secciones específicas del documento (actualmente: **Sección 1**).
- **Tier 1 (Regex):** Utiliza Expresiones Regulares robustas para recortar la sección sin consumir cuota de API, logrando una alta eficiencia en costos.
- **Tier 2 (Extracción Semántica LLM):** Si el formato del documento rompe la Regex, actúa un modelo LLM (`gemini-2.5-flash-lite`) a través de **LangChain** para identificar semánticamente la sección y extraerla en un esquema estricto (Pydantic).
- **Controlador de Presupuesto:** Incluye una clase personalizada de gestión de estado y cola de tiempos (`time.sleep`) que evita errores HTTP 429 limitando los Requests Per Minute (RPM) y calculando los tokens de entrada mediante `tiktoken`.

---

##️ Tecnologías Utilizadas

* **Python 3.x**
* **AWS SDK:** `boto3` (Integración con S3).
* **LLM & Orquestación:** `langchain`, `langchain-google-genai`, `pydantic`.
* **Procesamiento de Documentos:** `marker-pdf` (OCR y formato).
* **Control de Tokens:** `tiktoken`.

---

## Configuración del Entorno

1. Clona este repositorio.
2. Abre los cuadernos en la carpeta `notebooks/` (las dependencias se instalan automáticamente en la primera celda).
3. Crea un archivo `.env` en la raíz del proyecto (o configura las variables de entorno en tu plataforma) basándote en la plantilla de .env.example y añade tus credenciales