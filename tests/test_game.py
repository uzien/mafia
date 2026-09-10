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
    assert "O'YIN RO'YXATGA OLISH" in text
    assert "Ro'yxat:" in text
    assert "mydnva'" in text
    assert "Tolibjonov" in text
    assert "boburjon 🫀" in text
    assert "dkxolmaxammadov 🫀" in text
    assert "Ishtirokchilar:" in text

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
    assert "Tirik o'yinchilar" in living_text
    assert "dkxolmaxammadov 🫀" in living_text
    assert "Tolibjonov" in living_text
    assert "Ulardan:" in living_text
    assert "Fuqaro - 2" in living_text
    assert "Komissar katani" in living_text
    assert "Don (Mafiya Boshlig'i)" in living_text
    assert "Jami" in living_text

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
    # Check button presence in creator panel markup
    markup = room.get_creator_panel_markup()
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
    assert ROLE_META[Role.MISTRESS]["emoji"] == "💃"
    assert ROLE_META[Role.DON]["emoji"] == "👑"

@pytest.mark.asyncio
async def test_last_will_broadcast_night_and_lynch():
    from game.room import GameRoom
    from unittest.mock import AsyncMock

    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Victim", lang="uz")
    room.add_player(2, "Killer")
    room.add_player(3, "Observer")

    room.players[1].role = Role.CITIZEN
    room.players[1].last_will = "Mening vasiyatim: Shaharni asrang!"
    room.players[2].role = Role.DON
    room.players[3].role = Role.CITIZEN

    # Simulate mafia kill on player 1
    room.phase = GamePhase.NIGHT
    room.mafia_votes = {2: 1}

    mock_bot = AsyncMock()
    await room.resolve_night(mock_bot)

    assert not room.players[1].is_alive
    # Check that will was broadcast to chat
    will_calls = [
        call for call in mock_bot.send_message.call_args_list
        if "Mening vasiyatim: Shaharni asrang!" in (call.args[1] if len(call.args) > 1 else call.kwargs.get("text", ""))
    ]
    assert len(will_calls) == 1

@pytest.mark.asyncio
async def test_night_random_events_and_are_all_actions_done():
    from game.room import GameRoom
    from unittest.mock import AsyncMock

    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Player1", lang="uz")
    room.add_player(2, "Player2")
    room.add_player(3, "Player3")

    room.players[1].role = Role.DON
    room.players[2].role = Role.DOCTOR
    room.players[3].role = Role.DETECTIVE

    mock_bot = AsyncMock()
    await room.start_night(mock_bot)

    # Check that a night event was selected
    assert room.current_event in ["event_clear", "event_fog", "event_blood_moon", "event_blackout"]

    # At start of night, actions not done yet
    assert room.are_all_night_actions_done() is False

    # Submit actions
    room.mafia_votes[1] = 3
    room.doctor_target = 1
    room.detective_target = 2

    # Now all actions should be complete
    assert room.are_all_night_actions_done() is True

def test_three_player_distribution():
    from game.role_models import distribute_roles

    assignments = distribute_roles([10, 20, 30])
    assert len(assignments) == 3
    roles = set(assignments.values())
    assert Role.DON in roles
    assert Role.DETECTIVE in roles
    assert Role.DOCTOR in roles

def test_lobby_leave_and_creator_transfer():
    from game.room import GameRoom

    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host", lang="uz")
    room.add_player(2, "Player2")
    assert len(room.players) == 2

    # Player 2 leaves
    removed = room.remove_player(2)
    assert removed is True
    assert len(room.players) == 1
    assert 2 not in room.players

    # Non-player tries to leave
    assert room.remove_player(99) is False

@pytest.mark.asyncio
async def test_detective_shoot_action():
    import time
    from unittest.mock import AsyncMock, MagicMock
    from game.enums import GamePhase, Role
    from game.room import GameRoom

    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Detective", lang="uz")
    room.add_player(2, "Mafioso")
    room.add_player(3, "Citizen")

    room.players[1].role = Role.DETECTIVE
    room.players[2].role = Role.MAFIA
    room.players[3].role = Role.CITIZEN

    # Detective chooses to shoot player 2
    room.detective_kill_target = 2
    assert room.are_all_night_actions_done() is False
    room.mafia_votes[2] = 3
    assert room.are_all_night_actions_done() is True

    bot = AsyncMock()
    await room.resolve_night(bot)

    # Player 2 should be killed by detective
    assert room.players[2].is_alive is False
    assert room.players[2].awaiting_last_letter is True
    assert room.players[2].last_letter_deadline > time.time()

@pytest.mark.asyncio
async def test_last_letter_window_and_expiration():
    import time
    from game.role_models import Player

    p = Player(user_id=10, name="DeadPlayer")
    p.is_alive = False
    p.awaiting_last_letter = True
    p.last_letter_deadline = time.time() + 30.0

    # Within deadline
    assert time.time() < p.last_letter_deadline
    assert p.awaiting_last_letter is True

    # After deadline expired
    p.last_letter_deadline = time.time() - 1.0
    assert time.time() > p.last_letter_deadline

@pytest.mark.asyncio
async def test_end_game_message_formatting():
    from datetime import datetime, timedelta
    from unittest.mock import AsyncMock
    from game.enums import Role, Team
    from game.room import GameRoom

    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="DonPlayer", lang="uz")
    room.add_player(2, "Citizen1")
    room.add_player(3, "Citizen2")

    room.players[1].role = Role.DON
    room.players[2].role = Role.CITIZEN
    room.players[3].role = Role.CITIZEN

    room.start_time = datetime.utcnow() - timedelta(minutes=2, seconds=15)

    bot = AsyncMock()
    await room.end_game(bot, Team.MAFIA)

    assert bot.send_animation.called or bot.send_message.called
    if bot.send_animation.called:
        kwargs = bot.send_animation.call_args.kwargs
        chat_id = kwargs.get("chat_id")
        text = kwargs.get("caption")
    else:
        sent_args = bot.send_message.call_args[0]
        chat_id, text = sent_args[0], sent_args[1]

    assert chat_id == -1001
    assert "🏆 <b>O'yin tugadi!</b>" in text
    assert "🎉 <b>G'oliblar:</b>" in text
    assert "tg://user?id=1" in text
    assert "DonPlayer" in text
    assert "💀 <b>Qolgan o'yinchilar:</b>" in text
    assert "tg://user?id=2" in text
    assert "2 minut 15 soniya" in text
    assert "Har bir g'olib" in text

@pytest.mark.asyncio
async def test_send_pm_profile_summary():
    from unittest.mock import AsyncMock, MagicMock
    from game.enums import Role
    from game.role_models import Player
    from game.room import GameRoom

    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Winner", lang="uz")
    player = Player(user_id=100, name="WinnerPlayer")
    player.role = Role.DON

    fake_user = MagicMock()
    fake_user.id = 100
    fake_user.language = "uz"
    fake_user.title = "Buyuk Don"
    fake_user.level = 5
    fake_user.exp = 1200
    fake_user.coins = 750
    fake_user.diamonds = 12
    fake_user.wins = 15
    fake_user.losses = 5
    fake_user.games_played = 20

    bot = AsyncMock()
    await room._send_pm_profile_summary(bot, player, fake_user, is_win=True, coins=150, exp=100)

    assert bot.send_message.called
    args = bot.send_message.call_args
    assert args[0][0] == 100  # sent to player PM
    text = args[0][1]
    assert "O'YIN YAKUNI" in text
    assert "Tabriklaymiz, siz g'alaba qozondingiz!" in text
    assert "+150 Tanga" in text
    assert "+100 EXP" in text
    assert "750" in text
    assert "Buyuk Don" in text
    assert "12" in text

@pytest.mark.parametrize("player_count", list(range(3, 21)))
def test_all_player_counts_distribution(player_count: int):
    from game.role_models import distribute_roles
    ids = list(range(1, player_count + 1))
    roles = distribute_roles(ids)
    assert len(roles) == player_count
    for p_id in ids:
        assert p_id in roles
        assert roles[p_id] is not None

@pytest.mark.asyncio
async def test_clan_join_and_clan_war_reward():
    from database.database import async_session_maker, init_db
    from database.crud import (
        get_or_create_user,
        create_clan,
        join_clan,
        get_clan_by_tag,
        get_clan_members,
        add_clan_war_reward
    )

    await init_db()
    async with async_session_maker() as session:
        import uuid
        uid_suffix = uuid.uuid4().hex[:6].upper()
        tag = f"L{uid_suffix[:3]}"
        cname = f"Lords_{uid_suffix}"

        boss = await get_or_create_user(session, 5001, "boss_user", "Boss")
        boss.coins = 1000
        await session.commit()

        # Create Clan
        clan = await create_clan(session, 5001, cname, tag)
        assert clan is not None
        assert clan.tag == tag

        # Lookup by tag
        found = await get_clan_by_tag(session, tag.lower())
        assert found is not None
        assert found.id == clan.id

        # Member 2 joins
        m2 = await get_or_create_user(session, 5002, "m2_user", "Member2")
        m2.clan_id = None
        await session.commit()
        ok, reason, c = await join_clan(session, 5002, tag)
        assert ok is True
        assert c.id == clan.id
        assert m2.clan_id == clan.id

        # Check members list
        members = await get_clan_members(session, clan.id)
        assert len(members) == 2

        # Clan war reward
        prev_rating = clan.rating
        prev_treasury = clan.treasury
        awarded = await add_clan_war_reward(session, clan.id, rating_points=15, treasury_coins=25)
        assert awarded is True
        assert clan.rating == prev_rating + 15
        assert clan.treasury == prev_treasury + 25

@pytest.mark.asyncio
async def test_tournament_standings_and_points_award():
    from database.database import async_session_maker, init_db
    from database.crud import get_or_create_user
    from services.tournament_engine import (
        create_tournament,
        register_participant,
        add_tournament_points,
        get_tournament_standings,
        conclude_tournament
    )

    await init_db()
    async with async_session_maker() as session:
        u1 = await get_or_create_user(session, 6001, "tourn_p1", "Player1")
        u2 = await get_or_create_user(session, 6002, "tourn_p2", "Player2")
        u1.coins = 500
        u2.coins = 500
        await session.commit()

        t = await create_tournament(session, "Grand Cup", entry_fee=50, prize_pool=100)
        assert t is not None

        reg1, _ = await register_participant(session, t.id, 6001)
        reg2, _ = await register_participant(session, t.id, 6002)
        assert reg1 is True
        assert reg2 is True

        # Award tournament points
        await add_tournament_points(session, t.id, 6001, points=6)
        await add_tournament_points(session, t.id, 6002, points=3)

        standings = await get_tournament_standings(session, t.id)
        assert len(standings) == 2
        assert standings[0][0].id == 6001
        assert standings[0][1].points == 6
        assert standings[1][0].id == 6002
        assert standings[1][1].points == 3

        # Conclude tournament
        success, champ, prize = await conclude_tournament(session, t.id)
        assert success is True
        assert champ.id == 6001
        assert champ.title == "🏆 Litsey Chempioni"
        assert champ.diamonds >= 100

@pytest.mark.asyncio
async def test_stop_and_remove_room():
    from unittest.mock import AsyncMock, MagicMock
    from game.manager import GameManager
    from game.enums import GamePhase
    import asyncio

    gm = GameManager()
    room = gm.create_room(chat_id=-9999, creator_id=1001, creator_name="Boss")
    room.add_player(1001, "Boss")
    room.add_player(1002, "Player2")
    
    # Simulate a running timer task
    async def dummy_timer():
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            pass
    room.timer_task = asyncio.create_task(dummy_timer())
    room.last_words_event = asyncio.Event()

    mock_bot = MagicMock()
    mock_bot.unban_chat_member = AsyncMock()
    mock_bot.restrict_chat_member = AsyncMock()

    # Cancel via stop_and_remove_room
    removed = await gm.stop_and_remove_room(-9999, mock_bot)
    assert removed is True
    assert room.is_stopped is True
    assert room.phase == GamePhase.GAME_OVER
    await asyncio.sleep(0)  # Yield to event loop for task cancellation to complete
    assert room.timer_task.cancelled() or room.timer_task.done()
    assert room.last_words_event.is_set()
    assert gm.get_room(-9999) is None

@pytest.mark.asyncio
async def test_can_manage_game_permissions():
    from unittest.mock import AsyncMock, MagicMock
    from handlers.game_group import can_manage_game
    from config import settings

    mock_bot = MagicMock()
    creator_id = 1111
    regular_user = 2222
    chat_admin_user = 3333
    bot_admin_user = 999999
    settings.ADMIN_IDS_RAW = [bot_admin_user]

    # 1. Creator should have permission
    assert await can_manage_game(mock_bot, -1001, creator_id, creator_id) is True

    # 2. Bot superadmin should have permission
    assert await can_manage_game(mock_bot, -1001, bot_admin_user, creator_id) is True

    # 3. Chat admin should have permission
    admin_member = MagicMock()
    admin_member.status = "administrator"
    mock_bot.get_chat_member = AsyncMock(return_value=admin_member)
    assert await can_manage_game(mock_bot, -1001, chat_admin_user, creator_id) is True

    # 4. Regular chat member should NOT have permission
    regular_member = MagicMock()
    regular_member.status = "member"
    mock_bot.get_chat_member = AsyncMock(return_value=regular_member)
    assert await can_manage_game(mock_bot, -1001, regular_user, creator_id) is False

def test_lobby_markup_and_creator_panel():
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host")
    lobby_markup = room.get_lobby_markup()
    # Group lobby only contains join, leave, open bot
    lobby_cbs = [btn.callback_data for row in lobby_markup.inline_keyboard for btn in row if btn.callback_data]
    lobby_urls = [btn.url for row in lobby_markup.inline_keyboard for btn in row if btn.url]
    assert "game_leave" in lobby_cbs
    assert any("start=game_-1001" in url for url in lobby_urls)
    # Management buttons must NOT be in the group lobby!
    assert "game_start_early" not in lobby_cbs
    assert "game_extend_time" not in lobby_cbs
    assert "game_cancel_lobby" not in lobby_cbs

    # Creator panel markup contains the management buttons in PM
    panel_markup = room.get_creator_panel_markup()
    panel_cbs = [btn.callback_data for row in panel_markup.inline_keyboard for btn in row if btn.callback_data]
    assert "creator_start_-1001" in panel_cbs
    assert "creator_extend_-1001" in panel_cbs
    assert "creator_cancel_-1001" in panel_cbs

def test_check_winner_multi_player_with_jester():
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host")
    for i in range(2, 8):
        room.add_player(i, f"P{i}")

    # 7 players: 2 Mafia, 2 Town, 1 Jester alive (Maniac and 1 Town dead)
    room.players[1].role = Role.DON
    room.players[2].role = Role.MAFIA
    room.players[3].role = Role.CITIZEN
    room.players[4].role = Role.DOCTOR
    room.players[5].role = Role.JESTER
    room.players[6].role = Role.MANIAC
    room.players[6].is_alive = False
    room.players[7].role = Role.CITIZEN
    room.players[7].is_alive = False

    # 2 Mafia vs 3 living non-mafia (2 Town + 1 Jester)
    # Mafia should NOT win yet!
    winner = room.check_winner()
    assert winner is None

    # If another Town dies, now 2 Mafia vs 2 non-mafia (1 Town + 1 Jester) -> Parity -> Mafia wins
    room.players[4].is_alive = False
    winner = room.check_winner()
    assert winner == Team.MAFIA

def test_are_all_night_actions_done_multiple_mafia():
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host")
    for i in range(2, 7):
        room.add_player(i, f"P{i}")

    # 6 players: Don (1), Mafia (2), Detective (3), Doctor (4), Citizen (5, 6)
    room.players[1].role = Role.DON
    room.players[2].role = Role.MAFIA
    room.players[3].role = Role.DETECTIVE
    room.players[4].role = Role.DOCTOR
    room.players[5].role = Role.CITIZEN
    room.players[6].role = Role.CITIZEN

    # Doctor and Detective make actions
    room.doctor_target = 5
    room.detective_target = 2

    # Only DON votes, Mafia hasn't voted yet
    room.mafia_votes[1] = 5
    assert room.are_all_night_actions_done() is False

    # Now MAFIA also votes -> All living mafiosi have voted
    room.mafia_votes[2] = 5
    assert room.are_all_night_actions_done() is True

@pytest.mark.asyncio
async def test_start_game_no_early_will_button():
    from unittest.mock import AsyncMock, MagicMock
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Host")
    for i in range(2, 6):
        room.add_player(i, f"P{i}")

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.set_chat_permissions = AsyncMock()
    mock_bot.edit_message_text = AsyncMock()

    await room.start_game(mock_bot)

    # Inspect all PM calls to players to verify reply_markup has no btn_set_will
    for call in mock_bot.send_message.call_args_list:
        reply_markup = call.kwargs.get("reply_markup")
        if reply_markup:
            for row in reply_markup.inline_keyboard:
                for btn in row:
                    if btn.callback_data:
                        assert not btn.callback_data.startswith("set_will_")

@pytest.mark.asyncio
async def test_send_game_animation_success_and_fallback():
    from unittest.mock import AsyncMock, MagicMock
    from services.media_service import send_game_animation

    mock_bot = MagicMock()
    mock_bot.send_animation = AsyncMock()
    mock_bot.send_message = AsyncMock()

    # 1. Success case
    await send_game_animation(mock_bot, -1001, "game_start", "Test caption")
    assert mock_bot.send_animation.called
    assert not mock_bot.send_message.called

    # 2. Fallback case when send_animation raises exception
    mock_bot.send_animation.reset_mock()
    mock_bot.send_message.reset_mock()
    mock_bot.send_animation.side_effect = Exception("Telegram API error")

    await send_game_animation(mock_bot, -1001, "game_start", "Fallback caption")
    assert mock_bot.send_animation.called
    assert mock_bot.send_message.called
    assert mock_bot.send_message.call_args.kwargs.get("text") == "Fallback caption"

@pytest.mark.asyncio
async def test_cast_day_vote_skip_and_resolve():
    from unittest.mock import AsyncMock, MagicMock
    room = GameRoom(chat_id=-1001, creator_id=1, creator_name="Player1")
    room.add_player(2, "Player2")
    room.add_player(3, "Player3")
    room.phase = GamePhase.VOTING

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    # Player 1 votes for Player 2
    await room.cast_day_vote(1, 2, mock_bot)
    assert room.day_votes[1] == 2

    # Player 2 & 3 vote to SKIP (0)
    await room.cast_day_vote(2, 0, mock_bot)
    assert room.day_votes[2] == 0
    await room.cast_day_vote(3, 0, mock_bot)
    assert room.day_votes[3] == 0

    # Resolve voting: Skip has 2 votes, Player 2 has 1 vote -> Skip wins
    await room.resolve_voting(mock_bot)
    # Check that vote_skipped_result was sent, nobody lynched (condemned_player_id is None)
    assert room.condemned_player_id is None
    all_msgs = [
        call.args[1] if len(call.args) > 1 else call.kwargs.get("text", "")
        for call in mock_bot.send_message.call_args_list
    ]
    assert any("hech kimni osmaslikka" in m.lower() or "hech kim jazolanmadi" in m.lower() for m in all_msgs)

@pytest.mark.asyncio
async def test_cleanup_group_messages_during_night():
    from unittest.mock import AsyncMock, MagicMock
    from handlers.game_group import cleanup_group_messages
    from game.manager import game_manager

    room = game_manager.create_room(chat_id=-2001, creator_id=1, creator_name="Host")
    room.phase = GamePhase.NIGHT

    # 1. Normal user text sent during night -> MUST be deleted
    mock_msg = MagicMock()
    mock_msg.chat.id = -2001
    mock_msg.chat.type = "supergroup"
    mock_msg.from_user.id = 999
    mock_msg.from_user.is_bot = False
    mock_msg.text = "Hello everyone, who is mafia?"
    mock_msg.delete = AsyncMock()

    await cleanup_group_messages(mock_msg)
    assert mock_msg.delete.called

    # 2. Admin /stop command during night -> MUST NOT be deleted
    mock_stop_msg = MagicMock()
    mock_stop_msg.chat.id = -2001
    mock_stop_msg.chat.type = "supergroup"
    mock_stop_msg.from_user.id = 1
    mock_stop_msg.from_user.is_bot = False
    mock_stop_msg.text = "/stop"
    mock_stop_msg.delete = AsyncMock()

    await cleanup_group_messages(mock_stop_msg)
    assert not mock_stop_msg.delete.called


