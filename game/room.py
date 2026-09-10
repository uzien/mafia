import asyncio
from datetime import datetime
import html
import logging
import random
import time
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
from services.media_service import send_game_animation

logger = logging.getLogger(__name__)

class GameRoom:
    def __init__(self, chat_id: int, creator_id: int, creator_name: str, lang: str = "uz", chat_title: str = "Guruh"):
        self.chat_id: int = chat_id
        self.creator_id: int = creator_id
        self.creator_name: str = creator_name
        self.chat_title: str = chat_title
        self.lang: str = lang
        self.phase: GamePhase = GamePhase.LOBBY
        self.round: int = 1
        self.lobby_message_id: Optional[int] = None
        self.creator_pm_message_id: Optional[int] = None
        self.current_event: Optional[str] = None
        self.start_time: Optional[datetime] = None
        
        self.players: Dict[int, Player] = {}
        self.timer_task: Optional[asyncio.Task] = None
        self.seconds_left: int = settings.LOBBY_TIMEOUT
        
        # Night actions
        self.mafia_votes: Dict[int, int] = {}       # mafioso_id -> target_id
        self.doctor_target: Optional[int] = None
        self.detective_target: Optional[int] = None
        self.detective_kill_target: Optional[int] = None
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
        
        self.is_stopped: bool = False
        
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
            # If creator left, assign new creator if any players left
            if user_id == self.creator_id and self.players:
                new_creator = next(iter(self.players.values()))
                self.creator_id = new_creator.user_id
                self.creator_name = new_creator.name
                self.creator_pm_message_id = None
            return True
        return False

    @property
    def alive_players(self) -> List[Player]:
        return [p for p in self.players.values() if p.is_alive]

    def get_lobby_markup(self) -> InlineKeyboardMarkup:
        """Group lobby markup: only contains Join, Leave, and Open Bot buttons."""
        buttons = [
            [
                InlineKeyboardButton(
                    text=i18n.get("btn_join", self.lang),
                    url=f"https://t.me/{settings.BOT_USERNAME}?start=game_{self.chat_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get("btn_leave", self.lang),
                    callback_data="game_leave"
                ),
                InlineKeyboardButton(
                    text=i18n.get("btn_open_bot_pm", self.lang),
                    url=f"https://t.me/{settings.BOT_USERNAME}"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def get_creator_panel_markup(self) -> InlineKeyboardMarkup:
        """Control panel markup exclusively for the game creator in PM."""
        buttons = [
            [
                InlineKeyboardButton(
                    text=i18n.get("btn_start_now", self.lang),
                    callback_data=f"creator_start_{self.chat_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get("btn_extend_time", self.lang),
                    callback_data=f"creator_extend_{self.chat_id}"
                ),
                InlineKeyboardButton(
                    text=i18n.get("btn_cancel_game", self.lang),
                    callback_data=f"creator_cancel_{self.chat_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    def get_creator_panel_text(self) -> str:
        """Detailed status message sent to the creator's private bot chat."""
        players_rows = []
        for idx, p in enumerate(self.players.values()):
            clean_name = html.escape(p.name or "O'yinchi")
            players_rows.append(f"{idx+1}. {clean_name}")
        players_str = "\n".join(players_rows) if players_rows else "—"
        group_name = html.escape(self.chat_title or "Guruh")

        return (
            f"🎮 <b>O'yin Boshqaruv Paneli (Faqat Yaratuvchi uchun)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Guruh: <b>{group_name}</b>\n"
            f"⏳ Qolgan vaqt: <b>{self.seconds_left} soniya</b>\n"
            f"👤 O'yinchilar: <b>{len(self.players)}/{settings.MIN_PLAYERS}</b> (Maks: {settings.MAX_PLAYERS})\n\n"
            f"📋 <b>Ro'yxatdan o'tganlar:</b>\n{players_str}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>O'yinni boshlash, vaqt uzaytirish yoki bekor qilishni faqat siz shu yerdan boshqarasiz.</i>"
        )

    async def sync_lobby_messages(self, bot: Bot):
        """Keep group lobby message and creator PM panel synchronized."""
        if self.phase != GamePhase.LOBBY or self.is_stopped:
            return

        # 1. Update group lobby
        if self.lobby_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=self.chat_id,
                    message_id=self.lobby_message_id,
                    text=self.get_lobby_text(),
                    reply_markup=self.get_lobby_markup(),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.debug(f"Could not edit group lobby message: {e}")

        # 2. Update creator PM panel
        if self.creator_id:
            try:
                if self.creator_pm_message_id:
                    await bot.edit_message_text(
                        chat_id=self.creator_id,
                        message_id=self.creator_pm_message_id,
                        text=self.get_creator_panel_text(),
                        reply_markup=self.get_creator_panel_markup(),
                        parse_mode="HTML"
                    )
                else:
                    pm_msg = await bot.send_message(
                        self.creator_id,
                        self.get_creator_panel_text(),
                        reply_markup=self.get_creator_panel_markup(),
                        parse_mode="HTML"
                    )
                    self.creator_pm_message_id = pm_msg.message_id
            except Exception as e:
                logger.debug(f"Could not update creator PM panel: {e}")

    def extend_lobby_time(self, seconds: int = 30) -> int:
        """Extend lobby countdown, capped at 300 seconds (5 minutes)."""
        self.seconds_left = min(self.seconds_left + seconds, 300)
        return self.seconds_left

    def get_lobby_text(self) -> str:
        if self.players:
            player_rows = []
            for idx, p in enumerate(self.players.values()):
                clean_name = html.escape(p.name or "O'yinchi", quote=False)
                player_rows.append(f"{idx+1}. 👤 <a href=\"tg://user?id={p.user_id}\">{clean_name}</a>")
            players_str = "\n".join(player_rows)
        else:
            players_str = i18n.get("lobby_no_players", self.lang)

        clean_creator = html.escape(self.creator_name or "Tashkilotchi", quote=False)
        return i18n.get(
            "lobby_created",
            self.lang,
            players_list=players_str,
            count=len(self.players),
            creator=clean_creator,
            min=settings.MIN_PLAYERS,
            max=settings.MAX_PLAYERS,
            seconds=self.seconds_left
        )

    def get_living_players_text(self) -> str:
        living = self.alive_players
        lines = [f"{idx+1}. 👤 <a href=\"tg://user?id={p.user_id}\">{html.escape(p.name or 'O`yinchi')}</a>" for idx, p in enumerate(living)]
        players_block = "\n".join(lines) if lines else "..."

        role_counts: Dict[str, int] = {}
        for p in living:
            if p.role:
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

        return f"{title}\n\n{players_block}\n\n{from_them}  {breakdown_str}\n{total}"

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
            if self.is_stopped or self.phase != GamePhase.LOBBY:
                return
            self.seconds_left -= 5
            await self.sync_lobby_messages(bot)

        if self.is_stopped or self.phase != GamePhase.LOBBY:
            return

        if len(self.players) >= settings.MIN_PLAYERS:
            await self.start_game(bot)
        else:
            await bot.send_message(self.chat_id, i18n.get("game_cancelled", self.lang), parse_mode="HTML")
            self.phase = GamePhase.GAME_OVER

    async def start_game(self, bot: Bot):
        """Distribute roles and begin night 1."""
        if self.is_stopped or self.phase != GamePhase.LOBBY:
            return

        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()

        self.phase = GamePhase.STARTING
        self.start_time = datetime.utcnow()

        # Update creator control panel
        if self.creator_id and self.creator_pm_message_id:
            try:
                await bot.edit_message_text(
                    chat_id=self.creator_id,
                    message_id=self.creator_pm_message_id,
                    text="🎬 <b>O'yin boshlandi!</b> Barcha o'yinchilarga rollar tarqatildi.",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # Assign roles
        role_assignments = distribute_roles(list(self.players.keys()))
        for p_id, role in role_assignments.items():
            self.players[p_id].role = role
            # Send private message with role info (WITHOUT early vasiyatnoma button)
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

        # Ensure no player was left without a role
        for p in self.players.values():
            if not p.role:
                p.role = Role.CITIZEN

        # Check if any player has fake documents or belongs to a clan
        try:
            from services.economy_service import has_fake_documents
            from database.models import User, Clan
            async with async_session_maker() as session:
                for p_id in list(self.players.keys()):
                    u = await session.get(User, p_id)
                    if u and u.clan_id:
                        clan = await session.get(Clan, u.clan_id)
                        if clan and clan.tag:
                            tag_prefix = f"[{clan.tag}]"
                            if not self.players[p_id].name.startswith(tag_prefix):
                                self.players[p_id].name = f"{tag_prefix} {self.players[p_id].name}"
                    if await has_fake_documents(session, p_id):
                        self.players[p_id].has_fake_docs = True
        except Exception as e:
            logger.warning(f"Error checking fake documents or clan: {e}")

        # Send group message: O'yin boshlandi! with animated banner & "Sizning rolingiz" button
        role_markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=i18n.get("btn_check_role", self.lang), callback_data=f"check_role_{self.chat_id}"),
                InlineKeyboardButton(text=i18n.get("btn_open_bot_pm", self.lang), url=f"https://t.me/{settings.BOT_USERNAME}")
            ]
        ])
        try:
            await send_game_animation(
                bot=bot,
                chat_id=self.chat_id,
                animation_key="game_start",
                caption=i18n.get("game_starting", self.lang),
                reply_markup=role_markup
            )
        except Exception as e:
            logger.error(f"Error sending game_starting message: {e}")

        await asyncio.sleep(3)
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
        await self.start_night(bot)

    async def broadcast_mafia_chat(self, bot: Bot, sender_id: int, sender_name: str, text: str) -> bool:
        """Relay secret message to other living mafia members during night."""
        if self.phase != GamePhase.NIGHT or self.is_stopped:
            return False
        sender = self.players.get(sender_id)
        if not sender or not sender.is_alive or sender.team != Team.MAFIA:
            return False

        role_title = i18n.get(f"roles.{sender.role.value}", self.lang)
        msg = f"🩸 <b>[Mafiya Maxfiy Chati]</b> <b>{html.escape(sender_name, quote=False)}</b> ({role_title}):\n<i>\"{html.escape(text, quote=False)}\"</i>"

        mafia_teammates = [
            p for p in self.alive_players
            if p.team == Team.MAFIA and p.user_id != sender_id
        ]
        for mate in mafia_teammates:
            try:
                await bot.send_message(mate.user_id, msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Could not send mafia chat message to {mate.user_id}: {e}")
        return True

    async def start_night(self, bot: Bot):
        """Trigger the night phase and collect secret actions via PM."""
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
        self.phase = GamePhase.NIGHT
        self.night_announced_roles.clear()
        self.mafia_votes.clear()
        self.doctor_target = None
        self.detective_target = None
        self.detective_kill_target = None
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

        # Mute group chat safely
        try:
            await mute_chat_night(bot, self.chat_id)
        except Exception as e:
            logger.warning(f"Error muting chat {self.chat_id}: {e}")

        # Roll random night event
        events = ["event_clear", "event_fog", "event_blood_moon", "event_blackout"]
        self.current_event = random.choices(events, weights=[0.55, 0.15, 0.15, 0.15], k=1)[0]
        event_banner = i18n.get(self.current_event, self.lang)

        # Message 1: Night banner with event, animation and 'Bot-ga o'tish' button
        night_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.get("btn_open_bot", self.lang), url=f"https://t.me/{settings.BOT_USERNAME}")]
        ])
        night_title = i18n.get("night_started", self.lang, round=self.round)
        try:
            await send_game_animation(
                bot=bot,
                chat_id=self.chat_id,
                animation_key="night_start",
                caption=f"{night_title}\n\n{event_banner}",
                reply_markup=night_markup
            )
        except Exception as e:
            logger.error(f"Error sending night banner: {e}")

        # Message 2: Living players list
        try:
            await bot.send_message(
                self.chat_id,
                self.get_living_players_text(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error sending living players text: {e}")

        # Prompt each night-active role in PM
        await self._send_night_prompts(bot)

        # Wait for night duration
        self.timer_task = asyncio.create_task(self._night_timer(bot))

    async def _send_night_prompts(self, bot: Bot):
        living = self.alive_players
        for p in living:
            if not p.role:
                continue

            target_buttons = [
                [InlineKeyboardButton(text=f"🎯 {html.escape(target.name)}", callback_data=f"act_{self.chat_id}_{p.role.value}_{target.user_id}")]
                for target in living
                if target.user_id != p.user_id or (p.role == Role.DOCTOR and not p.last_healed)
            ]
            markup = InlineKeyboardMarkup(inline_keyboard=target_buttons) if target_buttons else None

            if p.team == Team.MAFIA:
                if markup:
                    try:
                        await bot.send_message(
                            p.user_id,
                            i18n.get("night_prompt_mafia", self.lang),
                            reply_markup=markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not send night prompt to {p.user_id}: {e}")
            elif p.role == Role.DOCTOR:
                if markup:
                    try:
                        await bot.send_message(
                            p.user_id,
                            i18n.get("night_prompt_doctor", self.lang),
                            reply_markup=markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not send night prompt to {p.user_id}: {e}")
            elif p.role == Role.DETECTIVE:
                det_buttons = []
                for target in living:
                    if target.user_id != p.user_id:
                        det_buttons.append([
                            InlineKeyboardButton(
                                text=f"🔍 {html.escape(target.name)}",
                                callback_data=f"act_{self.chat_id}_det_check_{target.user_id}"
                            ),
                            InlineKeyboardButton(
                                text="🔫 Otish",
                                callback_data=f"act_{self.chat_id}_det_shoot_{target.user_id}"
                            )
                        ])
                det_markup = InlineKeyboardMarkup(inline_keyboard=det_buttons) if det_buttons else None
                if det_markup:
                    try:
                        await bot.send_message(
                            p.user_id,
                            i18n.get("night_prompt_detective", self.lang),
                            reply_markup=det_markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not send night prompt to detective {p.user_id}: {e}")
            elif p.role == Role.MANIAC:
                if markup:
                    try:
                        await bot.send_message(
                            p.user_id,
                            i18n.get("night_prompt_maniac", self.lang),
                            reply_markup=markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not send night prompt to {p.user_id}: {e}")
            elif p.role == Role.MISTRESS:
                if markup:
                    try:
                        await bot.send_message(
                            p.user_id,
                            i18n.get("night_prompt_mistress", self.lang),
                            reply_markup=markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not send night prompt to {p.user_id}: {e}")
            elif p.role == Role.SNIPER and p.sniper_ammo > 0:
                if markup:
                    try:
                        await bot.send_message(
                            p.user_id,
                            i18n.get("night_prompt_sniper", self.lang),
                            reply_markup=markup,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not send night prompt to {p.user_id}: {e}")
            else:
                try:
                    await bot.send_message(
                        p.user_id,
                        i18n.get("night_prompt_citizen", self.lang),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

    def are_all_night_actions_done(self) -> bool:
        """Check if all living roles with required night actions have submitted them."""
        living = self.alive_players
        mafiosi = [p for p in living if p.team == Team.MAFIA and not p.is_blocked]
        if mafiosi and len(self.mafia_votes) < len(mafiosi):
            return False

        has_doctor = any(p.role == Role.DOCTOR and not p.is_blocked for p in living)
        if has_doctor and self.doctor_target is None:
            return False

        has_detective = any(p.role == Role.DETECTIVE and not p.is_blocked for p in living)
        if has_detective and self.detective_target is None and self.detective_kill_target is None:
            return False

        has_maniac = any(p.role == Role.MANIAC and not p.is_blocked for p in living)
        if has_maniac and self.maniac_target is None:
            return False

        has_mistress = any(p.role == Role.MISTRESS and not p.is_blocked for p in living)
        if has_mistress and self.mistress_target is None:
            return False

        return True

    async def _night_timer(self, bot: Bot):
        try:
            await asyncio.sleep(settings.NIGHT_DURATION)
            if self.phase == GamePhase.NIGHT and not self.is_stopped:
                await self.resolve_night(bot)
        except asyncio.CancelledError:
            pass

    async def resolve_night(self, bot: Bot):
        """Calculate the outcome of all night actions."""
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
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

        # 3. Determine Mafia kill target (Don has priority, otherwise plurality)
        mafia_kill_id = None
        don_player = next((p for p in self.alive_players if p.role == Role.DON), None)
        if don_player and don_player.user_id in self.mafia_votes and not don_player.is_blocked:
            mafia_kill_id = self.mafia_votes[don_player.user_id]
        elif self.mafia_votes:
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

        # 5b. Determine Detective kill target
        detective_kill_id = None
        det_player = next((p for p in self.players.values() if p.role == Role.DETECTIVE), None)
        if det_player and not det_player.is_blocked and self.detective_kill_target:
            detective_kill_id = self.detective_kill_target

        # 6. Resolve casualties
        deaths: List[Player] = []
        doctor_saved = False

        targets_to_kill = set()
        killer_map: Dict[int, str] = {}
        if mafia_kill_id:
            targets_to_kill.add(mafia_kill_id)
            killer_map[mafia_kill_id] = "Don"
        if maniac_kill_id:
            targets_to_kill.add(maniac_kill_id)
            killer_map[maniac_kill_id] = "Manyak"
        if sniper_kill_id:
            targets_to_kill.add(sniper_kill_id)
            killer_map[sniper_kill_id] = "Snayper"
        if detective_kill_id:
            targets_to_kill.add(detective_kill_id)
            killer_map[detective_kill_id] = "Komissar katani"

        for t_id in targets_to_kill:
            if t_id in self.players:
                victim = self.players[t_id]
                if victim.protected_by_doctor:
                    doctor_saved = True
                else:
                    victim.is_alive = False
                    victim.awaiting_last_letter = True
                    victim.last_letter_deadline = time.time() + 30.0
                    deaths.append(victim)
                    await mute_dead_player(bot, self.chat_id, victim.user_id)
                    try:
                        skip_btn = InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(
                                text="⏩ O'tkazib yuborish (Skip)",
                                callback_data=f"skip_letter_{self.chat_id}_{victim.user_id}"
                            )
                        ]])
                        await bot.send_message(
                            victim.user_id,
                            "⚰️ <b>Siz halok bo'ldingiz!</b>\n\n"
                            "Shaharga o'lim oldi so'nggi xatingizni (vasiyatingizni) yuborish uchun sizda <b>30 soniya</b> bor!\n"
                            "Xabaringizni shu yerga (botga) yozib yuboring:",
                            reply_markup=skip_btn,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.warning(f"Could not send last letter prompt to {victim.user_id}: {e}")

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
                p.awaiting_last_letter = True
                p.last_letter_deadline = time.time() + 30.0
                deaths.append(p)
                await mute_dead_player(bot, self.chat_id, p.user_id)
                try:
                    skip_btn = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="⏩ O'tkazib yuborish (Skip)",
                            callback_data=f"skip_letter_{self.chat_id}_{p.user_id}"
                        )
                    ]])
                    await bot.send_message(
                        p.user_id,
                        "⚰️ <b>Siz pushaymonlikdan halok bo'ldingiz!</b>\n\n"
                        "Shaharga o'lim oldi so'nggi xatingizni yuborish uchun sizda <b>30 soniya</b> bor!\n"
                        "Xabaringizni shu yerga yozib yuboring:",
                        reply_markup=skip_btn,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # Unmute group chat safely
        await unmute_chat_day(bot, self.chat_id)

        # 1. Morning greeting with animated visual (murder vs peaceful)
        morning_anim_key = "morning_murder" if deaths else "morning_peaceful"
        morning_text = i18n.get("morning_report_title", self.lang, round=self.round)
        try:
            await send_game_animation(
                bot=bot,
                chat_id=self.chat_id,
                animation_key=morning_anim_key,
                caption=morning_text
            )
        except Exception as e:
            logger.error(f"Error sending morning report animation: {e}")

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
                victim_name = html.escape(d.name or "O'yinchi")
                killer_name = killer_map.get(d.user_id)
                killer_note = f" Aytishlaricha unikiga <b>{killer_name}</b> kelgan..." if killer_name else ""
                await bot.send_message(
                    self.chat_id,
                    f"Tunda <b>{role_title}</b> {victim_name} vaxshiylarcha o'ldirildi.{killer_note}",
                    parse_mode="HTML"
                )
                if getattr(d, "last_will", None):
                    clean_will = html.escape(d.last_will)
                    await bot.send_message(
                        self.chat_id,
                        i18n.get("will_reveal", self.lang, name=victim_name, will=clean_will),
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
            clean_s_name = html.escape(sergeant_promoted.name or "O'yinchi")
            await bot.send_message(
                self.chat_id,
                f"🎖 <b>{role_sergeant} {clean_s_name}</b> {role_detective} lavozimiga ko'tarildi!",
                parse_mode="HTML"
            )

        if don_promoted:
            promoted_player, old_role_title = don_promoted
            clean_don_name = html.escape(promoted_player.name or "O'yinchi")
            await bot.send_message(
                self.chat_id,
                i18n.get("don_promoted", self.lang, old_role=old_role_title, name=clean_don_name),
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
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
        self.phase = GamePhase.DAY
        await bot.send_message(
            self.chat_id,
            i18n.get("day_discussion", self.lang, seconds=settings.DAY_DURATION),
            parse_mode="HTML"
        )
        self.timer_task = asyncio.create_task(self._day_timer(bot))

    async def _day_timer(self, bot: Bot):
        try:
            await asyncio.sleep(settings.DAY_DURATION)
            if self.phase == GamePhase.DAY and not self.is_stopped:
                await self.start_voting(bot)
        except asyncio.CancelledError:
            pass

    async def start_voting(self, bot: Bot):
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
        self.phase = GamePhase.VOTING
        self.day_votes.clear()

        living = self.alive_players
        voting_buttons = [
            [InlineKeyboardButton(text=f"🗳 {p.name}", callback_data=f"vote_{self.chat_id}_{p.user_id}")]
            for p in living
        ]
        # Add 'Skip / Hech kimni osmaslik' button
        voting_buttons.append([
            InlineKeyboardButton(text=i18n.get("btn_skip_vote", self.lang), callback_data=f"vote_{self.chat_id}_0")
        ])
        markup = InlineKeyboardMarkup(inline_keyboard=voting_buttons)

        try:
            await send_game_animation(
                bot=bot,
                chat_id=self.chat_id,
                animation_key="court_trial",
                caption=i18n.get("voting_started", self.lang, seconds=settings.VOTING_DURATION),
                reply_markup=markup
            )
        except Exception as e:
            logger.error(f"Error sending court trial animation: {e}")

        self.timer_task = asyncio.create_task(self._voting_timer(bot))

    async def _voting_timer(self, bot: Bot):
        try:
            await asyncio.sleep(settings.VOTING_DURATION)
            if self.phase == GamePhase.VOTING and not self.is_stopped:
                await self.resolve_voting(bot)
        except asyncio.CancelledError:
            pass

    async def cast_day_vote(self, voter_id: int, target_id: int, bot: Bot) -> bool:
        if self.phase != GamePhase.VOTING or voter_id not in self.players or not self.players[voter_id].is_alive:
            return False
        # target_id == 0 means "Skip / Hech kimni osmaslik"
        if target_id != 0 and (target_id not in self.players or not self.players[target_id].is_alive):
            return False

        self.day_votes[voter_id] = target_id
        voter = self.players[voter_id]

        if target_id == 0:
            await bot.send_message(
                self.chat_id,
                i18n.get("vote_cast_skip", self.lang, voter=voter.name),
                parse_mode="HTML"
            )
        else:
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
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
        if not self.day_votes:
            await bot.send_message(self.chat_id, i18n.get("vote_tie", self.lang), parse_mode="HTML")
            await self._finish_voting_phase(bot)
        else:
            vote_counts: Dict[int, int] = {}
            for t_id in self.day_votes.values():
                vote_counts[t_id] = vote_counts.get(t_id, 0) + 1

            max_votes = max(vote_counts.values())
            suspects = [t_id for t_id, cnt in vote_counts.items() if cnt == max_votes]

            if len(suspects) > 1:
                # If there's a tie, nobody is lynched
                await bot.send_message(self.chat_id, i18n.get("vote_tie", self.lang), parse_mode="HTML")
                await self._finish_voting_phase(bot)
            elif suspects[0] == 0:
                # Majority voted to Skip / Hech kimni osmaslik
                await bot.send_message(self.chat_id, i18n.get("vote_skipped_result", self.lang), parse_mode="HTML")
                await self._finish_voting_phase(bot)
            else:
                lynched_id = suspects[0]
                await self.start_last_words(bot, lynched_id)

    async def start_last_words(self, bot: Bot, lynched_id: int):
        """Allow the condemned suspect a final defense speech before hanging."""
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
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

        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return

        await self.execute_lynch(bot, lynched_id)

    async def execute_lynch(self, bot: Bot, lynched_id: int):
        """Execute the condemned player and process death effects."""
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
        lynched = self.players.get(lynched_id)
        if not lynched or not lynched.is_alive:
            return await self._finish_voting_phase(bot)

        lynched.is_alive = False
        lynched.awaiting_last_letter = True
        lynched.last_letter_deadline = time.time() + 30.0
        await mute_dead_player(bot, self.chat_id, lynched.user_id)
        try:
            skip_btn = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="⏩ O'tkazib yuborish (Skip)",
                    callback_data=f"skip_letter_{self.chat_id}_{lynched.user_id}"
                )
            ]])
            await bot.send_message(
                lynched.user_id,
                "⚰️ <b>Siz sudda dorga osildingiz (linch qilindingiz)!</b>\n\n"
                "Shaharga o'lim oldi so'nggi xatingizni (vasiyatingizni) yuborish uchun sizda <b>30 soniya</b> bor!\n"
                "Xabaringizni shu yerga (botga) yozib yuboring:",
                reply_markup=skip_btn,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not send last letter prompt to {lynched.user_id}: {e}")

        role_title = i18n.get(f"roles.{lynched.role.value}", self.lang)
        lynched_name = html.escape(lynched.name or "O'yinchi")

        try:
            await send_game_animation(
                bot=bot,
                chat_id=self.chat_id,
                animation_key="execution",
                caption=i18n.get("player_lynched", self.lang, name=lynched_name, user_id=lynched.user_id, role=role_title)
            )
        except Exception as e:
            logger.error(f"Error sending execution animation: {e}")

        if getattr(lynched, "last_will", None):
            clean_will = html.escape(lynched.last_will)
            await bot.send_message(
                self.chat_id,
                i18n.get("will_reveal", self.lang, name=lynched_name, will=clean_will),
                parse_mode="HTML"
            )

        # Jester win check
        if lynched.role == Role.JESTER:
            self.jester_won = True
            await bot.send_message(
                self.chat_id,
                i18n.get("jester_lynched", self.lang, name=lynched_name),
                parse_mode="HTML"
            )

        # Kamikaze ability
        if lynched.role == Role.KAMIKAZE:
            voters_for_lynch = [v_id for v_id, target in self.day_votes.items() if target == lynched_id and self.players[v_id].is_alive]
            if voters_for_lynch:
                collateral = self.players[voters_for_lynch[0]]
                collateral.is_alive = False
                collateral.awaiting_last_letter = True
                collateral.last_letter_deadline = time.time() + 30.0
                await mute_dead_player(bot, self.chat_id, collateral.user_id)
                try:
                    skip_btn = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="⏩ O'tkazib yuborish (Skip)",
                            callback_data=f"skip_letter_{self.chat_id}_{collateral.user_id}"
                        )
                    ]])
                    await bot.send_message(
                        collateral.user_id,
                        "⚰️ <b>Siz kamikadze portlashida halok bo'ldingiz!</b>\n\n"
                        "Shaharga o'lim oldi so'nggi xatingizni yuborish uchun sizda <b>30 soniya</b> bor!\n"
                        "Xabaringizni shu yerga yozib yuboring:",
                        reply_markup=skip_btn,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                c_role = i18n.get(f"roles.{collateral.role.value}", self.lang)
                clean_col_name = html.escape(collateral.name or "O'yinchi")
                await bot.send_message(
                    self.chat_id,
                    f"💣 <b>Kamikadze portladi!</b> {clean_col_name} ({c_role}) ham halok bo'ldi!",
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
                clean_sgt_name = html.escape(sergeant.name or "O'yinchi")
                await bot.send_message(
                    self.chat_id,
                    f"🎖 <b>{role_sergeant} {clean_sgt_name}</b> {role_detective} lavozimiga ko'tarildi!",
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
                clean_succ_name = html.escape(successor.name or "O'yinchi")
                await bot.send_message(
                    self.chat_id,
                    i18n.get("don_promoted", self.lang, old_role=old_role_title, name=clean_succ_name),
                    parse_mode="HTML"
                )

        await self._finish_voting_phase(bot)

    async def _finish_voting_phase(self, bot: Bot):
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
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
        if self.is_stopped or self.phase == GamePhase.GAME_OVER:
            return
        await self.start_night(bot)

    def check_winner(self) -> Optional[Team]:
        if self.jester_won:
            return Team.JESTER

        living = self.alive_players
        mafia_count = sum(1 for p in living if p.team == Team.MAFIA)
        non_mafia_count = sum(1 for p in living if p.team != Team.MAFIA)
        maniac_count = sum(1 for p in living if p.role == Role.MANIAC)

        if mafia_count == 0 and maniac_count == 0:
            return Team.TOWN

        if mafia_count >= non_mafia_count and maniac_count == 0:
            return Team.MAFIA

        if maniac_count == 1 and non_mafia_count <= 1:
            return Team.NEUTRAL

        if len(living) == 0:
            return Team.TOWN

        return None

    async def end_game(self, bot: Bot, winner_team: Team):
        self.phase = GamePhase.GAME_OVER
        await restore_players(bot, self.chat_id, list(self.players.keys()))

        # Calculate duration
        if self.start_time:
            elapsed_seconds = max(1, int((datetime.utcnow() - self.start_time).total_seconds()))
            mins = elapsed_seconds // 60
            secs = elapsed_seconds % 60
            if mins > 0:
                duration_str = f"{mins} minut {secs} soniya" if secs > 0 else f"{mins} minut"
            else:
                duration_str = f"{secs} soniya"
        else:
            duration_str = "1 minut"

        winners: List[Player] = []
        others: List[Player] = []
        for p in self.players.values():
            is_win = (p.team == winner_team) or (winner_team == Team.NEUTRAL and p.role == Role.MANIAC) or (winner_team == Team.JESTER and p.role == Role.JESTER)
            if is_win:
                winners.append(p)
            else:
                others.append(p)

        lines = [
            "🏆 <b>O'yin tugadi!</b>",
            "",
            "🎉 <b>G'oliblar:</b>"
        ]
        idx = 1
        for p in winners:
            role_title = i18n.get(f"roles.{p.role.value}", self.lang)
            p_name = html.escape(p.name or "O'yinchi")
            lines.append(f" {idx}. <a href=\"tg://user?id={p.user_id}\">{p_name}</a> - <b>{role_title}</b>")
            idx += 1

        if others:
            lines.extend(["", "💀 <b>Qolgan o'yinchilar:</b>"])
            for p in others:
                role_title = i18n.get(f"roles.{p.role.value}", self.lang)
                p_name = html.escape(p.name or "O'yinchi")
                lines.append(f" {idx}. <a href=\"tg://user?id={p.user_id}\">{p_name}</a> - {role_title}")
                idx += 1

        lines.extend([
            "",
            f"⏳ O'yin: <b>{duration_str}</b> davom etdi",
            f"💰 Har bir g'olib: <b>+{settings.WIN_COIN_REWARD} Tanga</b> | <b>+{settings.WIN_EXP_REWARD} EXP</b>"
        ])
        full_msg = "\n".join(lines)

        # Select victory animation based on winning team
        if winner_team == Team.MAFIA:
            victory_anim = "victory_mafia"
        elif winner_team == Team.NEUTRAL:
            victory_anim = "victory_maniac"
        elif winner_team == Team.JESTER:
            victory_anim = "victory_jester"
        else:
            victory_anim = "victory_town"

        try:
            await send_game_animation(
                bot=bot,
                chat_id=self.chat_id,
                animation_key=victory_anim,
                caption=full_msg
            )
        except Exception as e:
            logger.error(f"Error sending victory animation: {e}")
            await bot.send_message(self.chat_id, full_msg, parse_mode="HTML")

        # Distribute database stats and rewards, and send PM profile summary
        clan_rewards_announced = []
        async with async_session_maker() as session:
            from database.crud import add_clan_war_reward, get_clan
            for p in self.players.values():
                is_win = (p.team == winner_team) or (winner_team == Team.NEUTRAL and p.role == Role.MANIAC) or (winner_team == Team.JESTER and p.role == Role.JESTER)
                coins = settings.WIN_COIN_REWARD if is_win else settings.LOSE_COIN_REWARD
                exp = settings.WIN_EXP_REWARD if is_win else settings.LOSE_EXP_REWARD
                user = await add_game_stats(session, p.user_id, is_win, p.role.value, coins, exp)
                if user:
                    # Clan war reward for winning clan members
                    if is_win and user.clan_id:
                        await add_clan_war_reward(session, user.clan_id, rating_points=15, treasury_coins=25)
                        clan = await get_clan(session, user.clan_id)
                        if clan and clan.tag not in clan_rewards_announced:
                            clan_rewards_announced.append(clan.tag)
                    await self._send_pm_profile_summary(bot, p, user, is_win, coins, exp)

        # Check active tournament points
        tourn_points_announced = []
        async with async_session_maker() as session:
            from database.crud import get_active_tournaments
            from services.tournament_engine import add_tournament_points
            active_tourns = await get_active_tournaments(session)
            if active_tourns:
                curr_t = active_tourns[0]
                for p in self.players.values():
                    is_win = (p.team == winner_team) or (winner_team == Team.NEUTRAL and p.role == Role.MANIAC) or (winner_team == Team.JESTER and p.role == Role.JESTER)
                    pts = 3 if is_win else 1
                    added = await add_tournament_points(session, curr_t.id, p.user_id, points=pts)
                    if added:
                        tourn_points_announced.append(f"{p.name} (+{pts})")

        if clan_rewards_announced:
            tags_str = ", ".join([f"<b>[{t}]</b>" for t in clan_rewards_announced])
            await bot.send_message(
                self.chat_id,
                f"🛡 <b>Klan Urushi Natijasi:</b>\n"
                f"{tags_str} klanlariga g'alaba uchun <b>+15 Reyting Ball</b> va xazinaga <b>+25 Tanga</b> qo'shildi!",
                parse_mode="HTML"
            )

        if tourn_points_announced:
            players_str = ", ".join(tourn_points_announced)
            await bot.send_message(
                self.chat_id,
                f"🏆 <b>Turnir Natijasi:</b>\n"
                f"Qatnashuvchilarga ballar qo'shildi: {players_str}\n"
                f"Jadval: <code>/tournstandings</code>",
                parse_mode="HTML"
            )

    async def _send_pm_profile_summary(
        self,
        bot: Bot,
        player: Player,
        user,
        is_win: bool,
        coins: int,
        exp: int
    ):
        """Send personal post-game profile card and reward details to the player via PM."""
        try:
            lang = user.language or self.lang or "uz"
            role_title = i18n.get(f"roles.{player.role.value}", lang)
            win_rate = round((user.wins / user.games_played * 100), 1) if user.games_played > 0 else 0

            if is_win:
                result_banner = {
                    "uz": "🎉 <b>Tabriklaymiz, siz g'alaba qozondingiz!</b>",
                    "ru": "🎉 <b>Поздравляем, вы победили!</b>",
                    "en": "🎉 <b>Victory! You won!</b>",
                    "az": "🎉 <b>Təbriklər, qalib gəldiniz!</b>",
                    "tr": "🎉 <b>Tebrikler, kazandınız!</b>"
                }.get(lang, "🎉 <b>Tabriklaymiz, siz g'alaba qozondingiz!</b>")
            else:
                result_banner = {
                    "uz": "💀 <b>Bu safar jamoangiz mag'lub bo'ldi.</b>",
                    "ru": "💀 <b>В этот раз ваша команда потерпела поражение.</b>",
                    "en": "💀 <b>Defeat this time.</b>",
                    "az": "💀 <b>Bu dəfə komandanız məğlub oldu.</b>",
                    "tr": "💀 <b>Bu sefer takımınız kaybetti.</b>"
                }.get(lang, "💀 <b>Bu safar jamoangiz mag'lub bo'ldi.</b>")

            reward_label = {
                "uz": "O'yindan olingan mukofot",
                "ru": "Награда за игру",
                "en": "Match Reward",
                "az": "Oyun mükafatı",
                "tr": "Oyun ödülü"
            }.get(lang, "O'yindan olingan mukofot")

            profile_header = {
                "uz": "Sizning Yangilangan Profilingiz",
                "ru": "Ваш Обновленный Профиль",
                "en": "Your Updated Profile",
                "az": "Sizin Yenilənmiş Profiliniz",
                "tr": "Güncellenmiş Profiliniz"
            }.get(lang, "Sizning Yangilangan Profilingiz")

            coins_earned_str = f"+{coins}" if coins > 0 else "0"

            msg = (
                f"🎮 <b>O'YIN YAKUNI VA HISOBOT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"{result_banner}\n"
                f"🎭 Sizning rolingiz: <b>{role_title}</b>\n\n"
                f"💰 <b>{reward_label}:</b> <b>{coins_earned_str} Tanga</b> | <b>+{exp} EXP</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>{profile_header}:</b>\n"
                f"🏷 Unvon: <b>{user.title}</b>\n"
                f"⭐ Daraja: <b>{user.level}</b> ({user.exp} EXP)\n"
                f"💰 Jami Tanga: <b>{user.coins}</b> | 💎 Olmos: <b>{user.diamonds}</b>\n\n"
                f"📊 <b>Umumiy statistika:</b>\n"
                f"• O'yinlar: <b>{user.games_played}</b> | G'alabalar: <b>{user.wins}</b> ({win_rate}%)\n"
                f"━━━━━━━━━━━━━━━━━━━━"
            )

            markup = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🛒 Do'kon", callback_data="nav_shop"),
                    InlineKeyboardButton(text="🎁 Kunlik Bonus", callback_data="nav_daily")
                ],
                [
                    InlineKeyboardButton(text="💎 Olmos olish (@mx767)", url="https://t.me/mx767")
                ]
            ])

            await bot.send_message(player.user_id, msg, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            logger.debug(f"Could not send PM profile summary to {player.user_id}: {e}")

    async def stop_game(self, bot: Bot):
        """Immediately aborts the game, cancels all timers and background tasks, and restores player permissions."""
        self.is_stopped = True
        self.phase = GamePhase.GAME_OVER
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        if getattr(self, "last_words_event", None) and not self.last_words_event.is_set():
            self.last_words_event.set()
        try:
            await restore_players(bot, self.chat_id, list(self.players.keys()))
        except Exception as e:
            logger.warning(f"Error in stop_game restore_players: {e}")
