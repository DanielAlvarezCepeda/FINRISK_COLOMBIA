# FINRISK — Integración local, entrega final

Base: `index.html` de Entregable_2 (1).zip (SHA-256 `dfaeced04a1318aad5ffd3e2336498c391f007c45c2ecde1c83b7701a9d2308b`). Conserva resumen, indicadores y calidad; reemplaza las vistas predictiva y evaluación. No altera `api/main.py`, el modelo ni sus dependencias. El único comparador disponible es la mediana histórica general; no se inventan pares por tamaño ni condición de insolvencia.

1. Detenga el Uvicorn anterior con Ctrl+C. Ubíquese en la raíz del proyecto.
2. Compruebe que el dashboard local corresponde a la segunda entrega (`Get-FileHash .\dashboard\index.html`); si difiere, revise cambios y conserve una copia. Extraiga este ZIP encima del repositorio, reemplazando `dashboard/index.html` solo si corresponde. No borre archivos existentes.
3. Ejecute `.\.venv-api\Scripts\python.exe -m uvicorn api.dashboard_app:app --host 127.0.0.1 --port 8000`.
4. Abra `http://127.0.0.1:8000/dashboard/` (no abra el HTML con doble clic). Swagger permanece en `http://127.0.0.1:8000/docs`.
5. En Modelo predictivo, cargue Ejemplo A y pulse Calcular puntaje (esperado ~0,2820, sin alerta); luego Ejemplo B (esperado ~0,6066, con alerta). Los puntajes son calculados por la API, no por JavaScript. Los campos deuda, ROA y margen se introducen en porcentaje y se convierten a razones. Liquidez en veces. Modificar la entrada limpia la predicción anterior.
6. En Evaluación del modelo compruebe sensibilidad 40%, precisión de alertas 2,48%, AP 0,02282; 62 VP, 93 FN, 2442 FP, 26352 VN. Prueba 2024 reutilizada; no es una validación independiente ni prospectiva.
7. Pruebe los filtros de año y navegación. Capture las dos predicciones y las métricas para evidencias. No se deben incluir datos reales confidenciales en el video ni capturas.

Validación del paquete: comprobación sintáctica JS y prueba de navegador con respuestas simuladas del contrato y métricas publicadas; no equivale a probar el servicio completo con la versión original de Python y bibliotecas. La inferencia real del modelo se validó por separado en el equipo del usuario. La integración local completa y Docker/AWS quedan pendientes de verificar.

No subir el entorno `.venv-api/` ni `models/*.joblib` a GitHub. Registrar solo fuentes y documentación tras validar los resultados.
