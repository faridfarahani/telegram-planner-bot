from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .config import Settings
from .constants import DAY_LABELS, DAYS, REMINDER_LABELS
from .db import Database
from .keyboards import (
    add_plan_only_keyboard,
    days_keyboard,
    delete_plan_confirm_keyboard,
    delete_plan_list_keyboard,
    edit_actions_keyboard,
    edit_plan_list_keyboard,
    main_menu_keyboard,
    manage_plans_keyboard,
    plan_detail_keyboard,
    reminder_plan_list_keyboard,
    reminder_times_keyboard,
    start_reply_keyboard,
    tick_count_keyboard,
)
from .states import CreatePlanState, EditPlanState
from .utils import day_code_for_date, fa_digits, format_history_line, local_now


def build_router(db: Database, settings: Settings) -> Router:
    router = Router(name="plan_bot")

    async def ensure_message_user(message: Message) -> None:
        if not message.from_user:
            return
        await db.upsert_user(
            telegram_user_id=message.from_user.id,
            chat_id=message.chat.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            timezone_name=settings.timezone,
        )

    async def ensure_callback_user(callback: CallbackQuery) -> None:
        if not callback.from_user or not callback.message:
            return
        await db.upsert_user(
            telegram_user_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name,
            timezone_name=settings.timezone,
        )

    async def show_main_menu(message: Message) -> None:
        await message.answer("گزینه مورد نظر را انتخاب کنید:", reply_markup=main_menu_keyboard())

    async def show_manage(callback: CallbackQuery) -> None:
        plans = await db.list_plans(callback.from_user.id)
        text = "پلنی وجود ندارد" if not plans else "پلن های ثبت شده:"
        if callback.message:
            await callback.message.edit_text(text, reply_markup=manage_plans_keyboard(plans))

    async def show_edit_menu(callback: CallbackQuery) -> None:
        plans = await db.list_plans(callback.from_user.id)
        if not callback.message:
            return
        if not plans:
            await callback.message.edit_text(
                "ابتدا پلن خود را ثبت کنید",
                reply_markup=add_plan_only_keyboard("menu:main"),
            )
            return
        await callback.message.edit_text(
            "انتخاب پلن",
            reply_markup=edit_plan_list_keyboard(plans),
        )

    async def show_plan_detail(callback: CallbackQuery, plan_id: int) -> None:
        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not callback.message:
            return
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            await show_manage(callback)
            return

        now = local_now(settings.timezone)
        today_code = day_code_for_date(now.date())
        today_count = await db.get_today_tick_count(callback.from_user.id, plan_id, settings.timezone)
        history = await db.get_plan_history(callback.from_user.id, plan_id, limit=40)

        ordered_days = [label for code, label in DAYS if code in set(plan["days"])]
        reminder = REMINDER_LABELS.get(plan["reminder_preset"], "تنظیم نشده")

        lines = [
            f"اسم پلن: {plan['name']}",
            f"تعداد تیک مورد نیاز در هر روز: {fa_digits(plan['required_ticks'])}",
            f"روز های انجام: {'، '.join(ordered_days)}",
            f"ساعت یادآوری: {reminder}",
            f"تیک امروز: {fa_digits(today_count)} از {fa_digits(plan['required_ticks'])}",
            "",
            "تاریخچه تیک ها:",
        ]

        if history:
            for item in history:
                lines.append(
                    format_history_line(
                        item["local_date"],
                        item["local_time"],
                        int(item["ordinal"]),
                        int(item["required_ticks_snapshot"]),
                    )
                )
        else:
            lines.append("هنوز تیکی برای این پلن ثبت نشده است.")

        scheduled_today = today_code in set(plan["days"])
        show_tick = scheduled_today and today_count < int(plan["required_ticks"])

        if not scheduled_today:
            lines.extend(["", "امروز جزو روز های انجام این پلن نیست."])
        elif today_count >= int(plan["required_ticks"]):
            lines.extend(["", "تیک های امروز این پلن کامل شده است ✅"])

        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=plan_detail_keyboard(plan_id, show_tick),
        )

    @router.message(CommandStart())
    async def start_command(message: Message, state: FSMContext) -> None:
        await ensure_message_user(message)
        await state.clear()
        await message.answer(
            "ربات پلن آماده است. برای ورود به منو روی «شروع» بزنید.",
            reply_markup=start_reply_keyboard(),
        )
        await show_main_menu(message)

    @router.message(F.text == "شروع")
    async def start_button(message: Message, state: FSMContext) -> None:
        await ensure_message_user(message)
        await state.clear()
        await show_main_menu(message)

    @router.callback_query(F.data == "menu:main")
    async def menu_main(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.clear()
        await callback.answer()
        if callback.message:
            await callback.message.edit_text("گزینه مورد نظر را انتخاب کنید:", reply_markup=main_menu_keyboard())

    @router.callback_query(F.data == "menu:manage")
    async def menu_manage(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.clear()
        await callback.answer()
        await show_manage(callback)

    @router.callback_query(F.data == "plan:add")
    async def plan_add(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.clear()
        await state.set_state(CreatePlanState.waiting_name)
        await callback.answer()
        if callback.message:
            await callback.message.answer("اسم پلن را وارد کنید:")

    @router.message(CreatePlanState.waiting_name)
    async def plan_name_received(message: Message, state: FSMContext) -> None:
        await ensure_message_user(message)
        name = (message.text or "").strip()
        if not name:
            await message.answer("اسم پلن نمی تواند خالی باشد. اسم پلن را وارد کنید:")
            return
        if len(name) > 100:
            await message.answer("اسم پلن حداکثر باید 100 کاراکتر باشد. دوباره وارد کنید:")
            return

        await state.update_data(name=name)
        await state.set_state(CreatePlanState.choosing_ticks)
        await message.answer(
            "این پلن نیازمند چند تیک در روزهای مشخص میباشد؟",
            reply_markup=tick_count_keyboard("create:ticks", "menu:manage"),
        )

    @router.callback_query(CreatePlanState.choosing_ticks, F.data.startswith("create:ticks:"))
    async def plan_ticks_selected(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            required_ticks = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("مقدار نامعتبر است.", show_alert=True)
            return

        if required_ticks not in {1, 2, 3, 4, 5}:
            await callback.answer("مقدار نامعتبر است.", show_alert=True)
            return

        await state.update_data(required_ticks=required_ticks, days=[])
        await state.set_state(CreatePlanState.choosing_days)
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                "روز های انجام این پلن را انتخاب کنید و سپس «ثبت» را بزنید:",
                reply_markup=days_keyboard(set(), "create:day", "create:save", "menu:manage"),
            )

    @router.callback_query(CreatePlanState.choosing_days, F.data.startswith("create:day:"))
    async def create_day_toggle(callback: CallbackQuery, state: FSMContext) -> None:
        day = callback.data.rsplit(":", 1)[1]
        if day not in DAY_LABELS:
            await callback.answer("روز نامعتبر است.", show_alert=True)
            return

        data = await state.get_data()
        selected = set(data.get("days", []))
        if day in selected:
            selected.remove(day)
        else:
            selected.add(day)
        await state.update_data(days=sorted(selected))
        await callback.answer()
        if callback.message:
            await callback.message.edit_reply_markup(
                reply_markup=days_keyboard(selected, "create:day", "create:save", "menu:manage")
            )

    @router.callback_query(CreatePlanState.choosing_days, F.data == "create:save")
    async def create_plan_save(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        name = (data.get("name") or "").strip()
        required_ticks = data.get("required_ticks")
        days = list(data.get("days") or [])

        if not name or required_ticks not in {1, 2, 3, 4, 5} or not days:
            await callback.answer(
                "اسم پلن، تعداد تیک و حداقل یک روز باید مشخص شده باشد.",
                show_alert=True,
            )
            return

        await db.create_plan(callback.from_user.id, name, int(required_ticks), days)
        await state.clear()
        await callback.answer("پلن ثبت شد ✅")
        await show_manage(callback)

    @router.callback_query(F.data.startswith("plan:view:"))
    async def plan_view(callback: CallbackQuery) -> None:
        await ensure_callback_user(callback)
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        await callback.answer()
        await show_plan_detail(callback, plan_id)

    @router.callback_query(F.data.startswith("tick:add:"))
    async def add_tick(callback: CallbackQuery) -> None:
        await ensure_callback_user(callback)
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return

        result = await db.add_tick(callback.from_user.id, plan_id, settings.timezone)
        status = result.get("status")
        if status == "added":
            await callback.answer(
                f"تیک ثبت شد: {fa_digits(result['count'])} از {fa_digits(result['required'])}"
            )
            await show_plan_detail(callback, plan_id)
            return
        if status == "complete":
            await callback.answer("تیک های امروز این پلن قبلا کامل شده است.", show_alert=True)
            await show_plan_detail(callback, plan_id)
            return
        if status == "not_scheduled":
            await callback.answer("امروز روز انجام این پلن نیست.", show_alert=True)
            return
        await callback.answer("پلن پیدا نشد.", show_alert=True)

    @router.callback_query(F.data == "menu:reminders")
    async def menu_reminders(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.clear()
        plans = await db.list_plans(callback.from_user.id)
        await callback.answer()
        if not callback.message:
            return
        if not plans:
            await callback.message.edit_text(
                "ابتدا پلن خود را ثبت کنید",
                reply_markup=add_plan_only_keyboard("menu:main"),
            )
            return
        await callback.message.edit_text(
            "پلن مورد نظر را انتخاب کنید:",
            reply_markup=reminder_plan_list_keyboard(plans),
        )

    @router.callback_query(F.data.startswith("reminder:plan:"))
    async def reminder_plan(callback: CallbackQuery) -> None:
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        current = REMINDER_LABELS.get(plan["reminder_preset"], "تنظیم نشده")
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                f"پلن: {plan['name']}\nساعت یادآوری فعلی: {current}\n\nساعت یادآوری را انتخاب کنید:",
                reply_markup=reminder_times_keyboard(plan_id, "menu:reminders"),
            )

    @router.callback_query(F.data.startswith("reminder:set:"))
    async def reminder_set(callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 4:
            await callback.answer("درخواست نامعتبر است.", show_alert=True)
            return
        try:
            plan_id = int(parts[2])
        except ValueError:
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        preset = parts[3]
        if preset not in REMINDER_LABELS:
            await callback.answer("ساعت نامعتبر است.", show_alert=True)
            return
        updated = await db.update_reminder_preset(callback.from_user.id, plan_id, preset)
        if not updated:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        await callback.answer("ساعت یادآوری ذخیره شد ✅")
        if callback.message and plan:
            await callback.message.edit_text(
                f"پلن: {plan['name']}\nساعت یادآوری فعلی: {REMINDER_LABELS[preset]}\n\nساعت یادآوری را انتخاب کنید:",
                reply_markup=reminder_times_keyboard(plan_id, "menu:reminders"),
            )

    @router.callback_query(F.data == "menu:edit")
    async def menu_edit(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.clear()
        await callback.answer()
        await show_edit_menu(callback)

    @router.callback_query(F.data == "edit:delete")
    async def edit_delete_menu(callback: CallbackQuery, state: FSMContext) -> None:
        await ensure_callback_user(callback)
        await state.clear()
        plans = await db.list_plans(callback.from_user.id)
        await callback.answer()
        if not callback.message:
            return
        if not plans:
            await callback.message.edit_text(
                "ابتدا پلن خود را ثبت کنید",
                reply_markup=add_plan_only_keyboard("menu:main"),
            )
            return
        await callback.message.edit_text(
            "پلنی که می خواهید حذف کنید را انتخاب کنید:",
            reply_markup=delete_plan_list_keyboard(plans),
        )

    @router.callback_query(F.data.startswith("edit:delete:plan:"))
    async def edit_delete_plan(callback: CallbackQuery) -> None:
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return

        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return

        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                f"آیا از حذف پلن «{plan['name']}» مطمئن هستید؟\n\nتاریخچه تیک های قبلی در دیتابیس حفظ می شود.",
                reply_markup=delete_plan_confirm_keyboard(plan_id),
            )

    @router.callback_query(F.data.startswith("edit:delete:confirm:"))
    async def edit_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return

        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return

        deleted = await db.delete_plan(callback.from_user.id, plan_id)
        if not deleted:
            await callback.answer("حذف پلن انجام نشد.", show_alert=True)
            return

        await state.clear()
        await callback.answer("پلن حذف شد ✅")

        plans = await db.list_plans(callback.from_user.id)
        if not callback.message:
            return

        if plans:
            await callback.message.edit_text(
                f"پلن «{plan['name']}» حذف شد.\n\nپلن دیگری برای حذف انتخاب کنید:",
                reply_markup=delete_plan_list_keyboard(plans),
            )
        else:
            await callback.message.edit_text(
                "پلن حذف شد.\n\nابتدا پلن خود را ثبت کنید",
                reply_markup=add_plan_only_keyboard("menu:main"),
            )

    @router.callback_query(F.data.startswith("edit:plan:"))
    async def edit_plan(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                f"انتخاب پلن: {plan['name']}",
                reply_markup=edit_actions_keyboard(plan_id),
            )

    @router.callback_query(F.data.startswith("edit:name:"))
    async def edit_name(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        await state.clear()
        await state.set_state(EditPlanState.waiting_name)
        await state.update_data(plan_id=plan_id)
        await callback.answer()
        if callback.message:
            await callback.message.answer(f"نام جدید برای «{plan['name']}» را وارد کنید:")

    @router.message(EditPlanState.waiting_name)
    async def edit_name_received(message: Message, state: FSMContext) -> None:
        await ensure_message_user(message)
        name = (message.text or "").strip()
        if not name:
            await message.answer("نام پلن نمی تواند خالی باشد. نام جدید را وارد کنید:")
            return
        if len(name) > 100:
            await message.answer("نام پلن حداکثر باید 100 کاراکتر باشد. دوباره وارد کنید:")
            return
        data = await state.get_data()
        plan_id = int(data["plan_id"])
        updated = await db.update_plan_name(message.from_user.id, plan_id, name)
        await state.clear()
        if not updated:
            await message.answer("پلن پیدا نشد.")
            return
        await message.answer(
            f"نام پلن تغییر کرد ✅\n\nانتخاب پلن: {name}",
            reply_markup=edit_actions_keyboard(plan_id),
        )

    @router.callback_query(F.data.startswith("edit:daysopen:"))
    async def edit_days(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        selected = set(plan["days"])
        await state.clear()
        await state.set_state(EditPlanState.choosing_days)
        await state.update_data(plan_id=plan_id, days=sorted(selected))
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                "روز های انجام پلن را انتخاب کنید و سپس «ثبت» را بزنید:",
                reply_markup=days_keyboard(
                    selected,
                    "edit:daytoggle",
                    f"edit:days:save:{plan_id}",
                    f"edit:plan:{plan_id}",
                ),
            )

    @router.callback_query(EditPlanState.choosing_days, F.data.startswith("edit:daytoggle:"))
    async def edit_day_toggle(callback: CallbackQuery, state: FSMContext) -> None:
        day = callback.data.rsplit(":", 1)[1]
        if day not in DAY_LABELS:
            await callback.answer("روز نامعتبر است.", show_alert=True)
            return
        data = await state.get_data()
        plan_id = int(data["plan_id"])
        selected = set(data.get("days", []))
        if day in selected:
            selected.remove(day)
        else:
            selected.add(day)
        await state.update_data(days=sorted(selected))
        await callback.answer()
        if callback.message:
            await callback.message.edit_reply_markup(
                reply_markup=days_keyboard(
                    selected,
                    "edit:daytoggle",
                    f"edit:days:save:{plan_id}",
                    f"edit:plan:{plan_id}",
                )
            )

    @router.callback_query(EditPlanState.choosing_days, F.data.startswith("edit:days:save:"))
    async def edit_days_save(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        selected = list(data.get("days") or [])
        plan_id = int(data["plan_id"])
        if not selected:
            await callback.answer("حداقل یک روز باید انتخاب شود.", show_alert=True)
            return
        updated = await db.update_plan_days(callback.from_user.id, plan_id, selected)
        await state.clear()
        if not updated:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        await callback.answer("روز های انجام پلن تغییر کرد ✅")
        if callback.message and plan:
            await callback.message.edit_text(
                f"انتخاب پلن: {plan['name']}",
                reply_markup=edit_actions_keyboard(plan_id),
            )

    @router.callback_query(F.data.startswith("edit:ticks:"))
    async def edit_ticks(callback: CallbackQuery) -> None:
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                f"پلن: {plan['name']}\nتعداد تیک فعلی: {fa_digits(plan['required_ticks'])}\n\nتعداد تیک جدید را انتخاب کنید:",
                reply_markup=tick_count_keyboard("edit:setticks:%d" % plan_id, f"edit:plan:{plan_id}"),
            )

    @router.callback_query(F.data.startswith("edit:setticks:"))
    async def edit_set_ticks(callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 4:
            await callback.answer("درخواست نامعتبر است.", show_alert=True)
            return
        try:
            plan_id = int(parts[2])
            required_ticks = int(parts[3])
        except ValueError:
            await callback.answer("مقدار نامعتبر است.", show_alert=True)
            return
        updated = await db.update_required_ticks(callback.from_user.id, plan_id, required_ticks)
        if not updated:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        await callback.answer("تعداد تیک تغییر کرد ✅")
        if callback.message and plan:
            await callback.message.edit_text(
                f"انتخاب پلن: {plan['name']}",
                reply_markup=edit_actions_keyboard(plan_id),
            )

    @router.callback_query(F.data.startswith("edit:reminder:"))
    async def edit_reminder(callback: CallbackQuery) -> None:
        try:
            plan_id = int(callback.data.rsplit(":", 1)[1])
        except (ValueError, AttributeError):
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        if not plan:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        current = REMINDER_LABELS.get(plan["reminder_preset"], "تنظیم نشده")
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                f"پلن: {plan['name']}\nساعت یادآوری فعلی: {current}\n\nساعت یادآوری جدید را انتخاب کنید:",
                reply_markup=reminder_times_keyboard(
                    plan_id,
                    f"edit:plan:{plan_id}",
                    set_prefix="edit:setreminder",
                ),
            )

    @router.callback_query(F.data.startswith("edit:setreminder:"))
    async def edit_set_reminder(callback: CallbackQuery) -> None:
        parts = (callback.data or "").split(":")
        if len(parts) != 4:
            await callback.answer("درخواست نامعتبر است.", show_alert=True)
            return
        try:
            plan_id = int(parts[2])
        except ValueError:
            await callback.answer("پلن نامعتبر است.", show_alert=True)
            return
        preset = parts[3]
        updated = await db.update_reminder_preset(callback.from_user.id, plan_id, preset)
        if not updated:
            await callback.answer("پلن پیدا نشد.", show_alert=True)
            return
        plan = await db.get_plan(callback.from_user.id, plan_id)
        await callback.answer("ساعت یادآوری تغییر کرد ✅")
        if callback.message and plan:
            await callback.message.edit_text(
                f"انتخاب پلن: {plan['name']}",
                reply_markup=edit_actions_keyboard(plan_id),
            )

    return router
