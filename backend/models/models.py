import secrets
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, Float, ForeignKey, Index, Integer,
    String, Text, BigInteger, SmallInteger, TIMESTAMP, UniqueConstraint, text,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from backend.db.base import Base


def _gen_invite_code() -> str:
    return secrets.token_urlsafe(8)  # ~11 chars


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Unified identity (Sprint 2). One row = one person.

    Created in PR 2.1 by merging legacy `web_users` + `players` tables.
    PR 2.5 dropped those legacy tables; `users` is now the single source of
    truth for identity (auth side + racing side).

    `legacy_web_user_id` / `legacy_player_id` survive PR 2.5 as audit columns;
    a future cosmetic migration will drop them.
    """
    __tablename__ = "users"

    id                  = Column(Integer, primary_key=True)
    email               = Column(String(255), unique=True, nullable=True)
    hashed_password     = Column(Text, nullable=True)
    google_id           = Column(String(100), unique=True, nullable=True)
    name                = Column(String(100), nullable=False)
    avatar_url          = Column(Text, nullable=True)
    telegram_id         = Column(BigInteger, unique=True, nullable=True)
    steam_id64          = Column(String(20), unique=True, nullable=True)
    steam_names         = Column(ARRAY(Text), nullable=True)
    steam_url           = Column(Text, nullable=True)
    is_system_admin     = Column(Boolean, default=False, nullable=False, server_default="false")
    created_at          = Column(TIMESTAMP(timezone=True), default=_utcnow, server_default=text("now()"))
    legacy_web_user_id  = Column(Integer, unique=True, nullable=True)
    legacy_player_id    = Column(Integer, unique=True, nullable=True)

    contracts   = relationship("SeasonContract", back_populates="user")
    results     = relationship("RaceResult", back_populates="user", foreign_keys="RaceResult.user_id")


class Lobby(Base):
    """Лобби — группа сезонов с участниками и ролями."""
    __tablename__ = "lobbies"

    id              = Column(Integer, primary_key=True)
    name            = Column(String(100), nullable=False)
    description     = Column(Text, nullable=True)
    avatar_url      = Column(Text, nullable=True)
    creator_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    invite_code     = Column(String(20), unique=True, nullable=False, default=_gen_invite_code)
    created_at      = Column(TIMESTAMP(timezone=True), default=_utcnow)

    creator     = relationship("User", foreign_keys=[creator_user_id])
    members     = relationship("LobbyMember", back_populates="lobby", cascade="all, delete-orphan")
    seasons     = relationship("Season", back_populates="lobby")


class LobbyMember(Base):
    """Участник лобби с ролью."""
    __tablename__ = "lobby_members"
    __table_args__ = (
        UniqueConstraint("lobby_id", "user_id", name="uq_lobby_member"),
        Index("ix_lobby_members_user_id", "user_id"),
    )

    id          = Column(Integer, primary_key=True)
    lobby_id    = Column(Integer, ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role        = Column(String(20), nullable=False, default="member")  # admin / moderator / member
    joined_at   = Column(TIMESTAMP(timezone=True), default=_utcnow)

    lobby       = relationship("Lobby", back_populates="members")
    user        = relationship("User")


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        Index("ix_seasons_lobby_id", "lobby_id"),
    )

    id              = Column(Integer, primary_key=True)
    name            = Column(String(50))
    status          = Column(String(20), default="active")   # active / completed / archived
    calendar        = Column(JSONB)  # [{round: 1, track_id: 3, track_name: "Bahrain"}, ...]
    points_system   = Column(JSONB)  # {1: 25, 2: 18, ...}
    creator_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    lobby_id        = Column(Integer, ForeignKey("lobbies.id", ondelete="SET NULL"), nullable=True)
    created_at      = Column(TIMESTAMP(timezone=True), default=_utcnow)

    races           = relationship("Race", back_populates="season")
    contracts       = relationship("SeasonContract", back_populates="season")
    creator         = relationship("User", foreign_keys=[creator_user_id])
    lobby           = relationship("Lobby", back_populates="seasons")


class SeasonContract(Base):
    __tablename__ = "season_contracts"

    id          = Column(Integer, primary_key=True)
    season_id   = Column(Integer, ForeignKey("seasons.id"))
    user_id     = Column(Integer, ForeignKey("users.id"))
    driver_id   = Column(Integer, nullable=False)
    driver_name = Column(String(50))
    team_id     = Column(Integer, nullable=False)
    team_name   = Column(String(50))

    season      = relationship("Season", back_populates="contracts")
    user        = relationship("User", back_populates="contracts")


class Race(Base):
    __tablename__ = "races"

    id             = Column(Integer, primary_key=True)
    season_id      = Column(Integer, ForeignKey("seasons.id"))
    round_number   = Column(Integer, nullable=False)
    track_id       = Column(Integer, nullable=False)
    track_name     = Column(String(50))
    session_uid    = Column(BigInteger, unique=True)   # защита от дублей
    packet_format  = Column(Integer, default=2025)
    weather_start  = Column(Integer, nullable=True)
    weather_end    = Column(Integer, nullable=True)
    total_laps     = Column(Integer, nullable=True)
    air_temp       = Column(Integer, nullable=True)
    track_temp     = Column(Integer, nullable=True)
    raced_at       = Column(TIMESTAMP(timezone=True), default=_utcnow)

    season         = relationship("Season", back_populates="races")
    results        = relationship("RaceResult", back_populates="race")
    events         = relationship("RaceEvent", back_populates="race")


class RaceResult(Base):
    __tablename__ = "race_results"
    __table_args__ = (
        Index("ix_race_results_season_id", "season_id"),
        Index("ix_race_results_race_id", "race_id"),
    )

    id              = Column(Integer, primary_key=True)
    race_id         = Column(Integer, ForeignKey("races.id"))
    vehicle_index   = Column(Integer, nullable=False)
    is_human        = Column(Boolean, nullable=False)
    user_id         = Column(Integer, ForeignKey("users.id"), nullable=True)
    driver_id       = Column(Integer, nullable=False)
    driver_name     = Column(String(50))
    team_id         = Column(Integer, nullable=False)
    team_name       = Column(String(50))
    grid_position   = Column(Integer, nullable=True)
    position        = Column(Integer, nullable=True)
    points          = Column(Float, default=0)
    result_status   = Column(Integer)  # 3=finished, 4=DNF, 5=DSQ, 6=retired
    total_race_time = Column(Float, nullable=True)
    best_lap_ms     = Column(Integer, nullable=True)
    penalties_time  = Column(Integer, nullable=True)
    num_penalties   = Column(Integer, nullable=True)
    num_pit_stops   = Column(Integer, nullable=True)
    num_tyre_stints = Column(Integer, nullable=True)
    tyre_stints     = Column(JSONB, nullable=True)  # [{compound: "C3", laps: 12}, ...]
    has_fastest_lap = Column(Boolean, default=False)
    season_id       = Column(Integer, ForeignKey("seasons.id"), nullable=True)

    race            = relationship("Race", back_populates="results")
    user            = relationship("User", back_populates="results", foreign_keys=[user_id])


class RaceEvent(Base):
    __tablename__ = "race_events"

    id           = Column(Integer, primary_key=True)
    race_id      = Column(Integer, ForeignKey("races.id"))
    event_code   = Column(String(4))
    event_data   = Column(JSONB)
    lap_number   = Column(Integer, nullable=True)
    session_time = Column(Float, nullable=True)

    race         = relationship("Race", back_populates="events")


class ChampionshipStanding(Base):
    __tablename__ = "championship_standings"

    season_id    = Column(Integer, ForeignKey("seasons.id"), primary_key=True)
    driver_id    = Column(Integer, primary_key=True)
    driver_name  = Column(String(50))
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_human     = Column(Boolean)
    team_id      = Column(Integer)
    team_name    = Column(String(50))
    total_points = Column(Float, default=0)
    wins         = Column(Integer, default=0)
    podiums      = Column(Integer, default=0)
    fastest_laps = Column(Integer, default=0)
    dnfs         = Column(Integer, default=0)
    best_finish  = Column(Integer, nullable=True)
    position     = Column(Integer, nullable=True)
    consistency_index = Column(Float, nullable=True)   # 0.0–1.0
    avg_grid_delta    = Column(Float, nullable=True)   # avg positions gained/lost


class ConstructorStanding(Base):
    __tablename__ = "constructor_standings"

    season_id    = Column(Integer, ForeignKey("seasons.id"), primary_key=True)
    team_id      = Column(Integer, primary_key=True)
    team_name    = Column(String(50))
    total_points = Column(Float, default=0)
    wins         = Column(Integer, default=0)
    driver_1_name = Column(String(50), nullable=True)
    driver_2_name = Column(String(50), nullable=True)


class Achievement(Base):
    __tablename__ = "achievements"

    id          = Column(Integer, primary_key=True)
    code        = Column(String(50), unique=True, nullable=False)
    name        = Column(String(100), nullable=False)
    description = Column(Text)
    icon        = Column(String(10))
    phase       = Column(Integer, default=2)

    unlocks     = relationship("PlayerAchievement", back_populates="achievement")


class PlayerAchievement(Base):
    __tablename__ = "player_achievements"

    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    race_id        = Column(Integer, ForeignKey("races.id"), nullable=True)
    unlocked_at    = Column(TIMESTAMP(timezone=True), default=_utcnow)
    context        = Column(JSONB, nullable=True)

    user        = relationship("User")
    achievement = relationship("Achievement", back_populates="unlocks")


class LapTelemetry(Base):
    """
    Телеметрия одного круга одного пилота.
    Семплируется 5Hz агентом, хранится как компактный JSONB массив.
    samples: [{t, x, z, spd, thr, brk, gear, drs, dist}]
    """
    __tablename__ = "lap_telemetry"
    __table_args__ = (
        Index("ix_lap_telemetry_race_vehicle", "race_id", "vehicle_index"),
        Index("ix_lap_telemetry_race_lap", "race_id", "vehicle_index", "lap_number", unique=True),
    )

    id             = Column(Integer, primary_key=True)
    race_id        = Column(Integer, ForeignKey("races.id"), nullable=False)
    vehicle_index  = Column(Integer, nullable=False)
    lap_number     = Column(Integer, nullable=False)
    lap_time_ms    = Column(Integer, nullable=True)   # итоговое время круга в мс
    samples        = Column(JSONB, nullable=False)    # [{t,x,z,spd,thr,brk,gear,drs,dist}]


class PlayerRating(Base):
    """Glicko-2 рейтинг игрока."""
    __tablename__ = "player_ratings"

    id          = Column(Integer, primary_key=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    rating      = Column(Float, default=1500.0)
    rd          = Column(Float, default=350.0)       # rating deviation
    volatility  = Column(Float, default=0.06)
    wins        = Column(Integer, default=0)
    losses      = Column(Integer, default=0)
    races_rated = Column(Integer, default=0)
    peak_rating = Column(Float, default=1500.0)
    updated_at  = Column(TIMESTAMP(timezone=True), default=_utcnow)

    user        = relationship("User")


class RatingHistory(Base):
    """История изменения рейтинга для графиков."""
    __tablename__ = "rating_history"

    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    race_id       = Column(Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False)
    rating_before = Column(Float, nullable=False)
    rating_after  = Column(Float, nullable=False)
    rd_after      = Column(Float, nullable=False)
    recorded_at   = Column(TIMESTAMP(timezone=True), default=_utcnow)


class RaceSessionHistory(Base):
    """
    Sector times per lap per vehicle from SessionHistory UDP packet.
    Stored per-race, per-vehicle.
    """
    __tablename__ = "race_session_history"
    __table_args__ = (
        Index("ix_race_session_history_race_vehicle", "race_id", "vehicle_index", unique=True),
    )

    id             = Column(Integer, primary_key=True)
    race_id        = Column(Integer, ForeignKey("races.id", ondelete="CASCADE"), nullable=False)
    vehicle_index  = Column(Integer, nullable=False)
    best_lap_num   = Column(Integer, nullable=True)
    best_s1_lap    = Column(Integer, nullable=True)
    best_s2_lap    = Column(Integer, nullable=True)
    best_s3_lap    = Column(Integer, nullable=True)
    laps           = Column(JSONB, nullable=False)  # [{lap_number, lap_time_ms, sector1_ms, sector2_ms, sector3_ms, lap_valid}]


class PenaltyCorrection(Base):
    __tablename__ = "penalty_corrections"

    id                  = Column(Integer, primary_key=True)
    race_id             = Column(Integer, ForeignKey("races.id"))
    user_id             = Column(Integer, ForeignKey("users.id"))
    correction_sec      = Column(Integer)   # +5 или -5
    reason              = Column(Text)
    applied_by_user_id  = Column(Integer, ForeignKey("users.id"))
    applied_at          = Column(TIMESTAMP(timezone=True), default=_utcnow)
