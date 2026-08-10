from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError


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
    """MongoDB-backed data layer. Public method signatures match the previous
    SQLite implementation 1:1 so no handler code needs to change.

    Giveaways / Participants / Payments keep small sequential integer IDs
    (via a `counters` collection) instead of MongoDB ObjectIds, because those
    IDs get embedded in Telegram callback_data strings and deep-link URLs
    throughout the handlers (e.g. "vote:{giveaway_id}:{participant_id}"),
    and are parsed back with int(). Votes / ChannelPosts / Broadcasts are
    never referenced by ID outside this file, so they use ObjectIds.
    """

    def __init__(self, uri: str, db_name: str = "madara_vote"):
        self.client: AsyncIOMotorClient = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]

        self.users = self.db["users"]
        self.owners = self.db["owners"]
        self.banned_users = self.db["banned_users"]
        self.giveaways = self.db["giveaways"]
        self.participants = self.db["participants"]
        self.votes = self.db["votes"]
        self.payments = self.db["payments"]
        self.channel_posts = self.db["channel_posts"]
        self.user_channels = self.db["user_channels"]
        self.broadcasts = self.db["broadcasts"]
        self.counters = self.db["counters"]

    async def init(self) -> None:
        await self.participants.create_index(
            [("giveaway_id", ASCENDING), ("user_id", ASCENDING)], unique=True
        )
        await self.votes.create_index(
            [("giveaway_id", ASCENDING), ("voter_id", ASCENDING)], unique=True
        )
        await self.user_channels.create_index(
            [("user_id", ASCENDING), ("chat_id", ASCENDING)], unique=True
        )
        await self.giveaways.create_index([("host_id", ASCENDING), ("status", ASCENDING)])
        await self.giveaways.create_index([("channel_id", ASCENDING)])
        await self.participants.create_index([("giveaway_id", ASCENDING), ("vote_count", DESCENDING)])
        await self.votes.create_index([("giveaway_id", ASCENDING)])
        await self.channel_posts.create_index([("giveaway_id", ASCENDING)])

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _next_id(self, name: str) -> int:
        doc = await self.counters.find_one_and_update(
            {"_id": name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc["seq"]

    # ── Users / Owners / Bans ────────────────────────────────────────────────

    async def ensure_user(self, user_id: int, username: str | None, full_name: str, is_admin: bool = False) -> None:
        await self.users.update_one(
            {"_id": user_id},
            {
                "$set": {"username": username, "full_name": full_name},
                "$max": {"is_admin": int(is_admin)},
                "$setOnInsert": {"created_at": self.now()},
            },
            upsert=True,
        )

    async def set_initial_owners(self, owner_ids: tuple[int, ...]) -> None:
        for owner_id in owner_ids:
            await self.owners.update_one(
                {"_id": owner_id},
                {"$setOnInsert": {"created_at": self.now()}},
                upsert=True,
            )
            await self.users.update_one({"_id": owner_id}, {"$set": {"is_admin": 1}})

    async def is_owner(self, user_id: int) -> bool:
        return await self.owners.find_one({"_id": user_id}) is not None

    async def is_banned(self, user_id: int) -> bool:
        return await self.banned_users.find_one({"_id": user_id}) is not None

    async def ban_user(self, user_id: int, banned_by: int, reason: str | None = None) -> None:
        await self.banned_users.replace_one(
            {"_id": user_id},
            {"_id": user_id, "banned_by": banned_by, "reason": reason, "created_at": self.now()},
            upsert=True,
        )

    async def unban_user(self, user_id: int) -> None:
        await self.banned_users.delete_one({"_id": user_id})

    async def add_owner(self, user_id: int) -> None:
        await self.owners.update_one(
            {"_id": user_id},
            {"$setOnInsert": {"created_at": self.now()}},
            upsert=True,
        )
        await self.users.update_one({"_id": user_id}, {"$set": {"is_admin": 1}})

    async def get_all_user_ids(self) -> list[int]:
        return [doc["_id"] async for doc in self.users.find({}, {"_id": 1})]

    async def total_users(self) -> int:
        return await self.users.count_documents({})

    async def total_giveaways(self) -> int:
        return await self.giveaways.count_documents({})

    async def active_giveaways(self) -> int:
        return await self.giveaways.count_documents({"status": "active"})

    async def save_broadcast(self, sent_by: int, message: str, total_users: int, sent_count: int) -> None:
        await self.broadcasts.insert_one({
            "sent_by": sent_by,
            "message": message,
            "total_users": total_users,
            "sent_count": sent_count,
            "created_at": self.now(),
        })

    # ── Giveaways ─────────────────────────────────────────────────────────────

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
        gid = await self._next_id("giveaways")
        await self.giveaways.insert_one({
            "_id": gid,
            "host_id": host_id,
            "title": title,
            "channel_id": channel_id,
            "channel_username": channel_username,
            "giveaway_type": giveaway_type,
            "mode": mode,
            "qr_file_id": qr_file_id,
            "stars_username": stars_username,
            "upi_id": upi_id,
            "status": "active",
            "paid_votes_enabled": 1,
            "participation_enabled": 1,
            "referral_enabled": referral_enabled,
            "votes_per_referral": votes_per_referral,
            "max_participants": max_participants,
            "ended_at": None,
            "winner_participant_id": None,
            "created_at": self.now(),
        })
        return gid

    async def get_giveaway(self, giveaway_id: int) -> Giveaway | None:
        d = await self.giveaways.find_one({"_id": giveaway_id})
        if not d:
            return None
        return Giveaway(
            id=d["_id"], host_id=d["host_id"], title=d["title"],
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
        active = await self.giveaways.count_documents({"host_id": host_id, "status": "active"})
        past = await self.giveaways.count_documents({"host_id": host_id, "status": {"$ne": "active"}})
        return {"active": active, "past": past}

    async def get_host_giveaways(self, host_id: int, status: str = "active") -> list[dict[str, Any]]:
        cursor = (
            self.giveaways.find(
                {"host_id": host_id, "status": status},
                {"title": 1, "giveaway_type": 1, "status": 1, "created_at": 1},
            )
            .sort("_id", DESCENDING)
            .limit(20)
        )
        out = []
        async for d in cursor:
            out.append({
                "id": d["_id"], "title": d["title"], "giveaway_type": d["giveaway_type"],
                "status": d["status"], "created_at": d["created_at"],
            })
        return out

    async def update_giveaway_flags(
        self, giveaway_id: int, *,
        paid_votes_enabled: int | None = None,
        participation_enabled: int | None = None,
        referral_enabled: int | None = None,
        status: str | None = None,
    ) -> None:
        updates: dict[str, Any] = {}
        if paid_votes_enabled is not None:
            updates["paid_votes_enabled"] = paid_votes_enabled
        if participation_enabled is not None:
            updates["participation_enabled"] = participation_enabled
        if referral_enabled is not None:
            updates["referral_enabled"] = referral_enabled
        if status is not None:
            updates["status"] = status
            if status == "ended":
                updates["ended_at"] = self.now()
        if not updates:
            return
        await self.giveaways.update_one({"_id": giveaway_id}, {"$set": updates})

    async def clear_channel_posts(self, giveaway_id: int) -> list[int]:
        ids = [d["message_id"] async for d in self.channel_posts.find({"giveaway_id": giveaway_id}, {"message_id": 1})]
        await self.channel_posts.delete_many({"giveaway_id": giveaway_id})
        return ids

    # ── Participants ──────────────────────────────────────────────────────────

    async def add_participant(
        self, giveaway_id: int, user_id: int, username: str | None, full_name: str | None,
        referred_by: int | None = None,
    ) -> int | None:
        pid = await self._next_id("participants")
        try:
            await self.participants.insert_one({
                "_id": pid,
                "giveaway_id": giveaway_id,
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "vote_count": 0,
                "referral_count": 0,
                "post_message_id": None,
                "referred_by": referred_by,
                "joined_at": self.now(),
            })
            return pid
        except DuplicateKeyError:
            return None

    async def credit_referral(self, giveaway_id: int, referrer_user_id: int, votes: int) -> None:
        await self.participants.update_one(
            {"giveaway_id": giveaway_id, "user_id": referrer_user_id},
            {"$inc": {"vote_count": votes, "referral_count": 1}},
        )

    async def set_participant_post_message(self, participant_id: int, message_id: int) -> None:
        participant = await self.participants.find_one({"_id": participant_id}, {"giveaway_id": 1})
        await self.participants.update_one({"_id": participant_id}, {"$set": {"post_message_id": message_id}})
        if participant:
            await self.channel_posts.insert_one({
                "giveaway_id": participant["giveaway_id"],
                "participant_id": participant_id,
                "message_id": message_id,
                "created_at": self.now(),
            })

    async def get_participant(self, giveaway_id: int, user_id: int) -> dict[str, Any] | None:
        d = await self.participants.find_one({"giveaway_id": giveaway_id, "user_id": user_id})
        return _with_id(d)

    async def get_participant_by_id(self, participant_id: int) -> dict[str, Any] | None:
        d = await self.participants.find_one({"_id": participant_id})
        return _with_id(d)

    async def count_participants(self, giveaway_id: int) -> int:
        return await self.participants.count_documents({"giveaway_id": giveaway_id})

    async def participant_votes(self, participant_id: int) -> int:
        d = await self.participants.find_one({"_id": participant_id}, {"vote_count": 1})
        return d["vote_count"] if d else 0

    async def leaderboard(self, giveaway_id: int, limit: int = 10) -> list[dict[str, Any]]:
        cursor = (
            self.participants.find(
                {"giveaway_id": giveaway_id},
                {"user_id": 1, "username": 1, "full_name": 1, "vote_count": 1, "referral_count": 1},
            )
            .sort([("vote_count", DESCENDING), ("_id", ASCENDING)])
            .limit(limit)
        )
        return [d async for d in cursor]

    async def top_participant(self, giveaway_id: int) -> dict[str, Any] | None:
        cursor = (
            self.participants.find({"giveaway_id": giveaway_id})
            .sort([("vote_count", DESCENDING), ("_id", ASCENDING)])
            .limit(1)
        )
        async for d in cursor:
            return _with_id(d)
        return None

    async def random_winner(self, giveaway_id: int) -> dict[str, Any] | None:
        cursor = self.participants.aggregate([
            {"$match": {"giveaway_id": giveaway_id}},
            {"$sample": {"size": 1}},
        ])
        async for d in cursor:
            return _with_id(d)
        return None

    async def add_manual_votes(self, participant_id: int, amount: int) -> None:
        await self.participants.update_one({"_id": participant_id}, {"$inc": {"vote_count": amount}})

    # ── Votes ─────────────────────────────────────────────────────────────────

    async def add_vote(self, giveaway_id: int, participant_id: int, voter_id: int) -> bool:
        try:
            await self.votes.insert_one({
                "giveaway_id": giveaway_id,
                "participant_id": participant_id,
                "voter_id": voter_id,
                "created_at": self.now(),
            })
        except DuplicateKeyError:
            return False
        await self.participants.update_one({"_id": participant_id}, {"$inc": {"vote_count": 1}})
        return True

    async def has_voted_in_giveaway(self, giveaway_id: int, voter_id: int) -> bool:
        return await self.votes.find_one({"giveaway_id": giveaway_id, "voter_id": voter_id}) is not None

    async def remove_votes_by_voter_for_channel(self, channel_id: int, voter_id: int) -> list[dict[str, Any]]:
        giveaway_ids = [
            d["_id"] async for d in self.giveaways.find({"channel_id": channel_id}, {"_id": 1})
        ]
        if not giveaway_ids:
            return []

        rows: list[dict[str, Any]] = []
        cursor = self.votes.find({"giveaway_id": {"$in": giveaway_ids}, "voter_id": voter_id})
        async for vote in cursor:
            participant = await self.participants.find_one({"_id": vote["participant_id"]})
            await self.votes.delete_one({"_id": vote["_id"]})
            await self.participants.update_one(
                {"_id": vote["participant_id"], "vote_count": {"$gt": 0}},
                {"$inc": {"vote_count": -1}},
            )
            rows.append({
                "vote_id": vote["_id"],
                "participant_id": vote["participant_id"],
                "giveaway_id": vote["giveaway_id"],
                "post_message_id": participant.get("post_message_id") if participant else None,
            })
        return rows

    # ── Payments ──────────────────────────────────────────────────────────────

    async def save_payment(
        self, giveaway_id: int, participant_id: int, payer_id: int,
        mode: str, screenshot_file_id: str, ref: str, amount: int, votes_to_add: int = 0,
    ) -> int:
        payment_id = await self._next_id("payments")
        await self.payments.insert_one({
            "_id": payment_id,
            "giveaway_id": giveaway_id,
            "participant_id": participant_id,
            "payer_id": payer_id,
            "mode": mode,
            "screenshot_file_id": screenshot_file_id,
            "utr_or_stars_ref": ref,
            "amount": amount,
            "votes_to_add": votes_to_add,
            "status": "pending",
            "reviewed_by": None,
            "created_at": self.now(),
            "reviewed_at": None,
        })
        return payment_id

    async def get_payment(self, payment_id: int) -> dict[str, Any] | None:
        d = await self.payments.find_one({"_id": payment_id})
        return _with_id(d)

    async def update_payment_status(self, payment_id: int, status: str, reviewed_by: int) -> bool:
        """Only transitions a still-pending payment. Returns True if this call actually
        changed the status (guards against double-tap approve/deny races)."""
        result = await self.payments.update_one(
            {"_id": payment_id, "status": "pending"},
            {"$set": {"status": status, "reviewed_by": reviewed_by, "reviewed_at": self.now()}},
        )
        return result.modified_count > 0

    # ── User Channels ─────────────────────────────────────────────────────────

    async def save_user_chat(self, user_id: int, chat_id: int, chat_title: str, chat_username: str | None, chat_type: str) -> None:
        await self.user_channels.update_one(
            {"user_id": user_id, "chat_id": chat_id},
            {
                "$setOnInsert": {
                    "user_id": user_id, "chat_id": chat_id, "chat_title": chat_title,
                    "chat_username": chat_username, "chat_type": chat_type, "created_at": self.now(),
                }
            },
            upsert=True,
        )

    async def list_user_chats(self, user_id: int, chat_type: str | None = None) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"user_id": user_id}
        if chat_type:
            query["chat_type"] = chat_type
        cursor = self.user_channels.find(
            query, {"chat_id": 1, "chat_title": 1, "chat_username": 1, "chat_type": 1}
        ).sort("_id", DESCENDING)
        return [{"chat_id": d["chat_id"], "chat_title": d["chat_title"], "chat_username": d["chat_username"], "chat_type": d["chat_type"]} async for d in cursor]


def _with_id(d: dict[str, Any] | None) -> dict[str, Any] | None:
    """Mongo docs use _id; the rest of the app expects 'id'. Mirror both."""
    if d is None:
        return None
    d = dict(d)
    d["id"] = d.pop("_id")
    return d
