"""
PacMan - A Beautiful Retro PacMan Game
Built with Pygame | Classic mechanics + Modern aesthetics
"""

import array
import json
import math
import os
import random
import sys
from collections import deque
from enum import Enum, auto

import pygame

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TILE = 24
COLS, ROWS = 28, 28          # 24 maze rows + 4 HUD rows
MAZE_ROWS = 24
WIDTH, HEIGHT = COLS * TILE, ROWS * TILE
FPS = 60
EXTRA_LIFE_AT = 10000
SAVE_FILE = os.path.join(os.path.expanduser("~"), ".pacman_highscore.json")

# Colours (retro-neon palette)
BLACK       = (0, 0, 0)
DARK_BLUE   = (10, 10, 40)
WALL_BLUE   = (33, 33, 222)
WALL_HIGHLIGHT = (80, 80, 255)
DOT_COLOR   = (255, 183, 174)
YELLOW      = (255, 255, 0)
WHITE       = (255, 255, 255)
RED         = (255, 0, 0)
PINK        = (255, 184, 255)
CYAN        = (0, 255, 255)
ORANGE      = (255, 184, 82)
GHOST_BLUE  = (33, 33, 255)
GHOST_WHITE = (255, 255, 255)
SCORE_COLOR = (255, 255, 255)
HUD_BG      = (0, 0, 0)
FRUIT_RED   = (255, 50, 50)
FRUIT_GREEN = (50, 200, 50)

# Directions
UP    = (0, -1)
DOWN  = (0, 1)
LEFT  = (-1, 0)
RIGHT = (1, 0)
STOP  = (0, 0)

# Ghost states
class GhostState(Enum):
    HOUSE    = auto()   # waiting inside the ghost house
    LEAVING  = auto()   # floating out through the door
    ACTIVE   = auto()   # roaming the maze (scatter / chase)
    EATEN    = auto()   # eyes heading back to the door
    ENTERING = auto()   # eyes dropping into the house

# Game states
class GameState(Enum):
    TITLE     = auto()
    READY     = auto()
    PLAYING   = auto()
    DYING     = auto()
    GAME_OVER = auto()
    LEVEL_COMPLETE = auto()

# ---------------------------------------------------------------------------
# Maze layouts (28 x 24). Levels cycle through them.
# 1=wall, 0=dot, 3=power pellet, 4=empty, 5=ghost house wall,
# 6=ghost door, 7=tunnel. Rows 7-14 (ghost house + tunnel) are shared.
# ---------------------------------------------------------------------------
MAZES = [[
    "1111111111111111111111111111",
    "1000000000000110000000000001",
    "1011110111110110111110111101",
    "1311110111110110111110111131",
    "1000000000000000000000000001",
    "1011110110111111110110111101",
    "1000000110000110000110000001",
    "1111110111114114111110111111",
    "4444410114444444444110144444",
    "4444410114555665554110144444",
    "1111110114544444454110111111",
    "7777770444544444454440777777",
    "1111110114555555554110111111",
    "4444410114444444444110144444",
    "1111110114111111114110111111",
    "1000000000000110000000000001",
    "1011110111110110111110111101",
    "1300110000000440000000110031",
    "1110110110111111110110110111",
    "1000000110000110000110000001",
    "1011111111110110111111111101",
    "1011111111110110111111111101",
    "1000000000000000000000000001",
    "1111111111111111111111111111",
], [
    "1111111111111111111111111111",
    "1000000000100000010000000001",
    "1011111110101001010111111101",
    "1300000000001001000000000031",
    "1011011011100000011101101101",
    "1000011000001111000001100001",
    "1001000011000110001100001001",
    "1111110111114114111110111111",
    "4444410114444444444110144444",
    "4444410114555665554110144444",
    "1111110114544444454110111111",
    "7777770444544444454440777777",
    "1111110114555555554110111111",
    "4444410114444444444110144444",
    "1111110114111111114110111111",
    "1000000000000110000000000001",
    "1011110111110110111110111101",
    "1300010000000440000000100031",
    "1111010111011111101110101111",
    "1000010000000110000000100001",
    "1011000111110110111110001101",
    "1011110111110110111110111101",
    "1000000000000000000000000001",
    "1111111111111111111111111111",
]]

PAC_START = (13.5, 17)
DOOR_COL = 13.5          # ghosts pass through the middle of the 2-tile door
HOUSE_EXIT_ROW = 8       # row just above the door
HOUSE_ROW = 10.5         # vertical middle of the house interior
FRUIT_POS = (13.5, 13)
TUNNEL_LEN = 6           # ghosts slow down in the outer 6 columns of a tunnel row


def build_maze(level):
    """Build the maze grid for a level, dropping any dot PacMan can't reach."""
    maze = [[int(ch) for ch in row] for row in MAZES[level % len(MAZES)]]
    seen = reachable(maze, int(PAC_START[0]), PAC_START[1])
    for r, row in enumerate(maze):
        for c, cell in enumerate(row):
            if cell in (0, 3) and (c, r) not in seen:
                row[c] = 4
    return maze


def reachable(maze, col, row):
    seen = {(col, row)}
    queue = deque([(col, row)])
    while queue:
        c, r = queue.popleft()
        for dx, dy in (UP, DOWN, LEFT, RIGHT):
            if not can_move(maze, c + dx, r + dy):
                continue
            n = ((c + dx) % COLS, r + dy)
            if n not in seen:
                seen.add(n)
                queue.append(n)
    return seen


# ---------------------------------------------------------------------------
# Helper: pixel <-> grid conversions
# ---------------------------------------------------------------------------
MAZE_OFFSET_Y = 4 * TILE  # top 4 rows reserved for HUD

def grid_to_pixel(col, row):
    """Grid cell -> pixel centre."""
    return col * TILE + TILE / 2, row * TILE + MAZE_OFFSET_Y + TILE / 2

def pixel_to_grid(x, y):
    """Pixel -> grid cell."""
    return int(x // TILE), int((y - MAZE_OFFSET_Y) // TILE)

def is_tunnel_row(maze, row):
    return 0 <= row < len(maze) and maze[row][0] == 7

def can_move(maze, col, row):
    """Return True if the cell at (col, row) is passable."""
    if row < 0 or row >= len(maze):
        return False
    # Off the side of the maze is only open on tunnel rows
    if col < 0 or col >= COLS:
        return is_tunnel_row(maze, row)
    return maze[row][col] not in (1, 5, 6)

def is_wall(maze, col, row):
    if row < 0 or row >= len(maze) or col < 0 or col >= COLS:
        return False
    return maze[row][col] == 1 or maze[row][col] == 5


EPS = 1e-4

def travel(actor, dist, choose):
    """Move `actor` up to `dist` pixels along the grid.

    Each time it lands on a tile centre, `choose(col, row)` returns the next
    direction (STOP halts it). Works for any speed, so actors never overshoot
    a junction.
    """
    for _ in range(8):
        if dist <= EPS:
            return
        u = (actor.x - TILE / 2) / TILE
        v = (actor.y - MAZE_OFFSET_Y - TILE / 2) / TILE
        cu, cv = round(u), round(v)
        if abs(u - cu) < EPS and abs(v - cv) < EPS:
            actor.x, actor.y = grid_to_pixel(cu, cv)
            actor.dir = choose(cu, cv)
            if actor.dir == STOP:
                return
            # Tunnel wrap: the virtual tiles -1 and COLS are the same place
            if cu == -1 and actor.dir == LEFT:
                actor.x = grid_to_pixel(COLS, cv)[0]
            elif cu == COLS and actor.dir == RIGHT:
                actor.x = grid_to_pixel(-1, cv)[0]
            step = min(dist, TILE)
        else:
            if actor.dir == STOP:
                return
            along = u if actor.dir[0] else v
            sign = actor.dir[0] or actor.dir[1]
            nxt = math.floor(along + EPS) + 1 if sign > 0 else math.ceil(along - EPS) - 1
            step = min(dist, abs(nxt - along) * TILE)
        actor.x += actor.dir[0] * step
        actor.y += actor.dir[1] * step
        dist -= step


def move_toward(actor, tx, ty, speed):
    """Move straight toward a point, x first then y (used inside the ghost house)."""
    if abs(actor.x - tx) > EPS:
        actor.dir = RIGHT if tx > actor.x else LEFT
        actor.x += actor.dir[0] * min(speed, abs(tx - actor.x))
        return False
    if abs(actor.y - ty) > EPS:
        actor.dir = DOWN if ty > actor.y else UP
        actor.y += actor.dir[1] * min(speed, abs(ty - actor.y))
        return False
    actor.x, actor.y = tx, ty
    return True


# ---------------------------------------------------------------------------
# Level tuning
# ---------------------------------------------------------------------------
def level_spec(level):
    i = min(level, 4)
    return {
        'pac':    [2.0, 2.2, 2.2, 2.2, 2.4][i],
        'ghost':  [1.9, 2.1, 2.1, 2.1, 2.3][i],
        'fright': max(120, 360 - level * 45),      # frames ghosts stay blue
        'elroy_dots': 20 + min(level, 6) * 5,      # Blinky speeds up when this few dots remain
    }

FRIGHT_SPEED, TUNNEL_SPEED, EYES_SPEED, HOUSE_SPEED = 1.2, 1.0, 4.8, 1.2
# Scatter/chase schedule in seconds; the last chase lasts forever.
MODE_SCHEDULE = [7, 20, 7, 20, 5, 20, 5, float('inf')]


# ---------------------------------------------------------------------------
# Sound (synthesised, so no asset files are needed)
# ---------------------------------------------------------------------------
class Sound:
    RATE = 22050

    def __init__(self):
        self.enabled = False
        self.muted = False
        self.waka_hi = False
        self.sounds = {}
        try:
            pygame.mixer.init(self.RATE, -16, 1)
            self.sounds = {
                'waka_hi': self._tone([(520, 380, 0.07)]),
                'waka_lo': self._tone([(380, 520, 0.07)]),
                'power':   self._tone([(200, 800, 0.35)], vol=0.25),
                'ghost':   self._tone([(300, 1400, 0.25)], vol=0.25),
                'fruit':   self._tone([(660, 660, 0.07), (880, 880, 0.07), (1100, 1100, 0.07)]),
                'life':    self._tone([(f, f, 0.09) for f in (880, 1100, 880, 1100, 1320)]),
                'death':   self._tone([(900, 60, 1.2)], vol=0.25),
                'clear':   self._tone([(f, f, 0.1) for f in (523, 659, 784, 1047)]),
                'start':   self._tone([(f, f, 0.13) for f in
                                       (494, 988, 740, 622, 988, 740, 622,
                                        523, 1047, 784, 659, 1047, 784, 659)]),
            }
            self.enabled = True
        except (pygame.error, NotImplementedError):
            pass

    def _tone(self, notes, vol=0.3):
        """Build a square-wave sound from (start_hz, end_hz, seconds) segments."""
        buf = array.array('h')
        for f0, f1, dur in notes:
            n = int(self.RATE * dur)
            phase = 0.0
            for i in range(n):
                t = i / n
                phase += (f0 * (f1 / f0) ** t) / self.RATE
                env = (1 - t) ** 2
                buf.append(int(32767 * vol * env * (1 if phase % 1 < 0.5 else -1)))
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if not self.enabled or self.muted:
            return
        if name == 'waka':
            self.waka_hi = not self.waka_hi
            name = 'waka_hi' if self.waka_hi else 'waka_lo'
        self.sounds[name].play()


# ---------------------------------------------------------------------------
# Draw helpers
# ---------------------------------------------------------------------------
def draw_rounded_wall_segment(surface, col, row, maze):
    """Draw a wall tile with rounded aesthetics."""
    x = col * TILE
    y = row * TILE + MAZE_OFFSET_Y
    rect = pygame.Rect(x, y, TILE, TILE)

    # Main wall colour
    pygame.draw.rect(surface, WALL_BLUE, rect)

    # Inner darker rect for depth
    inner = rect.inflate(-4, -4)
    pygame.draw.rect(surface, DARK_BLUE, inner)

    # Edges: draw bright borders towards empty cells
    for dx, dy in [UP, DOWN, LEFT, RIGHT]:
        nc, nr = col + dx, row + dy
        if not is_wall(maze, nc, nr):
            if dx == -1:
                pygame.draw.line(surface, WALL_HIGHLIGHT, (x + 1, y), (x + 1, y + TILE - 1), 2)
            elif dx == 1:
                pygame.draw.line(surface, WALL_HIGHLIGHT, (x + TILE - 2, y), (x + TILE - 2, y + TILE - 1), 2)
            elif dy == -1:
                pygame.draw.line(surface, WALL_HIGHLIGHT, (x, y + 1), (x + TILE - 1, y + 1), 2)
            elif dy == 1:
                pygame.draw.line(surface, WALL_HIGHLIGHT, (x, y + TILE - 2), (x + TILE - 1, y + TILE - 2), 2)


def draw_ghost_door(surface, col, row):
    """Draw the ghost house door."""
    x = col * TILE
    y = row * TILE + MAZE_OFFSET_Y
    pygame.draw.rect(surface, PINK, (x, y + TILE // 2 - 2, TILE, 4))


# ---------------------------------------------------------------------------
# PacMan class
# ---------------------------------------------------------------------------
class PacMan:
    def __init__(self, col, row):
        self.start_col = col
        self.start_row = row
        self.reset()

    def reset(self):
        self.x, self.y = grid_to_pixel(self.start_col, self.start_row)
        self.dir = LEFT
        self.face = LEFT
        self.next_dir = STOP
        self.speed = 2
        self.anim_timer = 0
        self.mouth_angle = 0  # 0..45 degrees
        self.mouth_opening = True
        self.alive = True
        self.death_frame = 0

    def set_direction(self, d):
        self.next_dir = d

    def _choose(self, maze, col, row):
        if self.next_dir != STOP and can_move(maze, col + self.next_dir[0], row + self.next_dir[1]):
            return self.next_dir
        if self.dir != STOP and can_move(maze, col + self.dir[0], row + self.dir[1]):
            return self.dir
        return STOP

    def update(self, maze):
        if not self.alive:
            return

        # Reversing is allowed anywhere; other turns wait for the next tile centre
        if self.next_dir != STOP and self.next_dir == (-self.dir[0], -self.dir[1]):
            self.dir = self.next_dir

        before = (self.x, self.y)
        travel(self, self.speed, lambda c, r: self._choose(maze, c, r))
        if self.dir != STOP:
            self.face = self.dir

        # Animate mouth only while moving
        if (self.x, self.y) != before:
            self.anim_timer += 1
            if self.anim_timer % 3 == 0:
                if self.mouth_opening:
                    self.mouth_angle += 8
                    if self.mouth_angle >= 45:
                        self.mouth_opening = False
                else:
                    self.mouth_angle -= 8
                    if self.mouth_angle <= 5:
                        self.mouth_opening = True

    def draw(self, surface):
        if not self.alive:
            self._draw_death(surface)
            return

        # Determine start angle based on facing
        if self.face == LEFT:
            start = 180 + self.mouth_angle
        elif self.face == UP:
            start = 90 + self.mouth_angle
        elif self.face == DOWN:
            start = 270 + self.mouth_angle
        else:
            start = self.mouth_angle

        extent = 360 - 2 * self.mouth_angle
        if extent <= 0:
            extent = 1

        r = TILE // 2 + 2
        # Draw filled arc (pie shape)
        start_rad = math.radians(start)
        end_rad = math.radians(start + extent)

        points = [(self.x, self.y)]
        steps = 20
        for i in range(steps + 1):
            angle = start_rad + (end_rad - start_rad) * i / steps
            px = self.x + r * math.cos(angle)
            py = self.y - r * math.sin(angle)
            points.append((px, py))

        if len(points) > 2:
            pygame.draw.polygon(surface, YELLOW, points)

    def _draw_death(self, surface):
        """Death animation - pacman shrinks."""
        r = TILE // 2 + 2
        progress = self.death_frame / 60
        if progress > 1:
            progress = 1

        start_angle = 90 * progress
        extent = 360 - 360 * progress
        if extent <= 0:
            return

        start_rad = math.radians(start_angle)
        end_rad = math.radians(start_angle + extent)
        points = [(self.x, self.y)]
        steps = 20
        for i in range(steps + 1):
            angle = start_rad + (end_rad - start_rad) * i / steps
            px = self.x + r * math.cos(angle)
            py = self.y - r * math.sin(angle)
            points.append((px, py))

        if len(points) > 2:
            pygame.draw.polygon(surface, YELLOW, points)


# ---------------------------------------------------------------------------
# Ghost class
# ---------------------------------------------------------------------------
class Ghost:
    NAMES = ['blinky', 'pinky', 'inky', 'clyde']
    COLORS = {
        'blinky': RED,
        'pinky': PINK,
        'inky': CYAN,
        'clyde': ORANGE,
    }
    SCATTER_TARGETS = {
        'blinky': (25, -3),
        'pinky': (2, -3),
        'inky': (27, 24),
        'clyde': (0, 24),
    }
    # A ghost leaves the house once enough dots are eaten, or after a time-out
    RELEASE = {
        'blinky': (0, 0),
        'pinky': (0, 60),
        'inky': (30, 240),
        'clyde': (60, 480),
    }

    def __init__(self, name, col, row):
        self.name = name
        self.color = self.COLORS[name]
        self.start_col = col
        self.start_row = row
        self.reset()

    def reset(self):
        self.x, self.y = grid_to_pixel(self.start_col, self.start_row)
        in_house = self.name != 'blinky'
        self.state = GhostState.HOUSE if in_house else GhostState.ACTIVE
        self.dir = UP if in_house else LEFT
        self.fright = 0
        self.reverse = False
        self.house_timer = 0
        self.anim_timer = 0

    @property
    def frightened(self):
        return self.fright > 0

    @property
    def edible(self):
        return self.frightened and self.state in (GhostState.ACTIVE, GhostState.LEAVING)

    @property
    def harmful(self):
        return not self.frightened and self.state in (GhostState.ACTIVE, GhostState.LEAVING)

    def frighten(self, frames):
        if self.state in (GhostState.EATEN, GhostState.ENTERING):
            return
        self.fright = frames
        if self.state == GhostState.ACTIVE:
            self.reverse = True

    def get_target(self, pacman, blinky_pos, mode, elroy):
        """Determine target tile based on ghost AI personality."""
        if self.state == GhostState.EATEN:
            return (int(DOOR_COL), HOUSE_EXIT_ROW)

        pac_col, pac_row = pixel_to_grid(pacman.x, pacman.y)

        if mode == 'scatter' and not (elroy and self.name == 'blinky'):
            return self.SCATTER_TARGETS[self.name]

        # Chase mode - each ghost has unique targeting
        if self.name == 'blinky':
            # Directly targets PacMan
            return (pac_col, pac_row)

        elif self.name == 'pinky':
            # Targets 4 tiles ahead of PacMan
            return (pac_col + pacman.dir[0] * 4, pac_row + pacman.dir[1] * 4)

        elif self.name == 'inky':
            # Complex: uses Blinky's position
            ahead_col = pac_col + pacman.dir[0] * 2
            ahead_row = pac_row + pacman.dir[1] * 2
            bx, by = blinky_pos
            return (ahead_col + (ahead_col - bx), ahead_row + (ahead_row - by))

        else:  # clyde
            # If far from PacMan: chase; if close: retreat to his corner
            gc, gr = pixel_to_grid(self.x, self.y)
            if math.hypot(pac_col - gc, pac_row - gr) > 8:
                return (pac_col, pac_row)
            return self.SCATTER_TARGETS['clyde']

    def _speed(self, maze, spec, elroy):
        if self.state == GhostState.EATEN:
            return EYES_SPEED
        c, r = pixel_to_grid(self.x, self.y)
        if is_tunnel_row(maze, r) and (c < TUNNEL_LEN or c >= COLS - TUNNEL_LEN):
            return TUNNEL_SPEED
        if self.frightened:
            return FRIGHT_SPEED
        if elroy and self.name == 'blinky':
            return spec['ghost'] + 0.25
        return spec['ghost']

    def _choose(self, maze, col, row, pacman, blinky_pos, mode, elroy):
        if self.state == GhostState.EATEN and row == HOUSE_EXIT_ROW and abs(col - DOOR_COL) <= 0.5:
            self.state = GhostState.ENTERING   # reached the door - drop into the house
            return STOP

        opposite = (-self.dir[0], -self.dir[1])
        if self.reverse:
            self.reverse = False
            if can_move(maze, col + opposite[0], row + opposite[1]):
                return opposite

        # No reversing on a normal turn
        possible = [d for d in (UP, LEFT, DOWN, RIGHT)
                    if d != opposite and can_move(maze, col + d[0], row + d[1])]
        if not possible:
            possible = [opposite] if can_move(maze, col + opposite[0], row + opposite[1]) else []
        if not possible:
            return STOP

        if self.frightened and self.state != GhostState.EATEN:
            return random.choice(possible)

        # Pick direction that minimises distance to target
        tx, ty = self.get_target(pacman, blinky_pos, mode, elroy)
        return min(possible, key=lambda d: (col + d[0] - tx) ** 2 + (row + d[1] - ty) ** 2)

    def update(self, maze, pacman, blinky_pos, mode, dots_eaten, level, spec, elroy):
        self.anim_timer += 1
        if self.fright > 0:
            self.fright -= 1
        door_x, exit_y = grid_to_pixel(DOOR_COL, HOUSE_EXIT_ROW)
        house_y = grid_to_pixel(DOOR_COL, HOUSE_ROW)[1]

        if self.state == GhostState.HOUSE:
            # Bob up and down in house
            self.house_timer += 1
            self.y = grid_to_pixel(self.start_col, self.start_row)[1] + math.sin(self.anim_timer * 0.1) * 4
            self.dir = DOWN if math.cos(self.anim_timer * 0.1) > 0 else UP
            dots, delay = self.RELEASE[self.name]
            if level > 0:
                dots //= 2
            if self.house_timer >= delay and (dots_eaten >= dots or self.house_timer >= delay + 600):
                self.state = GhostState.LEAVING
            return

        if self.state == GhostState.LEAVING:
            # Line up with the door, then float up through it
            at_door = abs(self.x - door_x) < EPS
            if move_toward(self, door_x, exit_y if at_door else self.y, HOUSE_SPEED):
                self.state = GhostState.ACTIVE
                self.dir = LEFT
                self.reverse = False
            return

        if self.state == GhostState.ENTERING:
            if move_toward(self, door_x, house_y, EYES_SPEED / 2):
                self.state = GhostState.LEAVING
            return

        travel(self, self._speed(maze, spec, elroy),
               lambda c, r: self._choose(maze, c, r, pacman, blinky_pos, mode, elroy))

    def draw(self, surface):
        if self.state in (GhostState.EATEN, GhostState.ENTERING):
            self._draw_eyes(surface)
            return

        # Body colour
        flash = self.frightened and self.fright < 120 and (self.fright // 15) % 2 == 0
        if self.frightened:
            color = GHOST_WHITE if flash else GHOST_BLUE
        else:
            color = self.color

        cx, cy = int(self.x), int(self.y)
        r = TILE // 2 + 1

        # Ghost body: semicircle top + straight sides + wavy feet
        pygame.draw.circle(surface, color, (cx, cy - 2), r, draw_top_left=True, draw_top_right=True)
        bottom = cy + r - 1
        points = [(cx - r, cy - 2), (cx + r, cy - 2), (cx + r, bottom)]
        n, w = 4, 2 * r / 4
        wave_offset = (self.anim_timer // 8) % 2
        for i in range(n):
            x0 = cx + r - i * w
            points.append((x0 - w / 2, bottom - (4 if (i + wave_offset) % 2 else 0)))
            points.append((x0 - w, bottom))
        pygame.draw.polygon(surface, color, points)

        if self.frightened:
            # Scared face
            face = RED if flash else (255, 184, 174)
            pygame.draw.rect(surface, face, (cx - 5, cy - 5, 3, 3))
            pygame.draw.rect(surface, face, (cx + 2, cy - 5, 3, 3))
            mouth = [(cx - 6 + i * 3, cy + 4 + (-1.5 if i % 2 == 0 else 1.5)) for i in range(5)]
            pygame.draw.lines(surface, face, False, mouth, 1)
            return

        self._draw_eyes(surface)

    def _draw_eyes(self, surface):
        """Draw ghost eyes that look toward movement direction."""
        cx, cy = int(self.x), int(self.y)

        for side in [-1, 1]:
            ex = cx + side * 4
            ey = cy - 3

            # White of eye
            pygame.draw.ellipse(surface, WHITE, (ex - 4, ey - 3, 8, 7))

            # Pupil - offset by direction
            px = ex + self.dir[0] * 2
            py = ey + self.dir[1] * 2
            pygame.draw.circle(surface, (33, 33, 222), (px, py), 2)


# ---------------------------------------------------------------------------
# Fruit class
# ---------------------------------------------------------------------------
FRUIT_DATA = [
    {'name': 'cherry',     'color': FRUIT_RED,   'points': 100},
    {'name': 'strawberry', 'color': FRUIT_RED,   'points': 300},
    {'name': 'orange',     'color': ORANGE,      'points': 500},
    {'name': 'apple',      'color': FRUIT_RED,   'points': 700},
    {'name': 'melon',      'color': FRUIT_GREEN, 'points': 1000},
]
FRUIT_AT_DOTS = (70, 170)


def fruit_for(level):
    return FRUIT_DATA[min(level, len(FRUIT_DATA) - 1)]


def draw_fruit(surface, data, x, y, r):
    pygame.draw.circle(surface, data['color'], (int(x), int(y)), r)
    # Stem
    pygame.draw.line(surface, FRUIT_GREEN, (x, y - r), (x + 2, y - r - 4), 2)
    # Highlight
    pygame.draw.circle(surface, WHITE, (int(x - r / 4), int(y - r / 4)), max(1, r // 5))


class Fruit:
    def __init__(self, col, row, level):
        self.x, self.y = grid_to_pixel(col, row)
        self.data = fruit_for(level)
        self.timer = 570  # ~9.5 seconds
        self.active = True

    def update(self):
        if self.active:
            self.timer -= 1
            if self.timer <= 0:
                self.active = False

    def draw(self, surface):
        if self.active:
            draw_fruit(surface, self.data, self.x, self.y, TILE // 2 - 2)


# ---------------------------------------------------------------------------
# Floating Score (ghost combos, fruit, extra life)
# ---------------------------------------------------------------------------
class FloatingScore:
    def __init__(self, x, y, points, color=CYAN):
        self.x = x
        self.y = y
        self.points = points
        self.color = color
        self.timer = 60

    def update(self):
        self.timer -= 1
        self.y -= 0.3

    def draw(self, surface, font):
        if self.timer > 0:
            txt = font.render(str(self.points), True, self.color)
            surface.blit(txt, (self.x - txt.get_width() // 2, int(self.y) - txt.get_height() // 2))


# ---------------------------------------------------------------------------
# Main Game class
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        self.sound = Sound()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("PacMan")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 24)
        self.font_tiny = pygame.font.Font(None, 20)

        self.high_score, self.sound.muted = self._load_save()
        self.tick = 0
        self.new_game()
        self.state = GameState.TITLE

    # -- persistence --------------------------------------------------------
    def _load_save(self):
        try:
            with open(SAVE_FILE) as f:
                data = json.load(f)
            return int(data.get('high_score', 0)), bool(data.get('muted', False))
        except (OSError, ValueError, AttributeError):
            return 0, False

    def _save(self):
        try:
            with open(SAVE_FILE, 'w') as f:
                json.dump({'high_score': self.high_score, 'muted': self.sound.muted}, f)
        except OSError:
            pass

    # -- game flow ----------------------------------------------------------
    def new_game(self):
        self.score = 0
        self.lives = 3
        self.level = 0
        self.extra_life_given = False
        self.paused = False
        self._start_level()

    def _start_level(self):
        self.maze = build_maze(self.level)
        self.total_dots = self._count_dots()
        self.dots_eaten = 0
        self.fruits_shown = 0
        self.pacman = PacMan(*PAC_START)
        self._reset_positions()

    def _init_ghosts(self):
        self.ghosts = [
            Ghost('blinky', DOOR_COL, HOUSE_EXIT_ROW),
            Ghost('pinky', DOOR_COL, HOUSE_ROW),
            Ghost('inky', DOOR_COL - 2, HOUSE_ROW),
            Ghost('clyde', DOOR_COL + 2, HOUSE_ROW),
        ]

    def _count_dots(self):
        return sum(cell in (0, 3) for row in self.maze for cell in row)

    def _reset_positions(self):
        self.pacman.reset()
        self._init_ghosts()
        self.ghost_eat_combo = 0
        self.floating_scores = []
        self.fruit = None
        self.mode_index = 0
        self.mode_timer = 0
        self.mode = 'scatter'
        self.fright_timer = 0
        self.freeze_timer = 0
        self.level_flash_timer = 0
        self.state = GameState.READY
        self.ready_timer = 120

    def _add_score(self, points):
        self.score += points
        if self.score > self.high_score:
            self.high_score = self.score
        if not self.extra_life_given and self.score >= EXTRA_LIFE_AT:
            self.extra_life_given = True
            self.lives += 1
            self.floating_scores.append(FloatingScore(WIDTH // 2, MAZE_OFFSET_Y + TILE * 6, '1UP!', YELLOW))
            self.sound.play('life')

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.WINDOWFOCUSLOST and self.state in (GameState.READY, GameState.PLAYING):
                self.paused = True
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_ESCAPE and self.state in (GameState.TITLE, GameState.GAME_OVER):
                return False
            if event.key == pygame.K_m:
                self.sound.muted = not self.sound.muted
                self._save()
            elif self.state in (GameState.TITLE, GameState.GAME_OVER):
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self.new_game()
                    self.ready_timer = 150
                    self.sound.play('start')
            elif event.key in (pygame.K_p, pygame.K_ESCAPE, pygame.K_SPACE):
                self.paused = not self.paused
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.pacman.set_direction(UP)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.pacman.set_direction(DOWN)
            elif event.key in (pygame.K_LEFT, pygame.K_a):
                self.pacman.set_direction(LEFT)
            elif event.key in (pygame.K_RIGHT, pygame.K_d):
                self.pacman.set_direction(RIGHT)
        return True

    def update(self):
        self.tick += 1
        if self.state in (GameState.TITLE, GameState.GAME_OVER) or self.paused:
            return

        if self.state == GameState.READY:
            self.ready_timer -= 1
            if self.ready_timer <= 0:
                self.state = GameState.PLAYING
            return

        if self.state == GameState.DYING:
            self.pacman.death_frame += 1
            if self.pacman.death_frame >= 60:
                self.lives -= 1
                if self.lives <= 0:
                    self.state = GameState.GAME_OVER
                    self._save()
                else:
                    self._reset_positions()
            return

        if self.state == GameState.LEVEL_COMPLETE:
            self.level_flash_timer -= 1
            if self.level_flash_timer <= 0:
                self.level += 1
                self._start_level()
            return

        if self.state != GameState.PLAYING:
            return

        # Short freeze after eating a ghost
        if self.freeze_timer > 0:
            self.freeze_timer -= 1
            self._update_floating_scores()
            return

        spec = level_spec(self.level)

        # Scatter/chase schedule (paused while ghosts are frightened)
        if self.fright_timer > 0:
            self.fright_timer -= 1
        else:
            self.mode_timer += 1
            if self.mode_timer >= MODE_SCHEDULE[self.mode_index] * FPS:
                self.mode_index += 1
                self.mode_timer = 0
                self.mode = 'scatter' if self.mode_index % 2 == 0 else 'chase'
                for g in self.ghosts:
                    if g.state == GhostState.ACTIVE:
                        g.reverse = True

        # Update PacMan
        self.pacman.speed = spec['pac']
        self.pacman.update(self.maze)

        # Check dot eating
        pc, pr = pixel_to_grid(self.pacman.x, self.pacman.y)
        if 0 <= pr < len(self.maze) and 0 <= pc < COLS:
            cell = self.maze[pr][pc]
            if cell == 0:  # dot
                self.maze[pr][pc] = 4
                self._add_score(10)
                self.dots_eaten += 1
                self.sound.play('waka')
            elif cell == 3:  # power pellet
                self.maze[pr][pc] = 4
                self._add_score(50)
                self.dots_eaten += 1
                self.ghost_eat_combo = 0
                self.fright_timer = spec['fright']
                for g in self.ghosts:
                    g.frighten(spec['fright'])
                self.sound.play('power')

        # Fruit appears twice per level
        if self.fruits_shown < len(FRUIT_AT_DOTS) and self.dots_eaten >= FRUIT_AT_DOTS[self.fruits_shown]:
            self.fruit = Fruit(FRUIT_POS[0], FRUIT_POS[1], self.level)
            self.fruits_shown += 1

        if self.fruit:
            self.fruit.update()
            if self.fruit.active and math.hypot(self.pacman.x - self.fruit.x,
                                                self.pacman.y - self.fruit.y) < TILE / 2 + 2:
                self._add_score(self.fruit.data['points'])
                self.fruit.active = False
                self.floating_scores.append(FloatingScore(self.fruit.x, self.fruit.y,
                                                          self.fruit.data['points'], WHITE))
                self.sound.play('fruit')

        # Update ghosts
        elroy = self.total_dots - self.dots_eaten <= spec['elroy_dots']
        blinky_pos = pixel_to_grid(self.ghosts[0].x, self.ghosts[0].y)
        for ghost in self.ghosts:
            ghost.update(self.maze, self.pacman, blinky_pos, self.mode,
                         self.dots_eaten, self.level, spec, elroy)

            # Check collision with PacMan
            if math.hypot(ghost.x - self.pacman.x, ghost.y - self.pacman.y) >= TILE * 0.75:
                continue
            if ghost.edible:
                ghost.state = GhostState.EATEN
                ghost.fright = 0
                self.ghost_eat_combo += 1
                points = 200 * (2 ** (self.ghost_eat_combo - 1))
                self._add_score(points)
                self.floating_scores.append(FloatingScore(ghost.x, ghost.y, points))
                self.freeze_timer = 30
                self.sound.play('ghost')
            elif ghost.harmful:
                self.pacman.alive = False
                self.state = GameState.DYING
                self.pacman.death_frame = 0
                self.sound.play('death')
                return

        self._update_floating_scores()

        # Check level complete
        if self.dots_eaten >= self.total_dots:
            self.state = GameState.LEVEL_COMPLETE
            self.level_flash_timer = 120
            self.sound.play('clear')

    def _update_floating_scores(self):
        for fs in self.floating_scores:
            fs.update()
        self.floating_scores = [fs for fs in self.floating_scores if fs.timer > 0]

    def draw(self):
        self.screen.fill(BLACK)

        # Draw maze
        flash = self.state == GameState.LEVEL_COMPLETE and (self.level_flash_timer // 15) % 2 == 0
        for row_idx, row in enumerate(self.maze):
            for col_idx, cell in enumerate(row):
                x = col_idx * TILE
                y = row_idx * TILE + MAZE_OFFSET_Y

                if cell in (1, 5):
                    if flash:
                        pygame.draw.rect(self.screen, WHITE, (x, y, TILE, TILE))
                        inner = pygame.Rect(x + 2, y + 2, TILE - 4, TILE - 4)
                        pygame.draw.rect(self.screen, BLACK, inner)
                    else:
                        draw_rounded_wall_segment(self.screen, col_idx, row_idx, self.maze)
                elif cell == 6:
                    if not flash:
                        draw_ghost_door(self.screen, col_idx, row_idx)
                elif cell == 0:
                    # Dot
                    pygame.draw.circle(self.screen, DOT_COLOR, (x + TILE // 2, y + TILE // 2), 2)
                elif cell == 3:
                    # Power pellet (pulsing)
                    pulse = abs(math.sin(self.tick * 0.08)) * 3 + 4
                    pygame.draw.circle(self.screen, DOT_COLOR, (x + TILE // 2, y + TILE // 2), int(pulse))

        if self.state != GameState.TITLE:
            if self.fruit:
                self.fruit.draw(self.screen)
            self.pacman.draw(self.screen)
            # Ghosts hide while PacMan dies and while the maze flashes
            if self.state not in (GameState.LEVEL_COMPLETE, GameState.DYING):
                for ghost in self.ghosts:
                    ghost.draw(self.screen)
            for fs in self.floating_scores:
                fs.draw(self.screen, self.font_tiny)

        # HUD
        self._draw_hud()

        # Overlay text
        mid_y = MAZE_OFFSET_Y + int(13.5 * TILE)   # the open row under the ghost house
        if self.state == GameState.TITLE:
            self._dim()
            self._center(self.font_large, "PAC-MAN", YELLOW, HEIGHT // 2 - 90)
            lines = [("Arrows / WASD : move", WHITE),
                     ("P / Esc / Space : pause    M : mute", WHITE),
                     (f"Extra life at {EXTRA_LIFE_AT} points", CYAN)]
            for i, (text, color) in enumerate(lines):
                self._center(self.font_small, text, color, HEIGHT // 2 - 40 + i * 26)
            self._blink("Press ENTER to start", HEIGHT // 2 + 60)

        elif self.state == GameState.READY:
            self._center(self.font_medium, "READY!", YELLOW, mid_y - 10)

        elif self.state == GameState.LEVEL_COMPLETE:
            self._center(self.font_medium, f"LEVEL {self.level + 1} CLEAR!", YELLOW, mid_y - 10)

        elif self.state == GameState.GAME_OVER:
            self._dim()
            self._center(self.font_large, "GAME OVER", RED, HEIGHT // 2 - 40)
            self._center(self.font_medium, f"Score: {self.score}", WHITE, HEIGHT // 2 + 10)
            self._blink("Press ENTER to restart", HEIGHT // 2 + 50)

        if self.paused:
            self._dim()
            self._center(self.font_large, "PAUSED", YELLOW, HEIGHT // 2 - 20)
            self._blink("Press P to resume", HEIGHT // 2 + 30)

        pygame.display.flip()

    def _dim(self):
        overlay = pygame.Surface((WIDTH, HEIGHT - MAZE_OFFSET_Y), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 165))
        self.screen.blit(overlay, (0, MAZE_OFFSET_Y))

    def _center(self, font, text, color, y):
        txt = font.render(text, True, color)
        self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, y))

    def _blink(self, text, y):
        txt = self.font_small.render(text, True, WHITE)
        txt.set_alpha(int(abs(math.sin(self.tick * 0.05)) * 255))
        self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, y))

    def _draw_hud(self):
        """Draw score, lives, and level info at top."""
        # Background bar
        pygame.draw.rect(self.screen, HUD_BG, (0, 0, WIDTH, MAZE_OFFSET_Y))

        # Score
        score_txt = self.font_medium.render(f"SCORE  {self.score:>8}", True, WHITE)
        self.screen.blit(score_txt, (10, 8))

        # High Score
        hi_txt = self.font_small.render(f"HIGH SCORE  {self.high_score:>8}", True, (180, 180, 180))
        self.screen.blit(hi_txt, (WIDTH // 2 - hi_txt.get_width() // 2, 40))

        # Level
        lvl_txt = self.font_small.render(f"LEVEL {self.level + 1}", True, CYAN)
        self.screen.blit(lvl_txt, (WIDTH - lvl_txt.get_width() - 10, 8))
        if self.sound.muted:
            mute_txt = self.font_tiny.render("MUTED", True, (136, 136, 136))
            self.screen.blit(mute_txt, (WIDTH - mute_txt.get_width() - 10, 32))

        # Lives (draw small pacmans)
        for i in range(self.lives - 1):
            lx = 20 + i * 28
            ly = MAZE_OFFSET_Y - 20
            # Mini pacman
            points = [(lx, ly)]
            for j in range(16):
                angle = math.radians(30 + (300 * j / 15))
                points.append((lx + 9 * math.cos(angle), ly - 9 * math.sin(angle)))
            pygame.draw.polygon(self.screen, YELLOW, points)

        # Fruits of the levels reached (most recent 7)
        for i in range(min(7, self.level + 1)):
            draw_fruit(self.screen, fruit_for(self.level - i), WIDTH - 20 - i * 26, MAZE_OFFSET_Y - 20, 8)

        # Separator line
        pygame.draw.line(self.screen, WALL_BLUE, (0, MAZE_OFFSET_Y - 1), (WIDTH, MAZE_OFFSET_Y - 1), 1)

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

        self._save()
        pygame.quit()
        sys.exit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    game = Game()
    game.run()
