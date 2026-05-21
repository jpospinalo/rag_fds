import os
import time
from pathlib import Path
import pandas as pd
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

from api_backend.config import Config
from api_backend.rag_engine.search_retriever import buscar_contexto
from api_backend import rate_limiter

# ==========================================
# 1. CONFIGURACIÓN DEL JUEZ (LLM)
# ==========================================
def obtener_llm_inspector():
    """Inicializa a Gemini en modo estricto (Temperatura 0) para evitar alucinaciones."""
    print(" Inicializando Juez Auditor (Gemini-3.1-flash)...")
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview", 
        temperature=0.5, 
        google_api_key=Config.GOOGLE_API_KEY
    )

# Plantilla estricta para forzar la salida tabular
PROMPT_INSPECTOR = PromptTemplate.from_template(
    """Eres un Analista de Extracción de Datos de Seguridad Química (SGA). 
    Tu única tarea es verificar la PRESENCIA o AUSENCIA de la información requerida en la Sección {num_seccion} de una Ficha de Datos de Seguridad (FDS).

    LISTA DE REQUERIMIENTOS A VERIFICAR:
    {rubrica}

    TEXTO EXTRAÍDO DE LA FDS DEL USUARIO:
    {texto_fds}

    INSTRUCCIONES CRÍTICAS:
    1. Lee cuidadosamente el texto de la FDS recuperado.
    2. Compara el texto con los ítems solicitados en la lista de requerimientos.
    3. NO evalúes la calidad, exactitud o veracidad de la información. Tu única misión es detectar si el tema se menciona.
    4. Tu salida debe ser ÚNICAMENTE una tabla en formato texto separado por tabulaciones (TSV).
    5. Las columnas deben ser exactamente: "Ítem Solicitado" y "Estado (Presente / No Presente)".
    6. Usa los mismos nombres de "Ítem Solicitado" que aparecen en la lista.
    7. Sin saludos, sin explicaciones adicionales, y sin bloques de código Markdown (```).
    """
)

# Secciones objetivo (Solo texto)
SECCIONES_OBJETIVO = [1, 3, 9, 10]

# ==========================================
# 2. MOTOR DE AUDITORÍA AUTOMATIZADA
# ==========================================
def inspeccionar_documento_texto(doc_id: str):
    print(f"\n==================================================")
    print(f" INICIANDO CHECKLIST SGA (SOLO TEXTO): {doc_id}")
    print(f"==================================================\n")
    

    
    llm_inspector = obtener_llm_inspector()
    cadena_inspeccion = PROMPT_INSPECTOR | llm_inspector
    
    reportes_dir = Config.DATA_DIR / "evaluation_reports"
    reportes_dir.mkdir(parents=True, exist_ok=True)
    
    # --- CAMBIO CORE: LEER EL DICCIONARIO CSV ---
    # Asegúrate de que el CSV esté en la raíz de tu proyecto
    ruta_diccionario = Config.ROOT_DIR / "apps" /"api_backend" / "auditor" /  "diccionario_items.csv"
    if not ruta_diccionario.exists():
        print(f" Error: No se encontró el archivo '{ruta_diccionario}'.")
        return
        
    df_diccionario = pd.read_csv(ruta_diccionario)
    resultados_totales = {}

    for num_seccion in SECCIONES_OBJETIVO:
        print(f" Inspeccionando Sección {num_seccion}...")
        
        # Filtrar el CSV: Buscar IDs que empiecen por "N_" seguido de un número del 1 al 9 (ignora los "_0")
        mascara_seccion = df_diccionario['id'].str.match(rf"^{num_seccion}_[1-9]") 
        items_seccion = df_diccionario[mascara_seccion]
        
        if items_seccion.empty:
            print(f"   No hay ítems en el diccionario para la Sección {num_seccion}.")
            continue
            
        # Construir la lista dinámica de cosas que debe buscar el LLM
        lista_requerimientos = "\n".join([f"- {row['descripcion']} (ID: {row['id']})" for _, row in items_seccion.iterrows()])
        
        query_busqueda = f"Contenido de la sección {num_seccion}"
        fragmentos = buscar_contexto(query=query_busqueda, doc_id=doc_id, num_seccion=num_seccion, top_k=10)
        
        if not fragmentos:
            print(f"   No hay datos en la base vectorial para la Sección {num_seccion}.")
            resultados_totales[f"Seccion_{num_seccion}"] = "ERROR: Sección no encontrada en la FDS."
            continue
            
        texto_evidencia = "\n\n".join([f['texto'] for f in fragmentos])
        
        try:
            rate_limiter.wait_if_needed()

            respuesta = cadena_inspeccion.invoke({
                "num_seccion": num_seccion,
                "rubrica": lista_requerimientos,
                "texto_fds": texto_evidencia
            })

            # Registrar consumo de tokens si el modelo los reporta
            tokens = 0
            try:
                meta = getattr(respuesta, "usage_metadata", None) or {}
                tokens = (
                    getattr(meta, "total_tokens", 0)
                    or getattr(meta, "total_token_count", 0)
                    or (meta.get("total_token_count", 0) if isinstance(meta, dict) else 0)
                )
            except Exception:
                pass
            rate_limiter.record_call(int(tokens))

            # Manejo robusto de la salida
            if isinstance(respuesta.content, list):
                veredicto = "".join([bloque.get("text", "") for bloque in respuesta.content if isinstance(bloque, dict)])
            else:
                veredicto = str(respuesta.content)

            resultados_totales[f"Seccion_{num_seccion}"] = veredicto.strip()
            print(f"   Checklist Sección {num_seccion} completado.")
            
        except Exception as e:
            print(f"   ERROR EXACTO en Sección {num_seccion}: {type(e).__name__} - {str(e)}")
            resultados_totales[f"Seccion_{num_seccion}"] = "ERROR: Falló la inspección del LLM."

    # ==========================================
    # 3. GENERACIÓN DE REPORTE FINAL
    # ==========================================
    ruta_reporte = reportes_dir / f"Checklist_SGA_{doc_id}.txt"
    with open(ruta_reporte, 'w', encoding='utf-8') as f:
        f.write(f"REPORTE DE CHECKLIST (PRESENCIA) SGA - {doc_id}\n")
        f.write("="*50 + "\n\n")
        for seccion, veredicto in resultados_totales.items():
            f.write(f"--- SECCIÓN {seccion.upper()} ---\n")
            f.write(f"{veredicto}\n\n")
            
    print(f"\n INSPECCIÓN FINALIZADA. Reporte guardado en: {ruta_reporte}")
    return ruta_reporte
# ==========================================
# PUNTO DE ENTRADA (PRUEBA)
# ==========================================
if __name__ == "__main__":
    DOCUMENTO_PRUEBA = "FDS 22 - Esmalte Uretano AR Comp. B" 
    inspeccionar_documento_texto(DOCUMENTO_PRUEBA)