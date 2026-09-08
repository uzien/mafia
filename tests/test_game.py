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
    assert "Tinch axoli - 2" in living_text
    assert "Komissar katani" in living_text
    assert "Don" in living_text
    assert "Jami:" in living_text

