import random
from typing import Dict, List, Optional
from game.enums import Role, Team

ROLE_TEAMS: Dict[Role, Team] = {
    Role.CITIZEN: Team.TOWN,
    Role.DOCTOR: Team.TOWN,
    Role.DETECTIVE: Team.TOWN,
    Role.SERGEANT: Team.TOWN,
    Role.SNIPER: Team.TOWN,
    Role.BODYGUARD: Team.TOWN,
    Role.KAMIKAZE: Team.TOWN,
    
    Role.DON: Team.MAFIA,
    Role.MAFIA: Team.MAFIA,
    Role.LAWYER: Team.MAFIA,
    
    Role.MANIAC: Team.NEUTRAL,
    Role.MISTRESS: Team.NEUTRAL,
    Role.JESTER: Team.JESTER
}

class Player:
    def __init__(self, user_id: int, name: str, username: str = None):
        self.user_id: int = user_id
        self.name: str = name
        self.username: str = username
        self.role: Role = Role.CITIZEN
        self.is_alive: bool = True
        self.is_blocked: bool = False  # By mistress
        self.protected_by_doctor: bool = False
        self.protected_by_bodyguard: bool = False
        self.protected_by_lawyer: bool = False
        self.last_healed: bool = False  # Track doctor self-heal limit
        self.sniper_ammo: int = 1
        self.missed_votes: int = 0      # AFK detection
        self.guilt_suicide: bool = False
        self.has_fake_docs: bool = False
        self.last_will: Optional[str] = None
        self.awaiting_last_letter: bool = False
        self.last_letter_deadline: float = 0.0

    @property
    def team(self) -> Team:
        return ROLE_TEAMS.get(self.role, Team.TOWN)

def distribute_roles(player_ids: List[int], role_boosts: Dict[int, Role] = None) -> Dict[int, Role]:
    """
    Distribute balanced roles based on the total number of players.
    Applies any role cards used by players if eligible.
    """
    count = len(player_ids)
    role_pool: List[Role] = []

    if count <= 2:
        role_pool = [Role.DON, Role.DETECTIVE][:count]
    elif count == 3:
        role_pool = [Role.DON, Role.DETECTIVE, Role.DOCTOR]
    elif count == 4:
        role_pool = [Role.DON, Role.DETECTIVE, Role.DOCTOR, Role.CITIZEN]
    elif count == 5:
        role_pool = [Role.DON, Role.DETECTIVE, Role.DOCTOR, Role.CITIZEN, Role.CITIZEN]
    elif count == 6:
        role_pool = [Role.DON, Role.MAFIA, Role.DETECTIVE, Role.DOCTOR, Role.CITIZEN, Role.CITIZEN]
    elif count == 7:
        role_pool = [Role.DON, Role.MAFIA, Role.DETECTIVE, Role.DOCTOR, Role.MANIAC, Role.JESTER, Role.CITIZEN]
    elif count == 8:
        role_pool = [Role.DON, Role.MAFIA, Role.DETECTIVE, Role.DOCTOR, Role.MANIAC, Role.MISTRESS, Role.JESTER, Role.CITIZEN]
    elif count <= 10:
        role_pool = [Role.DON, Role.MAFIA, Role.MAFIA, Role.DETECTIVE, Role.DOCTOR, Role.SERGEANT, Role.MANIAC, Role.MISTRESS, Role.JESTER, Role.BODYGUARD][:count]
        while len(role_pool) < count:
            role_pool.append(Role.CITIZEN)
    elif count == 11:
        role_pool = [Role.DON, Role.MAFIA, Role.MAFIA, Role.DETECTIVE, Role.SERGEANT, Role.SNIPER, Role.DOCTOR, Role.MANIAC, Role.MISTRESS, Role.BODYGUARD, Role.JESTER][:count]
    else:  # 12+
        role_pool = [Role.DON, Role.MAFIA, Role.MAFIA, Role.LAWYER, Role.DETECTIVE, Role.SERGEANT, Role.SNIPER, Role.DOCTOR, Role.MANIAC, Role.MISTRESS, Role.BODYGUARD, Role.KAMIKAZE, Role.JESTER][:count]
        while len(role_pool) < count:
            role_pool.append(Role.CITIZEN)

    shuffled_players = list(player_ids)
    random.shuffle(shuffled_players)
    random.shuffle(role_pool)

    # Process role card boosts if any
    assignments: Dict[int, Role] = {}
    if role_boosts:
        for p_id in list(shuffled_players):
            desired_role = role_boosts.get(p_id)
            if desired_role in role_pool and random.random() < 0.65:  # 65% success chance
                assignments[p_id] = desired_role
                role_pool.remove(desired_role)
                shuffled_players.remove(p_id)

    # Distribute remaining
    for p_id, role in zip(shuffled_players, role_pool):
        assignments[p_id] = role

    # Fallback to ensure no player has None role
    for p_id in player_ids:
        if p_id not in assignments:
            assignments[p_id] = Role.CITIZEN

    return assignments
