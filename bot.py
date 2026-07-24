import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)

# Konfigurasi Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State untuk ConversationHandler
GET_PRICE, GET_TENOR = range(2)

# Fungsi Hitung Asuransi "Santai"
def hitung_asuransi(harga: float) -> float:
    if 1_000_000 <= harga <= 10_000_000:
        return 599_000
    elif 10_000_000 < harga <= 30_000_000:
        return 899_000
    elif harga > 30_000_000:
        return 1_299_000  # Tambahan opsional jika di atas 30jt
    return 0.0

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Halo! Selamat datang di **Bot Simulasi Cicilan**.\n\n"
        "Silakan masukkan **Harga Barang** (contoh: `5000000` atau `12500000`):"
    )
    return GET_PRICE

# Menerima Harga
async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.replace(".", "").replace(",", "").strip()
    try:
        harga = float(text)
        if harga <= 0:
            raise ValueError
        context.user_data["harga"] = harga
        
        await update.message.reply_text(
            f"Harga barang dicatat: **Rp {harga:,.0f}**\n\n"
            "Sekarang, masukkan **Tenor Cicilan** dalam bulan (contoh: `6`, `12`, `24`):"
        )
        return GET_TENOR
    except ValueError:
        await update.message.reply_text("Format harga tidak valid. Masukkan angka saja (contoh: `7500000`):")
        return GET_PRICE

# Menerima Tenor dan Hitung Hasil Simulasi
async def receive_tenor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        tenor = int(text)
        if tenor <= 0:
            raise ValueError
        
        harga = context.user_data["harga"]
        asuransi = hitung_asuransi(harga)
        total_pokok_asuransi = harga + asuransi
        
        # Simulasi bunga sederhana (misal 1.5% flat per bulan dari harga barang)
        bunga_per_bulan = (harga * 0.015) 
        total_bunga = bunga_per_bulan * tenor
        
        total_keseluruhan = total_pokok_asuransi + total_bunga
        cicilan_per_bulan = total_keseluruhan / tenor

        pesan = (
            f"📊 **HASIL SIMULASI CICILAN** 📊\n\n"
            f"• Harga Barang: Rp {harga:,.0f}\n"
            f"• Asuransi Santai: Rp {asuransi:,.0f}\n"
            f"• Tenor: {tenor} Bulan\n"
            f"-----------------------------------\n"
            f"• **Cicilan per Bulan: Rp {cicilan_per_bulan:,.0f} / bln**\n"
            f"• Total Pembayaran: Rp {total_keseluruhan:,.0f}\n\n"
            f"Ketik /start untuk menghitung simulasi baru."
        )
        
        await update.message.reply_text(pesan, parse_mode="Markdown")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("Format tenor tidak valid. Masukkan angka bulat bulan (contoh: `12`):")
        return GET_TENOR

# /cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Simulasi dibatalkan. Ketik /start untuk mulai lagi.")
    return ConversationHandler.END

def main() -> None:
    # Ambil Token dari Environment Variable Railway
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        logger.error("TELEGRAM_TOKEN tidak ditemukan di environment variables!")
        return

    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)],
            GET_TENOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tenor)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Menjalankan bot dengan polling
    application.run_polling()

if __name__ == "__main__":
    main()
      
