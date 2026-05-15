"""
game.py
=======
Space Shooter dikontrol gestur tangan.

Kontrol:
  ☝  SHOOT  → tembak peluru
  🖐 SHIELD → aktifkan perisai (invincible 2 detik)
  ↔↕ MOVE   → gerakkan pesawat (kiri/kanan/atas/bawah)
  IDLE       → pesawat berhenti

Skor naik setiap musuh dihancurkan.
"""

import pygame
import sys
import random
import math
import time
from dataclasses import dataclass, field
from typing import List
from hand_controller import HandController, Gesture

# ──────────────────────────────────────────────
# Konstanta
# ──────────────────────────────────────────────
W, H         = 900, 650
FPS          = 60
PLAYER_SPEED = 6
BULLET_SPEED = 12
ENEMY_SPEED_BASE = 2.5

# Warna
BLACK   = (5,   5,  15)
WHITE   = (240, 240, 255)
CYAN    = (0,   220, 255)
YELLOW  = (255, 220,  30)
RED     = (255,  50,  50)
GREEN   = (80,  255, 120)
PURPLE  = (160,  80, 255)
ORANGE  = (255, 140,  20)
GRAY    = (80,   80,  90)
DKBLUE  = (10,   20,  60)

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
def lerp(a, b, t):
    return a + (b - a) * t

def rand_star():
    return [random.randint(0, W), random.randint(0, H),
            random.uniform(0.3, 2.5), random.uniform(0.5, 3)]


# ──────────────────────────────────────────────
# Partikel
# ──────────────────────────────────────────────
@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float          # 0.0 → 1.0 (1 = baru lahir)
    color: tuple
    size: float = 4.0

    def update(self, dt):
        self.x    += self.vx * dt
        self.y    += self.vy * dt
        self.life -= dt * 1.5
        self.vx   *= 0.96
        self.vy   *= 0.96

    def draw(self, surf):
        alpha = max(0, self.life)
        r, g, b = self.color
        col = (int(r * alpha), int(g * alpha), int(b * alpha))
        radius = max(1, int(self.size * alpha))
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), radius)


def explode(particles: List[Particle], x, y, color, n=18, speed=5):
    for _ in range(n):
        angle = random.uniform(0, math.tau)
        spd   = random.uniform(speed * 0.3, speed)
        particles.append(Particle(
            x, y,
            math.cos(angle) * spd * 60,
            math.sin(angle) * spd * 60,
            1.0, color,
            random.uniform(2, 5)
        ))


# ──────────────────────────────────────────────
# Sprite Gambar (programmatic)
# ──────────────────────────────────────────────
def draw_player(surf, x, y, shield_active, shield_timer):
    """Gambar pesawat triangular."""
    pts = [
        (x,      y - 24),   # ujung depan
        (x - 18, y + 16),
        (x,      y +  8),
        (x + 18, y + 16),
    ]
    pygame.draw.polygon(surf, CYAN, pts)
    pygame.draw.polygon(surf, WHITE, pts, 2)

    # Engine glow
    glow_y = y + 16
    for i in range(4):
        alpha = (4 - i) / 4
        r = int(8 - i * 1.5)
        col = (int(255 * alpha), int(100 * alpha), 0)
        pygame.draw.circle(surf, col, (x - 8, glow_y + i * 2), r)
        pygame.draw.circle(surf, col, (x + 8, glow_y + i * 2), r)

    # Perisai
    if shield_active:
        t   = time.time()
        pulse = 0.6 + 0.4 * math.sin(t * 8)
        col = (int(0 * pulse), int(200 * pulse), int(255 * pulse))
        pygame.draw.circle(surf, col, (x, y), 34, 3)
        # Efek cincin kedua
        pygame.draw.circle(surf, (50, 50, 200), (x, y), 40, 1)


def draw_enemy(surf, x, y, hp_frac, etype=0):
    """Berbagai tipe musuh berdasarkan etype."""
    if etype == 0:
        # Diamond
        pts = [(x, y-18), (x+14, y), (x, y+18), (x-14, y)]
        col = lerp_color(RED, YELLOW, 1 - hp_frac)
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 2)
    elif etype == 1:
        # Hexagon
        pts = [(x + 16*math.cos(math.radians(60*i - 90)),
                y + 16*math.sin(math.radians(60*i - 90))) for i in range(6)]
        col = lerp_color(PURPLE, RED, 1 - hp_frac)
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 2)
    else:
        # Boss: besar
        pts = [(x, y-26), (x+20, y-10), (x+26, y+10),
               (x, y+22), (x-26, y+10), (x-20, y-10)]
        col = lerp_color(ORANGE, RED, 1 - hp_frac)
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, WHITE, pts, 2)

        # HP bar boss
        bw = 60
        pygame.draw.rect(surf, GRAY, (x - bw//2, y - 36, bw, 6))
        pygame.draw.rect(surf, GREEN, (x - bw//2, y - 36, int(bw * hp_frac), 6))


def lerp_color(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


# ──────────────────────────────────────────────
# Entity classes
# ──────────────────────────────────────────────
class Player:
    SHIELD_DURATION = 2.0    # detik
    SHIELD_COOLDOWN = 5.0

    def __init__(self):
        self.x      = W // 2
        self.y      = H - 100
        self.hp     = 5
        self.shield_active   = False
        self.shield_end      = 0.0
        self.shield_cooldown = 0.0
        self.score  = 0
        self.invuln_until = 0.0   # brief invuln setelah kena hit

    @property
    def rect(self):
        return pygame.Rect(self.x - 15, self.y - 20, 30, 40)

    def activate_shield(self):
        now = time.time()
        if now >= self.shield_cooldown:
            self.shield_active = True
            self.shield_end    = now + self.SHIELD_DURATION
            self.shield_cooldown = now + self.SHIELD_DURATION + self.SHIELD_COOLDOWN

    def update(self, gesture: Gesture, dt: float):
        now = time.time()

        # Gerak
        if gesture == Gesture.MOVE_LEFT:
            self.x -= PLAYER_SPEED
        elif gesture == Gesture.MOVE_RIGHT:
            self.x += PLAYER_SPEED
        elif gesture == Gesture.MOVE_UP:
            self.y -= PLAYER_SPEED
        elif gesture == Gesture.MOVE_DOWN:
            self.y += PLAYER_SPEED

        self.x = max(20, min(W - 20, self.x))
        self.y = max(20, min(H - 20, self.y))

        # Shield
        if self.shield_active and now >= self.shield_end:
            self.shield_active = False

    def take_damage(self, dmg=1):
        now = time.time()
        if self.shield_active or now < self.invuln_until:
            return False
        self.hp         -= dmg
        self.invuln_until = now + 1.0
        return True


class Bullet:
    def __init__(self, x, y, vy=-BULLET_SPEED, color=CYAN, dmg=1):
        self.x, self.y = x, y
        self.vy  = vy
        self.color = color
        self.dmg   = dmg

    def update(self, dt):
        self.y += self.vy

    def draw(self, surf):
        pygame.draw.rect(surf, self.color, (self.x - 2, self.y - 8, 4, 14), border_radius=2)
        # Glow
        pygame.draw.rect(surf, WHITE, (self.x - 1, self.y - 6, 2, 10), border_radius=2)

    @property
    def off_screen(self):
        return self.y < -20 or self.y > H + 20

    @property
    def rect(self):
        return pygame.Rect(self.x - 3, self.y - 9, 6, 18)


class Enemy:
    def __init__(self, level=1):
        self.etype    = random.choices([0, 1, 2], weights=[60, 30, 10])[0]
        self.x        = random.randint(40, W - 40)
        self.y        = random.randint(-80, -20)
        base_speed    = ENEMY_SPEED_BASE + level * 0.4
        self.vx       = random.uniform(-1, 1)
        self.vy       = random.uniform(base_speed * 0.6, base_speed)
        self.max_hp   = [1, 2, 6][self.etype] + level // 3
        self.hp       = self.max_hp
        self.shoot_cd = random.uniform(1.5, 3.5)   # detik sampai tembak
        self.last_shot = time.time() + self.shoot_cd

    @property
    def hp_frac(self):
        return self.hp / self.max_hp

    @property
    def size(self):
        return [18, 22, 30][self.etype]

    @property
    def rect(self):
        s = self.size
        return pygame.Rect(self.x - s, self.y - s, s * 2, s * 2)

    @property
    def score_value(self):
        return [10, 20, 80][self.etype]

    def update(self, dt):
        self.x += self.vx
        self.y += self.vy
        if self.x < 30 or self.x > W - 30:
            self.vx *= -1

    def should_shoot(self) -> bool:
        now = time.time()
        if self.etype >= 1 and now >= self.last_shot:
            self.last_shot = now + random.uniform(1.5, 3.0)
            return True
        return False

    def draw(self, surf):
        draw_enemy(surf, int(self.x), int(self.y), self.hp_frac, self.etype)


# ──────────────────────────────────────────────
# UI helpers
# ──────────────────────────────────────────────
class Font:
    """Cache font pygame."""
    _cache = {}

    @classmethod
    def get(cls, size, bold=False):
        key = (size, bold)
        if key not in cls._cache:
            cls._cache[key] = pygame.font.SysFont("consolas", size, bold=bold)
        return cls._cache[key]

    @classmethod
    def render(cls, surf, text, x, y, color=WHITE, size=18, bold=False, center=False):
        fnt  = cls.get(size, bold)
        img  = fnt.render(text, True, color)
        rect = img.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        surf.blit(img, rect)


def draw_hud(surf, player: Player, level: int, wave: int):
    # Panel kiri atas
    pygame.draw.rect(surf, (0, 0, 0, 180), (8, 8, 200, 90), border_radius=8)
    pygame.draw.rect(surf, CYAN, (8, 8, 200, 90), 1, border_radius=8)

    Font.render(surf, f"SCORE  {player.score:07d}", 18, 18, YELLOW, 16, bold=True)
    Font.render(surf, f"LEVEL  {level}   WAVE {wave}", 18, 38, CYAN, 14)

    # HP bar
    Font.render(surf, "HP", 18, 58, WHITE, 13)
    for i in range(5):
        col = GREEN if i < player.hp else GRAY
        pygame.draw.rect(surf, col, (42 + i * 26, 58, 20, 12), border_radius=3)

    # Perisai cooldown
    now = time.time()
    cd_left = max(0, player.shield_cooldown - now)
    if cd_left > 0:
        Font.render(surf, f"SHIELD CD {cd_left:.1f}s", 18, 76, ORANGE, 12)
    else:
        Font.render(surf, "SHIELD READY", 18, 76, GREEN, 12)


def draw_gesture_indicator(surf, gesture: Gesture):
    """Panel kanan atas menampilkan gesture aktif."""
    icons = {
        Gesture.IDLE:       ("●  IDLE",     GRAY),
        Gesture.MOVE_LEFT:  ("◀  MOVE LEFT",  CYAN),
        Gesture.MOVE_RIGHT: ("▶  MOVE RIGHT", CYAN),
        Gesture.MOVE_UP:    ("▲  MOVE UP",    CYAN),
        Gesture.MOVE_DOWN:  ("▼  MOVE DOWN",  CYAN),
        Gesture.SHOOT:      ("☞  SHOOT",     YELLOW),
        Gesture.SHIELD:     ("🛡  SHIELD",    GREEN),
    }
    label, color = icons.get(gesture, ("?", WHITE))
    px = W - 200
    pygame.draw.rect(surf, (0, 0, 0), (px - 4, 8, 196, 34), border_radius=6)
    pygame.draw.rect(surf, color, (px - 4, 8, 196, 34), 1, border_radius=6)
    Font.render(surf, label, px, 18, color, 15, bold=True)


# ──────────────────────────────────────────────
# Game State Machine
# ──────────────────────────────────────────────
class State:
    MENU    = "menu"
    PLAYING = "playing"
    PAUSED  = "paused"
    DEAD    = "dead"
    WIN     = "win"


class SpaceGame:
    ENEMY_PER_WAVE = 8
    WAVES_PER_LEVEL = 3

    def __init__(self, controller: HandController):
        pygame.init()
        pygame.display.set_caption("✋ Hand Gesture Space Shooter")
        self.screen  = pygame.display.set_mode((W, H))
        self.clock   = pygame.time.Clock()
        self.ctrl    = controller

        self.state   = State.MENU
        self._reset()

        # Latar bintang
        self.stars = [rand_star() for _ in range(180)]

    def _reset(self):
        self.player     = Player()
        self.bullets    : List[Bullet]  = []
        self.e_bullets  : List[Bullet]  = []
        self.enemies    : List[Enemy]   = []
        self.particles  : List[Particle] = []
        self.level      = 1
        self.wave       = 1
        self.enemies_spawned = 0
        self.enemies_killed  = 0
        self.spawn_timer     = 0.0
        self.last_shoot_time = 0.0
        self.shoot_cooldown  = 0.25   # detik

    # ── Main loop ──────────────────────────────
    def run(self):
        self.ctrl.start()
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.state == State.PLAYING:
                            self.state = State.PAUSED
                        elif self.state == State.PAUSED:
                            self.state = State.PLAYING
                    if event.key == pygame.K_RETURN:
                        if self.state in (State.MENU, State.DEAD, State.WIN):
                            self._reset()
                            self.state = State.PLAYING

            gesture = self.ctrl.gesture

            if self.state == State.PLAYING:
                self._update(dt, gesture)

            self._draw(gesture)
            pygame.display.flip()

        self.ctrl.stop()
        pygame.quit()
        sys.exit()

    # ── Update ─────────────────────────────────
    def _update(self, dt: float, gesture: Gesture):
        now = time.time()
        player = self.player

        # --- Player ---
        player.update(gesture, dt)

        # Tembak dengan gestur SHOOT
        if gesture == Gesture.SHOOT and now - self.last_shoot_time >= self.shoot_cooldown:
            self.bullets.append(Bullet(player.x, player.y - 24, color=CYAN))
            # Spread shot di level tinggi
            if self.level >= 3:
                self.bullets.append(Bullet(player.x - 10, player.y - 18, vy=-BULLET_SPEED * 0.9, color=CYAN))
                self.bullets.append(Bullet(player.x + 10, player.y - 18, vy=-BULLET_SPEED * 0.9, color=CYAN))
            self.last_shoot_time = now

        # Shield
        if gesture == Gesture.SHIELD:
            player.activate_shield()

        # --- Bullets ---
        for b in self.bullets:
            b.update(dt)
        self.bullets = [b for b in self.bullets if not b.off_screen]

        for b in self.e_bullets:
            b.update(dt)
        self.e_bullets = [b for b in self.e_bullets if not b.off_screen]

        # --- Spawn musuh ---
        self.spawn_timer += dt
        interval = max(0.6, 2.0 - self.level * 0.15)
        if (self.enemies_spawned < self.ENEMY_PER_WAVE * self.wave
                and self.spawn_timer >= interval):
            self.enemies.append(Enemy(self.level))
            self.enemies_spawned += 1
            self.spawn_timer = 0

        # --- Update musuh ---
        for e in self.enemies:
            e.update(dt)
            if e.should_shoot():
                dx = player.x - e.x
                dy = player.y - e.y
                dist = math.hypot(dx, dy) + 1e-6
                spd  = 4 + self.level * 0.3
                self.e_bullets.append(Bullet(
                    e.x, e.y,
                    vy=dy / dist * spd,
                    color=RED, dmg=1
                ))
                # e.bullet bisa punya vx juga tapi kita simplifikasi

        # Musuh keluar bawah layar
        for e in self.enemies[:]:
            if e.y > H + 40:
                self.enemies.remove(e)
                if player.take_damage():
                    explode(self.particles, player.x, player.y, RED, 10)

        # --- Tabrakan peluru player vs musuh ---
        for b in self.bullets[:]:
            for e in self.enemies[:]:
                if b.rect.colliderect(e.rect):
                    e.hp -= b.dmg
                    if b in self.bullets:
                        self.bullets.remove(b)
                    explode(self.particles, e.x, e.y, ORANGE, 6, 3)
                    if e.hp <= 0:
                        player.score += e.score_value
                        self.enemies_killed += 1
                        explode(self.particles, e.x, e.y,
                                [ORANGE, PURPLE, YELLOW][e.etype], 20, 6)
                        self.enemies.remove(e)
                    break

        # --- Tabrakan peluru musuh vs player ---
        for b in self.e_bullets[:]:
            if b.rect.colliderect(player.rect):
                self.e_bullets.remove(b)
                if player.take_damage():
                    explode(self.particles, player.x, player.y, RED, 8)

        # --- Tabrakan langsung musuh vs player ---
        for e in self.enemies[:]:
            if e.rect.colliderect(player.rect):
                self.enemies.remove(e)
                explode(self.particles, e.x, e.y, RED, 15)
                if player.take_damage(2):
                    explode(self.particles, player.x, player.y, RED, 10)

        # --- Partikel ---
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]

        # --- Cek mati ---
        if player.hp <= 0:
            self.state = State.DEAD
            return

        # --- Wave / Level progression ---
        total_needed = self.ENEMY_PER_WAVE * self.wave
        if (self.enemies_spawned >= total_needed
                and len(self.enemies) == 0
                and self.enemies_killed >= total_needed):
            if self.wave < self.WAVES_PER_LEVEL:
                self.wave += 1
                self.enemies_spawned = 0
                self.enemies_killed  = 0
            elif self.level < 5:
                self.level += 1
                self.wave   = 1
                self.enemies_spawned = 0
                self.enemies_killed  = 0
            else:
                self.state = State.WIN

    # ── Draw ───────────────────────────────────
    def _draw(self, gesture: Gesture):
        surf = self.screen
        surf.fill(BLACK)

        # Parallax stars
        for s in self.stars:
            s[1] += s[3] * 0.3
            if s[1] > H:
                s[0] = random.randint(0, W)
                s[1] = -2
            brightness = int(100 + s[2] * 60)
            col = (brightness, brightness, brightness)
            pygame.draw.circle(surf, col, (int(s[0]), int(s[1])), max(1, int(s[2] * 0.5)))

        if self.state == State.MENU:
            self._draw_menu(surf)
            return

        if self.state == State.PAUSED:
            self._draw_game_elements(surf)
            self._draw_overlay_msg(surf, "PAUSED", CYAN,
                                   sub="Tekan ESC untuk lanjut")
            return

        if self.state == State.DEAD:
            self._draw_game_elements(surf)
            self._draw_overlay_msg(surf, "GAME OVER", RED,
                                   sub=f"Score: {self.player.score:,}   ENTER untuk main lagi")
            return

        if self.state == State.WIN:
            self._draw_overlay_msg(surf, "YOU WIN! 🎉", GREEN,
                                   sub=f"Score: {self.player.score:,}   ENTER untuk main lagi")
            return

        self._draw_game_elements(surf)

    def _draw_game_elements(self, surf):
        p = self.player

        # Partikel
        for pt in self.particles:
            pt.draw(surf)

        # Peluru player
        for b in self.bullets:
            b.draw(surf)

        # Peluru musuh
        for b in self.e_bullets:
            pygame.draw.rect(surf, RED, (b.x - 2, b.y - 6, 4, 12), border_radius=2)

        # Musuh
        for e in self.enemies:
            e.draw(surf)

        # Player (kedip saat invuln)
        now = time.time()
        invuln = now < p.invuln_until
        if not invuln or int(now * 10) % 2 == 0:
            draw_player(surf, int(p.x), int(p.y), p.shield_active, p.shield_end)

        # HUD
        draw_hud(surf, p, self.level, self.wave)
        draw_gesture_indicator(surf, self.ctrl.gesture)

        # Wave info
        total = self.ENEMY_PER_WAVE * self.wave
        Font.render(surf, f"Wave {self.wave}/{self.WAVES_PER_LEVEL}  [{self.enemies_killed}/{total}]",
                    W // 2, 14, GRAY, 13, center=True)

    def _draw_menu(self, surf):
        # Judul
        Font.render(surf, "✋ HAND GESTURE", W//2, 140, CYAN,  52, bold=True, center=True)
        Font.render(surf, "  SPACE SHOOTER", W//2, 200, YELLOW, 52, bold=True, center=True)

        pygame.draw.line(surf, CYAN, (W//2 - 200, 260), (W//2 + 200, 260), 2)

        controls = [
            ("1 jari (telunjuk)",  "TEMBAK"),
            ("2 jari (peace sign)", "GESER KIRI"),
            ("3 jari",             "GESER KANAN"),
            ("5 jari (telapak)",   "PERISAI (2 dtk)"),
            ("Gerak atas/bawah",   "Naik / Turun"),
        ]
        y = 290
        for gesture_text, action in controls:
            Font.render(surf, gesture_text, W//2 - 180, y, WHITE,  15, center=False)
            Font.render(surf, f"→  {action}",  W//2 + 20,  y, YELLOW, 15, center=False)
            y += 30

        pygame.draw.line(surf, CYAN, (W//2 - 200, y + 10), (W//2 + 200, y + 10), 2)

        # Blink ENTER
        if int(time.time() * 2) % 2:
            Font.render(surf, "Tekan ENTER untuk mulai", W//2, y + 40, GREEN, 20, bold=True, center=True)

        Font.render(surf, "Pastikan kamera terbuka di jendela OpenCV", W//2, H - 30,
                    GRAY, 12, center=True)

    @staticmethod
    def _draw_overlay_msg(surf, title, color, sub=""):
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))

        Font.render(surf, title, W//2, H//2 - 40, color, 54, bold=True, center=True)
        if sub:
            Font.render(surf, sub, W//2, H//2 + 30, WHITE, 18, center=True)
