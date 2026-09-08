import random
from typing import Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from database.models import InventoryItem, User
from game.enums import Role

SHOP_ITEMS: Dict[str, Dict] = {
    "don_card": {
        "name_az": "👑 Don Kartı",
        "name_uz": "👑 Don Kartasi",
        "name_ru": "👑 Карта Дона",
        "name_en": "👑 Don Card",
        "name_tr": "👑 Don Kartı",
        "cost": 300,
        "currency": "coins",
        "role": Role.DON
    },
    "det_card": {
        "name_az": "🕵️ Komissar Kartı",
        "name_uz": "🕵️ Komissar Kartasi",
        "name_ru": "🕵️ Карта Комиссара",
        "name_en": "🕵️ Detective Card",
        "name_tr": "🕵️ Komiser Kartı",
        "cost": 300,
        "currency": "coins",
        "role": Role.DETECTIVE
    },
    "doc_card": {
        "name_az": "💉 Həkim Kartı",
        "name_uz": "💉 Shifokor Kartasi",
        "name_ru": "💉 Карта Доктора",
        "name_en": "💉 Doctor Card",
        "name_tr": "💉 Doktor Kartı",
        "cost": 250,
        "currency": "coins",
        "role": Role.DOCTOR
    },
    "fake_docs": {
        "name_az": "🪪 Saxta Sənəd (Pasport)",
        "name_uz": "🪪 Soxta Hujjat (Pasport)",
        "name_ru": "🪪 Поддельные Документы",
        "name_en": "🪪 Fake Identity Documents",
        "name_tr": "🪪 Sahte Kimlik Belgesi",
        "cost": 200,
        "currency": "coins",
        "desc": "Komissar tekshirganda rolingiz o'rniga soxta tinch fuqaro ma'lumotlarini ko'rsatadi!"
    },
    "title_godfather": {
        "name_az": "🏆 'Xaç Atası' Ləqəbi",
        "name_uz": "🏆 'Buyuk Don' Unvoni",
        "name_ru": "🏆 Титул 'Крестный Отец'",
        "name_en": "🏆 'Godfather' Title",
        "name_tr": "🏆 'Mafya Babası' Unvanı",
        "cost": 50,
        "currency": "diamonds",
        "title": "👑 Godfather"
    },
    "vip_pass": {
        "name_az": "💎 VIP Status (30 gün)",
        "name_uz": "💎 VIP Status (30 kun)",
        "name_ru": "💎 VIP Статус (30 дней)",
        "name_en": "💎 VIP Pass (30 Days)",
        "name_tr": "💎 VIP Statüsü (30 Gün)",
        "cost": 100,
        "currency": "diamonds",
        "vip_days": 30
    }
}

async def buy_shop_item(session: AsyncSession, user_id: int, item_key: str) -> Tuple[bool, str]:
    item = SHOP_ITEMS.get(item_key)
    if not item:
        return False, "item_not_found"

    user = await session.get(User, user_id)
    if not user:
        return False, "user_not_found"

    cost = item["cost"]
    currency = item["currency"]

    if currency == "coins":
        if user.coins < cost:
            return False, "not_enough_money"
        user.coins -= cost
    elif currency == "diamonds":
        if user.diamonds < cost:
            return False, "not_enough_money"
        user.diamonds -= cost

    # Apply effect
    if "title" in item:
        user.title = item["title"]
    elif "vip_days" in item:
        user.is_vip = True
    else:
        # Inventory item (role card or fake docs)
        stmt = select(InventoryItem).where(
            InventoryItem.user_id == user_id,
            InventoryItem.item_key == item_key
        )
        res = await session.execute(stmt)
        inv = res.scalar_one_or_none()
        if inv:
            inv.quantity += 1
        else:
            session.add(InventoryItem(user_id=user_id, item_key=item_key, quantity=1))

    await session.commit()
    return True, item.get(f"name_{user.language}", item.get("name_uz", item["name_az"]))

async def consume_role_card(session: AsyncSession, user_id: int) -> Optional[Role]:
    """Check and consume a user's role card if equipped."""
    stmt = select(InventoryItem).where(
        InventoryItem.user_id == user_id,
        InventoryItem.quantity > 0
    )
    result = await session.execute(stmt)
    inv = result.scalars().first()
    if inv and inv.item_key in SHOP_ITEMS and "role" in SHOP_ITEMS[inv.item_key]:
        role = SHOP_ITEMS[inv.item_key]["role"]
        inv.quantity -= 1
        if inv.quantity <= 0:
            await session.delete(inv)
        await session.commit()
        return role
    return None

async def has_fake_documents(session: AsyncSession, user_id: int) -> bool:
    """Check if user has active fake documents in inventory."""
    stmt = select(InventoryItem).where(
        InventoryItem.user_id == user_id,
        InventoryItem.item_key == "fake_docs",
        InventoryItem.quantity > 0
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None

async def consume_fake_documents(session: AsyncSession, user_id: int) -> bool:
    """Consume 1 unit of fake documents upon detective inspection."""
    stmt = select(InventoryItem).where(
        InventoryItem.user_id == user_id,
        InventoryItem.item_key == "fake_docs",
        InventoryItem.quantity > 0
    )
    result = await session.execute(stmt)
    inv = result.scalar_one_or_none()
    if inv:
        inv.quantity -= 1
        if inv.quantity <= 0:
            await session.delete(inv)
        await session.commit()
        return True
    return False

async def get_user_inventory(session: AsyncSession, user_id: int) -> Dict[str, int]:
    """Fetch user's inventory item quantities."""
    stmt = select(InventoryItem).where(
        InventoryItem.user_id == user_id,
        InventoryItem.quantity > 0
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    return {item.item_key: item.quantity for item in items}

async def add_diamonds_to_user(session: AsyncSession, user_id: int, amount: int) -> Optional[User]:
    """Admin function to grant diamonds."""
    user = await session.get(User, user_id)
    if not user:
        return None
    user.diamonds += amount
    await session.commit()
    return user
