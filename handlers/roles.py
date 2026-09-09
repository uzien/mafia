from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from config import settings
from database.crud import get_or_create_user
from database.database import async_session_maker
from game.enums import Role, Team
from locales.i18n import i18n

roles_router = Router()

ROLE_META = {
    Role.CITIZEN: {
        "emoji": "👨🏼‍🌾",
        "phase": {"uz": "Kunduz (Ovoz berish)", "az": "Gündüz (Səsvermə)", "ru": "День (Голосование)", "en": "Day (Voting)", "tr": "Gündüz (Oylama)"},
        "win": {
            "uz": "Barcha jinoyatchilar (Mafiya va Maniak) yo'q qilinganda g'alaba qozonadi.",
            "az": "Bütün cinayətkarlar (Mafiya və Manyaq) məhv edildikdə qələbə qazanır.",
            "ru": "Побеждает, когда все преступники (Мафия и Маньяк) устранены.",
            "en": "Wins when all criminals (Mafia and Maniac) are eliminated.",
            "tr": "Tüm suçlular (Mafya ve Manyak) elendiğinde kazanır."
        }
    },
    Role.DOCTOR: {
        "emoji": "🩺",
        "phase": {"uz": "Tun (Davolash)", "az": "Gecə (Müalicə)", "ru": "Ночь (Лечение)", "en": "Night (Heal)", "tr": "Gece (İyileştirme)"},
        "win": {
            "uz": "Tinch aholi bilan birgalikda shaharni himoya qilish va g'alaba qozonish.",
            "az": "Dinc sakinlər ilə birgə şəhəri qoruyub qalib gəlmək.",
            "ru": "Победа вместе с мирными жителями.",
            "en": "Wins with the Town once threats are eliminated.",
            "tr": "Masum vatandaşlarla birlikte şehri koruyup kazanmak."
        }
    },
    Role.DETECTIVE: {
        "emoji": "🕵️",
        "phase": {"uz": "Tun (Tekshiruv yoki Otish)", "az": "Gecə (Təhqiqat və ya Atəş)", "ru": "Ночь (Проверка или Выстрел)", "en": "Night (Investigate or Shoot)", "tr": "Gece (Soruşturma veya Atış)"},
        "win": {
            "uz": "Tinch aholi bilan birga barcha yovuzlarni fosh qilib g'alaba qozonish.",
            "az": "Dinc sakinlər ilə birgə bütün cinayətkarları ifşa etmək.",
            "ru": "Победа вместе с мирными жителями после разоблачения мафии.",
            "en": "Wins with the Town by exposing the underworld.",
            "tr": "Masum vatandaşlarla birlikte suçluları ifşa edip kazanmak."
        }
    },
    Role.SERGEANT: {
        "emoji": "👮",
        "phase": {"uz": "Passiv (Komissar vorisi)", "az": "Passiv (Komissarın varisi)", "ru": "Пассивно (Преемник Комиссара)", "en": "Passive (Detective Successor)", "tr": "Pasif (Komiser Halefi)"},
        "win": {
            "uz": "Tinch aholi bilan birga g'alaba qozonish.",
            "az": "Dinc sakinlər ilə birgə qələbə qazanmaq.",
            "ru": "Победа вместе с мирными жителями.",
            "en": "Wins with the Town.",
            "tr": "Masum vatandaşlarla birlikte kazanmak."
        }
    },
    Role.SNIPER: {
        "emoji": "🎯",
        "phase": {"uz": "Tun (Yagona aniq o'q)", "az": "Gecə (Tək dəqiq atəş)", "ru": "Ночь (Один точный выстрел)", "en": "Night (One deadly shot)", "tr": "Gece (Tek kritik atış)"},
        "win": {
            "uz": "Tinch aholi bilan birga g'alaba qozonish.",
            "az": "Dinc sakinlər ilə birgə qələbə qazanmaq.",
            "ru": "Победа вместе с мирными жителями.",
            "en": "Wins with the Town.",
            "tr": "Masum vatandaşlarla birlikte kazanmak."
        }
    },
    Role.BODYGUARD: {
        "emoji": "🛡",
        "phase": {"uz": "Tun (Jonli qalqon)", "az": "Gecə (Canlı sipər)", "ru": "Ночь (Живой щит)", "en": "Night (Body shield)", "tr": "Gece (Canlı kalkan)"},
        "win": {
            "uz": "Tinch aholi bilan birga g'alaba qozonish.",
            "az": "Dinc sakinlər ilə birgə qələbə qazanmaq.",
            "ru": "Победа вместе с мирными жителями.",
            "en": "Wins with the Town.",
            "tr": "Masum vatandaşlarla birlikte kazanmak."
        }
    },
    Role.KAMIKAZE: {
        "emoji": "💣",
        "phase": {"uz": "Sudda o'lganda (Qasos portlashi)", "az": "Məhkəmədə linç olunanda", "ru": "При казни на суде (Возмездие)", "en": "Upon Lynch (Revenge Bomb)", "tr": "Mahkemede asıldığında"},
        "win": {
            "uz": "Tinch aholi bilan birga g'alaba qozonish.",
            "az": "Dinc sakinlər ilə birgə qələbə qazanmaq.",
            "ru": "Победа вместе с мирными жителями.",
            "en": "Wins with the Town.",
            "tr": "Masum vatandaşlarla birlikte kazanmak."
        }
    },
    Role.DON: {
        "emoji": "👑",
        "phase": {"uz": "Tun (Qotillik & Komissar qidiruvi)", "az": "Gecə (Qətl və Komissar axtarışı)", "ru": "Ночь (Убийство и Поиск Комиссара)", "en": "Night (Kill & Find Detective)", "tr": "Gece (Cinayet ve Komiser Arama)"},
        "win": {
            "uz": "Mafiya a'zolari soni tinch aholi bilan tenglashganda yoki oshganda g'alaba qozonadi.",
            "az": "Mafiya sayı dinc sakinlərə bərabər və ya çox olduqda qələbə qazanır.",
            "ru": "Побеждает при равенстве сил с мирными жителями или перевесе.",
            "en": "Wins when Mafia reaches parity with Town members.",
            "tr": "Mafya sayısı masum vatandaşlara eşit veya fazla olduğunda kazanır."
        }
    },
    Role.MAFIA: {
        "emoji": "🩸",
        "phase": {"uz": "Tun (Jamoaviy tungi qotillik)", "az": "Gecə (Komanda qətli)", "ru": "Ночь (Командное убийство)", "en": "Night (Team kill)", "tr": "Gece (Takım cinayeti)"},
        "win": {
            "uz": "Shahar to'liq Mafiya nazoratiga o'tganda g'alaba qozonadi.",
            "az": "Şəhər tam Mafiya nəzarətinə keçdikdə qələbə qazanır.",
            "ru": "Победа вместе с Доном при захвате города.",
            "en": "Wins with the Mafia by dominating the city.",
            "tr": "Şehir tamamen Mafya kontrolüne geçtiğinde kazanır."
        }
    },
    Role.LAWYER: {
        "emoji": "💼",
        "phase": {"uz": "Tun (Mafiyani yashirish)", "az": "Gecə (Mafiyanı qorumaq)", "ru": "Ночь (Прикрытие Мафии)", "en": "Night (Shield Mafia from scan)", "tr": "Gece (Mafyayı gizleme)"},
        "win": {
            "uz": "Mafiya jamoasi bilan birgalikda g'alaba qozonish.",
            "az": "Mafiya komandası ilə birgə qələbə qazanmaq.",
            "ru": "Победа вместе с Мафией.",
            "en": "Wins with the Mafia.",
            "tr": "Mafya takımıyla birlikte kazanmak."
        }
    },
    Role.MANIAC: {
        "emoji": "🔪",
        "phase": {"uz": "Tun (Yakka qotillik)", "az": "Gecə (Təkbaşına qətl)", "ru": "Ночь (Одиночное убийство)", "en": "Night (Solo Kill)", "tr": "Gece (Tekli cinayet)"},
        "win": {
            "uz": "Shahardagi barchani qirib tashlab, oxirgi tirik o'yinchi bo'lib qolish!",
            "az": "Şəhərdəki hər kəsi məhv edib sonuncu tək sağ qalan olmaq!",
            "ru": "Уничтожить абсолютно всех и остаться единственным выжившим!",
            "en": "Eliminate every single player and be the last one standing!",
            "tr": "Herkesi ortadan kaldırıp hayatta kalan tek kişi olmak!"
        }
    },
    Role.MISTRESS: {
        "emoji": "💃",
        "phase": {"uz": "Tun (Qobiliyatni bloklash)", "az": "Gecə (Bacarığı bloklamaq)", "ru": "Ночь (Блокировка способности)", "en": "Night (Block ability)", "tr": "Gece (Yetenek engelleme)"},
        "win": {
            "uz": "O'yin oxirigacha omon qolish va tinch aholi bilan g'alaba qozonish.",
            "az": "Oyunun sonuna qədər sağ qalmaq.",
            "ru": "Выжить до конца игры.",
            "en": "Survive until the end of the game.",
            "tr": "Oyunun sonuna kadar hayatta kalmak."
        }
    },
    Role.JESTER: {
        "emoji": "🃏",
        "phase": {"uz": "Kunduzgi sud (O'zini osdirish)", "az": "Gündüz məhkəməsi (Özünü asdırmaq)", "ru": "Дневной суд (Казнить себя)", "en": "Day Court (Get lynched)", "tr": "Gündüz mahkemesi (Kendini astırma)"},
        "win": {
            "uz": "Shaharliklarni aldab, o'zini kunduzgi sudda dorga osishlariga erishish! (Yakka o'zi g'olib bo'ladi)",
            "az": "Şəhər sakinlərini aldadaraq özünü məhkəmədə asdırmaq! (Tək qalib gəlir)",
            "ru": "Обвести всех вокруг пальца и добиться своей казни на суде! (Одиночная победа)",
            "en": "Deceive the Town into hanging them during the day trial! (Solo triumph)",
            "tr": "Kasabalıları kandırarak kendisini astırmak! (Tek başına kazanır)"
        }
    }
}

def get_roles_catalog_markup(lang: str) -> InlineKeyboardMarkup:
    buttons = []
    all_roles = [
        Role.CITIZEN, Role.DOCTOR,
        Role.DETECTIVE, Role.SERGEANT,
        Role.SNIPER, Role.BODYGUARD,
        Role.KAMIKAZE, Role.DON,
        Role.MAFIA, Role.LAWYER,
        Role.MANIAC, Role.MISTRESS,
        Role.JESTER
    ]
    
    row = []
    for r in all_roles:
        r_name = i18n.get(f"roles.{r.value}", lang)
        emoji = ROLE_META[r]["emoji"]
        row.append(InlineKeyboardButton(text=f"{emoji} {r_name}", callback_data=f"role_info_{r.value}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    group_txt = "👥 Asosiy Guruh: @mafia_adu_litsey" if lang in ["uz", "az"] else "👥 Main Group: @mafia_adu_litsey"
    buttons.append([InlineKeyboardButton(text=group_txt, url=settings.MAIN_GROUP_URL)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_roles_catalog_text(lang: str) -> str:
    if lang == "uz":
        return (
            "🎭 <b>Mafia Litsey — O'yindagi Barcha Rollar</b>\n\n"
            "O'yinda <b>13 xil noyob rol</b> mavjud bo'lib, ular 3 ta lagerga bo'lingan:\n\n"
            "🕊 <b>Tinch Aholi (Town):</b>\n"
            "• 👨🏼‍🌾 <b>Tinch axoli</b> — Asosiy ovoz berish kuchi\n"
            "• 🩺 <b>Shifokor</b> — Tungi najotkor\n"
            "• 🕵️ <b>Komissar Katani</b> — Tekshiruvchi va qotillarni fosh etuvchi\n"
            "• 👮 <b>Serjant</b> — Komissar o'rnini bosuvchi yordamchi\n"
            "• 🎯 <b>Snayper</b> — Yagona aniq mergan\n"
            "• 🛡 <b>Tansoqchi</b> — Jonini fido qiluvchi himoyachi\n"
            "• 💣 <b>Kamikadze</b> — Sudda osilsa, aybdorni o'zi bilan olib ketuvchi\n\n"
            "🩸 <b>Mafiya Sindikati (Mafia):</b>\n"
            "• 👑 <b>Don (The Boss)</b> — Mafiya yetakchisi, Komissar izquvari\n"
            "• 🩸 <b>Oddiy Mafiya</b> — Tungi qotillar (Don o'lsa, o'rniga Don bo'ladi)\n"
            "• 💼 <b>Advokat</b> — Mafiyani tekshiruvdan qutqaruvchi\n\n"
            "🔪 <b>Neytral va Yolg'izlar (Neutral):</b>\n"
            "• 🔪 <b>Maniak</b> — Butun shaharni yakson qiluvchi qotil\n"
            "• 💃 <b>Ma'shuqa</b> — Tunda qobiliyatlarni to'xtatuvchi\n"
            "• 🃏 <b>Joker (Jester)</b> — O'zini osdirishni xohlovchi daho\n\n"
            "<i>Batafsil ma'lumot olish uchun quyidagi rolni tanlang:</i>"
        )
    elif lang == "az":
        return (
            "🎭 <b>Mafia Litsey — Oyundakı Bütün Rollar</b>\n\n"
            "Oyunda <b>13 müxtəlif rol</b> var və onlar 3 qrupa bölünür:\n\n"
            "🕊 <b>Dinc Sakinlər (Town):</b>\n"
            "• 👨🏼‍🌾 <b>Dinc sakin</b>, 🩺 <b>Həkim</b>, 🕵️ <b>Komissar</b>, 👮 <b>Serjant</b>, 🎯 <b>Snayper</b>, 🛡 <b>Cangüdən</b>, 💣 <b>Kamikadze</b>\n\n"
            "🩸 <b>Mafiya (Mafia):</b>\n"
            "• 👑 <b>Don</b>, 🩸 <b>Mafiya</b>, 💼 <b>Vəkil</b>\n\n"
            "🔪 <b>Neytrallar:</b>\n"
            "• 🔪 <b>Manyaq</b>, 💃 <b>Məşuqə</b>, 🃏 <b>Jester (Təlxək)</b>\n\n"
            "<i>Ətraflı məlumat üçün rolu seçin:</i>"
        )
    elif lang == "ru":
        return (
            "🎭 <b>Mafia Litsey — Все роли в игре</b>\n\n"
            "В игре присутствует <b>13 уникальных ролей</b>, разделенных на 3 фракции:\n\n"
            "🕊 <b>Мирные Жители (Город):</b>\n"
            "• 👨🏼‍🌾 <b>Мирный житель</b>, 🩺 <b>Доктор</b>, 🕵️ <b>Комиссар</b>, 👮 <b>Сержант</b>, 🎯 <b>Снайпер</b>, 🛡 <b>Телохранитель</b>, 💣 <b>Камикадзе</b>\n\n"
            "🩸 <b>Мафия:</b>\n"
            "• 👑 <b>Дон</b>, 🩸 <b>Мафия</b>, 💼 <b>Адвокат</b>\n\n"
            "🔪 <b>Нейтральные роли:</b>\n"
            "• 🔪 <b>Маньяк</b>, 💃 <b>Любовница</b>, 🃏 <b>Шут (Самоубийца)</b>\n\n"
            "<i>Нажмите на роль ниже, чтобы узнать способности:</i>"
        )
    else:
        return (
            "🎭 <b>Mafia Litsey — All Game Roles</b>\n\n"
            "The game features <b>13 unique roles</b> across 3 teams:\n\n"
            "🕊 <b>Town:</b> Citizen, Doctor, Detective, Sergeant, Sniper, Bodyguard, Kamikaze\n"
            "🩸 <b>Mafia:</b> Don, Mafia, Lawyer\n"
            "🔪 <b>Neutrals:</b> Maniac, Mistress, Jester\n\n"
            "<i>Click any role below to inspect detailed abilities:</i>"
        )

def get_role_detail_text(role: Role, lang: str) -> str:
    meta = ROLE_META.get(role, {})
    emoji = meta.get("emoji", "🎭")
    role_name = i18n.get(f"roles.{role.value}", lang)
    desc = i18n.get(f"role_desc.{role.value}", lang)
    phase = meta.get("phase", {}).get(lang, meta.get("phase", {}).get("uz", "Tun"))
    win = meta.get("win", {}).get(lang, meta.get("win", {}).get("uz", "G'alaba qozonish"))

    team_map = {
        Role.CITIZEN: Team.TOWN, Role.DOCTOR: Team.TOWN, Role.DETECTIVE: Team.TOWN,
        Role.SERGEANT: Team.TOWN, Role.SNIPER: Team.TOWN, Role.BODYGUARD: Team.TOWN,
        Role.KAMIKAZE: Team.TOWN, Role.DON: Team.MAFIA, Role.MAFIA: Team.MAFIA,
        Role.LAWYER: Team.MAFIA, Role.MANIAC: Team.NEUTRAL, Role.MISTRESS: Team.NEUTRAL,
        Role.JESTER: Team.JESTER
    }
    t = team_map.get(role, Team.TOWN)
    team_labels = {
        Team.TOWN: {"uz": "🕊 Tinch Aholi (Town)", "az": "🕊 Dinc Sakinlər", "ru": "🕊 Мирные Жители", "en": "🕊 Town", "tr": "🕊 Masum Vatandaşlar"},
        Team.MAFIA: {"uz": "🩸 Mafiya Sindikati (Mafia)", "az": "🩸 Mafiya", "ru": "🩸 Мафия", "en": "🩸 Mafia", "tr": "🩸 Mafya"},
        Team.NEUTRAL: {"uz": "🔪 Neytral / Yolg'iz", "az": "🔪 Neytral", "ru": "🔪 Нейтрал", "en": "🔪 Neutral", "tr": "🔪 Nötr"},
        Team.JESTER: {"uz": "🃏 Yolg'onchi (Yakka o'zi)", "az": "🃏 Təlxək", "ru": "🃏 Шут (Одиночка)", "en": "🃏 Jester (Solo)", "tr": "🃏 Soytarı"}
    }
    team_name = team_labels.get(t, team_labels[Team.TOWN]).get(lang, "🕊 Town")

    return (
        f"{emoji} <b>{role_name}</b>\n\n"
        f"⚔️ <b>Jamoasi:</b> {team_name}\n"
        f"🌙 <b>Harakat vaqti:</b> <b>{phase}</b>\n\n"
        f"📖 <b>Qobiliyati:</b>\n"
        f"<i>{desc}</i>\n\n"
        f"🏆 <b>G'alaba sharti:</b>\n"
        f"<i>{win}</i>"
    )

@roles_router.message(Command("roles", "rollar", "rol"))
async def cmd_roles(message: Message):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, message.from_user.id, message.from_user.username, message.from_user.first_name)
        lang = user.language or settings.DEFAULT_LANGUAGE

    parts = (message.text or "").strip().split()
    if len(parts) > 1:
        target_role_str = parts[1].lower()
        for r in Role:
            if r.value == target_role_str or target_role_str in r.value:
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Barcha Rollar", callback_data="roles_list")],
                    [InlineKeyboardButton(text="👥 Asosiy Guruh (@mafia_adu_litsey)", url=settings.MAIN_GROUP_URL)]
                ])
                return await message.answer(get_role_detail_text(r, lang), reply_markup=markup, parse_mode="HTML")

    await message.answer(
        get_roles_catalog_text(lang),
        reply_markup=get_roles_catalog_markup(lang),
        parse_mode="HTML"
    )

@roles_router.callback_query(F.data.startswith("role_info_"))
async def cb_role_info(callback: CallbackQuery):
    role_str = callback.data.replace("role_info_", "")
    role = None
    for r in Role:
        if r.value == role_str:
            role = r
            break

    if not role:
        return await callback.answer("Rol topilmadi!", show_alert=True)

    async with async_session_maker() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language or settings.DEFAULT_LANGUAGE

    back_txt = "◀️ Barcha Rollar" if lang in ["uz", "az"] else "◀️ All Roles"
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=back_txt, callback_data="roles_list")],
        [InlineKeyboardButton(text="👥 Asosiy Guruh (@mafia_adu_litsey)", url=settings.MAIN_GROUP_URL)]
    ])
    try:
        await callback.message.edit_text(get_role_detail_text(role, lang), reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@roles_router.callback_query(F.data == "roles_list")
async def cb_roles_list(callback: CallbackQuery):
    async with async_session_maker() as session:
        user = await get_or_create_user(session, callback.from_user.id)
        lang = user.language or settings.DEFAULT_LANGUAGE

    try:
        await callback.message.edit_text(
            get_roles_catalog_text(lang),
            reply_markup=get_roles_catalog_markup(lang),
            parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer()
