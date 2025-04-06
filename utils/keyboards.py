from telegram import InlineKeyboardButton,InlineKeyboardMarkup
from typing import List,Tuple,Optional
from . import localization as lang,constants as c

def today_habits_keyboard(habits_data:List[Tuple[int,str,str]])->InlineKeyboardMarkup:
	kbd:List[List[InlineKeyboardButton]]=[]
	for hid,name,status in habits_data:
		cb_data=f"{c.CALLBACK_NOOP}{hid}"
		if status=='done': btn_txt=f"✅ {name}"
		else: btn_txt=f"{name} ({lang.BUTTON_MARK_DONE})"; cb_data=f"{c.CALLBACK_MARK_DONE}{hid}"
		kbd.append([InlineKeyboardButton(btn_txt,callback_data=cb_data)])
	return InlineKeyboardMarkup(kbd)

def reminder_management_keyboard(rems_data:List[Tuple[int,str,str]])->InlineKeyboardMarkup:
	kbd:List[List[InlineKeyboardButton]]=[]
	for hid,name,time_str in rems_data:
		btn_txt=f"{name} ({time_str}) - {lang.BUTTON_DELETE_REMINDER}"
		cb_data=f"{c.CALLBACK_DELETE_REMINDER}{hid}"
		kbd.append([InlineKeyboardButton(btn_txt,callback_data=cb_data)])
	return InlineKeyboardMarkup(kbd)

def select_habit_keyboard(habits:List[Tuple[int,str,Optional[str],Optional[str]]],cb_prefix:str)->List[List[InlineKeyboardButton]]:
	"""Generates rows for generic habit selection."""
	kbd_rows:List[List[InlineKeyboardButton]]=[]
	if habits:
		sorted_habits=sorted(habits,key=lambda h:h[1].lower())
		for hid,name,_,_ in sorted_habits: kbd_rows.append([InlineKeyboardButton(name,callback_data=f"{cb_prefix}{hid}")])
	return kbd_rows

def yes_no_keyboard(yes_cb:str,no_cb:str)->InlineKeyboardMarkup:
	kbd=[[InlineKeyboardButton(lang.BUTTON_YES,callback_data=yes_cb),
		 InlineKeyboardButton(lang.BUTTON_NO,callback_data=no_cb)]]
	return InlineKeyboardMarkup(kbd)

def history_pagination_keyboard(offset:int,total:int,limit:int)->Optional[InlineKeyboardMarkup]:
	btns=[]
	if offset>0: prev_off=max(0,offset-limit); btns.append(InlineKeyboardButton(lang.BUTTON_PREVIOUS,callback_data=f"{c.CALLBACK_HISTORY_PAGE}{prev_off}"))
	if offset+limit<total: next_off=offset+limit; btns.append(InlineKeyboardButton(lang.BUTTON_NEXT,callback_data=f"{c.CALLBACK_HISTORY_PAGE}{next_off}"))
	return InlineKeyboardMarkup([btns]) if btns else None

def edit_habit_field_keyboard(hid:int)->InlineKeyboardMarkup:
	kbd=[[InlineKeyboardButton(lang.BUTTON_EDIT_NAME,callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}name_{hid}")],
		 [InlineKeyboardButton(lang.BUTTON_EDIT_DESCRIPTION,callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}description_{hid}")],
		 [InlineKeyboardButton(lang.BUTTON_EDIT_CATEGORY,callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}category_{hid}")]]
	return InlineKeyboardMarkup(kbd)