from __future__ import annotations

import aiosqlite
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Giveaway:
    id: int
    host_id: int
    title: str
    channel_id: int
    channel_username: str
    giveaway_type: str
    mode: str
    qr_file_id: str | None
    stars_username: str | None
    upi_id: str | None
    status: str
    paid_votes_enabled: int
    participation_enabled: int
    referral_enabled: int
    votes_per_referral: int
    max_participants: int | None
    created_at: str


class Database:
    def __init__(self, path: str):
        self.path = path

    def _open(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.path)

    async def _setup(self, db: aiosqlite.Connection) -> None:
        await db.execute("PRAGMA foreign_keys = ON")
        db.row_factory = aiosqlite.Row

    async def init(self) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS Users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    is_admin INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS Owners (
                    user_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS BannedUsers (
                    user_id INTEGER PRIMARY KEY,
                    banned_by INTEGER NOT NULL,
                    reason TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS Giveaways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    host_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    channel_username TEXT NOT NULL,
                    giveaway_type TEXT NOT NULL DEFAULT 'voting',
                    mode TEXT NOT NULL DEFAULT 'free',
                    qr_file_id TEXT,
                    stars_username TEXT,
                    upi_id TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    paid_votes_enabled INTEGER NOT NULL DEFAULT 1,
                    participation_enabled INTEGER NOT NULL DEFAULT 1,
                    referral_enabled INTEGER NOT NULL DEFAULT 0,
                    votes_per_referral INTEGER NOT NULL DEFAULT 1,
                    max_participants INTEGER,
                    ended_at TEXT,
                    winner_participant_id INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(host_id) REFERENCES Users(user_id)
                );

                CREATE TABLE IF NOT EXISTS Participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giveaway_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    vote_count INTEGER NOT NULL DEFAULT 0,
                    referral_count INTEGER NOT NULL DEFAULT 0,
                    post_message_id INTEGER,
                    referred_by INTEGER,
                    joined_at TEXT NOT NULL,
                    UNIQUE(giveaway_id, user_id),
                    FOREIGN KEY(giveaway_id) REFERENCES Giveaways(id) ON DELETE CASCADE,
                    FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS Votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giveaway_id INTEGER NOT NULL,
                    participant_id INTEGER NOT NULL,
                    voter_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(giveaway_id, voter_id),
                    FOREIGN KEY(giveaway_id) REFERENCES Giveaways(id) ON DELETE CASCADE,
                    FOREIGN KEY(participant_id) REFERENCES Participants(id) ON DELETE CASCADE,
                    FOREIGN KEY(voter_id) REFERENCES Users(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS Payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giveaway_id INTEGER NOT NULL,
                    participant_id INTEGER NOT NULL,
                    payer_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    screenshot_file_id TEXT NOT NULL,
                    utr_or_stars_ref TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    votes_to_add INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    reviewed_by INTEGER,
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    FOREIGN KEY(giveaway_id) REFERENCES Giveaways(id) ON DELETE CASCADE,
                    FOREIGN KEY(participant_id) REFERENCES Participants(id) ON DELETE CASCADE,
                    FOREIGN KEY(payer_id) REFERENCES Users(user_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ChannelPosts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    giveaway_id INTEGER NOT NULL,
                    participant_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(giveaway_id) REFERENCES Giveaways(id) ON DELETE CASCADE,
                    FOREIGN KEY(participant_id) REFERENCES Participants(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS UserChannels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    chat_title TEXT NOT NULL,
                    chat_username TEXT,
                    chat_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS Broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sent_by INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    total_users INTEGER NOT NULL DEFAULT 0,
                    sent_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );
            """)
            await db.commit()

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def ensure_user(self, user_id: int, username: str | None, full_name: str, is_admin: bool = False) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.execute(
                """
                INSERT INTO Users(user_id, username, full_name, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    full_name=excluded.full_name,
                    is_admin=MAX(is_admin, excluded.is_admin)
                """,
                (user_id, username, full_name, int(is_admin), self.now()),
            )
            await db.commit()

    async def set_initial_owners(self, owner_ids: tuple[int, ...]) -> None:
        async with self._open() as db:
            await self._setup(db)
            for owner_id in owner_ids:
                await db.execute("INSERT OR IGNORE INTO Owners(user_id, created_at) VALUES (?, ?)", (owner_id, self.now()))
                await db.execute("UPDATE Users SET is_admin=1 WHERE user_id=?", (owner_id,))
            await db.commit()

    async def is_owner(self, user_id: int) -> bool:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT 1 FROM Owners WHERE user_id=?", (user_id,))
            return (await cur.fetchone()) is not None

    async def is_banned(self, user_id: int) -> bool:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT 1 FROM BannedUsers WHERE user_id=?", (user_id,))
            return (await cur.fetchone()) is not None

    async def ban_user(self, user_id: int, banned_by: int, reason: str | None = None) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.execute(
                "INSERT OR REPLACE INTO BannedUsers(user_id, banned_by, reason, created_at) VALUES (?, ?, ?, ?)",
                (user_id, banned_by, reason, self.now()),
            )
            await db.commit()

    async def unban_user(self, user_id: int) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.execute("DELETE FROM BannedUsers WHERE user_id=?", (user_id,))
            await db.commit()

    async def add_owner(self, user_id: int) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.execute("INSERT OR IGNORE INTO Owners(user_id, created_at) VALUES (?, ?)", (user_id, self.now()))
            await db.execute("UPDATE Users SET is_admin=1 WHERE user_id=?", (user_id,))
            await db.commit()

    async def get_all_user_ids(self) -> list[int]:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT user_id FROM Users")
            return [r["user_id"] for r in await cur.fetchall()]

    async def total_users(self) -> int:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT COUNT(*) AS cnt FROM Users")
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    async def total_giveaways(self) -> int:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT COUNT(*) AS cnt FROM Giveaways")
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    async def active_giveaways(self) -> int:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT COUNT(*) AS cnt FROM Giveaways WHERE status='active'")
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    async def save_broadcast(self, sent_by: int, message: str, total_users: int, sent_count: int) -> int:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                "INSERT INTO Broadcasts(sent_by, message, total_users, sent_count, created_at) VALUES (?, ?, ?, ?, ?)",
                (sent_by, message, total_users, sent_count, self.now()),
            )
            await db.commit()
            return cur.lastrowid

    async def create_giveaway(
        self,
        host_id: int,
        title: str,
        channel_id: int,
        channel_username: str,
        giveaway_type: str,
        mode: str,
        qr_file_id: str | None,
        stars_username: str | None,
        upi_id: str | None,
        referral_enabled: int = 0,
        votes_per_referral: int = 1,
        max_participants: int | None = None,
    ) -> int:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                """
                INSERT INTO Giveaways(
                    host_id, title, channel_id, channel_username, giveaway_type, mode,
                    qr_file_id, stars_username, upi_id,
                    referral_enabled, votes_per_referral, max_participants, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    host_id, title, channel_id, channel_username, giveaway_type, mode,
                    qr_file_id, stars_username, upi_id,
                    referral_enabled, votes_per_referral, max_participants, self.now(),
                ),
            )
            await db.commit()
            return cur.lastrowid

    async def get_giveaway(self, giveaway_id: int) -> Giveaway | None:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT * FROM Giveaways WHERE id=?", (giveaway_id,))
            row = await cur.fetchone()
            if not row:
                return None
            d = dict(row)
            return Giveaway(
                id=d["id"], host_id=d["host_id"], title=d["title"],
                channel_id=d["channel_id"], channel_username=d["channel_username"],
                giveaway_type=d.get("giveaway_type", "voting"),
                mode=d.get("mode", "free"),
                qr_file_id=d.get("qr_file_id"), stars_username=d.get("stars_username"),
                upi_id=d.get("upi_id"),
                status=d["status"],
                paid_votes_enabled=d.get("paid_votes_enabled", 1),
                participation_enabled=d.get("participation_enabled", 1),
                referral_enabled=d.get("referral_enabled", 0),
                votes_per_referral=d.get("votes_per_referral", 1),
                max_participants=d.get("max_participants"),
                created_at=d["created_at"],
            )

    async def host_giveaway_counts(self, host_id: int) -> dict[str, int]:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                "SELECT SUM(status='active') AS active_count, SUM(status!='active') AS past_count FROM Giveaways WHERE host_id=?",
                (host_id,),
            )
            row = await cur.fetchone()
            return {"active": row["active_count"] or 0, "past": row["past_count"] or 0}

    async def get_host_giveaways(self, host_id: int, status: str = "active") -> list[dict[str, Any]]:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                "SELECT id, title, giveaway_type, status, created_at FROM Giveaways WHERE host_id=? AND status=? ORDER BY id DESC LIMIT 20",
                (host_id, status),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def add_participant(self, giveaway_id: int, user_id: int, username: str | None, full_name: str | None, referred_by: int | None = None) -> int | None:
        async with self._open() as db:
            await self._setup(db)
            try:
                cur = await db.execute(
                    "INSERT INTO Participants(giveaway_id, user_id, username, full_name, referred_by, joined_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (giveaway_id, user_id, username, full_name, referred_by, self.now()),
                )
                await db.commit()
                return cur.lastrowid
            except aiosqlite.IntegrityError:
                return None

    async def credit_referral(self, giveaway_id: int, referrer_user_id: int, votes: int) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.execute(
                "UPDATE Participants SET vote_count=vote_count+?, referral_count=referral_count+1 WHERE giveaway_id=? AND user_id=?",
                (votes, giveaway_id, referrer_user_id),
            )
            await db.commit()

    async def set_participant_post_message(self, participant_id: int, message_id: int) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.execute("UPDATE Participants SET post_message_id=? WHERE id=?", (message_id, participant_id))
            await db.execute(
                "INSERT INTO ChannelPosts(giveaway_id, participant_id, message_id, created_at) SELECT giveaway_id, id, ?, ? FROM Participants WHERE id=?",
                (message_id, self.now(), participant_id),
            )
            await db.commit()

    async def get_participant(self, giveaway_id: int, user_id: int) -> dict[str, Any] | None:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT * FROM Participants WHERE giveaway_id=? AND user_id=?", (giveaway_id, user_id))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_participant_by_id(self, participant_id: int) -> dict[str, Any] | None:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT * FROM Participants WHERE id=?", (participant_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def count_participants(self, giveaway_id: int) -> int:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT COUNT(*) AS cnt FROM Participants WHERE giveaway_id=?", (giveaway_id,))
            row = await cur.fetchone()
            return row["cnt"] if row else 0

    async def add_vote(self, giveaway_id: int, participant_id: int, voter_id: int) -> bool:
        async with self._open() as db:
            await self._setup(db)
            try:
                await db.execute(
                    "INSERT INTO Votes(giveaway_id, participant_id, voter_id, created_at) VALUES (?, ?, ?, ?)",
                    (giveaway_id, participant_id, voter_id, self.now()),
                )
                await db.execute("UPDATE Participants SET vote_count=vote_count+1 WHERE id=?", (participant_id,))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def has_voted_in_giveaway(self, giveaway_id: int, voter_id: int) -> bool:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT 1 FROM Votes WHERE giveaway_id=? AND voter_id=?", (giveaway_id, voter_id))
            return (await cur.fetchone()) is not None

    async def remove_votes_by_voter_for_channel(self, channel_id: int, voter_id: int) -> list[dict[str, Any]]:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                """
                SELECT v.id AS vote_id, v.participant_id, p.giveaway_id, p.post_message_id
                FROM Votes v
                JOIN Participants p ON p.id=v.participant_id
                JOIN Giveaways g ON g.id=p.giveaway_id
                WHERE g.channel_id=? AND v.voter_id=?
                """,
                (channel_id, voter_id),
            )
            rows = [dict(r) for r in await cur.fetchall()]
            for row in rows:
                await db.execute("DELETE FROM Votes WHERE id=?", (row["vote_id"],))
                await db.execute("UPDATE Participants SET vote_count=MAX(vote_count-1,0) WHERE id=?", (row["participant_id"],))
            await db.commit()
            return rows

    async def participant_votes(self, participant_id: int) -> int:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT vote_count FROM Participants WHERE id=?", (participant_id,))
            row = await cur.fetchone()
            return row["vote_count"] if row else 0

    async def leaderboard(self, giveaway_id: int, limit: int = 10) -> list[dict[str, Any]]:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                "SELECT user_id, username, full_name, vote_count, referral_count FROM Participants WHERE giveaway_id=? ORDER BY vote_count DESC, id ASC LIMIT ?",
                (giveaway_id, limit),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def update_giveaway_flags(
        self, giveaway_id: int, *,
        paid_votes_enabled: int | None = None,
        participation_enabled: int | None = None,
        referral_enabled: int | None = None,
        status: str | None = None,
    ) -> None:
        fields, values = [], []
        if paid_votes_enabled is not None:
            fields.append("paid_votes_enabled=?"); values.append(paid_votes_enabled)
        if participation_enabled is not None:
            fields.append("participation_enabled=?"); values.append(participation_enabled)
        if referral_enabled is not None:
            fields.append("referral_enabled=?"); values.append(referral_enabled)
        if status is not None:
            fields.append("status=?"); values.append(status)
            if status == "ended":
                fields.append("ended_at=?"); values.append(self.now())
        if not fields:
            return
        values.append(giveaway_id)
        async with self._open() as db:
            await self._setup(db)
            await db.execute(f"UPDATE Giveaways SET {', '.join(fields)} WHERE id=?", values)
            await db.commit()

    async def top_participant(self, giveaway_id: int) -> dict[str, Any] | None:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                "SELECT id, user_id, username, full_name, vote_count FROM Participants WHERE giveaway_id=? ORDER BY vote_count DESC, id ASC LIMIT 1",
                (giveaway_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def random_winner(self, giveaway_id: int) -> dict[str, Any] | None:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                "SELECT id, user_id, username, full_name FROM Participants WHERE giveaway_id=? ORDER BY RANDOM() LIMIT 1",
                (giveaway_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def clear_channel_posts(self, giveaway_id: int) -> list[int]:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT message_id FROM ChannelPosts WHERE giveaway_id=?", (giveaway_id,))
            ids = [r["message_id"] for r in await cur.fetchall()]
            await db.execute("DELETE FROM ChannelPosts WHERE giveaway_id=?", (giveaway_id,))
            await db.commit()
            return ids

    async def save_payment(
        self, giveaway_id: int, participant_id: int, payer_id: int,
        mode: str, screenshot_file_id: str, ref: str, amount: int, votes_to_add: int = 0,
    ) -> int:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                """
                INSERT INTO Payments(giveaway_id, participant_id, payer_id, mode, screenshot_file_id, utr_or_stars_ref, amount, votes_to_add, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (giveaway_id, participant_id, payer_id, mode, screenshot_file_id, ref, amount, votes_to_add, self.now()),
            )
            await db.commit()
            return cur.lastrowid

    async def get_payment(self, payment_id: int) -> dict[str, Any] | None:
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute("SELECT * FROM Payments WHERE id=?", (payment_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def update_payment_status(self, payment_id: int, status: str, reviewed_by: int) -> bool:
        """Only transitions a still-pending payment. Returns True if this call actually
        changed the status (guards against double-tap approve/deny races)."""
        async with self._open() as db:
            await self._setup(db)
            cur = await db.execute(
                "UPDATE Payments SET status=?, reviewed_by=?, reviewed_at=? WHERE id=? AND status='pending'",
                (status, reviewed_by, self.now(), payment_id),
            )
            await db.commit()
            return cur.rowcount > 0

    async def add_manual_votes(self, participant_id: int, amount: int) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.execute("UPDATE Participants SET vote_count=vote_count+? WHERE id=?", (amount, participant_id))
            await db.commit()

    async def save_user_chat(self, user_id: int, chat_id: int, chat_title: str, chat_username: str | None, chat_type: str) -> None:
        async with self._open() as db:
            await self._setup(db)
            await db.execute(
                """
                INSERT INTO UserChannels(user_id, chat_id, chat_title, chat_username, chat_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, chat_id) DO NOTHING
                """,
                (user_id, chat_id, chat_title, chat_username, chat_type, self.now()),
            )
            await db.commit()

    async def list_user_chats(self, user_id: int, chat_type: str | None = None) -> list[dict[str, Any]]:
        async with self._open() as db:
            await self._setup(db)
            if chat_type:
                cur = await db.execute(
                    "SELECT chat_id, chat_title, chat_username, chat_type FROM UserChannels WHERE user_id=? AND chat_type=? ORDER BY id DESC",
                    (user_id, chat_type),
                )
            else:
                cur = await db.execute(
                    "SELECT chat_id, chat_title, chat_username, chat_type FROM UserChannels WHERE user_id=? ORDER BY id DESC",
                    (user_id,),
                )
            return [dict(r) for r in await cur.fetchall()]
