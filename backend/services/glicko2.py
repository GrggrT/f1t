"""
Glicko-2 рейтинговая система для F1 League.

После каждой гонки каждая пара (human vs human) считается как матч:
- Если A финишировал выше B → A wins, B loses
- Ничьи нет (разные позиции всегда)

Алгоритм: http://www.glicko.net/glicko/glicko2.pdf
"""
from __future__ import annotations
import math
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from backend.db.base import get_database_url
from backend.models.models import RaceResult, Race, PlayerRating, RatingHistory

# Glicko-2 constants
TAU = 0.5        # система volatility constraint
EPSILON = 0.000001
GLICKO2_SCALE = 173.7178


def _to_glicko2(rating: float, rd: float) -> tuple[float, float]:
    mu = (rating - 1500) / GLICKO2_SCALE
    phi = rd / GLICKO2_SCALE
    return mu, phi


def _from_glicko2(mu: float, phi: float) -> tuple[float, float]:
    rating = mu * GLICKO2_SCALE + 1500
    rd = phi * GLICKO2_SCALE
    return rating, rd


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi * math.pi))


def _E(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def update_rating(
    rating: float, rd: float, volatility: float,
    opponents: list[tuple[float, float, float]],  # [(opp_rating, opp_rd, score), ...]
) -> tuple[float, float, float]:
    """
    Update Glicko-2 rating given list of opponents and outcomes.
    score: 1.0 = win, 0.0 = loss
    Returns: (new_rating, new_rd, new_volatility)
    """
    if not opponents:
        # No games: RD increases (decay)
        mu, phi = _to_glicko2(rating, rd)
        phi_new = math.sqrt(phi * phi + volatility * volatility)
        new_rating, new_rd = _from_glicko2(mu, phi_new)
        return new_rating, min(new_rd, 350.0), volatility

    mu, phi = _to_glicko2(rating, rd)

    # Step 3: compute v (estimated variance)
    v_inv = 0.0
    delta_sum = 0.0
    for opp_r, opp_rd_val, score in opponents:
        mu_j, phi_j = _to_glicko2(opp_r, opp_rd_val)
        g_val = _g(phi_j)
        e_val = _E(mu, mu_j, phi_j)
        v_inv += g_val * g_val * e_val * (1.0 - e_val)
        delta_sum += g_val * (score - e_val)

    if v_inv < EPSILON:
        new_rating, new_rd = _from_glicko2(mu, phi)
        return new_rating, min(new_rd, 350.0), volatility

    v = 1.0 / v_inv
    delta = v * delta_sum

    # Step 4: compute new volatility (iterative algorithm)
    a = math.log(volatility * volatility)
    tau2 = TAU * TAU

    def f(x):
        ex = math.exp(x)
        d2 = delta * delta
        p2 = phi * phi
        t1 = ex * (d2 - p2 - v - ex) / (2.0 * (p2 + v + ex) ** 2)
        t2 = (x - a) / tau2
        return t1 - t2

    # Bracket
    A = a
    if delta * delta > phi * phi + v:
        B = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * TAU) < 0:
            k += 1
        B = a - k * TAU

    fA = f(A)
    fB = f(B)
    for _ in range(100):
        if abs(B - A) < EPSILON:
            break
        C = A + (A - B) * fA / (fB - fA)
        fC = f(C)
        if fC * fB <= 0:
            A = B
            fA = fB
        else:
            fA /= 2.0
        B = C
        fB = fC

    sigma_new = math.exp(A / 2.0)

    # Step 5-6: update rating and RD
    phi_star = math.sqrt(phi * phi + sigma_new * sigma_new)
    phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_new = mu + phi_new * phi_new * delta_sum

    new_rating, new_rd = _from_glicko2(mu_new, phi_new)
    return round(new_rating, 1), round(min(new_rd, 350.0), 1), round(sigma_new, 6)


async def recalc_ratings_after_race(race_id: int) -> None:
    """
    Update Glicko-2 ratings for all human players after a race.
    Each pair of human players is a match — higher finisher wins.
    """
    engine = create_async_engine(get_database_url(), echo=False)
    sf = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with sf() as db:
            # Get human results for this race
            res = await db.execute(
                select(RaceResult).where(
                    RaceResult.race_id == race_id,
                    RaceResult.is_human == True,  # noqa: E712
                    RaceResult.user_id != None,  # noqa: E711
                    RaceResult.position != None,   # noqa: E711
                )
            )
            human_results = res.scalars().all()

            if len(human_results) < 2:
                return

            # Load or create ratings for each player
            user_ids = [r.user_id for r in human_results]
            ratings_res = await db.execute(
                select(PlayerRating).where(PlayerRating.user_id.in_(user_ids))
            )
            ratings_map: dict[int, PlayerRating] = {
                pr.user_id: pr for pr in ratings_res.scalars().all()
            }

            # Create missing ratings
            for pid in user_ids:
                if pid not in ratings_map:
                    pr = PlayerRating(user_id=pid)
                    db.add(pr)
                    ratings_map[pid] = pr
            await db.flush()

            # Build matchups and compute new ratings
            new_values: dict[int, tuple[float, float, float]] = {}

            for rr in human_results:
                pid = rr.user_id
                pr = ratings_map[pid]
                opponents = []

                for other in human_results:
                    if other.user_id == pid:
                        continue
                    opr = ratings_map[other.user_id]
                    score = 1.0 if rr.position < other.position else 0.0
                    opponents.append((opr.rating, opr.rd, score))

                new_r, new_rd, new_vol = update_rating(pr.rating, pr.rd, pr.volatility, opponents)
                new_values[pid] = (new_r, new_rd, new_vol)

            # Apply updates + record history
            for pid, (new_r, new_rd, new_vol) in new_values.items():
                pr = ratings_map[pid]
                old_rating = pr.rating

                # Count wins/losses for this race
                rr = next(r for r in human_results if r.user_id == pid)
                wins = sum(1 for o in human_results if o.user_id != pid and rr.position < o.position)
                losses = sum(1 for o in human_results if o.user_id != pid and rr.position > o.position)

                db.add(RatingHistory(
                    user_id=pid,
                    race_id=race_id,
                    rating_before=old_rating,
                    rating_after=new_r,
                    rd_after=new_rd,
                ))

                pr.rating = new_r
                pr.rd = new_rd
                pr.volatility = new_vol
                pr.wins = (pr.wins or 0) + wins
                pr.losses = (pr.losses or 0) + losses
                pr.races_rated = (pr.races_rated or 0) + 1
                pr.peak_rating = max(pr.peak_rating or 1500, new_r)
                pr.updated_at = datetime.now(timezone.utc)

            await db.commit()
            print(f"[GLICKO] Updated ratings for {len(new_values)} players after race {race_id}")
    finally:
        await engine.dispose()
