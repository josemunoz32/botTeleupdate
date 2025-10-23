## version2.1
import os
import logging
import re
import asyncio
import time
from collections import defaultdict
from asyncio import Queue
from dotenv import load_dotenv
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
    ApplicationBuilder,
)
from aiohttp import web

load_dotenv()

"""
Funciones de bienvenida y ayuda para el usuario.
"""
async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "👋 <b>¡Bienvenido a Juegos Nintendo Switch Chile2!</b>\n\n"
        "Aquí puedes comprar packs y cuentas de juegos digitales para Nintendo Switch de forma segura y rápida.\n\n"
        "<b>¿Cómo comprar?</b>\n"
        "1️⃣ Elige el pack o cuenta que te interese en el canal.\n"
        "2️⃣ Pulsa el botón <b>Comprar</b> para iniciar la compra.\n"
        "3️⃣ Realiza la transferencia bancaria siguiendo las instrucciones.\n"
        "4️⃣ Envía el comprobante de pago aquí mismo (como foto o archivo).\n"
        "5️⃣ Un administrador validará tu pago y te contactará para la instalación.\n\n"
        "<b>Comandos útiles:</b>\n"
        "/start — Ver mensaje de bienvenida\n"
        "/ayuda — Ver este mensaje de ayuda\n\n"
        "Si tienes dudas, contáctanos:\n"
        "Telegram: @NintendoChile2\n"
        "WhatsApp: +56 9 7475 1810\n"
        "Instagram: @juegos_nintendo_switch_chile2"
    )
    await update.message.reply_text(mensaje, parse_mode='HTML')

async def bienvenida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "👋 <b>¡Bienvenido a Juegos Nintendo Switch Chile2!</b>\n\n"
        "¿Quieres comprar juegos digitales para tu Nintendo Switch?\n"
        "Explora los packs y cuentas en nuestro canal y sigue las instrucciones para comprar.\n\n"
        "Si necesitas ayuda, escribe /ayuda."
    )
    await update.message.reply_text(mensaje, parse_mode='HTML')

"""
Seguimiento automático tras iniciar compra.
"""
USUARIOS_COMPRA = defaultdict(float)  # Timestamp de inicio de compra por usuario

async def recordatorio_seguimiento(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data['user_id']
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "⏰ <b>Recordatorio de compra</b>\n\n"
                "¿Aún deseas completar tu compra?\n"
                "Recuerda realizar la transferencia y enviar el comprobante aquí mismo para continuar con la entrega.\n\n"
                "Si tienes dudas, escribe /ayuda o pulsa el botón de ayuda."
            ),
            parse_mode='HTML'
        )
    except Exception:
        pass

"""
Confirmación de pago manual por foto o archivo.
"""
async def enviar_comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not update.message.photo and not update.message.document:
        await update.message.reply_text("Por favor, envía una foto o archivo del comprobante de transferencia.")
        return

    file_id = None
    es_foto = False
    if update.message.photo:
        es_foto = True
        file_id = update.message.photo[-1].file_id
    elif update.message.document:
        file_id = update.message.document.file_id

    extra = update.message.caption or update.message.text or ""
    caption = (
        "🧾 <b>Nuevo comprobante de pago</b>\n\n"
        f"Usuario: {user.first_name or ''} (@{user.username})\n"
        f"User ID: <code>{user.id}</code>\n"
        f"Mensaje: {extra}"
    )

    await update.message.reply_text("✅ Comprobante recibido. Será revisado por un administrador. Te contactaremos pronto.", parse_mode='HTML')

    for admin_id in ADMIN_IDS:
        try:
            if es_foto:
                await context.bot.send_photo(chat_id=admin_id, photo=file_id, caption=caption, parse_mode='HTML')
            else:
                await context.bot.send_document(chat_id=admin_id, document=file_id, caption=caption, parse_mode='HTML')
        except Exception as e:
            logging.warning(f"No se pudo enviar comprobante al admin {admin_id}: {e}")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

"""
Variables de entorno
"""
BOT_USERNAME = os.environ['BOT_USERNAME']
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHANNEL_ID = os.environ['TELEGRAM_CHANNEL_ID']
ADMIN_IDS = [int(i) for i in os.environ['ADMIN_IDS'].split(',')]

PRODUCTOS_CACHE = {}
cola_envio = Queue()  # Cola asincrónica para enviar mensajes al canal

def guardar_producto(identificador, mensaje, tipo, precio_clp, precio_usdt):
    PRODUCTOS_CACHE[identificador] = {
        'mensaje': mensaje,
        'tipo': tipo,
        'precio_clp': precio_clp,
        'precio_usdt': precio_usdt
    }

def obtener_producto(identificador):
    return PRODUCTOS_CACHE.get(identificador)

"""
Procesa el texto de origen y genera el mensaje para publicar.
"""
def procesar_mensaje(mensaje):
    PANDA = '🐼'
    CASA = '🏠'
    CONTROL = '🎮'
    DADO = '🎲'
    USDT = '🇺🇸'
    BANDERA_CL = '🇨🇱'
    DINERO = '💰'
    RELOJ = '⏰'
    SEPARADOR = '━━━━━━━━━━━━━━'
    lineas = mensaje.strip().split('\n')

    linked_consoles = None
    for l in lineas:
        if l.strip().startswith('Linked Consoles'):
            try:
                linked_consoles = int(re.search(r'Linked Consoles\s*:\s*(\d+)', l).group(1))
            except Exception:
                linked_consoles = None
            break

    if linked_consoles is not None and linked_consoles >= 2:
        return {'error': f'❌ No se puede publicar: la cuenta tiene {linked_consoles} consolas vinculadas.'}

    es_nickname = any('Nickname' in l for l in lineas)

    if es_nickname:
        nickname = ''
        juegos = []
        precio_usd = 0
        en_transacciones = False
        for linea in lineas:
            if linea.startswith('Nickname'):
                nickname = linea.split(':', 1)[1].strip()
            if 'Transaction' in linea:
                en_transacciones = True
                continue
            if '====PRICE' in linea:
                m = re.search(r'PRICE\s*([0-9]+)', linea)
                if m:
                    precio_usd = int(m.group(1))
                en_transacciones = False
                continue
            if en_transacciones and linea.strip() and not linea.startswith('='):
                juego = linea.split('-')[0].strip()
                juegos.append(f"{DADO} {juego}")
        if not nickname or not juegos or not precio_usd:
            return None
        precio_clp = precio_usd * 1000 + 15000
        precio_usdt = precio_usd + 25
        mensaje_modificado = (
            f"{CASA} <b>CUENTA NINTENDO</b>\n"
            f"👤 <b>Nickname:</b> <code>{nickname}</code>\n\n"
            f"{CONTROL} <b>JUEGOS INCLUIDOS</b>\n"
            f"{SEPARADOR}\n" + '\n'.join(juegos) + f"\n{SEPARADOR}\n\n"
            f"{DINERO} <b>PRECIO:</b>\n"
            f"<b>{precio_clp:,} CLP</b> {BANDERA_CL} <b>{precio_usdt}.00 USD</b> {USDT}\n"
            f"{RELOJ} <b>Disponible las 24 horas</b>\n"
            f"{PANDA} <b>CONTÁCTAME:</b> @NintendoChile2"
        )
        identificador = f"cuenta_{re.sub(r'[^a-zA-Z0-9]+', '', nickname)}_{int(time.time())}"
        return {
            'mensaje': mensaje_modificado,
            'tipo': 'cuenta',
            'precio_clp': precio_clp,
            'precio_usdt': precio_usdt,
            'identificador': identificador,
        }

    else:
        codigo = lineas[0].strip()
        juegos = []
        en_lista = False
        precio_usd = 0
        for linea in lineas:
            if 'List Game' in linea:
                en_lista = True
                continue
            if 'End Game List' in linea:
                en_lista = False
                continue
            if en_lista and linea.strip():
                juegos.append(f"{DADO} {linea.strip()}")
        for linea in lineas:
            m = re.search(r'Price\s*:\s*([0-9]+)', linea)
            if m:
                precio_usd = int(m.group(1))
                break
        if not codigo or not juegos or not precio_usd:
            return None
        precio_clp = precio_usd * 1000 + 20000
        precio_usdt = precio_usd + 25
        mensaje_modificado = (
            f"{CASA} <b>PACK #{codigo}</b>\n"
            f"{CONTROL} <b>JUEGOS INCLUIDOS</b>\n"
            f"{SEPARADOR}\n" + '\n'.join(juegos) + f"\n{SEPARADOR}\n\n"
            f"{DINERO} <b>PRECIO:</b>\n"
            f"<b>{precio_clp:,} CLP</b> {BANDERA_CL} <b>{precio_usdt}.00 USD</b> {USDT}\n"
            f"{RELOJ} <b>Disponible de 12:00 a 19:00 hrs</b>\n"
            f"{PANDA} <b>CONTÁCTAME:</b> @NintendoChile2"
        )
        identificador = f"pack_{re.sub(r'[^a-zA-Z0-9]+', '', codigo)}_{int(time.time())}"
        return {
            'mensaje': mensaje_modificado,
            'tipo': 'pack',
            'precio_clp': precio_clp,
            'precio_usdt': precio_usdt,
            'identificador': identificador,
        }

"""
Cola de envío segura (evita perder mensajes y respeta límites)
"""
async def procesar_cola_envio(app):
    while True:
        item = await cola_envio.get()
        chat_id = item["chat_id"]
        texto = item["texto"]
        markup = item["markup"]
        try:
            await app.bot.send_message(chat_id=chat_id, text=texto, parse_mode='HTML', reply_markup=markup)
            logging.info("✅ Mensaje enviado correctamente al canal.")
        except Exception as e:
            logging.warning(f"⚠️ Error al enviar mensaje: {e}. Reintentando en 5 segundos.")
            await asyncio.sleep(5)
            await cola_envio.put(item)  # Reintentar
        await asyncio.sleep(1.5)  # Control de velocidad

"""
Publicación al canal (usa la cola)
"""
async def reenviar_al_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    user_id = message.from_user.id if message.from_user else None
    if user_id not in ADMIN_IDS:
        return
    contenido = message.text.strip()
    resultado = procesar_mensaje(contenido)
    if not resultado or (isinstance(resultado, dict) and resultado.get('error')):
        error_msg = resultado['error'] if resultado and 'error' in resultado else (
            "❌ Formato no válido.\n\n"
            "Formato correcto:\n\n"
            "• Cuenta:\nNickname: Panda\nTransaction: ...\n====PRICE 20\n\n"
            "• Pack:\n#1234\nList Game\nMario\nZelda\nEnd Game List\nPrice: 20"
        )
        await message.reply_text(error_msg)
        return

    identificador = resultado['identificador']
    guardar_producto(
        identificador,
        resultado['mensaje'],
        resultado['tipo'],
        resultado['precio_clp'],
        resultado['precio_usdt']
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton('🛒 Comprar este pack', url=f"https://t.me/{BOT_USERNAME}?start=buy_{identificador}")],
        [InlineKeyboardButton('❓ Ayuda', url=f"https://t.me/{BOT_USERNAME}?start=ayuda")]
    ])

    await cola_envio.put({
        "chat_id": TELEGRAM_CHANNEL_ID,
        "texto": resultado['mensaje'],
        "markup": keyboard
    })

    await message.reply_text("🕓 Mensaje agregado a la cola de envío. Se publicará pronto en el canal.")

"""
Start y callbacks
"""
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args and len(args) > 0:
        arg = args[0]
        if arg.startswith('buy_'):
            identificador = arg[len('buy_'):]
            producto = obtener_producto(identificador)
            if producto:
                await update.message.reply_text(
                    f"{producto['mensaje']}",
                    parse_mode='HTML'
                )
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton('💸 Ver datos para Transferencia Bancaria', callback_data=f'transferencia_{identificador}')],
                    [InlineKeyboardButton('❓ Ayuda', callback_data='ayuda')]
                ])
                await update.message.reply_text(
                    "<b>¿Cómo continuar?</b>\n\n1️⃣ Pulsa <b>💸 Ver datos para Transferencia Bancaria</b> para ver los datos y realizar el pago.\n2️⃣ Una vez pagado, envía el comprobante aquí mismo.\n3️⃣ Si tienes dudas, pulsa <b>❓ Ayuda</b>.",
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                user_id = update.message.from_user.id
                USUARIOS_COMPRA[user_id] = time.time()
                context.job_queue.run_once(
                    recordatorio_seguimiento,
                    1800,
                    data={'user_id': user_id, 'identificador': identificador}
                )
            else:
                await update.message.reply_text("❌ Producto no encontrado o expirado.")
            return
    await bienvenida(update, context)

async def pago_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = getattr(query, 'data', None)
    if not data:
        return
    if data.startswith('transferencia_'):
        identificador = data[len('transferencia_'):]
        producto = obtener_producto(identificador)
        if producto:
            datos_transferencia = (
                "💳 <b>Información de Pago – Juegos Nintendo Switch Chile2</b>\n\n"
                "🔗 Términos: https://pandastoreupdate.web.app/terminos\n\n"
                "🟣💰 <b>Detalles de la Cuenta</b> 🟣\n"
                "• Banco: Falabella\n"
                "• Tipo de cuenta: Corriente\n"
                "• Número de cuenta: 19822486630\n"
                "• RUT: 21.715.187-2\n"
                "• Titular: José Muñoz\n"
                "• Email: comprobantesswitch2@gmail.com\n"
                f"• Monto: <b>{producto['precio_clp']:,} CLP</b>\n\n"
                "📬 Contacto:\nTelegram: @NintendoChile2\nWhatsApp: +56 9 7475 1810\nInstagram: @juegos_nintendo_switch_chile2"
            )
            await query.edit_message_text(datos_transferencia, parse_mode='HTML')
    elif data == 'ayuda':
        await query.edit_message_text(
            "👋 <b>¡Bienvenido!</b>\nUsa /ayuda para ver cómo comprar juegos y contactar soporte.",
            parse_mode='HTML'
        )

async def healthcheck(request):
    return web.Response(text="OK")

"""
Función principal
"""
async def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('ayuda', ayuda))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reenviar_al_canal))
    app.add_handler(CallbackQueryHandler(pago_callback))
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE) & (~filters.COMMAND), enviar_comprobante))

    # Servidor web
    web_app = web.Application()
    web_app['bot'] = app.bot
    web_app.router.add_get("/healthcheck", healthcheck)

    port = int(os.environ.get('PORT', 0))
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    try:
        sockets = getattr(site._server, 'sockets', [])
        if sockets:
            port = sockets[0].getsockname()[1]
    except Exception:
        pass

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logging.info(f"🚀 Bot y servidor corriendo en puerto {port}")

    # 🔄 Lanza tarea para procesar la cola de mensajes
    asyncio.create_task(procesar_cola_envio(app))

    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
