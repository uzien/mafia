from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Clan, GroupChat, InventoryItem, Tournament, TournamentParticipant, User

async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    first_name: str = "Player",
    default_lang: str = "uz"
) -> User:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            id=user_id,
            username=username,
            first_name=first_name,
            language=default_lang
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # Update username/first_name if changed
        updated = False
        if username and user.username != username:
            user.username = username
            updated = True
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if updated:
            await session.commit()
    return user

async def set_user_language(session: AsyncSession, user_id: int, lang: str):
    stmt = update(User).where(User.id == user_id).values(language=lang)
    await session.execute(stmt)
    await session.commit()

async def get_or_create_group(
    session: AsyncSession,
    group_id: int,
    title: str = "Group Chat",
    default_lang: str = "uz"
) -> GroupChat:
    stmt = select(GroupChat).where(GroupChat.id == group_id)
    result = await session.execute(stmt)
    group = result.scalar_one_or_none()
    if not group:
        group = GroupChat(id=group_id, title=title, language=default_lang)
        session.add(group)
        await session.commit()
        await session.refresh(group)
    return group

async def set_group_language(session: AsyncSession, group_id: int, lang: str):
    stmt = update(GroupChat).where(GroupChat.id == group_id).values(language=lang)
    await session.execute(stmt)
    await session.commit()

async def claim_daily_bonus(session: AsyncSession, user_id: int, amount: int) -> tuple[bool, int]:
    """Returns (success, hours_remaining_if_failed)"""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return False, 0
    
    now = datetime.utcnow()
    if user.last_daily:
        diff = now - user.last_daily
        if diff < timedelta(hours=24):
            remaining = 24 - int(diff.total_seconds() // 3600)
            return False, max(1, remaining)
            
    user.coins += amount
    user.last_daily = now
    await session.commit()
    return True, 0

async def add_game_stats(session: AsyncSession, user_id: int, won: bool, role: str, coins: int, exp: int) -> Optional[User]:
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return None
    user.games_played += 1
    if won:
        user.wins += 1
    else:
        user.losses += 1
    user.coins += coins
    user.exp += exp
    # Level up threshold
    if user.exp >= user.level * 250:
        user.level += 1
    await session.commit()
    await session.refresh(user)
    return user

async def get_top_players(session: AsyncSession, limit: int = 10) -> List[User]:
    stmt = select(User).order_by(desc(User.wins), desc(User.exp)).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def create_clan(session: AsyncSession, leader_id: int, name: str, tag: str) -> Optional[Clan]:
    # Check if clan exists
    stmt = select(Clan).where((Clan.name == name) | (Clan.tag == tag))
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return None
    clan = Clan(name=name, tag=tag.upper(), leader_id=leader_id)
    session.add(clan)
    await session.commit()
    await session.refresh(clan)
    
    # Assign leader to clan
    user_stmt = update(User).where(User.id == leader_id).values(clan_id=clan.id)
    await session.execute(user_stmt)
    await session.commit()
    return clan

async def get_clan(session: AsyncSession, clan_id: int) -> Optional[Clan]:
    stmt = select(Clan).where(Clan.id == clan_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_active_tournaments(session: AsyncSession) -> List[Tournament]:
    stmt = select(Tournament).where(Tournament.status != "completed").order_by(desc(Tournament.created_at))
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def get_tournament_participant_count(session: AsyncSession, tournament_id: int) -> int:
    stmt = select(func.count(TournamentParticipant.id)).where(TournamentParticipant.tournament_id == tournament_id)
    result = await session.execute(stmt)
    return result.scalar() or 0

async def deposit_to_clan(session: AsyncSession, user_id: int, amount: int) -> bool:
    user = await session.get(User, user_id)
    if not user or not user.clan_id or user.coins < amount:
        return False
    clan = await session.get(Clan, user.clan_id)
    if not clan:
        return False
    user.coins -= amount
    clan.treasury += amount
    clan.rating += (amount // 10)  # 1 rating point per 10 coins
    await session.commit()
    return True

async def get_clan_members_count(session: AsyncSession, clan_id: int) -> int:
    stmt = select(func.count(User.id)).where(User.clan_id == clan_id)
    res = await session.execute(stmt)
    return res.scalar() or 0

async def leave_clan(session: AsyncSession, user_id: int) -> bool:
    user = await session.get(User, user_id)
    if not user or not user.clan_id:
        return False
    clan_id = user.clan_id
    user.clan_id = None
    
    # Check if clan has remaining members
    stmt = select(User).where(User.clan_id == clan_id)
    res = await session.execute(stmt)
    remaining_members = list(res.scalars().all())
    
    clan = await session.get(Clan, clan_id)
    if clan:
        if not remaining_members:
            await session.delete(clan)
        elif clan.leader_id == user_id:
            clan.leader_id = remaining_members[0].id
    await session.commit()
    return True

async def get_top_clans(session: AsyncSession, limit: int = 10) -> List[Clan]:
    stmt = select(Clan).order_by(desc(Clan.rating), desc(Clan.treasury)).limit(limit)
    res = await session.execute(stmt)
    return list(res.scalars().all())

async def get_all_user_ids(session: AsyncSession) -> List[int]:
    stmt = select(User.id)
    res = await session.execute(stmt)
    return list(res.scalars().all())

async def admin_add_currency(session: AsyncSession, user_id: int, coins: int = 0, diamonds: int = 0) -> bool:
    user = await session.get(User, user_id)
    if not user:
        return False
    user.coins += coins
    user.diamonds += diamonds
    await session.commit()
    return True
