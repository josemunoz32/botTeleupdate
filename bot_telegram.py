## version2.0
import os
import logging
import re
import asyncio
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
import time
from collections import defaultdict
USUARIOS_COMPRA = defaultdict(float)  # Timestamp de inicio de compra por usuario

async def recordatorio_seguimiento(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    user_id = job_data['user_id']
    identificador = job_data['identificador']
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
Las siguientes variables se leen desde el entorno o desde el archivo .env (usando python-dotenv).
Configura las variables en .env para ocultar credenciales sensibles.
"""
BOT_USERNAME = os.environ['BOT_USERNAME']
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TELEGRAM_CHANNEL_ID = os.environ['TELEGRAM_CHANNEL_ID']
ADMIN_IDS = [int(i) for i in os.environ['ADMIN_IDS'].split(',')]

PRODUCTOS_CACHE = {}

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
    # Si hay más de una consola vinculada, no publicar
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

async def reenviar_al_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    user_id = message.from_user.id if message.from_user else None
    # Solo admins pueden publicar al canal
    if user_id not in ADMIN_IDS:
        return
    contenido = message.text.strip()
    resultado = procesar_mensaje(contenido)
    if not resultado or (isinstance(resultado, dict) and resultado.get('error')):
        error_msg = resultado['error'] if resultado and 'error' in resultado else (
            "❌ Formato no válido.\n\n"
            "Envíame el texto de origen del pack o de la cuenta con el siguiente formato:\n\n"
            "• Cuenta (ejemplo):\n"
            "Nickname: Panda\nTransaction: ...\n====PRICE 20\n\n"
            "• Pack (ejemplo):\n"
            "#1234\nList Game\nMario\nZelda\nEnd Game List\nPrice: 20"
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
    await context.bot.send_message(
        chat_id=TELEGRAM_CHANNEL_ID,
        text=resultado['mensaje'],
        parse_mode='HTML',
        reply_markup=keyboard
    )
    await asyncio.sleep(1)
    await message.reply_text('✅ Mensaje enviado al canal.')

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
                    "<b>¿Cómo continuar?</b>\n\n1️⃣ Pulsa <b>💸 Ver datos para Transferencia Bancaria</b> para ver los datos y realizar el pago.\n2️⃣ Una vez pagado, envía el comprobante aquí mismo (foto o archivo).\n3️⃣ Si tienes dudas, pulsa <b>❓ Ayuda</b> o escribe /ayuda.",
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

"""
Handler para callbacks de botones (transferencia y ayuda).
"""
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
                "Al realizar el pago, aceptas nuestros Términos y Condiciones:\n"
                "🔗 https://pandastoreupdate.web.app/terminos\n\n"
                "🟣💰 <b>Detalles de la Cuenta</b> 🟣\n"
                "• Banco: Falabella\n"
                "• Tipo de cuenta: Corriente\n"
                "• Número de cuenta: 19822486630\n"
                "• RUT: 21.715.187-2\n"
                "• Titular: José Muñoz\n"
                "• Email comprobantes: comprobantesswitch2@gmail.com\n"
                f"• Monto: <b>{producto['precio_clp']:,} CLP</b>\n\n"
                "Una vez realizada la transferencia, envía el comprobante al correo indicado.\n\n"
                "1️⃣ Sigue el paso a paso aquí 👉 https://pandastoreupdate.web.app/instalacion-nintendo\n\n"
                "📬 <b>Contacto para instalación:</b>\n"
                "Telegram: @NintendoChile2\n"
                "WhatsApp: +56 9 7475 1810\n"
                "Instagram: @juegos_nintendo_switch_chile2"
            )
            await query.edit_message_text(
                datos_transferencia,
                parse_mode='HTML'
            )
    elif data == 'ayuda':
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
            "WhatsApp: +56 9 74751810\n"
            "Instagram: @juegos_nintendo_switch_chile2"
        )
        await query.edit_message_text(mensaje, parse_mode='HTML')

async def healthcheck(request):
    return web.Response(text="OK")

"""
Función principal: inicializa el bot y el servidor web.
"""
async def main():
    # Inicializar bot y handlers
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('ayuda', ayuda))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reenviar_al_canal))
    app.add_handler(CallbackQueryHandler(pago_callback))
    # Handler para comprobantes de pago
    app.add_handler(MessageHandler((filters.PHOTO | filters.Document.IMAGE) & (~filters.COMMAND), enviar_comprobante))
    # Servidor web aiohttp
    web_app = web.Application()
    web_app['bot'] = app.bot
    web_app.router.add_get("/healthcheck", healthcheck)
    # Puerto efímero por defecto para evitar conflictos
    port = int(os.environ.get('PORT', 0))
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    # Obtener el puerto real si se usó efímero
    try:
        sockets = getattr(site._server, 'sockets', [])
        if sockets:
            port = sockets[0].getsockname()[1]
    except Exception:
        pass
    # Arrancar el bot en modo polling
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logging.info(f"🚀 Bot y servidor corriendo en puerto {port}")
    # Mantener el proceso vivo
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
