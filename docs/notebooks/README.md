#  Pipeline RAG para Fichas de Datos de Seguridad (FDS/SGA)

Este repositorio contiene la arquitectura de datos y los scripts de procesamiento para automatizar la ingesta, extracción, enriquecimiento visual y limpieza de Fichas de Datos de Seguridad (FDS) de productos químicos. 

El sistema utiliza una **Arquitectura Medallón** en AWS S3 y un enfoque de extracción híbrido y multimodal (Regex + Modelos Semánticos + Visión por Computadora) para estructurar al 100% documentos caóticos y prepararlos para un sistema RAG (Retrieval-Augmented Generation).

---

##  Arquitectura de Datos (Medallón)

El almacenamiento está estructurado en un bucket de Amazon S3 con las siguientes capas:

* **1. Origen (`bronze/docs/`)**: Repositorio de los documentos originales en formato PDF.
* **2. Capa Bronce (`bronze/processed/`)**: Almacena "cápsulas" por documento. Utiliza un motor de ingesta ultraligero que extrae la estructura del PDF en un único archivo Markdown (`.md`), dejando marcadores semánticos en lugar de extraer imágenes físicas, ahorrando drásticamente en almacenamiento y computo.
* **3. Capa Silver (`silver/seccion_X/`)**: Contiene fragmentos de texto segmentados rigurosamente por sección (de la 1 a la 16), limpios de ruido visual y con las imágenes críticas ya traducidas a texto. Guardados en formato `.jsonl`.
* **4. Capa Gold (`gold/chunks/`) y Base Vectorial**: Archivos consolidados y fragmentados semánticamente en "chunks" de alta densidad, listos para consumo. Estos fragmentos se traducen a Embeddings y residen en una base de datos vectorial remota (ChromaDB en EC2) para búsquedas de similitud o filtrado por metadatos.
* **5. Cuarentena (`Quarantine/`)**: Archivos que el sistema no pudo procesar, aislados para revisión manual.

---

## Fases de Procesamiento

El pipeline está modularizado en cuadernos individuales para garantizar la resiliencia y el procesamiento en paralelo.

### Fase 1: Ingesta Estructural Ligera (PDF ➔ Bronce)
Script encargado de leer los PDFs originales y transformarlos a texto estructurado de forma masiva.
- **Herramienta principal:** `Docling` (En modo ligero / Sin generación de imágenes físicas).
- **Lógica:** Genera la estructura base en Markdown conservando las tablas y jerarquías, preparando el terreno para la extracción quirúrgica de la Fase 2.

### Fase 2: Extracción Híbrida y Auditoría Visual (Bronce ➔ Silver)
Consiste en 16 cuadernos orquestadores (uno por cada sección de la FDS) divididos en dos categorías:
- **A. Secciones de Texto Puro:** Utilizan un pipeline de **2 Niveles**. Tier 1 (Regex rápidas a costo cero) y Tier 2 (Extracción Semántica de respaldo con Gemini Flash mediante LangChain).
- **B. Secciones Multimodales (2, 8 y 14):** Activan el Tier 3 (Inyección Visual). `PyMuPDF` toma una foto del área rota y **Gemma 3 27B** actúa como "Auditor Visual" para reemplazar espacios ciegos con descriptores exactos (Ej: `[PICTOGRAMA: líquido inflamable]`).

### Fase 3: Chunking Semántico (Silver ➔ Gold)
Unifica las secciones dispersas de la capa Silver en un solo documento listo para el RAG.
- Utiliza `MarkdownHeaderTextSplitter` y `RecursiveCharacterTextSplitter` para crear bloques de texto densos (~3000 caracteres con 300 de solapamiento).
- Preserva la jerarquía de los títulos como metadatos críticos para evitar la pérdida de contexto en la búsqueda.

### Fase 4: Vectorización (Gold ➔ ChromaDB)
El cerebro del sistema RAG. Transforma el texto estructurado en vectores matemáticos.
- Consume los archivos `.jsonl` de la capa Gold.
- Genera Embeddings utilizando **Azure OpenAI** (`text-embedding-3-large`).
- Ingesta los vectores y sus metadatos aplanados en un servidor remoto de **ChromaDB** alojado en una instancia EC2, dejándolo listo para consultas o para actuar como un Juez Automático (RAG-as-a-Judge).

---

##  Tecnologías Utilizadas

* **Python 3.x**
* **AWS:** `boto3` (Integración S3) y EC2 (Alojamiento del motor vectorial).
* **Ingesta Estructural:** `docling` (Conversión avanzada a Markdown).
* **Análisis PDF / Visión:** `pymupdf` (fitz).
* **LLMs y Embeddings:** `google-generativeai` (Gemini/Gemma) y `langchain-openai` (Azure).
* **Orquestación y Chunking:** `langchain`, `langchain-text-splitters`, `pydantic`.
* **Base de Datos Vectorial:** `chromadb` (Arquitectura Cliente-Servidor).

---

## Configuración del Entorno

1. Clona este repositorio.
2. Crea un archivo `.env` en la raíz del proyecto o configura los **Secrets** con las siguientes variables:
   - **Google & AWS:**
     - `GOOGLE_API_KEY`
     - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`
     - `S3_BUCKET_NAME`, `S3_PREFIX_SILVER`, `S3_PREFIX_GOLD`
   - **Azure OpenAI (Embeddings):**
     - `AZURE_OPENAI_API_KEY`
     - `AZURE_OPENAI_ENDPOINT`
     - `AZURE_OPENAI_API_VERSION`
     - `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
   - **Base Vectorial (ChromaDB):**
     - `CHROMA_SERVER_HOST`
     - `CHROMA_SERVER_PORT`
3. Instala las dependencias y ejecuta los cuadernos en orden:
   - `01_ingesta_docling.ipynb` (Fase 1)
   - `02_silver_...` al `16_silver_...` (Fase 2)
   - `01_gold_chunking.ipynb` (Fase 3)
   - `02_gold_vectorizacion_chroma.ipynb` (Fase 4)
   - 
   

