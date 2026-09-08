import asyncio
import logging
from typing import Dict, List, Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import settings
from database.crud import add_game_stats
from database.database import async_session_maker
from game.enums import GamePhase, Role, Team
from game.role_models import Player, distribute_roles
from locales.i18n import i18n
from services.auto_moderator import (
    mute_chat_night,
    mute_dead_player,
    restore_players,
    unmute_chat_day,
)

logger = logging.getLogger(__name__)

class GameRoom:
    def __init__(self, chat_id: int, creator_id: int, creator_name: str, lang: str = "uz"):
        self.chat_id: int = chat_id
        self.creator_id: int = creator_id
        self.creator_name: str = creator_name
        self.lang: str = lang
        self.phase: GamePhase = GamePhase.LOBBY
        self.round: int = 1
        self.lobby_message_id: Optional[int] = None
        
        self.players: Dict[int, Player] = {}
        self.timer_task: Optional[asyncio.Task] = None
        self.seconds_left: int = settings.LOBBY_TIMEOUT
        
        # Night actions
        self.mafia_votes: Dict[int, int] = {}       # mafioso_id -> target_id
        self.doctor_target: Optional[int] = None
        self.detective_target: Optional[int] = None
        self.maniac_target: Optional[int] = None
        self.mistress_target: Optional[int] = None
        self.bodyguard_target: Optional[int] = None
        self.lawyer_target: Optional[int] = None
        self.sniper_target: Optional[int] = None
        self.jester_won: bool = False
        
        # Day trial votes
        self.day_votes: Dict[int, int] = {}         # voter_id -> target_id
        self.night_announced_roles: set = set()
        self.condemned_player_id: Optional[int] = None
        self.last_words_event: Optional[asyncio.Event] = None
        
        # Add creator automatically
        self.add_player(creator_id, creator_name)

    def add_player(self, user_id: int, name: str, username: str = None) -> bool:
        if user_id in self.players or len(self.players) >= settings.MAX_PLAYERS:
            return False
        self.players[user_id] = Player(user_id=user_id, name=name, username=username)
        return True

    def remove_player(self, user_id: int) -> bool:
        if user_id in self.players:
            del self.players[user_id]
            return True
        return False

    @property
    def alive_players(self) -> List[Player]:
        return [p for p in self.players.values() if p.is_alive]

    def get_lobby_markup(self) -> InlineKeyboardMarkup:
        buttons = [
            [
                InlineKeyboardButton(
                    text=i18n.get("btn_join", self.lang),
                    url=f"https://t.me/{settings.BOT_USERNAME}?start=game_{self.chat_id}"
                )
            ]
        ]
        action_row = []
        if len(self.players) >= settings.MIN_PLAYERS:
            action_row.append(
                InlineKeyboardButton(text=i18n.get("btn_start_now", self.lang), callback_data="game_start_early")
            )
        action_row.append(
            InlineKeyboardButton(text=i18n.get("btn_extend_time", self.lang), callback_data="game_extend_time")
        )
        action_row.append(
            InlineKeyboardButton(text=i18n.get("btn_leave", self.lang), callback_data="game_leave")
        )
        buttons.append(action_row)
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def extend_lobby_time(self, seconds: int = 30) -> int:
        """Extend lobby countdown, capped at 300 seconds (5 minutes)."""
        self.seconds_left = min(self.seconds_left + seconds, 300)
        return self.seconds_left

    def get_lobby_text(self) -> str:
        players_links = ", ".join([f'<a href="tg://user?id={p.user_id}">{p.name}</a>' for p in self.players.values()])
        return i18n.get(
            "lobby_created",
            self.lang,
            players_list=players_links if players_links else "...",
            count=len(self.players),
            creator=self.creator_name,
            max=settings.MAX_PLAYERS,
            seconds=self.seconds_left
        )

    def get_living_players_text(self) -> str:
        living = self.alive_players
        lines = [f"{idx+1}. <a href=\"tg://user?id={p.user_id}\">{p.name}</a>" for idx, p in enumerate(living)]
        players_block = "\n".join(lines) if lines else "..."

        role_counts: Dict[str, int] = {}
        for p in living:
            r_name = i18n.get(f"roles.{p.role.value}", self.lang)
            role_counts[r_name] = role_counts.get(r_name, 0) + 1

        breakdown_parts = []
        # Sort so Citizen (Fuqaro) comes first, then sorted by count descending
        sorted_roles = sorted(
            role_counts.items(),
            key=lambda x: (
                0 if any(k in x[0].lower() for k in ["fuqaro", "tinch", "vətəndaş", "мирн", "citiz", "sakin", "köylü"]) else 1,
                -x[1],
                x[0]
            )
        )
        for r_name, count in sorted_roles:
            if count > 1:
                breakdown_parts.append(f"{r_name} - {count}")
            else:
                breakdown_parts.append(f"{r_name}")

        breakdown_str = ", ".join(breakdown_parts) if breakdown_parts else "..."
        title = i18n.get("living_players_title", self.lang)
        from_them = i18n.get("living_roles_label", self.lang)
        total = i18n.get("living_total_label", self.lang, count=len(living))

        return f"{title}\n{players_block}\n\n{from_them}  {breakdown_str}\n{total}"

    async def announce_night_action(self, bot: Bot, role_str: str):
        if role_str in self.night_announced_roles:
            return
        self.night_announced_roles.add(role_str)
        text = i18n.get(f"night_action_{role_str}", self.lang)
        if text and not text.startswith("["):
            try:
                await bot.send_message(self.chat_id, text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Could not send night action announcement: {e}")

    async def start_countdown(self, bot: Bot):
        """Lobby countdown before auto-starting."""
        while self.seconds_left > 0:
            await asyncio.sleep(5)
            self.seconds_left -= 5
            if self.lobby_message_id:
                try:
                    await bot.edit_message_text(
                        chat_id=self.chat_id,
                        message_id=self.lobby_message_id,
                        text=self.get_lobby_text(),
                        reply_markup=self.get_lobby_markup(),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        if len(self.players) >= settings.MIN_PLAYERS:
            await self.start_game(bot)
        else:
            await bot.send_message(self.chat_id, i18n.get("game_cancelled", self.lang), parse_mode="HTML")
            self.phase = GamePhase.GAME_OVER

    async def start_game(self, bot: Bot):
        """Distribute roles and begin night 1."""
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()

        self.phase = GamePhase.STARTING

        # Assign roles
        role_assignments = distribute_roles(list(self.players.keys()))
        for p_id, role in role_assignments.items():
            self.players[p_id].role = role
            # Send private message with role info
            try:
                desc = i18n.get(f"role_desc.{role.value}", self.lang)
                role_title = i18n.get(f"roles.{role.value}", self.lang)
                await bot.send_message(
                    p_id,
                    i18n.get("pm_role_assigned", self.lang, role=role_title, description=desc),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not send PM to player {p_id}: {e}")

        # Check if any player has fake documents in DB
        try:
            from services.economy_service import has_fake_documents
            async with async_session_maker() as session:
                for p_id in self.players.keys():
                    if await has_fake_documents(session, p_id):
                        self.players[p_id].has_fake_docs = True
        except Exception as e:
            logger.warning(f"Error checking fake documents: {e}")

        # Send group message: O'yin boshlandi! with "Sizning rolingiz" button
        role_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.get("btn_check_role", self.lang), callback_data=f"check_role_{self.chat_id}")]
        ])
        await bot.send_message(
            self.chat_id,
            i18n.get("game_starting", self.lang),
            reply_markup=role_markup,
            parse_mode="HTML"
        )

        await asyncio.sleep(3)
        await self.start_night(bot)

    async def broadcast_mafia_chat(self, bot: Bot, sender_id: int, sender_name: str, text: str) -> bool:
        """Relay secret message to other living mafia members during night."""
        if self.phase != GamePhase.NIGHT:
            return False
        sender = self.players.get(sender_id)
        if not sender or not sender.is_alive or sender.role not in [Role.DON, Role.MAFIA]:
            return False

        role_title = i18n.get(f"roles.{sender.role.value}", self.lang)
        msg = f"🩸 <b>[Mafiya Maxfiy Chati]</b> <b>{sender_name}</b> ({role_title}):\n<i>\"{text}\"</i>"

        mafia_teammates = [
            p for p in self.alive_players
            if p.role in [Role.DON, Role.MAFIA] and p.user_id != sender_id
        ]
        for mate in mafia_teammates:
            try:
                await bot.send_message(mate.user_id, msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Could not send mafia chat message to {mate.user_id}: {e}")
        return True

    async def start_night(self, bot: Bot):
        """Trigger the night phase and collect secret actions via PM."""
        self.phase = GamePhase.NIGHT
        self.night_announced_roles.clear()
        self.mafia_votes.clear()
        self.doctor_target = None
        self.detective_target = None
        self.maniac_target = None
        self.mistress_target = None
        self.bodyguard_target = None
        self.lawyer_target = None
        self.sniper_target = None

        # Reset temporary buffs
        for p in self.alive_players:
            p.is_blocked = False
            p.protected_by_doctor = False
            p.protected_by_bodyguard = False
            p.protected_by_lawyer = False

        # Mute group chat
        await mute_chat_night(bot, self.chat_id)

        # Message 1: Night banner with 'Bot-ga o'tish' button
        night_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.get("btn_open_bot", self.lang), url=f"https://t.me/{settings.BOT_USERNAME}")]
        ])
        await bot.send_message(
            self.chat_id,
            i18n.get("night_started", self.lang, round=self.round),
            reply_markup=night_markup,
            parse_mode="HTML"
        )

        # Message 2: Living players list
        await bot.send_message(
            self.chat_id,
            self.get_living_players_text(),
            parse_mode="HTML"
        )

        # Prompt each night-active role in PM
        await self._send_night_prompts(bot)

        # Wait for night duration
        self.timer_task = asyncio.create_task(self._night_timer(bot))

    async def _send_night_prompts(self, bot: Bot):
        living = self.alive_players
        for p in living:
            target_buttons = [
                [InlineKeyboardButton(text=f"🎯 {target.name}", callback_data=f"act_{self.chat_id}_{p.role.value}_{target.user_id}")]
                for target in living
                if target.user_id != p.user_id or (p.role == Role.DOCTOR and not p.last_healed)
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=target_buttons)

            if p.role in [Role.DON, Role.MAFIA]:
                try:
                    await bot.send_message(
                        p.user_id,
                        i18n.get("night_prompt_mafia", self.lang),
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            elif p.role == Role.DOCTOR:
                try:
                    await bot.send_message(
                        p.user_id,
                        i18n.get("night_prompt_doctor", self.lang),
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            elif p.role == Role.DETECTIVE:
                try:
                    await bot.send_message(
                        p.user_id,
                        i18n.get("night_prompt_detective", self.lang),
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            elif p.role == Role.MANIAC:
                try:
                    await bot.send_message(
                        p.user_id,
                        i18n.get("night_prompt_maniac", self.lang),
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            elif p.role == Role.MISTRESS:
                try:
                    await bot.send_message(
                        p.user_id,
                        i18n.get("night_prompt_mistress", self.lang),
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            elif p.role == Role.SNIPER and p.sniper_ammo > 0:
                try:
                    await bot.send_message(
                        p.user_id,
                        i18n.get("night_prompt_sniper", self.lang),
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

    async def _night_timer(self, bot: Bot):
        await asyncio.sleep(settings.NIGHT_DURATION)
        await self.resolve_night(bot)

    async def resolve_night(self, bot: Bot):
        """Calculate the outcome of all night actions."""
        self.phase = GamePhase.MORNING

        # 1. Process Mistress block
        if self.mistress_target and self.mistress_target in self.players:
            blocked_player = self.players[self.mistress_target]
            blocked_player.is_blocked = True

        # 2. Process Doctor heal
        healed_id = None
        if self.doctor_target and self.doctor_target in self.players:
            doc_player = next((p for p in self.players.values() if p.role == Role.DOCTOR), None)
            if doc_player and not doc_player.is_blocked:
                healed_id = self.doctor_target
                self.players[healed_id].protected_by_doctor = True

        # 3. Determine Mafia kill target
        mafia_kill_id = None
        if self.mafia_votes:
            # Count target with most mafia votes
            vote_counts: Dict[int, int] = {}
            for target in self.mafia_votes.values():
                vote_counts[target] = vote_counts.get(target, 0) + 1
            mafia_kill_id = max(vote_counts, key=vote_counts.get)

        # 4. Determine Maniac kill target
        maniac_kill_id = None
        maniac_player = next((p for p in self.players.values() if p.role == Role.MANIAC), None)
        if maniac_player and not maniac_player.is_blocked and self.maniac_target:
            maniac_kill_id = self.maniac_target

        # 5. Determine Sniper kill target
        sniper_kill_id = None
        sniper_player = next((p for p in self.players.values() if p.role == Role.SNIPER), None)
        if sniper_player and not sniper_player.is_blocked and self.sniper_target and sniper_player.sniper_ammo > 0:
            sniper_kill_id = self.sniper_target
            sniper_player.sniper_ammo -= 1
            # If shot innocent town member, dies of guilt next morning
            target_p = self.players.get(sniper_kill_id)
            if target_p and target_p.team == Team.TOWN:
                sniper_player.guilt_suicide = True

        # 6. Resolve casualties
        deaths: List[Player] = []
        doctor_saved = False

        targets_to_kill = set()
        if mafia_kill_id:
            targets_to_kill.add(mafia_kill_id)
        if maniac_kill_id:
            targets_to_kill.add(maniac_kill_id)
        if sniper_kill_id:
            targets_to_kill.add(sniper_kill_id)

        for t_id in targets_to_kill:
            if t_id in self.players:
                victim = self.players[t_id]
                if victim.protected_by_doctor:
                    doctor_saved = True
                else:
                    victim.is_alive = False
                    deaths.append(victim)
                    await mute_dead_player(bot, self.chat_id, victim.user_id)

        # Check if detective died, promote sergeant!
        det_died = any(d.role == Role.DETECTIVE for d in deaths)
        sergeant_promoted = None
        if det_died:
            sergeant = next((p for p in self.alive_players if p.role == Role.SERGEANT), None)
            if sergeant:
                sergeant.role = Role.DETECTIVE
                sergeant_promoted = sergeant

        # Check if Don died, promote living Mafia to Don!
        don_died = any(d.role == Role.DON for d in deaths)
        don_promoted = None
        if don_died:
            successor = next((p for p in self.alive_players if p.role == Role.MAFIA), None)
            if not successor:
                successor = next((p for p in self.alive_players if p.role == Role.LAWYER), None)
            if successor:
                old_role_title = i18n.get(f"roles.{successor.role.value}", self.lang)
                successor.role = Role.DON
                don_promoted = (successor, old_role_title)

        # Check guilt suicide
        for p in list(self.alive_players):
            if p.guilt_suicide:
                p.is_alive = False
                p.guilt_suicide = False
                deaths.append(p)
                await mute_dead_player(bot, self.chat_id, p.user_id)

        # Unmute group chat for morning
        await unmute_chat_day(bot, self.chat_id)

        # 1. Morning greeting
        await bot.send_message(
            self.chat_id,
            i18n.get("morning_report_title", self.lang, round=self.round),
            parse_mode="HTML"
        )

        # 2. Intermediate events (Doctor shield used or deaths)
        if doctor_saved:
            await bot.send_message(
                self.chat_id,
                i18n.get("morning_doctor_saved", self.lang),
                parse_mode="HTML"
            )

        if deaths:
            for d in deaths:
                role_title = i18n.get(f"roles.{d.role.value}", self.lang)
                await bot.send_message(
                    self.chat_id,
                    i18n.get("morning_killed", self.lang, victim=d.name, role=role_title),
                    parse_mode="HTML"
                )
        elif not doctor_saved:
            await bot.send_message(
                self.chat_id,
                i18n.get("morning_nobody_died", self.lang),
                parse_mode="HTML"
            )

        if sergeant_promoted:
            role_sergeant = i18n.get("roles.sergeant", self.lang)
            role_detective = i18n.get("roles.detective", self.lang)
            await bot.send_message(
                self.chat_id,
                f"🎖 <b>{role_sergeant} {sergeant_promoted.name}</b> {role_detective} lavozimiga ko'tarildi!",
                parse_mode="HTML"
            )

        if don_promoted:
            promoted_player, old_role_title = don_promoted
            await bot.send_message(
                self.chat_id,
                i18n.get("don_promoted", self.lang, old_role=old_role_title, name=promoted_player.name),
                parse_mode="HTML"
            )

        # 3. Living players status list
        await bot.send_message(
            self.chat_id,
            self.get_living_players_text(),
            parse_mode="HTML"
        )

        # Check for victory
        winner = self.check_winner()
        if winner:
            await self.end_game(bot, winner)
            return

        # Advance to daytime discussion
        await self.start_day(bot)

    async def start_day(self, bot: Bot):
        self.phase = GamePhase.DAY
        await bot.send_message(
            self.chat_id,
            i18n.get("day_discussion", self.lang, seconds=settings.DAY_DURATION),
            parse_mode="HTML"
        )
        await asyncio.sleep(settings.DAY_DURATION)
        await self.start_voting(bot)

    async def start_voting(self, bot: Bot):
        self.phase = GamePhase.VOTING
        self.day_votes.clear()

        living = self.alive_players
        voting_buttons = [
            [InlineKeyboardButton(text=f"🗳 {p.name}", callback_data=f"vote_{self.chat_id}_{p.user_id}")]
            for p in living
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=voting_buttons)

        await bot.send_message(
            self.chat_id,
            i18n.get("voting_started", self.lang, seconds=settings.VOTING_DURATION),
            reply_markup=markup,
            parse_mode="HTML"
        )

        self.timer_task = asyncio.create_task(self._voting_timer(bot))

    async def _voting_timer(self, bot: Bot):
        await asyncio.sleep(settings.VOTING_DURATION)
        await self.resolve_voting(bot)

    async def cast_day_vote(self, voter_id: int, target_id: int, bot: Bot) -> bool:
        if self.phase != GamePhase.VOTING or voter_id not in self.players or not self.players[voter_id].is_alive:
            return False
        if target_id not in self.players or not self.players[target_id].is_alive:
            return False

        self.day_votes[voter_id] = target_id
        voter = self.players[voter_id]
        target = self.players[target_id]

        await bot.send_message(
            self.chat_id,
            i18n.get("vote_cast", self.lang, voter=voter.name, target=target.name),
            parse_mode="HTML"
        )

        # If everyone voted, finish voting early
        if len(self.day_votes) >= len(self.alive_players):
            if self.timer_task and not self.timer_task.done():
                self.timer_task.cancel()
            await self.resolve_voting(bot)
        return True

    async def resolve_voting(self, bot: Bot):
        if not self.day_votes:
            await bot.send_message(self.chat_id, i18n.get("vote_tie", self.lang), parse_mode="HTML")
        else:
            vote_counts: Dict[int, int] = {}
            for t_id in self.day_votes.values():
                vote_counts[t_id] = vote_counts.get(t_id, 0) + 1

            max_votes = max(vote_counts.values())
            suspects = [t_id for t_id, cnt in vote_counts.items() if cnt == max_votes]

            if len(suspects) > 1:
                await bot.send_message(self.chat_id, i18n.get("vote_tie", self.lang), parse_mode="HTML")
                await self._finish_voting_phase(bot)
            else:
                lynched_id = suspects[0]
                await self.start_last_words(bot, lynched_id)

    async def start_last_words(self, bot: Bot, lynched_id: int):
        """Allow the condemned suspect a final defense speech before hanging."""
        self.phase = GamePhase.LAST_WORDS
        self.condemned_player_id = lynched_id
        self.last_words_event = asyncio.Event()
        lynched = self.players.get(lynched_id)
        if not lynched:
            return await self._finish_voting_phase(bot)

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=i18n.get("btn_skip_last_words", self.lang),
                callback_data=f"skip_last_words_{self.chat_id}_{lynched_id}"
            )]
        ])
        await bot.send_message(
            self.chat_id,
            i18n.get("last_words_prompt", self.lang, name=lynched.name, user_id=lynched.user_id, seconds=settings.DEFENSE_DURATION),
            reply_markup=markup,
            parse_mode="HTML"
        )

        try:
            await asyncio.wait_for(self.last_words_event.wait(), timeout=settings.DEFENSE_DURATION)
        except asyncio.TimeoutError:
            pass

        await self.execute_lynch(bot, lynched_id)

    async def execute_lynch(self, bot: Bot, lynched_id: int):
        """Execute the condemned player and process death effects."""
        lynched = self.players.get(lynched_id)
        if not lynched or not lynched.is_alive:
            return await self._finish_voting_phase(bot)

        lynched.is_alive = False
        await mute_dead_player(bot, self.chat_id, lynched.user_id)
        role_title = i18n.get(f"roles.{lynched.role.value}", self.lang)

        await bot.send_message(
            self.chat_id,
            i18n.get("player_lynched", self.lang, name=lynched.name, user_id=lynched.user_id, role=role_title),
            parse_mode="HTML"
        )

        # Jester win check
        if lynched.role == Role.JESTER:
            self.jester_won = True
            await bot.send_message(
                self.chat_id,
                i18n.get("jester_lynched", self.lang, name=lynched.name),
                parse_mode="HTML"
            )

        # Kamikaze ability
        if lynched.role == Role.KAMIKAZE:
            voters_for_lynch = [v_id for v_id, target in self.day_votes.items() if target == lynched_id and self.players[v_id].is_alive]
            if voters_for_lynch:
                collateral = self.players[voters_for_lynch[0]]
                collateral.is_alive = False
                await mute_dead_player(bot, self.chat_id, collateral.user_id)
                c_role = i18n.get(f"roles.{collateral.role.value}", self.lang)
                await bot.send_message(
                    self.chat_id,
                    f"💣 <b>Kamikadze portladi!</b> {collateral.name} ({c_role}) ham halok bo'ldi!",
                    parse_mode="HTML"
                )

        # Check if Detective died in court, promote Sergeant!
        det_died = not any(p.role == Role.DETECTIVE and p.is_alive for p in self.players.values())
        if det_died:
            sergeant = next((p for p in self.alive_players if p.role == Role.SERGEANT), None)
            if sergeant:
                sergeant.role = Role.DETECTIVE
                role_sergeant = i18n.get("roles.sergeant", self.lang)
                role_detective = i18n.get("roles.detective", self.lang)
                await bot.send_message(
                    self.chat_id,
                    f"🎖 <b>{role_sergeant} {sergeant.name}</b> {role_detective} lavozimiga ko'tarildi!",
                    parse_mode="HTML"
                )

        # Check if Don died in court, promote living Mafia to Don!
        don_died = not any(p.role == Role.DON and p.is_alive for p in self.players.values())
        if don_died:
            successor = next((p for p in self.alive_players if p.role == Role.MAFIA), None)
            if not successor:
                successor = next((p for p in self.alive_players if p.role == Role.LAWYER), None)
            if successor:
                old_role_title = i18n.get(f"roles.{successor.role.value}", self.lang)
                successor.role = Role.DON
                await bot.send_message(
                    self.chat_id,
                    i18n.get("don_promoted", self.lang, old_role=old_role_title, name=successor.name),
                    parse_mode="HTML"
                )

        await self._finish_voting_phase(bot)

    async def _finish_voting_phase(self, bot: Bot):
        # AFK / Inactivity check for alive players who missed voting
        for p in list(self.alive_players):
            if p.user_id not in self.day_votes:
                p.missed_votes += 1
                if p.missed_votes >= 2:
                    p.is_alive = False
                    await mute_dead_player(bot, self.chat_id, p.user_id)
                    await bot.send_message(
                        self.chat_id,
                        f"💤 <b>{p.name}</b> 2 marta ketma-ket ovoz bermagani sababli AFK deb topilib, o'yindan chetlatildi!",
                        parse_mode="HTML"
                    )
            else:
                p.missed_votes = 0

        # Check win condition
        winner = self.check_winner()
        if winner:
            await self.end_game(bot, winner)
            return

        self.round += 1
        await asyncio.sleep(3)
        await self.start_night(bot)

    def check_winner(self) -> Optional[Team]:
        if self.jester_won:
            return Team.JESTER

        living = self.alive_players
        mafia_count = sum(1 for p in living if p.team == Team.MAFIA)
        town_count = sum(1 for p in living if p.team == Team.TOWN)
        maniac_count = sum(1 for p in living if p.role == Role.MANIAC)

        if mafia_count == 0 and maniac_count == 0:
            return Team.TOWN

        if mafia_count >= (town_count + maniac_count) and maniac_count == 0:
            return Team.MAFIA

        if maniac_count == 1 and (mafia_count + town_count) <= 1:
            return Team.NEUTRAL

        if len(living) == 0:
            return Team.TOWN

        return None

    async def end_game(self, bot: Bot, winner_team: Team):
        self.phase = GamePhase.GAME_OVER
        await restore_players(bot, self.chat_id, list(self.players.keys()))

        if winner_team == Team.TOWN:
            win_msg = i18n.get("victory_town", self.lang)
        elif winner_team == Team.MAFIA:
            win_msg = i18n.get("victory_mafia", self.lang)
        elif winner_team == Team.JESTER:
            win_msg = i18n.get("victory_jester", self.lang)
        else:
            win_msg = i18n.get("victory_maniac", self.lang)

        # Player roles summary
        summary_lines = []
        for p in self.players.values():
            role_title = i18n.get(f"roles.{p.role.value}", self.lang)
            status = "Alive" if p.is_alive else "Dead"
            summary_lines.append(f"• {p.name}: {role_title} ({status})")

        summary = "\n".join(summary_lines)
        full_msg = win_msg + i18n.get(
            "game_summary",
            self.lang,
            summary=summary,
            win_coins=settings.WIN_COIN_REWARD,
            win_exp=settings.WIN_EXP_REWARD
        )

        await bot.send_message(self.chat_id, full_msg, parse_mode="HTML")

        # Distribute database stats and rewards
        async with async_session_maker() as session:
            for p in self.players.values():
                is_win = (p.team == winner_team) or (winner_team == Team.NEUTRAL and p.role == Role.MANIAC) or (winner_team == Team.JESTER and p.role == Role.JESTER)
                coins = settings.WIN_COIN_REWARD if is_win else settings.LOSE_COIN_REWARD
                exp = settings.WIN_EXP_REWARD if is_win else settings.LOSE_EXP_REWARD
                await add_game_stats(session, p.user_id, is_win, p.role.value, coins, exp)
