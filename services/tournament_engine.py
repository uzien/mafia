from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Tournament, TournamentParticipant, User

async def create_tournament(
    session: AsyncSession,
    name: str,
    entry_fee: int = 100,
    prize_pool: int = 50,
    max_participants: int = 16
) -> Tournament:
    tournament = Tournament(
        name=name,
        entry_fee=entry_fee,
        prize_pool=prize_pool,
        max_participants=max_participants,
        status="registration",
        created_at=datetime.utcnow()
    )
    session.add(tournament)
    await session.commit()
    await session.refresh(tournament)
    return tournament

async def register_participant(
    session: AsyncSession,
    tournament_id: int,
    user_id: int
) -> Tuple[bool, str]:
    tournament = await session.get(Tournament, tournament_id)
    if not tournament or tournament.status != "registration":
        return False, "tournament_not_open"

    user = await session.get(User, user_id)
    if not user:
        return False, "user_not_found"

    if user.coins < tournament.entry_fee:
        return False, "not_enough_coins"

    # Check if already registered
    stmt = select(TournamentParticipant).where(
        TournamentParticipant.tournament_id == tournament_id,
        TournamentParticipant.user_id == user_id
    )
    res = await session.execute(stmt)
    if res.scalar_one_or_none():
        return False, "already_registered"

    # Check capacity
    count_stmt = select(TournamentParticipant).where(TournamentParticipant.tournament_id == tournament_id)
    count_res = await session.execute(count_stmt)
    if len(count_res.scalars().all()) >= tournament.max_participants:
        return False, "tournament_full"

    user.coins -= tournament.entry_fee
    tournament.prize_pool += int(tournament.entry_fee * 0.5)  # Add 50% of entry fee to pool

    participant = TournamentParticipant(tournament_id=tournament_id, user_id=user_id, points=0)
    session.add(participant)
    await session.commit()
    return True, "success"

async def conclude_tournament(
    session: AsyncSession,
    tournament_id: int,
    winner_id: int
) -> bool:
    tournament = await session.get(Tournament, tournament_id)
    if not tournament:
        return False
    winner = await session.get(User, winner_id)
    if not winner:
        return False

    tournament.status = "completed"
    tournament.winner_id = winner_id
    winner.diamonds += tournament.prize_pool
    winner.title = f"🏆 {tournament.name} Champ"
    await session.commit()
    return True
