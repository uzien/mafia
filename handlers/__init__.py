from .clans import clan_router
from .common import common_router
from .game_group import game_group_router
from .game_private import game_private_router
from .store import store_router
from .tournaments import tournament_router

__all__ = [
    "common_router",
    "game_group_router",
    "game_private_router",
    "store_router",
    "clan_router",
    "tournament_router"
]
