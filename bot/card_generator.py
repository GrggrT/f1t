"""
Генерирует PNG-карточки результатов гонки через Pillow.
Размер: 1200×675 (16:9, YouTube thumbnail compatible).
"""
from __future__ import annotations
import io
import math
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Константы дизайна
# ---------------------------------------------------------------------------
W, H    = 1200, 675
BG      = (15,  15,  19)
SURFACE = (26,  26,  34)
BORDER  = (42,  42,  54)
TEXT    = (232, 232, 240)
MUTED   = (107, 107, 128)
ACCENT  = (225,   6,   0)   # F1 red
GOLD    = (255, 199,   0)
SILVER  = (192, 192, 192)
BRONZE  = (180, 100,  30)
PURPLE  = (148,   0, 211)   # fastest lap

PODIUM_COLORS = {1: GOLD, 2: SILVER, 3: BRONZE}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Пробует загрузить системный шрифт, fallback на default."""
    candidates = (
        ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"] if bold
        else ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf"]
    )
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple,
) -> None:
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def generate_race_card(race: dict) -> bytes:
    """
    Принимает dict гонки (как возвращает /api/race/{id}),
    возвращает PNG bytes.
    """
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    results    = sorted(race.get("results", []), key=lambda r: r.get("position") or 99)
    track_name = race.get("track_name", "Unknown")
    round_num  = race.get("round", "?")

    # ------------------------------------------------------------------
    # Шрифты
    # ------------------------------------------------------------------
    f_huge   = _load_font(72, bold=True)
    f_big    = _load_font(40, bold=True)
    f_med    = _load_font(28, bold=True)
    f_small  = _load_font(22)
    f_tiny   = _load_font(18)
    f_label  = _load_font(16)

    # ------------------------------------------------------------------
    # Фоновый акцент — диагональная полоса
    # ------------------------------------------------------------------
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.polygon([(W-320, 0), (W, 0), (W, H), (W-80, H)], fill=(*ACCENT, 18))
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
    draw = ImageDraw.Draw(img)

    # ------------------------------------------------------------------
    # Левая колонка — шапка
    # ------------------------------------------------------------------
    # "F1 LEAGUE" лейбл
    draw.text((48, 36), "F1 LEAGUE", font=f_label, fill=ACCENT)

    # Название трассы
    draw.text((48, 58), track_name.upper(), font=f_big, fill=TEXT)

    # Round
    draw.text((48, 106), f"ROUND {round_num}", font=f_small, fill=MUTED)

    # Разделитель
    draw.line([(48, 148), (W - 48, 148)], fill=BORDER, width=1)

    # ------------------------------------------------------------------
    # ТОП-3 подиум (крупно)
    # ------------------------------------------------------------------
    top3 = [r for r in results if r.get("position") in (1, 2, 3)][:3]
    pod_y = 170
    pod_x_start = 48
    pod_col_w   = 340

    for i, r in enumerate(top3):
        pos       = r.get("position", i + 1)
        name      = r.get("driver_name", "???")
        team      = r.get("team_name", "")
        pts       = r.get("points", 0)
        team_id   = r.get("team_id", -1)
        team_hex  = r.get("team_color") or "#888888"
        team_rgb  = _hex_to_rgb(team_hex)
        is_human  = r.get("is_human", False)
        fl        = r.get("has_fastest_lap", False)
        pos_color = PODIUM_COLORS.get(pos, TEXT)

        x = pod_x_start + i * pod_col_w

        # Командная полоска слева
        draw.rectangle([x, pod_y, x + 4, pod_y + 120], fill=team_rgb)

        # Позиция
        draw.text((x + 18, pod_y), str(pos), font=f_huge, fill=pos_color)

        # Имя
        name_display = name.upper()
        draw.text((x + 18, pod_y + 80), name_display, font=f_med, fill=TEXT if not is_human else (255, 255, 255))

        # Команда
        draw.text((x + 18, pod_y + 112), team, font=f_tiny, fill=team_rgb)

        # Очки
        draw.text((x + 18, pod_y + 135), f"{pts} pts", font=f_small, fill=pos_color)

        # PLAYER badge
        if is_human:
            bx, by = x + 18, pod_y + 162
            bw = 70
            _draw_rounded_rect(draw, (bx, by, bx + bw, by + 20), 4, (*ACCENT, 255))
            draw.text((bx + 4, by + 2), "PLAYER", font=_load_font(12, bold=True), fill=(255, 255, 255))

        # FL badge
        if fl:
            draw.text((x + 100, pod_y + 162), "🟣 FL", font=f_tiny, fill=PURPLE)

    # ------------------------------------------------------------------
    # Разделитель
    # ------------------------------------------------------------------
    draw.line([(48, 420), (W - 48, 420)], fill=BORDER, width=1)

    # ------------------------------------------------------------------
    # Остальные результаты (P4-P10 в две колонки)
    # ------------------------------------------------------------------
    rest = [r for r in results if (r.get("position") or 0) > 3 and (r.get("position") or 0) <= 10]
    col_w = (W - 96) // 2
    row_h = 32

    for idx, r in enumerate(rest):
        col   = idx % 2
        row   = idx // 2
        rx    = 48 + col * col_w
        ry    = 432 + row * row_h

        pos       = r.get("position", "?")
        name      = r.get("driver_name", "???")
        team_hex  = r.get("team_color") or "#888888"
        team_rgb  = _hex_to_rgb(team_hex)
        pts       = r.get("points", 0)
        is_human  = r.get("is_human", False)
        fl        = r.get("has_fastest_lap", False)

        # Командная точка
        draw.ellipse([rx, ry + 8, rx + 10, ry + 18], fill=team_rgb)

        # Позиция
        draw.text((rx + 18, ry), str(pos), font=f_small, fill=MUTED)

        # Имя
        name_color = (255, 255, 255) if is_human else TEXT
        draw.text((rx + 42, ry), name, font=f_small, fill=name_color)

        # FL
        if fl:
            draw.text((rx + 42 + len(name) * 12, ry), " 🟣", font=f_tiny, fill=PURPLE)

        # Очки
        pts_str = f"{pts}p" if pts > 0 else "—"
        draw.text((rx + col_w - 52, ry), pts_str, font=f_small, fill=MUTED)

    # ------------------------------------------------------------------
    # DNF строка внизу
    # ------------------------------------------------------------------
    dnf_list = [r for r in results if r.get("result_status") in ("DNF", "Retired", "DSQ")]
    if dnf_list:
        dnf_y = H - 38
        dnf_names = ", ".join(r.get("driver_name", "?") for r in dnf_list)
        draw.text((48, dnf_y), f"DNF: {dnf_names}", font=f_tiny, fill=MUTED)

    # ------------------------------------------------------------------
    # Footer — watermark
    # ------------------------------------------------------------------
    draw.text((W - 180, H - 28), "f1league.app", font=f_label, fill=BORDER)

    # ------------------------------------------------------------------
    # Сохраняем в bytes
    # ------------------------------------------------------------------
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def generate_standings_card(standings: list[dict], title: str = "DRIVERS CHAMPIONSHIP") -> bytes:
    """PNG-карточка WDC/WCC standings — топ-10."""
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    f_big   = _load_font(42, bold=True)
    f_med   = _load_font(30, bold=True)
    f_small = _load_font(22)
    f_tiny  = _load_font(18)
    f_label = _load_font(16)

    # Header
    draw.text((48, 36), "F1 LEAGUE", font=f_label, fill=ACCENT)
    draw.text((48, 60), title, font=f_big, fill=TEXT)
    draw.line([(48, 118), (W - 48, 118)], fill=BORDER, width=1)

    top = standings[:10]
    row_h = (H - 160) // max(len(top), 1)

    max_pts = top[0]["total_points"] if top else 1

    for i, s in enumerate(top):
        ry        = 130 + i * row_h
        pos       = s.get("position", i + 1)
        name      = s.get("driver_name") or s.get("team_name", "?")
        team_hex  = s.get("team_color") or "#888888"
        team_rgb  = _hex_to_rgb(team_hex)
        pts       = s.get("total_points", 0)
        is_human  = s.get("is_human", False)
        pos_color = PODIUM_COLORS.get(pos, TEXT)

        # Командная полоска
        draw.rectangle([48, ry + 4, 52, ry + row_h - 8], fill=team_rgb)

        # Позиция
        draw.text((62, ry + 2), str(pos), font=f_small, fill=pos_color)

        # Имя
        name_color = (255, 255, 255) if is_human else TEXT
        draw.text((100, ry + 2), name.upper() if is_human else name, font=f_small, fill=name_color)

        # PLAYER badge
        if is_human:
            bx = 100 + min(len(name) * 13, 260) + 10
            _draw_rounded_rect(draw, (bx, ry + 4, bx + 60, ry + 22), 3, (*ACCENT, 255))
            draw.text((bx + 4, ry + 5), "PLAYER", font=_load_font(12, bold=True), fill=(255, 255, 255))

        # Прогресс-бар
        bar_x  = W - 280
        bar_w  = 200
        bar_h  = 6
        bar_y  = ry + row_h // 2
        pct    = pts / max_pts if max_pts > 0 else 0
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=BORDER)
        if pct > 0:
            draw.rectangle([bar_x, bar_y, bar_x + int(bar_w * pct), bar_y + bar_h], fill=team_rgb)

        # Очки
        draw.text((W - 60, ry + 2), str(int(pts)), font=f_med, fill=TEXT)

    draw.text((W - 180, H - 28), "f1league.app", font=f_label, fill=BORDER)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
