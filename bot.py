import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
    ContextTypes,
)
from datetime import datetime

# Konfigurasi Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# State untuk ConversationHandler: Harga -> DP -> Tenor
GET_PRICE, GET_DP, GET_TENOR = range(3)

DAFTAR_TENOR_UMUM = [3, 6, 9, 12, 14, 15, 18, 21, 24]
DAFTAR_TENOR_PENDEK = [3, 6, 9, 12, 14]

def ambil_biaya_perlindungan(sisa_pokok: float) -> float:
    if 500_000 <= sisa_pokok <= 10_000_000:
        return 599_000
    elif 10_000_000 < sisa_pokok <= 30_000_000:
        return 899_000
    elif sisa_pokok > 30_000_000:
        return 1_299_000
    return 0.0

def ambil_biaya_admin(sisa_pokok: float, tenor: int) -> float:
    if tenor == 14:
        return 0.0
        
    if 500_000 <= sisa_pokok <= 5_000_000:
        return (sisa_pokok / 1_000_000) * 30_000
    else:
        if tenor in [3, 6, 9, 12]:
            return 199_000
        elif tenor in [15, 18, 21, 24]:
            return 299_000
    return 0.0

# Fungsi untuk mendeteksi waktu sapaan menggunakan waktu server lokal
def get_salam_waktu() -> str:
    jam = datetime.now().hour
    
    if 4 <= jam < 11:
        return "SELAMAT PAGI 🌅"
    elif 11 <= jam < 15:
        return "SELAMAT SIANG ☀️"
    elif 15 <= jam < 18:
        return "SELAMAT SORE 🌇"
    else:
        return "SELAMAT MALAM 🌙"

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    salam = get_salam_waktu()
    pesan_mulai = (
        f"✨ *{salam}* ✨\n"
        "🏢 *HOME CREDIT INDONESIA*\n\n"
        "📦 Silakan ketik dan kirimkan **Harga Barang** yang ingin anda hitung:\n\n"
        "_(Contoh: 3.500.000 atau 3500000)_"
    )
    if update.message:
        await update.message.reply_text(pesan_mulai, parse_mode="Markdown")
    return GET_PRICE

# Menerima Harga
async def receive_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.replace(".", "").replace(",", "").strip()
    try:
        harga = float(text)
        if harga < 500_000:
            await update.message.reply_text("⚠️ Minimal harga barang adalah Rp 500.000. Silakan masukkan harga yang valid:")
            return GET_PRICE
            
        context.user_data["harga"] = harga
        
        await update.message.reply_text(
            f"✅ Harga Barang tercatat: *Rp {harga:,.0f}*\n\n"
            "💵 Masukkan jumlah **Uang Muka (DP)** yang ingin dibayarkan\n\n"
            "_(Ketik 0 jika tanpa DP)_",
            parse_mode="Markdown"
        )
        return GET_DP
    except ValueError:
        await update.message.reply_text("⚠️ Format harga tidak valid. Masukkan angka saja tanpa titik/koma (contoh: `3500000`):")
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
        
        if sisa_pokok < 500_000:
            await update.message.reply_text("⚠️ Sisa pokok setelah DP minimal Rp 500.000. Silakan masukkan nominal DP yang lain:")
            return GET_DP
        
        if 500_000 <= sisa_pokok <= 5_000_000:
            info_tenor = "pilihan: 3, 6, 9, 12 bulan"
        else:
            info_tenor = "pilihan: 3, 6, 9, 12, 15, 18, 21, 24 bulan"
            
        await update.message.reply_text(
            f"✅ DP tercatat: *Rp {dp:,.0f}*\n\n"
            f"⏳ Masukkan **Tenor Cicilan** dalam satuan bulan ({info_tenor})\n\n"
            "_(Contoh: 12)_",
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
        tenor_input = int(text)
        harga = context.user_data["harga"]
        dp = context.user_data["dp"]
        sisa_pokok = harga - dp
        
        if 500_000 <= sisa_pokok <= 5_000_000:
            pilihan_valid = DAFTAR_TENOR_PENDEK
        else:
            pilihan_valid = DAFTAR_TENOR_UMUM

        if tenor_input not in pilihan_valid:
            await update.message.reply_text(
                "⚠️ Tenor tidak ada di pilihan!\n"
                f"Silakan masukkan tenor yang tersedia untuk kategori ini: ({', '.join(map(str, pilihan_valid))}) bulan."
            )
            return GET_TENOR
            
        # Efek loading / pesan proses menghitung
        msg_loading = await update.message.reply_text("🔄 _Sedang menghitung rincian simulasi terbaik untuk Anda..._")
        await asyncio.sleep(1.2)
        
        # Logika khusus kode 14: Harga dibagi 12 bulan (Free 2x / murni tanpa bunga/admin)
        if tenor_input == 14:
            tampilan_tenor = "14 Bulan (Free 2x)"
            cicilan_per_bulan = harga / 12  
        else:
            tampilan_tenor = f"{tenor_input} Bulan"
            biaya_perlindungan = ambil_biaya_perlindungan(sisa_pokok)
            biaya_admin = ambil_biaya_admin(sisa_pokok, tenor_input)
            total_biaya_bulanan = 10_000 * tenor_input  
            
            if 500_000 <= sisa_pokok <= 5_000_000:
                total_bunga = (sisa_pokok * 0.0225) * tenor_input
                total_keseluruhan = sisa_pokok + biaya_perlindungan + biaya_admin + total_biaya_bulanan + total_bunga
                cicilan_per_bulan = total_keseluruhan / tenor_input
            else:
                total_pembiayaan = sisa_pokok + biaya_perlindungan + biaya_admin + total_biaya_bulanan
                cicilan_per_bulan = total_pembiayaan / tenor_input

        pesan_wa = f"Halo Admin, saya ingin mengajukan cicilan Home Credit dengan rincian:\n- Harga Barang: Rp {harga:,.0f}\n- DP: Rp {dp:,.0f}\n- Tenor: {tampilan_tenor}\n- Cicilan: Rp {cicilan_per_bulan:,.0f} / bln"
        url_wa = f"https://wa.me/6285935491278?text={pesan_wa.replace(' ', '%20').replace(chr(10), '%0A')}"

        keyboard = [
            [InlineKeyboardButton("💬 Hubungi WhatsApp Admin", url=url_wa)],
            [InlineKeyboardButton("🔄 Hitung Simulasi Baru", callback_data="ulang")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        pesan_hasil = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊  *HASIL SIMULASI CICILAN*  📊\n"
            "🏢  *Home Credit Indonesia*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🏷️  *Harga Barang*  : Rp {harga:,.0f}\n"
            f"💵  *Uang Muka (DP)* : Rp {dp:,.0f}\n"
            f"📅  *Tenor Cicilan*  : {tampilan_tenor}\n\n"
            "──────────────────────\n"
            f"💳  *ESTIMASI CICILAN* :\n"
            f"👉  *Rp {cicilan_per_bulan:,.0f} / bln*\n"
            "──────────────────────\n\n"
            "ℹ️  *Catatan Penting:*\n"
            "• Besaran cicilan, bunga, & admin dapat bervariasi tergantung NIK dan profil akun masing-masing.\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        await msg_loading.delete()
        await update.message.reply_text(pesan_hasil, parse_mode="Markdown", reply_markup=reply_markup)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("⚠️ Tenor tidak ada di pilihan! Masukkan angka bulat untuk jumlah bulan yang valid:")
        return GET_TENOR

# Menangani tombol "Hitung Simulasi Baru" dan mengembalikan state ke GET_PRICE
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "ulang":
        salam = get_salam_waktu()
        pesan_ulang = (
            f"✨ *{salam}* ✨\n"
            "🏢 *HOME CREDIT INDONESIA*\n\n"
            "📦 Silakan masukkan **Harga Barang** baru yang ingin anda hitung:\n\n"
            "_(Contoh: 3.500.000 atau 3500000)_"
        )
        await query.message.reply_text(pesan_ulang, parse_mode="Markdown")
        return GET_PRICE
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Simulasi dibatalkan. Ketik /start untuk memulai kembali.")
    return ConversationHandler.END

def main() -> None:
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    if not TOKEN:
        logger.error("TELEGRAM_TOKEN tidak ditemukan di environment variables!")
        return

    application = Application.builder().token(TOKEN).build()

    # Menggunakan ConversationHandler tunggal yang mencakup start, tahapan hitung, hingga tombol ulang
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_price)],
            GET_DP: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_dp)],
            GET_TENOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_tenor)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(button_callback, pattern="ulang")
        ],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
