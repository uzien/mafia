from typing import Dict, Optional
from game.enums import GamePhase
from game.room import GameRoom

class GameManager:
    def __init__(self):
        self.rooms: Dict[int, GameRoom] = {}

    def get_room(self, chat_id: int) -> Optional[GameRoom]:
        return self.rooms.get(chat_id)

    def create_room(self, chat_id: int, creator_id: int, creator_name: str, lang: str = "az") -> Optional[GameRoom]:
        existing = self.get_room(chat_id)
        if existing and existing.phase != GamePhase.GAME_OVER:
            return None
        room = GameRoom(chat_id=chat_id, creator_id=creator_id, creator_name=creator_name, lang=lang)
        self.rooms[chat_id] = room
        return room

    def remove_room(self, chat_id: int):
        if chat_id in self.rooms:
            room = self.rooms[chat_id]
            if room.timer_task and not room.timer_task.done():
                room.timer_task.cancel()
            del self.rooms[chat_id]

    def find_user_room(self, user_id: int) -> Optional[GameRoom]:
        for room in self.rooms.values():
            if user_id in room.players and room.phase != GamePhase.GAME_OVER:
                return room
        return None

game_manager = GameManager()
