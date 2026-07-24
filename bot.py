import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
)

# Konfigurasi Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State untuk ConversationHandler: Harga -> DP -> Tenor
GET_PRICE, GET_DP, GET_TENOR = range(3)

# Fungsi untuk mengambil nominal perlindungan di balik layar berdasarkan SISA POKOK (setelah DP)
def ambil_biaya_perlindungan(sisa_pokok: float) -> float:
    if 1_000_000 <= sisa_pokok <= 10_000_000:
        return 599_000
    elif 10_000_000 < sisa_pokok <= 30_000_000:
        return 899_000
    elif sisa_pokok > 30_000_000:
        return 1_299_000
    return 0.0

# Fungsi untuk mengambil biaya admin di balik layar berdasarkan tenor
def ambil_biaya_admin(tenor: int) -> float:
    if tenor in [3, 6, 9, 12]:
        return 199_000
    elif tenor in [15, 18, 21, 24]:
        return 299_000
    return 0.0

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pesan_mulai = (
        "✨ *SELAMAT DATANG DI SIMULASI CICILAN* ✨\n"
        "🏢 *HOME CREDIT INDONESIA*\n\n"
        "📦 Silakan ketik dan kirimkan **Harga Barang** yang ingin anda hitung:\n\n"
        "_(Contoh: 5.000.000 atau 5000000)_"
    )
    await update.message.reply_text(pesan_mulai, parse_mode="Markdown")
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
            f"✅ Harga Barang tercatat: *Rp {harga:,.0f}*\n\n"
            "💵 Masukkan jumlah **Uang Muka (DP)** yang ingin dibayarkan:\n\n"
            "_(Ketik 0 jika tanpa DP, atau masukkan nominal seperti 200.000-1.000.000)_",
            parse_mode="Markdown"
        )
        return GET_DP
    except ValueError:
        await update.message.reply_text("⚠️ Format harga tidak valid. Masukkan angka saja tanpa titik/koma (contoh: `7500000`):")
        return GET_PRICE

# Menerima DP
async def receive_dp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.replace(".", "").replace(",", "").strip()
    try:
        dp = float(text)
        harga = context.user_data["harga"]
        
        if dp < 0:
            raise ValueError
        if dp >= harga:
            await update.message.reply_text("⚠️ DP tidak boleh melebihi atau sama dengan Harga Barang. Masukkan nominal DP yang valid:")
            return GET_DP
            
        context.user_data["dp"] = dp
        sisa_pokok = harga - dp
        
        # Batasan tenor berdasarkan sisa pokok (1 jt - 5 jt maksimal 12 bulan)
        if 1_000_000 <= sisa_pokok <= 5_000_000:
            info_tenor = "pilihan: 3, 6, 9, 12 bulan"
        else:
            info_tenor = "pilihan: 3, 6, 9, 12, 15, 18, 21, 24 bulan"
            
        await update.message.reply_text(
            f"✅ DP tercatat: *Rp {dp:,.0f}*\n\n"
            f"⏳ Masukkan **Tenor Cicilan** dalam satuan bulan ({info_tenor})\n\n"
            "_(Contoh: 6 , 12)_",
            parse_mode="Markdown"
        )
        return GET_TENOR
    except ValueError:
        await update.message.reply_text("⚠️ Format DP tidak valid. Masukkan angka saja (contoh: `500000` atau `0`):")
        return GET_DP

# Menerima Tenor dan Hitung Hasil Simulasi
async def receive_tenor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        tenor = int(text)
        harga = context.user_data["harga"]
        dp = context.user_data["dp"]
        sisa_pokok = harga - dp
        
        # Validasi batasan tenor berdasarkan sisa pokok (maksimal 12 bulan jika sisa pokok 1 - 5 juta)
        if 1_000_000 <= sisa_pokok <= 5_000_000 and tenor > 12:
            await update.message.reply_text(
                "⚠️ Berdasarkan sisa pokok setelah DP (Rp 1.000.000 - Rp 5.000.000), tenor maksimal adalah **12 bulan**.\n"
                "Silakan masukkan ulang tenor yang valid (contoh: `3`, `6`, `9`, `12`):"
            )
            return GET_TENOR
            
        # Hitung komponen tambahan di balik layar berdasarkan sisa pokok
        biaya_perlindungan = ambil_biaya_perlindungan(sisa_pokok)
        biaya_admin = ambil_biaya_admin(tenor)
        total_biaya_bulanan = 10_000 * tenor  # Biaya bulanan Rp10.000 dikali jumlah tenor
        
        # Kalkulasi total keseluruhan di balik layar
        total_keseluruhan = sisa_pokok + biaya_perlindungan + biaya_admin + total_biaya_bulanan
        cicilan_per_bulan = total_keseluruhan / tenor

        # Membuat tombol interaktif di bawah pesan
        keyboard = [
            [InlineKeyboardButton("💬 Hubungi WhatsApp Admin", url="https://wa.me/6285935491278")],
            [InlineKeyboardButton("🔄 Hitung Simulasi Baru", callback_data="ulang")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        pesan_hasil = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 **HASIL SIMULASI CICILAN** 📊\n"
            "🏢 **Home Credit Indonesia**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️ **Harga Barang:** Rp {harga:,.0f}\n"
            f"💵 **Uang Muka (DP):** Rp {dp:,.0f}\n"
            f"📅 **Tenor Cicilan:** {tenor} Bulan\n\n"
            "--------------------------------------\n"
            f"💳 **Cicilan per Bulan:**\n"
            f"👉 *Rp {cicilan_per_bulan:,.0f} / bln*\n\n"
            "ℹ️ **Catatan:**\n"
            "• Bunga dan Admin tergantung NIK dan Akun masing-masing\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        await update.message.reply_text(pesan_hasil, parse_mode="Markdown", reply_markup=reply_markup)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ Format tenor tidak valid. Masukkan angka bulat untuk jumlah bulan (contoh: `12`):")
        return GET_TENOR

# Handler tombol inline "Hitung Simulasi Baru"
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "ulang":
        await query.message.reply_text(
            "✨ *MULAI SIMULASI BARU* ✨\n\n"
            "📦 Silakan masukkan **Harga Barang** baru yang ingin anda hitung:",
            parse_mode="Markdown"
        )
        return GET_PRICE

# /cancel command
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Simulasi dibatalkan. Ketik /start untuk memulai kembali.")
    return ConversationHandler.END

def main() -> None:
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        logger.error("TELEGRAM_TOKEN tidak ditemukan di environment variables!")
        return

    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(button_callback, pattern="ulang")],
        states={
            GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)],
            GET_DP: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_dp)],
            GET_TENOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tenor)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
