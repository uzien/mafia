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
    SERGEANT = "sergeant"
    SNIPER = "sniper"
    BODYGUARD = "bodyguard"
    KAMIKAZE = "kamikaze"
    
    MAFIA = "mafia"
    DON = "don"
    LAWYER = "lawyer"
    
    MANIAC = "maniac"
    MISTRESS = "mistress"
    JESTER = "jester"

class Team(str, Enum):
    TOWN = "town"
    MAFIA = "mafia"
    NEUTRAL = "neutral"
    JESTER = "jester"
