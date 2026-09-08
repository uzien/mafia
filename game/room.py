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
    def __init__(self, chat_id: int, creator_id: int, creator_name: str, lang: str = "az"):
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
                InlineKeyboardButton(text=i18n.get("btn_join", self.lang), callback_data="game_join"),
                InlineKeyboardButton(text=i18n.get("btn_leave", self.lang), callback_data="game_leave")
            ]
        ]
        if len(self.players) >= settings.MIN_PLAYERS:
            buttons.append([
                InlineKeyboardButton(text=i18n.get("btn_start_now", self.lang), callback_data="game_start_early")
            ])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def get_lobby_text(self) -> str:
        players_list = "\n".join([f"{idx+1}. 👤 {p.name}" for idx, p in enumerate(self.players.values())])
        return i18n.get(
            "lobby_created",
            self.lang,
            creator=self.creator_name,
            count=len(self.players),
            max=settings.MAX_PLAYERS,
            players_list=players_list if players_list else "...",
            seconds=self.seconds_left
        )

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
        await bot.send_message(self.chat_id, i18n.get("game_starting", self.lang), parse_mode="HTML")

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

        await asyncio.sleep(4)
        await self.start_night(bot)

    async def start_night(self, bot: Bot):
        """Trigger the night phase and collect secret actions via PM."""
        self.phase = GamePhase.NIGHT
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
        await bot.send_message(
            self.chat_id,
            i18n.get("night_started", self.lang, round=self.round),
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

        # Check guilt suicide
        for p in list(self.alive_players):
            if p.guilt_suicide:
                p.is_alive = False
                p.guilt_suicide = False
                deaths.append(p)
                await mute_dead_player(bot, self.chat_id, p.user_id)

        # Unmute group chat for morning
        await unmute_chat_day(bot, self.chat_id)

        # Compose morning report
        report = i18n.get("morning_report_title", self.lang, round=self.round)
        if not deaths and not doctor_saved:
            report += i18n.get("morning_nobody_died", self.lang)
        else:
            if doctor_saved:
                report += i18n.get("morning_doctor_saved", self.lang) + "\n"
            for d in deaths:
                role_title = i18n.get(f"roles.{d.role.value}", self.lang)
                report += i18n.get("morning_killed", self.lang, victim=d.name, role=role_title) + "\n"

        await bot.send_message(self.chat_id, report, parse_mode="HTML")

        if sergeant_promoted:
            await bot.send_message(
                self.chat_id,
                f"🎖 <b>Komissar həlak oldu!</b> Lakin Çavuş <b>{sergeant_promoted.name}</b> onun nişanını qəbul edərək yeni Komissar oldu!",
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
            else:
                lynched_id = suspects[0]
                lynched = self.players[lynched_id]
                lynched.is_alive = False
                await mute_dead_player(bot, self.chat_id, lynched.user_id)
                role_title = i18n.get(f"roles.{lynched.role.value}", self.lang)

                await bot.send_message(
                    self.chat_id,
                    i18n.get("player_lynched", self.lang, name=lynched.name, role=role_title),
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
                            f"💣 <b>Kamikadze partladı!</b> {collateral.name} ({c_role}) də həlak oldu!",
                            parse_mode="HTML"
                        )

        # AFK / Inactivity check for alive players who missed voting
        for p in list(self.alive_players):
            if p.user_id not in self.day_votes:
                p.missed_votes += 1
                if p.missed_votes >= 2:
                    p.is_alive = False
                    await mute_dead_player(bot, self.chat_id, p.user_id)
                    await bot.send_message(
                        self.chat_id,
                        f"💤 <b>{p.name}</b> 2 dəfə səsvermədə iştirak etmədiyi üçün AFK olaraq oyundan kənarlaşdırıldı!",
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
