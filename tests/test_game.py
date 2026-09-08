import pytest
from game.enums import Role, Team
from game.role_models import distribute_roles
from game.room import GameRoom

def test_distribute_roles_4_players():
    player_ids = [101, 102, 103, 104]
    roles = distribute_roles(player_ids)
    assert len(roles) == 4
    role_values = list(roles.values())
    assert Role.DON in role_values
    assert Role.DETECTIVE in role_values
    assert Role.DOCTOR in role_values
    assert Role.CITIZEN in role_values

def test_distribute_roles_7_players():
    player_ids = [1, 2, 3, 4, 5, 6, 7]
    roles = distribute_roles(player_ids)
    assert len(roles) == 7
    role_values = list(roles.values())
    assert Role.DON in role_values
    assert Role.MAFIA in role_values
    assert Role.MANIAC in role_values
    assert Role.DETECTIVE in role_values
    assert Role.DOCTOR in role_values

def test_win_condition_town():
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host")
    room.add_player(2, "Player 2")
    room.add_player(3, "Player 3")
    room.add_player(4, "Player 4")
    
    # 3 town alive, 0 mafia alive
    room.players[1].role = Role.CITIZEN
    room.players[2].role = Role.DOCTOR
    room.players[3].role = Role.DETECTIVE
    room.players[4].role = Role.MAFIA
    room.players[4].is_alive = False

    winner = room.check_winner()
    assert winner == Team.TOWN

def test_win_condition_mafia():
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host")
    room.add_player(2, "Player 2")
    room.add_player(3, "Player 3")
    room.add_player(4, "Player 4")

    # 2 mafia, 2 citizens alive -> Mafia parity win
    room.players[1].role = Role.DON
    room.players[2].role = Role.MAFIA
    room.players[3].role = Role.CITIZEN
    room.players[4].role = Role.CITIZEN

    winner = room.check_winner()
    assert winner == Team.MAFIA

def test_win_condition_maniac():
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host")
    room.add_player(2, "Player 2")
    room.add_player(3, "Player 3")

    room.players[1].role = Role.MANIAC
    room.players[2].role = Role.CITIZEN
    room.players[3].role = Role.MAFIA
    room.players[2].is_alive = False
    room.players[3].is_alive = False

    winner = room.check_winner()
    assert winner == Team.NEUTRAL

def test_win_condition_jester():
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host")
    room.add_player(2, "Player 2")
    room.jester_won = True
    assert room.check_winner() == Team.JESTER

def test_distribute_roles_11_players():
    player_ids = list(range(1, 12))
    roles = distribute_roles(player_ids)
    assert len(roles) == 11
    role_values = list(roles.values())
    assert Role.DON in role_values
    assert Role.DETECTIVE in role_values
    assert Role.SERGEANT in role_values
    assert Role.SNIPER in role_values
    assert Role.JESTER in role_values
    assert Role.DOCTOR in role_values

@pytest.mark.asyncio
async def test_db_resilient_fallback():
    from database.database import session_manager, init_db
    # Point to an unreachable host
    session_manager.switch_engine("postgresql+asyncpg://invalid:invalid@unreachable-db-host-9999.xyz:5432/test")
    await init_db()
    assert "sqlite" in session_manager.url

def test_lobby_text_and_markup_uz():
    room = GameRoom(chat_id=-1001, creator_id=101, creator_name="mydnva'", lang="uz")
    room.add_player(102, "Tolibjonov")
    room.add_player(103, "boburjon 🫀")
    room.add_player(104, "dkxolmaxammadov 🫀")

    text = room.get_lobby_text()
    assert "Ro'yxatdan o'tish davom etmoqda" in text
    assert "Ro'yxatdan o'tganlar:" in text
    assert "mydnva'" in text
    assert "Tolibjonov" in text
    assert "boburjon 🫀" in text
    assert "dkxolmaxammadov 🫀" in text
    assert "Jami <b>4ta odam</b>." in text

    markup = room.get_lobby_markup()
    # Check that join button has deep link url
    join_btn = markup.inline_keyboard[0][0]
    assert "Qo'shilish" in join_btn.text
    assert "start=game_-1001" in join_btn.url

def test_living_players_text_format():
    room = GameRoom(chat_id=-1001, creator_id=101, creator_name="dkxolmaxammadov 🫀", lang="uz")
    room.add_player(102, "boburjon 🫀")
    room.add_player(103, "mydnva'")
    room.add_player(104, "Tolibjonov")

    room.players[101].role = Role.CITIZEN
    room.players[102].role = Role.CITIZEN
    room.players[103].role = Role.DETECTIVE
    room.players[104].role = Role.DON

    living_text = room.get_living_players_text()
    assert "Tirik o'yinchilar:" in living_text
    assert "dkxolmaxammadov 🫀" in living_text
    assert "Tolibjonov" in living_text
    assert "Ulardan:" in living_text
    assert "Fuqaro - 2" in living_text
    assert "Komissar katani" in living_text
    assert "Don (Mafiya Boshlig'i)" in living_text
    assert "Jami:" in living_text

def test_extend_lobby_time():
    room = GameRoom(chat_id=-1001, creator_id=101, creator_name="Host", lang="uz")
    initial = room.seconds_left
    new_time = room.extend_lobby_time(30)
    assert new_time == initial + 30
    assert room.seconds_left == initial + 30
    # Test capping at 300
    room.seconds_left = 290
    capped = room.extend_lobby_time(30)
    assert capped == 300
    # Check button presence in markup
    markup = room.get_lobby_markup()
    button_texts = [b.text for row in markup.inline_keyboard for b in row]
    assert any("+30s" in t for t in button_texts)

from unittest.mock import AsyncMock
from game.enums import GamePhase

def test_player_fake_docs_model():
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Don Corleone")
    player = room.players[1]
    assert player.has_fake_docs is False
    player.has_fake_docs = True
    assert player.has_fake_docs is True

@pytest.mark.asyncio
async def test_broadcast_mafia_chat():
    room = GameRoom(chat_id=-1001, creator_id=101, creator_name="Don")
    room.add_player(102, "Mafia1")
    room.add_player(103, "Citizen1")
    room.add_player(104, "DeadMafia")

    room.players[101].role = Role.DON
    room.players[102].role = Role.MAFIA
    room.players[103].role = Role.CITIZEN
    room.players[104].role = Role.MAFIA
    room.players[104].is_alive = False
    room.phase = GamePhase.NIGHT

    mock_bot = AsyncMock()
    # Don sends a message
    res = await room.broadcast_mafia_chat(mock_bot, sender_id=101, sender_name="Don", text="Let's kill citizen tonight")
    assert res is True

    # Only player 102 (living mafia) should receive the message
    assert mock_bot.send_message.call_count == 1
    call_args = mock_bot.send_message.call_args_list[0]
    target_chat_id = call_args.args[0] if call_args.args else call_args.kwargs.get("chat_id")
    assert target_chat_id == 102
    msg_text = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("text")
    assert "Let's kill citizen tonight" in msg_text
    assert "Mafiya Maxfiy Chati" in msg_text

@pytest.mark.asyncio
async def test_last_words_skip_mechanism():
    import asyncio
    room = GameRoom(chat_id=-1001, creator_id=101, creator_name="Accused", lang="uz")
    room.add_player(102, "Accuser")
    room.players[101].role = Role.CITIZEN
    room.phase = GamePhase.VOTING

    mock_bot = AsyncMock()
    # Start last words task
    task = asyncio.create_task(room.start_last_words(mock_bot, lynched_id=101))
    # Give event loop a cycle so last_words_event is created
    await asyncio.sleep(0.02)
    assert room.last_words_event is not None
    # Trigger skip immediately
    room.last_words_event.set()

    # Wait for completion without blocking
    await asyncio.wait_for(task, timeout=2.0)
    assert room.condemned_player_id == 101
    assert room.players[101].is_alive is False  # Executed after last words

@pytest.mark.asyncio
async def test_economy_fake_docs_and_diamonds():
    from database.database import async_session_maker, init_db
    from database.crud import get_or_create_user
    from services.economy_service import (
        add_diamonds_to_user,
        has_fake_documents,
        consume_fake_documents,
        buy_shop_item,
        SHOP_ITEMS
    )

    await init_db()
    async with async_session_maker() as session:
        test_uid = 998877
        user = await get_or_create_user(session, test_uid, "test_user", "Test")
        # Give enough coins to buy fake_docs
        user.coins = 1000
        await session.commit()

        # Buy fake_docs
        success, msg = await buy_shop_item(session, test_uid, "fake_docs")
        assert success is True

        # Verify has_fake_documents
        has_docs = await has_fake_documents(session, test_uid)
        assert has_docs is True

        # Consume fake documents
        consumed = await consume_fake_documents(session, test_uid)
        assert consumed is True

        # Check again - should be False now
        assert await has_fake_documents(session, test_uid) is False

        # Add diamonds
        updated_user = await add_diamonds_to_user(session, test_uid, 50)
        assert updated_user is not None
        assert updated_user.diamonds >= 50

def test_roulette_localization():
    from handlers.roulette import get_prize_label
    prize_coins = {"type": "coins", "amount": 100}
    prize_jackpot = {"type": "diamonds", "amount": 10, "jackpot": True}
    
    assert "Tanga" in get_prize_label(prize_coins, "uz")
    assert "Qızıl" in get_prize_label(prize_coins, "az")
    assert "Монет" in get_prize_label(prize_coins, "ru")
    assert "Coins" in get_prize_label(prize_coins, "en")
    assert "Altın" in get_prize_label(prize_coins, "tr")

    assert "OLMOS" in get_prize_label(prize_jackpot, "uz")
    assert "ALMAZ" in get_prize_label(prize_jackpot, "az")
    assert "АЛМАЗОВ" in get_prize_label(prize_jackpot, "ru")
    assert "DIAMONDS" in get_prize_label(prize_jackpot, "en")
    assert "ELMAS" in get_prize_label(prize_jackpot, "tr")

@pytest.mark.asyncio
async def test_clan_crud_and_methods():
    from database.database import async_session_maker, init_db
    from database.crud import (
        get_or_create_user,
        create_clan,
        get_clan,
        get_clan_members_count,
        deposit_to_clan,
        get_top_clans,
        leave_clan
    )

    await init_db()
    async with async_session_maker() as session:
        u1 = await get_or_create_user(session, 112233, "clan_boss", "Boss")
        u1.coins = 1000
        await session.commit()

        # Create clan
        clan = await create_clan(session, u1.id, "Test Mafia", "TM")
        assert clan is not None
        assert clan.tag == "TM"

        # Check members count
        cnt = await get_clan_members_count(session, clan.id)
        assert cnt == 1

        # Deposit
        dep = await deposit_to_clan(session, u1.id, 200)
        assert dep is True
        assert clan.treasury == 200
        assert clan.rating == 20

        # Top clans
        top = await get_top_clans(session)
        assert len(top) >= 1
        assert any(c.id == clan.id for c in top)

        # Leave clan
        left = await leave_clan(session, u1.id)
        assert left is True
        assert u1.clan_id is None

def test_roles_catalog_and_details():
    from handlers.roles import get_roles_catalog_text, get_role_detail_text, get_roles_catalog_markup
    from game.enums import Role

    # Test catalog text in Uzbek and Russian
    uz_text = get_roles_catalog_text("uz")
    assert "13 xil noyob rol" in uz_text
    assert "Komissar Katani" in uz_text
    assert "Don" in uz_text

    ru_text = get_roles_catalog_text("ru")
    assert "13 уникальных ролей" in ru_text

    # Test detail text for Don and Detective
    don_detail = get_role_detail_text(Role.DON, "uz")
    assert "Don" in don_detail
    assert "Mafiya Sindikati" in don_detail
    assert "G'alaba sharti" in don_detail

    # Test markup
    markup = get_roles_catalog_markup("uz")
    buttons = [b.text for row in markup.inline_keyboard for b in row]
    assert any("Don" in b for b in buttons)
    assert any("Komissar" in b for b in buttons)
    assert any("@mafia_adu_litsey" in b for b in buttons)

@pytest.mark.asyncio
async def test_don_promotion_when_don_dies_at_night():
    from game.room import GameRoom
    from unittest.mock import AsyncMock
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host", lang="uz")
    room.add_player(2, "DonPlayer")
    room.add_player(3, "MafiaPlayer")
    room.add_player(4, "CitizenPlayer")

    room.players[1].role = Role.MANIAC
    room.players[2].role = Role.DON
    room.players[3].role = Role.MAFIA
    room.players[4].role = Role.CITIZEN

    # Maniac targets Don at night
    room.maniac_target = 2
    mock_bot = AsyncMock()

    await room.resolve_night(mock_bot)

    # Don is dead
    assert not room.players[2].is_alive
    # Regular Mafia is promoted to Don!
    assert room.players[3].role == Role.DON
    assert room.players[3].is_alive

@pytest.mark.asyncio
async def test_don_promotion_when_don_lynched():
    from game.room import GameRoom
    from unittest.mock import AsyncMock
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host", lang="uz")
    room.add_player(2, "DonPlayer")
    room.add_player(3, "MafiaPlayer")
    room.add_player(4, "CitizenPlayer")

    room.players[1].role = Role.CITIZEN
    room.players[2].role = Role.DON
    room.players[3].role = Role.MAFIA
    room.players[4].role = Role.CITIZEN

    mock_bot = AsyncMock()
    await room.execute_lynch(mock_bot, lynched_id=2)

    # Don lynched
    assert not room.players[2].is_alive
    # Mafia promoted to Don
    assert room.players[3].role == Role.DON

def test_updated_role_emojis():
    from handlers.roles import ROLE_META
    assert ROLE_META[Role.CITIZEN]["emoji"] == "👨🏼‍🌾"
    assert ROLE_META[Role.MISTRESS]["emoji"] == "💋"
    assert ROLE_META[Role.DON]["emoji"] == "👑"



