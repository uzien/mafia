from enum import Enum

class GamePhase(str, Enum):
    LOBBY = "lobby"
    STARTING = "starting"
    NIGHT = "night"
    MORNING = "morning"
    DAY = "day"
    VOTING = "voting"
    GAME_OVER = "game_over"

class Role(str, Enum):
    CITIZEN = "citizen"
    DOCTOR = "doctor"
    DETECTIVE = "detective"
    MAFIA = "mafia"
    DON = "don"
    MANIAC = "maniac"
    MISTRESS = "mistress"
    BODYGUARD = "bodyguard"
    KAMIKAZE = "kamikaze"
    LAWYER = "lawyer"

class Team(str, Enum):
    TOWN = "town"
    MAFIA = "mafia"
    NEUTRAL = "neutral"
