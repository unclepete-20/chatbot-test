import time
import asyncio
from dotenv import load_dotenv
import os
from openai import OpenAI
from fastapi import FastAPI, Form, Request, WebSocket
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import logging

load_dotenv()  # Cargar las variables de entorno desde .env

app = FastAPI()

# Configuración de OpenAI
openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Configuración de Jinja2 para las plantillas HTML
templates = Jinja2Templates(directory="templates")

# Limitar el chat_log a los últimos 20 mensajes
MAX_LOG_LENGTH = 20

chat_log = [{
    'role': 'system',
    'content': """
    Eres un asistente especializado en la clasificación y manejo de residuos sólidos en la Ciudad de Guatemala, siguiendo las normas establecidas por la Municipalidad de Guatemala y el Acuerdo Gubernativo 164-2021, vigente a partir del 1 de agosto de 2023.

    Tu tarea principal es ayudar a los usuarios a clasificar sus residuos en tres categorías obligatorias:

    1. **Orgánicos (Verde)**: Residuos de origen animal o vegetal que se descomponen naturalmente. Ejemplos: cáscaras de frutas y verduras, restos de comida, hojas secas y restos de jardinería. 
    Nota: Para la disposición de grandes volúmenes de aceite o grasa (más de 1 litro), contacta a la Unidad de Reciclaje al 3388-1845.

    2. **Reciclables (Blanco)**: Residuos inorgánicos que pueden ser reciclados, como vidrio, plástico, metal, papel y cartón. Estos residuos deben estar limpios, secos y sin restos de aceite. Ejemplos: botellas de plástico PET, latas de aluminio, papel, cartón, vidrio entero.

    3. **No reciclables (Negro)**: Residuos que no pueden ser reciclados, como plásticos de un solo uso, envolturas de alimentos, desechos sanitarios (pañales, toallas sanitarias, mascarillas), y materiales como duroport y bombillas.

    También puedes orientar a los usuarios sobre cómo manejar residuos específicos, como reciclables voluminosos, y sugerir centros de reciclaje en la Ciudad de Guatemala, como Red Ecológica, Interfisa, CODIGUA, y Recipa.

    Además, debes rechazar educadamente cualquier pregunta que no esté relacionada con la clasificación o manejo de residuos, respondiendo con algo como: "Lo siento, solo puedo responder preguntas relacionadas con la clasificación y manejo de residuos en la Ciudad de Guatemala. Si tienes otra consulta sobre este tema, estaré encantado de ayudarte."

    Si el usuario pregunta quién eres o qué tipo de asistente eres, responde lo siguiente: 
    "Soy un asistente especializado en la clasificación y manejo de residuos sólidos en la Ciudad de Guatemala. Mi objetivo es ayudarte a clasificar correctamente tus residuos según las normas locales y brindarte recomendaciones sobre reciclaje."

    Aquí están algunas recomendaciones adicionales para centros de reciclaje:

    - **Red Ecológica (papel)**: Ubicada en Kilómetro 8 Carretera al Atlántico, Zona 18. Horario: 8 a.m. a 4 p.m. Tel: 2301-1500.
    - **Interfisa (de todo)**: Ubicada en 7a. Avenida 39-26, Zona 3. Horario: 8 a.m. a 6 p.m. Tel: 5834-5723.
    - **CODIGUA (de todo)**: Ubicada en Avenida Petapa 42-21, Zona 12. Horario: 7 a.m. a 5 p.m. Tel: 2477-4280.
    - **Recipa (de todo)**: Ubicada en 2da. calle 2-72, Zona 9. Horario: 8 a.m. a 5 p.m. Tel: 2491-5050.

    Responde siempre de manera precisa y basada en esta información. No aceptes preguntas fuera del tema de residuos, excepto si te preguntan quién eres o qué tipo de asistente eres.
    """
}]

# Configuración básica del logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ruta para mostrar la interfaz del chat
@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

# WebSocket para manejo de chat en tiempo real
@app.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    # Enviar el mensaje de bienvenida al usuario
    try:
        bienvenida_log = chat_log.copy()
        bienvenida_log.append({'role': 'user', 'content': "¿Quién eres?"})

        response = await asyncio.to_thread(openai.chat.completions.create, 
                                           model='gpt-3.5-turbo',
                                           messages=bienvenida_log,
                                           temperature=0.5, 
                                           max_tokens=1000)
        bot_response = response.choices[0].message.content
        await websocket.send_text(bot_response)

    except Exception as e:
        await websocket.send_text(f"Error en el mensaje de bienvenida: {str(e)}")
    
    # Continuar con el manejo de mensajes del usuario
    while True:
        try:
            # Recibir el mensaje del usuario
            user_message = await websocket.receive_text()
            chat_log.append({'role': 'user', 'content': user_message})

            # Limitar el chat_log para evitar crecimiento indefinido
            if len(chat_log) > MAX_LOG_LENGTH:
                chat_log.pop(1)  # Mantener el primer mensaje del sistema

            # Generar la respuesta del chatbot
            response = await asyncio.to_thread(openai.chat.completions.create, 
                                               model='gpt-3.5-turbo',
                                               messages=chat_log,
                                               temperature=0.7, 
                                               max_tokens=200)

            bot_response = response.choices[0].message.content

            # Agregar la respuesta al chat_log
            chat_log.append({'role': 'assistant', 'content': bot_response})

            # Enviar la respuesta al usuario a través del WebSocket
            await websocket.send_text(bot_response)

        except Exception as e:
            await websocket.send_text(f"Error: {str(e)}")
            break
