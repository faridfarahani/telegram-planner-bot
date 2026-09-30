from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .constants import DAYS, REMINDER_LABELS


def start_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="شروع")]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="برای ورود به منو، «شروع» را بزنید",
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="مدیریت پلن ها", callback_data="menu:manage")],
            [InlineKeyboardButton(text="یادآوری", callback_data="menu:reminders")],
            [InlineKeyboardButton(text="اصلاحات", callback_data="menu:edit")],
        ]
    )


def add_plan_only_keyboard(back_callback: str = "menu:main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="اضافه کردن پلن", callback_data="plan:add")],
            [InlineKeyboardButton(text="بازگشت", callback_data=back_callback)],
        ]
    )


def manage_plans_keyboard(plans: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        builder.button(text=plan["name"], callback_data=f"plan:view:{plan['id']}")
    if plans:
        builder.adjust(1)
    add_label = "اضافه کردن پلن جدید" if plans else "اضافه کردن پلن"
    builder.row(InlineKeyboardButton(text=add_label, callback_data="plan:add"))
    builder.row(InlineKeyboardButton(text="بازگشت", callback_data="menu:main"))
    return builder.as_markup()


def tick_count_keyboard(callback_prefix: str, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for number in range(1, 6):
        builder.button(text=str(number), callback_data=f"{callback_prefix}:{number}")
    builder.adjust(5)
    builder.row(InlineKeyboardButton(text="بازگشت", callback_data=back_callback))
    return builder.as_markup()


def days_keyboard(
    selected: set[str],
    toggle_prefix: str,
    save_callback: str,
    cancel_callback: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for code, label in DAYS:
        mark = "✅ " if code in selected else "▫️ "
        builder.button(text=f"{mark}{label}", callback_data=f"{toggle_prefix}:{code}")
    builder.adjust(2, 2, 2, 1)
    builder.row(InlineKeyboardButton(text="ثبت", callback_data=save_callback))
    builder.row(InlineKeyboardButton(text="انصراف", callback_data=cancel_callback))
    return builder.as_markup()


def plan_detail_keyboard(plan_id: int, show_tick: bool) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if show_tick:
        rows.append([InlineKeyboardButton(text="ثبت تیک امروز ✅", callback_data=f"tick:add:{plan_id}")])
    rows.append([InlineKeyboardButton(text="بازگشت به مدیریت پلن ها", callback_data="menu:manage")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reminder_plan_list_keyboard(plans: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        builder.button(text=plan["name"], callback_data=f"reminder:plan:{plan['id']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="بازگشت", callback_data="menu:main"))
    return builder.as_markup()


def reminder_times_keyboard(plan_id: int, back_callback: str, set_prefix: str = "reminder:set") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=REMINDER_LABELS["a"], callback_data=f"{set_prefix}:{plan_id}:a")],
            [InlineKeyboardButton(text=REMINDER_LABELS["b"], callback_data=f"{set_prefix}:{plan_id}:b")],
            [InlineKeyboardButton(text=REMINDER_LABELS["c"], callback_data=f"{set_prefix}:{plan_id}:c")],
            [InlineKeyboardButton(text="بازگشت", callback_data=back_callback)],
        ]
    )


def edit_plan_list_keyboard(plans: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        builder.button(text=plan["name"], callback_data=f"edit:plan:{plan['id']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="حذف پلن", callback_data="edit:delete"))
    builder.row(InlineKeyboardButton(text="بازگشت", callback_data="menu:main"))
    return builder.as_markup()


def delete_plan_list_keyboard(plans: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for plan in plans:
        builder.button(text=plan["name"], callback_data=f"edit:delete:plan:{plan['id']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="بازگشت", callback_data="menu:edit"))
    return builder.as_markup()


def delete_plan_confirm_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="بله، حذف شود", callback_data=f"edit:delete:confirm:{plan_id}")],
            [InlineKeyboardButton(text="انصراف", callback_data="edit:delete")],
        ]
    )


def edit_actions_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="تغییر نام پلن", callback_data=f"edit:name:{plan_id}")],
            [InlineKeyboardButton(text="تغییر روز های انجام پلن", callback_data=f"edit:daysopen:{plan_id}")],
            [InlineKeyboardButton(text="تغییر تیک هایی که پلن باید بخوره در روزهای مشخص شده", callback_data=f"edit:ticks:{plan_id}")],
            [InlineKeyboardButton(text="تغییر ساعت یادآوری", callback_data=f"edit:reminder:{plan_id}")],
            [InlineKeyboardButton(text="بازگشت", callback_data="menu:edit")],
        ]
    )
