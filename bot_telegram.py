import os
import logging
import requests
import re
import asyncio
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

# -------------------------
# Configura logging para consola
# -------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# -------------------------
# Variables de entorno
# -------------------------
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'PandaStoreSwitchBot')
PAYPAL_BUSINESS_EMAIL = os.environ.get('PAYPAL_BUSINESS_EMAIL')
MERCADOPAGO_ACCESS_TOKEN = os.environ.get('MERCADOPAGO_ACCESS_TOKEN')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID')
ADMIN_IDS = [int(i) for i in os.environ.get('ADMIN_IDS', '5158777962').split(',')]

# -------------------------
# Cache de productos
# -------------------------
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

# -------------------------
# Procesamiento de mensajes
# -------------------------
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
    es_nickname = any('Nickname' in l for l in lineas)
    
    if es_nickname:
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
                juego = linea.split('-')[0].strip()
                juegos.append(f"{DADO} {juego}")
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
            f"{SEPARADOR}\n"
            + '\n'.join(juegos) + f"\n{SEPARADOR}\n\n"
            f"{DINERO} <b>PRECIO:</b>\n"
            f"<b>{precio_clp:,} CLP</b> {BANDERA_CL}   <b>{precio_usdt}.00 USD</b> {USDT}\n"
            f"{RELOJ} <b>Disponible de 12:00 a 18:00 hrs</b>\n"
            f"{PANDA} <b>CONTÁCTAME:</b> @NintendoChile2"
        )
        return mensaje_modificado

# -------------------------
# Handlers del bot
# -------------------------
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
                    [InlineKeyboardButton('💳 Pagar con PayPal', callback_data=f'internacional_{identificador}')],
                    [InlineKeyboardButton('💵 Pagar con MercadoPago', callback_data=f'nacional_{identificador}')]
                ])
                await update.message.reply_text(
                    "Elige un método de pago:",
                    reply_markup=keyboard
                )
            else:
                await update.message.reply_text("❌ Producto no encontrado o expirado.")
            return
        elif arg.startswith('postpago_'):
            identificador = arg[len('postpago_'):]
            producto = obtener_producto(identificador)
            if producto:
                pasos_url = "https://juegosnintendoswitch.com/pages/instalacion"
                contactos = (
                    "📬 Contactos:\n"
                    "Telegram: @NintendoChile2\n"
                    "WhatsApp: +56 9 1234 5678\n"
                    "Instagram: @NintendoChile2"
                )
                await update.message.reply_text(
                    f"✅ Pago recibido por {identificador}.\n\n"
                    f"🔹 Pasos de instalación: {pasos_url}\n\n"
                    f"{contactos}",
                    parse_mode='HTML'
                )
                for admin_id in ADMIN_IDS:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"✅ El pack {identificador} ha sido comprado por @{update.message.from_user.username or update.message.from_user.full_name}"
                    )
            return
    await update.message.reply_text("✅ El bot está activo y funcionando correctamente.")

async def reenviar_al_canal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id in ADMIN_IDS:
        texto_modificado = procesar_mensaje(update.message.text)
        if not texto_modificado:
            await update.message.reply_text('El mensaje no cumple con el formato requerido. No se envió al canal.')
            return

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

        if tipo == 'cuenta':
            m = re.search(r'====PRICE\s*([0-9]+)', update.message.text)
            precio_usd = int(m.group(1)) if m else 0
        else:
            m = re.search(r'Price\s*:\s*([0-9]+)', update.message.text)
            precio_usd = int(m.group(1)) if m else 0

        precio_clp = precio_usd * 1000 + 20000
        precio_usdt = precio_usd + 25
        guardar_producto(identificador, texto_modificado, tipo, precio_clp, precio_usdt)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton('🛒 Comprar', url=f"https://t.me/{BOT_USERNAME}?start=buy_{identificador}")]
        ])
        await context.bot.send_message(
            chat_id=TELEGRAM_CHANNEL_ID,
            text=texto_modificado,
            parse_mode='HTML',
            reply_markup=keyboard
        )
        await asyncio.sleep(2)
        await update.message.reply_text('Mensaje enviado al canal.')

async def pago_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = getattr(query, 'data', None)
    if not data:
        return

    if data.startswith('nacional_'):
        identificador = data[len('nacional_'):]
        producto = obtener_producto(identificador)
        if producto:
            url = 'https://api.mercadopago.com/checkout/preferences'
            headers = {'Authorization': f'Bearer {MERCADOPAGO_ACCESS_TOKEN}', 'Content-Type': 'application/json'}
            data_mp = {
                "items":[{"title": f"Nintendo Switch {identificador}","quantity":1,"currency_id":"CLP","unit_price": producto['precio_clp']}],
                "payer": {"email":"comprador_test@test.com"},
                "payment_methods":{"excluded_payment_types":[{"id":"ticket"}],"installments":1},
                "back_urls":{"success":f"https://t.me/{BOT_USERNAME}?start=postpago_{identificador}",
                             "failure":f"https://t.me/{BOT_USERNAME}?start=postpago_{identificador}",
                             "pending":f"https://t.me/{BOT_USERNAME}?start=postpago_{identificador}"},
                "auto_return":"approved"
            }
            try:
                resp = requests.post(url, headers=headers, json=data_mp)
                resp.raise_for_status()
                mp_url = resp.json().get('init_point', 'https://www.mercadopago.cl')
            except Exception:
                mp_url = 'https://www.mercadopago.cl'
            await query.edit_message_text(f"Para pagar con MercadoPago (CLP):\n\nMonto: ${producto['precio_clp']:,} CLP\n\n<a href='{mp_url}'>Pagar ahora</a>", parse_mode='HTML')

    elif data.startswith('internacional_'):
        identificador = data[len('internacional_'):]
        producto = obtener_producto(identificador)
        if producto:
            monto_paypal = f"{producto['precio_usdt']:.2f}"
            return_url = f"https://t.me/{BOT_USERNAME}?start=postpago_{identificador}"
            paypal_url = (
                f"https://www.paypal.com/cgi-bin/webscr?cmd=_xclick"
                f"&business={PAYPAL_BUSINESS_EMAIL}"
                f"&item_name=Nintendo+Switch+{identificador}"
                f"&amount={monto_paypal}"
                f"&currency_code=USD"
                f"&return={return_url}"
            )
            await query.edit_message_text(f"Para pagar con PayPal (USD):\n\nMonto: ${monto_paypal} USD\n<a href='{paypal_url}'>Pagar ahora</a>", parse_mode='HTML')

# -------------------------
# Endpoint para UptimeRobot
# -------------------------
async def healthcheck(request):
    return web.Response(text="OK")

# -------------------------
# Main
# -------------------------
async def main():
    port = int(os.environ.get('PORT', 10000))
    webhook_url = f"https://{os.environ['RENDER_EXTERNAL_HOSTNAME']}/webhook"

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), reenviar_al_canal))
    application.add_handler(CallbackQueryHandler(pago_callback))

    # Eliminar polling y activar webhook
    await application.bot.delete_webhook()
    await application.bot.set_webhook(webhook_url)

    # Servidor aiohttp
    web_app = web.Application()
    web_app.router.add_get("/healthcheck", healthcheck)
    web_app.router.add_post("/webhook", application.update_queue.put)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    logging.info(f"🚀 Bot y servidor corriendo en puerto {port}, usando Webhooks en {webhook_url}")

    # Mantener app corriendo
    await application.start()
    await application.updater.start_polling()  # <-- ¡OJO! Ya no usamos polling real
    await application.updater.wait()

if __name__ == '__main__':
    asyncio.run(main())
