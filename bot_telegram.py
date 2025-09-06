import os
import requests
import re
import asyncio
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram import Update
from telegram.ext import ApplicationBuilder
from aiohttp import web

BOT_USERNAME = os.environ.get('BOT_USERNAME', 'PandaStoreSwitchBot')
PAYPAL_BUSINESS_EMAIL = os.environ.get('PAYPAL_BUSINESS_EMAIL')
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN')
MERCADOPAGO_PUBLIC_KEY = os.environ.get('MERCADOPAGO_PUBLIC_KEY')
PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID')
ADMIN_IDS = [int(i) for i in os.environ.get('ADMIN_IDS', '5158777962').split(',')]

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

def procesar_mensaje(mensaje):
    # Emojis y separadores
    PANDA = '🐼'
    CASA = '🏠'
    CODIGO = '🪪'
    CONTROL = '🎮'
    DADO = '🎲'
    USDT = '🇺🇸'
    BANDERA_CL = '🇨🇱'
    DINERO = '💰'
    RELOJ = '⏰'
    CONTACTO = '📞'
    SEPARADOR = '━━━━━━━━━━━━━━'

    lineas = mensaje.strip().split('\n')
    # Detectar tipo de mensaje
    es_nickname = any('Nickname' in l for l in lineas)
    if es_nickname:
        # --- Mensaje tipo Nickname ---
        nickname = ''
        juegos = []
        precio_usd = 0
        en_transacciones = False
        for linea in lineas:
            if linea.startswith('Nickname'):
                nickname = linea.split(':',1)[1].strip()
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
                # Solo el nombre del juego
                juego = linea.split('-')[0].strip()
                juegos.append(f"{DADO} {juego}")
        # Validar que existan nickname, juegos y precio
        if not nickname or not juegos or not precio_usd:
            return None
        precio_clp = precio_usd * 1000 + 20000
        precio_usdt = precio_usd + 25
        mensaje_modificado = (
            f"{CASA} <b>CUENTA NINTENDO</b>\n"
            f"👤 <b>Nickname:</b> <code>{nickname}</code>\n\n"
            f"{CONTROL} <b>JUEGOS INCLUIDOS</b>\n"
            f"{SEPARADOR}\n"
            + '\n'.join(juegos) + f"\n{SEPARADOR}\n\n"
            f"{DINERO} <b>PRECIO:</b>\n"
            f"<b>{precio_clp:,} CLP</b> {BANDERA_CL}   <b>{precio_usdt}.00 USD</b> {USDT}\n"
            f"{RELOJ} <b>Disponible las 24 horas</b>\n"
            f"{PANDA} <b>CONTÁCTAME:</b> @NintendoChile2"
        )
        return mensaje_modificado
    else:
        # --- Mensaje tipo Código (Pack) ---
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
        # Validar que existan codigo, juegos y precio
        if not codigo or not juegos or not precio_usd:
            return None
        precio_clp = precio_usd * 1000 + 20000
        precio_usdt = precio_usd + 25
        mensaje_modificado = (
            f"{CASA} <b>PACK #{codigo}</b>\n"
            f"{CONTROL} <b>JUEGOS INCLUIDOS</b>\n"
            f"{SEPARADOR}\n"
            + '\n'.join(juegos) + f"\n{SEPARADOR}\n\n"
            f"{DINERO} <b>PRECIO:</b>\n"
            f"<b>{precio_clp:,} CLP</b> {BANDERA_CL}   <b>{precio_usdt}.00 USD</b> {USDT}\n"
            f"{RELOJ} <b>Disponible de 12:00 a 18:00 hrs</b>\n"
            f"{PANDA} <b>CONTÁCTAME:</b> @NintendoChile2"
        )
        return mensaje_modificado

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print('DEBUG /start:')
    print('  context.args:', context.args)
    if hasattr(update, 'message') and update.message:
        print('  update.message.text:', update.message.text)
    # Soportar argumentos en /start (Telegram puede enviar todo como un solo string)
    arg = None
    if context.args:
        arg = ' '.join(context.args)
    elif hasattr(update, 'message') and update.message and update.message.text and ' ' in update.message.text:
        # /start postpago_xxx o /start buy_xxx
        arg = update.message.text.split(' ', 1)[1].strip()

    if arg:
        if arg.startswith('buy_'):
            identificador = arg[4:]
            producto = obtener_producto(identificador)
            if producto:
                texto = f"¡Bienvenido! Estás a punto de comprar este producto:\n\n{producto['mensaje']}\n\nElige una opción:"
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(f'🇨🇱 Nacional (MercadoPago) - ${producto["precio_clp"]:,} CLP', callback_data=f'nacional_{identificador}'),
                        InlineKeyboardButton(f'🌎 Internacional (PayPal) - ${producto["precio_usdt"]} USD', callback_data=f'internacional_{identificador}'),
                    ]
                ])
                await update.message.reply_text(texto, parse_mode='HTML', reply_markup=keyboard)
            else:
                await update.message.reply_text('Producto no encontrado o expirado.')
        elif arg.startswith('postpago_'):
            identificador = arg[9:]
            producto = obtener_producto(identificador)
            if producto:
                # Notificar a los admins sobre la compra
                user = update.effective_user
                username = user.username if user and user.username else f"id:{user.id}" if user else "desconocido"
                admin_msg = (
                    f"🛒 <b>Compra recibida</b>\n"
                    f"Cliente: @{username}\n"
                    f"Producto: <code>{identificador}</code>\n"
                    f"Detalle:\n{producto['mensaje']}"
                )
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode='HTML')
                    except Exception:
                        pass
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton('📦 Instalación (Ir a la web)', url='https://juegosnintendoswitch.com/pages/instalacion')]
                ])
                await update.message.reply_text(
                    '✅ ¡Pago recibido!\n\n'
                    'Pulsa el botón para ver los pasos de instalación.\n\n'
                    '📱 <b>Contáctame:</b>\n'
                    'Telegram: @NintendoChile2\n'
                    'WhatsApp: <a href="https://wa.me/56974751810">+56 9 7475 1810</a>\n'
                    'Instagram: <a href="https://instagram.com/juegos_nintendo_switch_chile2">@juegos_nintendo_switch_chile2</a>',
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text('¡Pago recibido! Pronto recibirás instrucciones para la instalación.')
        else:
            await update.message.reply_text('¡Hola! Envíame el mensaje que quieras publicar en el canal.')
    else:
        await update.message.reply_text('¡Hola! Envíame el mensaje que quieras publicar en el canal.')


async def reenviar_al_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in ADMIN_IDS:
        texto_modificado = procesar_mensaje(update.message.text)
        if not texto_modificado:
            await update.message.reply_text('El mensaje no cumple con el formato requerido. No se envió al canal.')
            return
        # Determinar identificador único del producto (código o nickname)
        lineas = update.message.text.strip().split('\n')
        if any('Nickname' in l for l in lineas):
            identificador = ''
            for linea in lineas:
                if linea.startswith('Nickname'):
                    identificador = linea.split(':',1)[1].strip()
                    break
            tipo = 'cuenta'
        else:
            identificador = lineas[0].strip()
            tipo = 'pack'
        # Extraer precios para cache
        if tipo == 'cuenta':
            m = re.search(r'====PRICE\s*([0-9]+)', update.message.text)
            precio_usd = int(m.group(1)) if m else 0
        else:
            m = re.search(r'Price\s*:\s*([0-9]+)', update.message.text)
            precio_usd = int(m.group(1)) if m else 0
        precio_clp = precio_usd * 1000 + 20000
        precio_usdt = precio_usd + 25
        guardar_producto(identificador, texto_modificado, tipo, precio_clp, precio_usdt)
        # Botón con enlace al bot y parámetro de producto
        url_boton = f"https://t.me/{BOT_USERNAME}?start=buy_{identificador}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('🛒 Comprar', url=url_boton)]
        ])
        # Espera 2 segundos antes de publicar (para evitar flood)
        await asyncio.sleep(2)
        await context.bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=texto_modificado, parse_mode='HTML', reply_markup=keyboard)
        await update.message.reply_text('Mensaje enviado al canal.')
async def pago_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = getattr(query, 'data', None)
    if data and data.startswith('webinstalacion_'):
        identificador = data[len('webinstalacion_'):]
        # Redirigir directamente a la web de instalación
        await query.edit_message_text(
            "Haz clic en el siguiente enlace para ver la guía de instalación:\n\n"
            "https://juegosnintendoswitch.com/pages/instalacion"
        )
        return
    if data and data.startswith('confirmainstalacion_'):
        await query.edit_message_text('Perfecto, aquí tienes la guía de instalación: https://juegosnintendoswitch.com/pages/instalacion')
        return
    if data and data.startswith('nopago_'):
        await query.edit_message_text('Por favor, realiza el pago antes de continuar con la instalación.')
        return
    if data.startswith('nacional_'):
        identificador = data[len('nacional_'):]
        producto = obtener_producto(identificador)
        if producto:
            # Crear preferencia de pago MercadoPago
            url = 'https://api.mercadopago.com/checkout/preferences'
            headers = {
                'Authorization': f'Bearer {MERCADOPAGO_ACCESS_TOKEN}',
                'Content-Type': 'application/json'
            }
            data_mp = {
                "items": [
                    {
                        "title": f"Nintendo Switch {identificador}",
                        "quantity": 1,
                        "currency_id": "CLP",
                        "unit_price": producto['precio_clp']
                    }
                ],
                "payer": {
                    "email": "comprador_test@test.com"
                },
                "payment_methods": {
                    "excluded_payment_types": [{"id": "ticket"}],
                    "installments": 1
                },
                "back_urls": {
                    "success": f"https://t.me/{BOT_USERNAME}?start=postpago_{identificador}",
                    "failure": f"https://t.me/{BOT_USERNAME}?start=postpago_{identificador}",
                    "pending": f"https://t.me/{BOT_USERNAME}?start=postpago_{identificador}"
                },
                "auto_return": "approved"
            }
            try:
                resp = requests.post(url, headers=headers, json=data_mp)
                resp.raise_for_status()
                mp_url = resp.json().get('init_point', 'https://www.mercadopago.cl')
            except Exception as e:
                mp_url = 'https://www.mercadopago.cl'
            await query.edit_message_text(f"Para pagar con MercadoPago (CLP):\n\nMonto: ${producto['precio_clp']:,} CLP\n\n<a href='{mp_url}'>Pagar ahora</a>", parse_mode='HTML')
        else:
            await query.edit_message_text('Producto no encontrado o expirado.')
    elif data.startswith('internacional_'):
        identificador = data[len('internacional_'):]
        producto = obtener_producto(identificador)
        if producto:
            # Generar link de pago PayPal usando el email sandbox y monto con dos decimales
            monto_paypal = f"{producto['precio_usdt']:.2f}"
            return_url = f"https://t.me/{BOT_USERNAME}?start=postpago_{identificador}"
            paypal_url = (
                f"https://www.sandbox.paypal.com/cgi-bin/webscr?cmd=_xclick"
                f"&business={PAYPAL_BUSINESS_EMAIL}"
                f"&item_name=Nintendo+Switch+{identificador}"
                f"&amount={monto_paypal}"
                f"&currency_code=USD"
                f"&return={return_url}"
            )
            await query.edit_message_text(
                f"Para pagar con PayPal (USDT):\n\nMonto: ${monto_paypal} USDT\n<a href='{paypal_url}'>Pagar ahora</a>",
                parse_mode='HTML')
        else:
            await query.edit_message_text('Producto no encontrado o expirado.')
    else:
        await update.message.reply_text('Este bot es solo para recibir información. No puedes enviar mensajes al canal.')
        
WEBHOOK_PATH = f"/webhook/{TELEGRAM_BOT_TOKEN}"
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Debes definir esto en Render, ejemplo: https://tu-servicio.onrender.com

# Mueve la creación de la app de Telegram aquí para que sea global
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(CommandHandler('start', start))
app.add_handler(CallbackQueryHandler(pago_callback))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reenviar_al_canal))

async def webhook_handler(request):
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
    except Exception as e:
        import logging
        logging.exception("Error en webhook_handler")
    return web.Response()

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.INFO)

    port = int(os.environ.get('PORT', 8080))
    async def on_startup(web_app):
        await app.initialize()  # <-- Inicializa la aplicación de Telegram
        await app.bot.set_webhook(url=WEBHOOK_URL + WEBHOOK_PATH)
    async def on_shutdown(web_app):
        await app.bot.delete_webhook()
        await app.shutdown()    # <-- Limpia la aplicación de Telegram
        await app.stop()        # <-- Detiene la aplicación de Telegram

    web_app = web.Application()
    web_app.router.add_post(WEBHOOK_PATH, webhook_handler)
    web_app.on_startup.append(on_startup)
    web_app.on_shutdown.append(on_shutdown)

    web.run_app(web_app, port=port)

# En la función reenviar_al_canal, el cliente (usuario final) NO recibe ningún mensaje automáticamente cuando el admin publica un pack.
# Solo el canal recibe el mensaje con el botón "Comprar".
# El cliente solo recibe mensajes si interactúa con el bot (por ejemplo, pulsando "Comprar" en el canal o usando /start con un parámetro).

# El código ya está listo para desplegar en Render o cualquier otro servidor siempre activo.
# Solo asegúrate de:
# 1. Guardar tus claves y tokens en variables de entorno (no en el código) para mayor seguridad.
# 2. Usar el webhook de Telegram en vez de polling si Render no soporta procesos en background.
#    (Polling funciona bien en servidores que permiten procesos siempre activos.)
# 3. Instalar todas las dependencias en requirements.txt:
#    python-telegram-bot
#    requests

# Si quieres máxima seguridad y compatibilidad Render:
# - Usa variables de entorno para las claves.
# - Considera cambiar ApplicationBuilder().token(...) por Application.builder().token(...).webhook(...) si usas webhooks.

# Por defecto, tu código funcionará en Render si usas un servicio tipo "background worker" o "web service" con polling.
#    python-telegram-bot
#    requests

# Si quieres máxima seguridad y compatibilidad Render:
# - Usa variables de entorno para las claves.
# - Considera cambiar ApplicationBuilder().token(...) por Application.builder().token(...).webhook(...) si usas webhooks.

# Por defecto, tu código funcionará en Render si usas un servicio tipo "background worker" o "web service" con polling.
