# utils/localization.py (Persian/Farsi)

# General
MSG_WELCOME = "سلام {user_name}! 👋 به ربات ردیاب عادت خوش آمدید."
MSG_HELP = """دستورات:
/add_habit افزودن عادت
/edit_habit ویرایش عادت
/today وضعیت امروز + ثبت
/done [نام] ثبت انجام عادت
/history تاریخچه (صفحه‌بندی)
/stats آمار ۳۰ روز اخیر
/set_reminder تنظیم یادآوری
/manage_reminders مشاهده/حذف یادآوری
/delete_habit حذف عادت
/refresh_membership بروزرسانی عضویت کانال
/cancel لغو عملیات
/help نمایش این پیام
/start خوشامدگویی

نکات: نام عادت در /done حساس به حروف نیست. برای رد کردن اختیاری‌ها در /add_habit یا /edit_habit از /skip استفاده کنید."""
MSG_CANCELLED = "عملیات لغو شد."
MSG_ERROR_GENERAL = "⛔️ خطا! لطفا دوباره تلاش کنید."
MSG_COMMAND_UNKNOWN = "دستور ناشناخته. /help"
ERR_DATABASE_CONNECTION = "⛔️ خطای پایگاه داده. بعدا تلاش کنید."
ERR_GENERIC_CALLBACK = "⛔️ خطای پردازش دکمه."
DEFAULT_HABIT_NAME = "این عادت" # Fallback name

# Input
ERR_INVALID_INPUT = "ورودی نامعتبر."
CMD_SKIP = "رد_شدن" # Localized /skip text

# Add Habit
PROMPT_HABIT_NAME = "نام عادت جدید:"
PROMPT_HABIT_DESCRIPTION = "اختیاری: توضیحات برای '{habit_name}' (یا /skip):"
PROMPT_HABIT_CATEGORY = "اختیاری: دسته‌بندی '{habit_name}' (مثلا: سلامتی) (یا /skip):"
CONFIRM_HABIT_ADDED = "✅ عادت '{habit_name}' اضافه شد. 🎉"
ERR_HABIT_ADD_FAILED = "⛔️ خطا در افزودن عادت."
ERR_HABIT_ADD_FAILED_CONTEXT = "⛔️ خطای داخلی: اطلاعات عادت یافت نشد. با /add_habit شروع کنید."
ERR_HABIT_ADD_FAILED_USER = "⛔️ خطای داخلی: اطلاعات کاربر یافت نشد."

# Mark Done
PROMPT_MARK_DONE_SELECT = "✅ کدام عادت را انجام دادید؟ انتخاب کنید یا /done [نام]:"
EXAMPLE_MARK_DONE = "مثال: /done مطالعه"
CONFIRM_HABIT_MARKED_DONE = "✅ عالی! '{habit_name}' برای امروز ثبت شد."
ERR_HABIT_ALREADY_DONE = "❗️ '{habit_name}' قبلاً برای امروز ثبت شده."
ERR_HABIT_NOT_FOUND = "⚠️ عادت '{habit_name}' یافت نشد. نام را بررسی یا از لیست /done انتخاب کنید."
ERR_HABIT_NOT_FOUND_GENERIC = "⚠️ عادت یافت نشد."
ERR_MARK_DONE_FAILED = "⛔️ خطا در ثبت انجام عادت."
ERR_MARK_DONE_FAILED_ID = "⛔️ خطای داخلی: ID عادت نامعتبر."
ERR_MARK_DONE_FAILED_NOT_FOUND = "⚠️ این عادت دیگر وجود ندارد."
MSG_NO_HABITS_TO_MARK_DONE = "عادتی برای ثبت وجود ندارد! با /add_habit شروع کنید."

# View Today
MSG_TODAY_HEADER = "🗓 وضعیت امروز ({today_date}):"
MSG_NO_HABITS_TODAY = "عادتی وجود ندارد. با /add_habit شروع کنید."
STATUS_DONE = "انجام شد"
STATUS_PENDING = "انجام نشده"
BUTTON_MARK_DONE = "انجام شد"

# History
MSG_HISTORY_HEADER = "📜 تاریخچه (صفحه {page_num}/{total_pages}):"
MSG_NO_HISTORY = "تاریخچه‌ای ثبت نشده."
MSG_HISTORY_FOOTER = "برای صفحات دیگر از دکمه‌ها استفاده کنید."

# Stats (MarkdownV2 Escaped)
MSG_STATS_HEADER = "📊 آمار تکمیل \\({days} روز گذشته\\):"
MSG_NO_STATS_DATA = "داده کافی برای آمار نیست\\."
MSG_STATS_COMPLETION = "تکمیل: {rate}% \\({done}/{total}\\) روز"
MSG_STATS_STREAK = "رشته فعلی: {current} روز \\| بیشترین: {max_streak} روز"

# Reminders
PROMPT_SELECT_REMINDER_HABIT_LIST = "برای کدام عادت یادآوری می‌خواهید؟:"
MSG_NO_HABITS_FOR_REMINDER = "عادتی برای تنظیم یادآوری نیست. با /add_habit شروع کنید."
PROMPT_REMINDER_TIME = "⏰ ساعت یادآوری روزانه برای '{habit_name}' (فرمت HH:MM مثل 09:00 یا 17:30):"
CONFIRM_REMINDER_SET = "⏰✅ یادآوری برای '{habit_name}' ساعت {time_str} تنظیم شد."
ERR_REMINDER_INVALID_TIME = "⚠️ فرمت زمان نامعتبر. از {example} استفاده کنید."
ERR_REMINDER_SET_FAILED_CONTEXT = "⛔️ خطای داخلی: اطلاعات یادآوری یافت نشد."
ERR_REMINDER_SET_FAILED_SCHEDULE = "⛔️ خطا در زمان‌بندی یادآوری."
ERR_REMINDER_SET_FAILED_DB = "⛔️ خطا در ذخیره یادآوری."
ERR_REMINDER_SET_FAILED = "⛔️ خطا در تنظیم یادآوری."
MSG_REMINDER_ALERT = "🔔 یادآوری: وقت انجام '{habit_name}'!"
PROMPT_MANAGE_REMINDERS = "⚙️ یادآوری‌های فعال (برای حذف کلیک کنید):"
BUTTON_DELETE_REMINDER = "حذف"
CONFIRM_REMINDER_DELETED = "🗑 یادآوری '{habit_name}' حذف شد."
ERR_REMINDER_DELETE_FAILED = "⛔️ خطا در حذف یادآوری '{habit_name}'."
ERR_REMINDER_DELETE_FAILED_INTERNAL = "⛔️ خطای داخلی هنگام حذف یادآوری."
MSG_NO_REMINDERS = "یادآوری فعالی ندارید."

# Delete Habit
PROMPT_SELECT_HABIT_TO_DELETE = "⚠️ کدام عادت برای همیشه حذف شود؟ (غیرقابل بازگشت)"
MSG_NO_HABITS_TO_DELETE = "عادتی برای حذف نیست."
PROMPT_CONFIRM_DELETE = "⁉️ مطمئنید می‌خواهید '{habit_name}' با تمام تاریخچه و یادآوری حذف شود؟"
CONFIRM_HABIT_DELETED = "🗑 عادت '{habit_name}' حذف شد."
ERR_DELETE_FAILED_CONTEXT = "⛔️ خطای داخلی: اطلاعات عادت برای حذف نیست."
ERR_DELETE_FAILED_INTERNAL = "⛔️ خطای داخلی هنگام حذف عادت."
ERR_DELETE_FAILED_DB = "⛔️ خطا در حذف '{habit_name}' از پایگاه داده."

# Edit Habit
PROMPT_SELECT_HABIT_TO_EDIT = "✏️ کدام عادت ویرایش شود؟"
MSG_NO_HABITS_TO_EDIT = "عادتی برای ویرایش نیست."
PROMPT_SELECT_FIELD_TO_EDIT = "کدام بخش از '{habit_name}' تغییر کند؟"
PROMPT_EDIT_NAME = "نام جدید برای '{habit_name}':"
PROMPT_EDIT_DESCRIPTION = "توضیحات جدید برای '{habit_name}' (یا /skip برای حذف):"
PROMPT_EDIT_CATEGORY = "دسته‌بندی جدید برای '{habit_name}' (یا /skip برای حذف):"
CONFIRM_HABIT_UPDATED = "✅ عادت '{habit_name}' ویرایش شد."
ERR_EDIT_FAILED_CONTEXT = "⛔️ خطای داخلی: اطلاعات لازم برای ویرایش نیست."
ERR_EDIT_FAILED_INVALID_FIELD = "⛔️ خطای داخلی: بخش نامعتبر برای ویرایش."
ERR_EDIT_FAILED_DB = "⛔️ خطا در بروزرسانی عادت."
ERR_EDIT_FAILED_NAME_EMPTY = "⛔️ نام عادت نمی‌تواند خالی باشد."
BUTTON_EDIT_NAME = "نام"
BUTTON_EDIT_DESCRIPTION = "توضیحات"
BUTTON_EDIT_CATEGORY = "دسته‌بندی"
BUTTON_CANCEL_EDIT = "لغو ویرایش"

# Buttons
BUTTON_YES = "بله"; BUTTON_NO = "خیر"; BUTTON_PREVIOUS = " قبلی ◀️"; BUTTON_NEXT = "▶️ بعدی "; BUTTON_CANCEL = "لغو"

# Channel Membership (MarkdownV2 Escaped)
MSG_MUST_JOIN_CHANNEL = """⚠️ برای استفاده از ربات، در کانال\\(های\\) زیر عضو شوید و /refresh_membership را بزنید:"""
MSG_MUST_JOIN_CHANNEL_ALERT = "⚠️ لطفاً ابتدا در کانال‌ها عضو شوید\\!"
BUTTON_JOIN_CHANNEL = "عضویت در کانال"
CMD_REFRESH_MEMBERSHIP_DESC = "بررسی مجدد عضویت کانال"
MSG_MEMBERSHIP_REFRESHING = "⏳ بررسی مجدد عضویت شما در کانال\\(ها\\)\\.\\.\\."
MSG_MEMBERSHIP_REFRESHED_OK = "✅ عضویت تأیید شد\\. می‌توانید از ربات استفاده کنید\\."
MSG_MEMBERSHIP_REFRESHED_FAIL = "⚠️ عضویت در کانال\\(های\\) لازم تأیید نشد\\. بررسی کنید و /refresh_membership بزنید\\."
ERR_MEMBERSHIP_REFRESH_API = "⛔️ خطا هنگام بررسی عضویت\\. بعدا تلاش کنید\\."