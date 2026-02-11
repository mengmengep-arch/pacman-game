"""
PacMan - A Beautiful Retro PacMan Game
Built with Pygame | Classic mechanics + Modern aesthetics
"""

import pygame
import sys
import math
import random
from enum import Enum, auto
from collections import deque

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TILE = 24
COLS, ROWS = 28, 36
WIDTH, HEIGHT = COLS * TILE, ROWS * TILE
FPS = 60

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
    SCATTER = auto()
    CHASE   = auto()
    FRIGHTENED = auto()
    EATEN   = auto()
    IN_HOUSE = auto()

# Game states
class GameState(Enum):
    READY     = auto()
    PLAYING   = auto()
    DYING     = auto()
    GAME_OVER = auto()
    WIN       = auto()
    LEVEL_COMPLETE = auto()

# ---------------------------------------------------------------------------
# Maze layout  (28 x 31 playfield, rows 0-4 are HUD area)
# 1=wall, 0=dot, 3=power pellet, 4=empty, 5=ghost house wall,
# 6=ghost door, 7=tunnel
# ---------------------------------------------------------------------------
MAZE_TEMPLATE = [
    "1111111111111111111111111111",
    "1000000000001110000000000001",
    "1031101111001110011110131001",
    "1001101111001110011110010001",
    "1000000000000000000000000001",
    "1001101001111111001011001001",
    "1000000001110111000000000001",
    "1111101111004001111011111001",  # note: row with side tunnels will be handled
    "4441101111004001111011004441",
    "1111100004440044400001111111",
    "4441100115555551100011004441",
    "7770004010000000104000007770",  # tunnel row
    "4441100101000000100011004441",
    "1111100400555555004001111111",
    "4441100400000000004001104441",
    "1111101001111111001011111111",
    "1000000000001110000000000001",
    "1031101111001110011110130001",
    "1000110000000040000000110001",
    "1101110010011110010011011001",  # note: adjusted
    "1000000010001110010000000001",
    "1011111110011110011111110001",
    "1000000000000000000000000001",
    "1111111111111111111111111111",
]

# Rebuild into a proper classic-style maze
CLASSIC_MAZE = [
    "1111111111111111111111111111",
    "1000000000001110000000000001",
    "1011101111001110011110111001",
    "1311100000000000000000013001",
    "1011101011111111101011101001",
    "1000000010001110010000000001",
    "1011101110011110011101110001",
    "1011100000001110000000110001",
    "1000001011104401011010000001",
    "1111001010044040010100111111",
    "7770001010555555010100007770",
    "1111001000500005000100111111",
    "7770001010500005010100007770",
    "1111001010555555010100111111",
    "4444000000044040000000004444",
    "1111001011111111101001111111",
    "1000000000001110000000000001",
    "1011101111001110011110111001",
    "1300100000000400000000010031",
    "1110101011111111101011010111",
    "1000000010001110010000000001",
    "1011111110011110011111110001",
    "1000000000000000000000000001",
    "1111111111111111111111111111",
]


def build_maze():
    """Build the maze grid from the template."""
    maze = []
    for row_str in CLASSIC_MAZE:
        row = []
        for ch in row_str:
            row.append(int(ch))
        maze.append(row)
    return maze


# ---------------------------------------------------------------------------
# Helper: pixel <-> grid conversions
# ---------------------------------------------------------------------------
MAZE_OFFSET_Y = 4 * TILE  # top 4 rows reserved for HUD

def grid_to_pixel(col, row):
    """Grid cell -> pixel centre."""
    return col * TILE + TILE // 2, row * TILE + MAZE_OFFSET_Y + TILE // 2

def pixel_to_grid(x, y):
    """Pixel -> grid cell."""
    return int(x // TILE), int((y - MAZE_OFFSET_Y) // TILE)

def can_move(maze, col, row):
    """Return True if the cell at (col, row) is passable."""
    if row < 0 or row >= len(maze):
        return False
    # Wrap horizontally for tunnels
    if col < 0 or col >= COLS:
        return True  # tunnel
    cell = maze[row][col]
    return cell != 1 and cell != 5

def is_wall(maze, col, row):
    if row < 0 or row >= len(maze) or col < 0 or col >= COLS:
        return False
    return maze[row][col] == 1 or maze[row][col] == 5


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
        self.dir = STOP
        self.next_dir = STOP
        self.speed = 2
        self.anim_frame = 0
        self.anim_timer = 0
        self.mouth_angle = 0  # 0..45 degrees
        self.mouth_opening = True
        self.alive = True
        self.death_frame = 0

    def set_direction(self, d):
        self.next_dir = d

    def update(self, maze):
        if not self.alive:
            return

        # Animate mouth
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

        # Check if aligned to grid
        cx, cy = pixel_to_grid(self.x, self.y)
        px, py = grid_to_pixel(cx, cy)

        at_center = abs(self.x - px) <= self.speed and abs(self.y - py) <= self.speed

        if at_center:
            self.x, self.y = px, py
            # Try next direction first
            ncol = cx + self.next_dir[0]
            nrow = cy + self.next_dir[1]
            if can_move(maze, ncol, nrow):
                self.dir = self.next_dir

            # Check current direction
            ncol2 = cx + self.dir[0]
            nrow2 = cy + self.dir[1]
            if not can_move(maze, ncol2, nrow2):
                self.dir = STOP

        if self.dir != STOP:
            self.x += self.dir[0] * self.speed
            self.y += self.dir[1] * self.speed

        # Tunnel wrap
        if self.x < -TILE // 2:
            self.x = COLS * TILE + TILE // 2
        elif self.x > COLS * TILE + TILE // 2:
            self.x = -TILE // 2

    def draw(self, surface):
        if not self.alive:
            self._draw_death(surface)
            return

        # Determine start angle based on direction
        if self.dir == RIGHT or self.dir == STOP:
            start = self.mouth_angle
        elif self.dir == LEFT:
            start = 180 + self.mouth_angle
        elif self.dir == UP:
            start = 90 + self.mouth_angle
        elif self.dir == DOWN:
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
        'blinky': (25, 0),
        'pinky': (2, 0),
        'inky': (27, 23),
        'clyde': (0, 23),
    }

    def __init__(self, name, col, row, house_col, house_row):
        self.name = name
        self.color = self.COLORS[name]
        self.start_col = col
        self.start_row = row
        self.house_col = house_col
        self.house_row = house_row
        self.release_dots = {'blinky': 0, 'pinky': 7, 'inky': 17, 'clyde': 32}
        self.reset()

    def reset(self):
        self.x, self.y = grid_to_pixel(self.start_col, self.start_row)
        self.dir = UP
        self.speed = 2
        self.state = GhostState.IN_HOUSE if self.name != 'blinky' else GhostState.SCATTER
        self.frightened_timer = 0
        self.frightened_flash = False
        self.anim_frame = 0
        self.anim_timer = 0
        if self.name == 'blinky':
            self.x, self.y = grid_to_pixel(self.start_col, self.start_row)
            self.state = GhostState.SCATTER

    def get_target(self, pacman, blinky_pos, mode):
        """Determine target tile based on ghost AI personality."""
        pac_col, pac_row = pixel_to_grid(pacman.x, pacman.y)

        if self.state == GhostState.SCATTER:
            return self.SCATTER_TARGETS[self.name]

        if self.state == GhostState.FRIGHTENED:
            return (random.randint(0, COLS - 1), random.randint(0, len(CLASSIC_MAZE) - 1))

        if self.state == GhostState.EATEN:
            return (self.house_col, self.house_row)

        # Chase mode - each ghost has unique targeting
        if self.name == 'blinky':
            # Directly targets PacMan
            return (pac_col, pac_row)

        elif self.name == 'pinky':
            # Targets 4 tiles ahead of PacMan
            target_col = pac_col + pacman.dir[0] * 4
            target_row = pac_row + pacman.dir[1] * 4
            return (target_col, target_row)

        elif self.name == 'inky':
            # Complex: uses Blinky's position
            ahead_col = pac_col + pacman.dir[0] * 2
            ahead_row = pac_row + pacman.dir[1] * 2
            bx, by = blinky_pos
            target_col = ahead_col + (ahead_col - bx)
            target_row = ahead_row + (ahead_row - by)
            return (target_col, target_row)

        else:  # clyde
            # If far from PacMan: chase; if close: scatter
            dist = math.sqrt((pac_col - pixel_to_grid(self.x, self.y)[0]) ** 2 +
                             (pac_row - pixel_to_grid(self.x, self.y)[1]) ** 2)
            if dist > 8:
                return (pac_col, pac_row)
            else:
                return self.SCATTER_TARGETS['clyde']

    def update(self, maze, pacman, blinky_pos, mode, dots_eaten):
        self.anim_timer += 1

        # Handle ghost house
        if self.state == GhostState.IN_HOUSE:
            # Bob up and down in house
            center_y = grid_to_pixel(self.start_col, self.start_row)[1]
            self.y = center_y + math.sin(self.anim_timer * 0.1) * 5
            # Release logic
            if dots_eaten >= self.release_dots.get(self.name, 0):
                self.state = GhostState.SCATTER
                # Move to exit
                exit_x, exit_y = grid_to_pixel(self.house_col, self.house_row - 3)
                self.x = exit_x
                self.y = exit_y
            return

        # Frightened timer
        if self.state == GhostState.FRIGHTENED:
            self.frightened_timer -= 1
            if self.frightened_timer <= 0:
                self.state = GhostState.CHASE if mode == 'chase' else GhostState.SCATTER
            self.frightened_flash = self.frightened_timer < 120 and (self.frightened_timer // 15) % 2 == 0

        # Eaten - move fast toward house
        if self.state == GhostState.EATEN:
            self.speed = 4
            tx, ty = grid_to_pixel(self.house_col, self.house_row)
            if abs(self.x - tx) < 5 and abs(self.y - ty) < 5:
                self.x, self.y = tx, ty
                self.state = GhostState.SCATTER
                self.speed = 2
                return
        else:
            self.speed = 1 if self.state == GhostState.FRIGHTENED else 2

        # Movement AI
        cx, cy = pixel_to_grid(self.x, self.y)
        px_center, py_center = grid_to_pixel(cx, cy)

        at_center = abs(self.x - px_center) <= self.speed and abs(self.y - py_center) <= self.speed

        if at_center:
            self.x, self.y = px_center, py_center
            target = self.get_target(pacman, blinky_pos, mode)

            # Get available directions (no reversing unless frightened)
            opposite = (-self.dir[0], -self.dir[1])
            possible_dirs = []
            for d in [UP, LEFT, DOWN, RIGHT]:
                if d == opposite and self.state != GhostState.FRIGHTENED:
                    continue
                ncol, nrow = cx + d[0], cy + d[1]
                if can_move(maze, ncol, nrow) and not (maze[nrow][ncol % COLS] == 5 if 0 <= nrow < len(maze) and 0 <= ncol < COLS else False):
                    possible_dirs.append(d)

            if not possible_dirs:
                # Allow reverse if stuck
                for d in [UP, LEFT, DOWN, RIGHT]:
                    ncol, nrow = cx + d[0], cy + d[1]
                    if can_move(maze, ncol, nrow):
                        possible_dirs.append(d)

            if possible_dirs:
                if self.state == GhostState.FRIGHTENED:
                    self.dir = random.choice(possible_dirs)
                else:
                    # Pick direction that minimises distance to target
                    best_dir = possible_dirs[0]
                    best_dist = float('inf')
                    for d in possible_dirs:
                        nc, nr = cx + d[0], cy + d[1]
                        dist = (nc - target[0]) ** 2 + (nr - target[1]) ** 2
                        if dist < best_dist:
                            best_dist = dist
                            best_dir = d
                    self.dir = best_dir

        self.x += self.dir[0] * self.speed
        self.y += self.dir[1] * self.speed

        # Tunnel wrap
        if self.x < -TILE // 2:
            self.x = COLS * TILE + TILE // 2
        elif self.x > COLS * TILE + TILE // 2:
            self.x = -TILE // 2

    def draw(self, surface):
        if self.state == GhostState.EATEN:
            self._draw_eyes(surface)
            return

        # Body colour
        if self.state == GhostState.FRIGHTENED:
            color = GHOST_WHITE if self.frightened_flash else GHOST_BLUE
        else:
            color = self.color

        cx, cy = int(self.x), int(self.y)
        r = TILE // 2 + 1

        # Ghost body: semicircle top + wavy bottom
        # Top half circle
        pygame.draw.circle(surface, color, (cx, cy - 2), r)
        # Bottom rectangle
        pygame.draw.rect(surface, color, (cx - r, cy - 2, r * 2, r))
        # Wavy bottom
        wave_offset = (self.anim_timer // 8) % 2
        for i in range(3):
            wx = cx - r + i * (r * 2 // 3) + (r // 3)
            wy = cy + r - 3
            wave_r = r // 3
            if (i + wave_offset) % 2 == 0:
                pygame.draw.circle(surface, color, (wx, wy), wave_r)
            else:
                pygame.draw.circle(surface, DARK_BLUE, (wx, wy), wave_r)
                # Cover the top of the cut-out
                pygame.draw.rect(surface, color, (wx - wave_r, wy - wave_r, wave_r * 2, wave_r))

        # Eyes
        self._draw_eyes(surface)

        # Frightened face
        if self.state == GhostState.FRIGHTENED:
            eye_color = RED if self.frightened_flash else WHITE
            # Wobbly mouth
            points = []
            for i in range(5):
                mx = cx - 5 + i * 3
                my = cy + 2 + (1 if i % 2 == 0 else -1) * 2
                points.append((mx, my))
            if len(points) > 1:
                pygame.draw.lines(surface, eye_color, False, points, 1)

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
class Fruit:
    FRUIT_DATA = [
        {'name': 'cherry',     'color': FRUIT_RED,   'points': 100},
        {'name': 'strawberry', 'color': FRUIT_RED,   'points': 300},
        {'name': 'orange',     'color': ORANGE,      'points': 500},
        {'name': 'apple',      'color': FRUIT_RED,   'points': 700},
        {'name': 'melon',      'color': FRUIT_GREEN,  'points': 1000},
    ]

    def __init__(self, col, row, level):
        self.col = col
        self.row = row
        self.x, self.y = grid_to_pixel(col, row)
        idx = min(level, len(self.FRUIT_DATA) - 1)
        self.data = self.FRUIT_DATA[idx]
        self.timer = 600  # ~10 seconds
        self.active = True
        self.collected = False
        self.display_timer = 0

    def update(self):
        if not self.active:
            if self.collected and self.display_timer > 0:
                self.display_timer -= 1
            return
        self.timer -= 1
        if self.timer <= 0:
            self.active = False

    def draw(self, surface):
        if self.collected and self.display_timer > 0:
            # Show points
            font = pygame.font.Font(None, 20)
            txt = font.render(str(self.data['points']), True, WHITE)
            surface.blit(txt, (self.x - txt.get_width() // 2, self.y - txt.get_height() // 2))
            return

        if not self.active:
            return

        # Draw simple fruit shape
        r = TILE // 2 - 2
        pygame.draw.circle(surface, self.data['color'], (self.x, self.y), r)
        # Stem
        pygame.draw.line(surface, FRUIT_GREEN, (self.x, self.y - r), (self.x + 2, self.y - r - 4), 2)
        # Highlight
        pygame.draw.circle(surface, WHITE, (self.x - 2, self.y - 2), 2)


# ---------------------------------------------------------------------------
# Floating Score (for ghost eat combos)
# ---------------------------------------------------------------------------
class FloatingScore:
    def __init__(self, x, y, points):
        self.x = x
        self.y = y
        self.points = points
        self.timer = 60

    def update(self):
        self.timer -= 1
        self.y -= 0.3

    def draw(self, surface):
        if self.timer > 0:
            font = pygame.font.Font(None, 20)
            txt = font.render(str(self.points), True, CYAN)
            surface.blit(txt, (self.x - txt.get_width() // 2, int(self.y)))


# ---------------------------------------------------------------------------
# Main Game class
# ---------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("PacMan")
        self.clock = pygame.time.Clock()

        # Fonts
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_small = pygame.font.Font(None, 24)

        self.high_score = 0
        self.new_game()

    def new_game(self):
        self.maze = build_maze()
        self.score = 0
        self.lives = 3
        self.level = 0
        self.state = GameState.READY
        self.ready_timer = 120
        self.dots_eaten = 0
        self.total_dots = self._count_dots()
        self.ghost_eat_combo = 0
        self.floating_scores = []
        self.fruit = None
        self.fruit_spawned = False
        self.mode_timer = 0
        self.mode = 'scatter'
        self.level_flash_timer = 0

        # Find PacMan start pos and ghost house
        self.pac_start = (14, 18)  # classic position
        self.ghost_house = (14, 11)

        self.pacman = PacMan(self.pac_start[0], self.pac_start[1])
        self._init_ghosts()

    def _init_ghosts(self):
        hc, hr = self.ghost_house
        self.ghosts = [
            Ghost('blinky', hc, hr - 3, hc, hr),
            Ghost('pinky', hc, hr, hc, hr),
            Ghost('inky', hc - 2, hr, hc, hr),
            Ghost('clyde', hc + 2, hr, hc, hr),
        ]

    def _count_dots(self):
        count = 0
        for row in self.maze:
            for cell in row:
                if cell == 0 or cell == 3:
                    count += 1
        return count

    def _reset_positions(self):
        self.pacman.reset()
        self._init_ghosts()
        self.state = GameState.READY
        self.ready_timer = 120

    def _next_level(self):
        self.level += 1
        self.maze = build_maze()
        self.total_dots = self._count_dots()
        self.dots_eaten = 0
        self.fruit = None
        self.fruit_spawned = False
        self.mode_timer = 0
        self.mode = 'scatter'
        self._reset_positions()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if self.state == GameState.GAME_OVER or self.state == GameState.WIN:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        self.new_game()
                        return True

                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.pacman.set_direction(UP)
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    self.pacman.set_direction(DOWN)
                elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    self.pacman.set_direction(LEFT)
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    self.pacman.set_direction(RIGHT)
        return True

    def update(self):
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
                    if self.score > self.high_score:
                        self.high_score = self.score
                else:
                    self._reset_positions()
            return

        if self.state == GameState.LEVEL_COMPLETE:
            self.level_flash_timer -= 1
            if self.level_flash_timer <= 0:
                self._next_level()
            return

        if self.state != GameState.PLAYING:
            return

        # Mode switching (scatter <-> chase)
        self.mode_timer += 1
        if self.mode == 'scatter' and self.mode_timer > 420:  # 7 seconds
            self.mode = 'chase'
            self.mode_timer = 0
        elif self.mode == 'chase' and self.mode_timer > 1200:  # 20 seconds
            self.mode = 'scatter'
            self.mode_timer = 0

        # Update PacMan
        self.pacman.update(self.maze)

        # Check dot eating
        pc, pr = pixel_to_grid(self.pacman.x, self.pacman.y)
        if 0 <= pr < len(self.maze) and 0 <= pc < COLS:
            cell = self.maze[pr][pc]
            if cell == 0:  # dot
                self.maze[pr][pc] = 4
                self.score += 10
                self.dots_eaten += 1
            elif cell == 3:  # power pellet
                self.maze[pr][pc] = 4
                self.score += 50
                self.dots_eaten += 1
                self.ghost_eat_combo = 0
                for g in self.ghosts:
                    if g.state not in (GhostState.EATEN, GhostState.IN_HOUSE):
                        g.state = GhostState.FRIGHTENED
                        g.frightened_timer = 360  # 6 seconds
                        g.dir = (-g.dir[0], -g.dir[1])  # reverse

        # Check fruit spawn
        if not self.fruit_spawned and self.dots_eaten >= self.total_dots // 3:
            self.fruit = Fruit(14, 14, self.level)
            self.fruit_spawned = True

        # Update fruit
        if self.fruit:
            self.fruit.update()
            if self.fruit.active:
                fc, fr = pixel_to_grid(self.fruit.x, self.fruit.y)
                if abs(pc - fc) <= 1 and abs(pr - fr) <= 1:
                    dist = math.sqrt((self.pacman.x - self.fruit.x) ** 2 + (self.pacman.y - self.fruit.y) ** 2)
                    if dist < TILE:
                        self.score += self.fruit.data['points']
                        self.fruit.active = False
                        self.fruit.collected = True
                        self.fruit.display_timer = 60

        # Update ghosts
        blinky_pos = pixel_to_grid(self.ghosts[0].x, self.ghosts[0].y)
        for ghost in self.ghosts:
            ghost.update(self.maze, self.pacman, blinky_pos, self.mode, self.dots_eaten)

            # Check collision with PacMan
            dist = math.sqrt((ghost.x - self.pacman.x) ** 2 + (ghost.y - self.pacman.y) ** 2)
            if dist < TILE - 2:
                if ghost.state == GhostState.FRIGHTENED:
                    # Eat ghost
                    ghost.state = GhostState.EATEN
                    self.ghost_eat_combo += 1
                    points = 200 * (2 ** (self.ghost_eat_combo - 1))
                    self.score += points
                    self.floating_scores.append(FloatingScore(ghost.x, ghost.y, points))
                elif ghost.state not in (GhostState.EATEN, GhostState.IN_HOUSE):
                    # PacMan dies
                    self.pacman.alive = False
                    self.state = GameState.DYING
                    self.pacman.death_frame = 0

        # Update floating scores
        for fs in self.floating_scores[:]:
            fs.update()
            if fs.timer <= 0:
                self.floating_scores.remove(fs)

        # Check level complete
        if self.dots_eaten >= self.total_dots:
            self.state = GameState.LEVEL_COMPLETE
            self.level_flash_timer = 120

    def draw(self):
        self.screen.fill(BLACK)

        # Draw maze
        flash = self.state == GameState.LEVEL_COMPLETE and (self.level_flash_timer // 15) % 2 == 0
        for row_idx, row in enumerate(self.maze):
            for col_idx, cell in enumerate(row):
                x = col_idx * TILE
                y = row_idx * TILE + MAZE_OFFSET_Y

                if cell == 1:
                    if flash:
                        pygame.draw.rect(self.screen, WHITE, (x, y, TILE, TILE))
                        inner = pygame.Rect(x + 2, y + 2, TILE - 4, TILE - 4)
                        pygame.draw.rect(self.screen, BLACK, inner)
                    else:
                        draw_rounded_wall_segment(self.screen, col_idx, row_idx, self.maze)
                elif cell == 5:
                    draw_rounded_wall_segment(self.screen, col_idx, row_idx, self.maze)
                elif cell == 6:
                    draw_ghost_door(self.screen, col_idx, row_idx)
                elif cell == 0:
                    # Dot
                    cx = x + TILE // 2
                    cy = y + TILE // 2
                    pygame.draw.circle(self.screen, DOT_COLOR, (cx, cy), 2)
                elif cell == 3:
                    # Power pellet (pulsing)
                    cx = x + TILE // 2
                    cy = y + TILE // 2
                    pulse = abs(math.sin(pygame.time.get_ticks() * 0.005)) * 3 + 4
                    pygame.draw.circle(self.screen, DOT_COLOR, (cx, cy), int(pulse))

        # Draw fruit
        if self.fruit:
            self.fruit.draw(self.screen)

        # Draw PacMan
        self.pacman.draw(self.screen)

        # Draw ghosts (not during level complete)
        if self.state != GameState.LEVEL_COMPLETE:
            for ghost in self.ghosts:
                ghost.draw(self.screen)

        # Draw floating scores
        for fs in self.floating_scores:
            fs.draw(self.screen)

        # HUD
        self._draw_hud()

        # Overlay text
        if self.state == GameState.READY:
            txt = self.font_large.render("READY!", True, YELLOW)
            self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2))

        elif self.state == GameState.GAME_OVER:
            # Dim overlay
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))

            txt = self.font_large.render("GAME OVER", True, RED)
            self.screen.blit(txt, (WIDTH // 2 - txt.get_width() // 2, HEIGHT // 2 - 40))

            score_txt = self.font_medium.render(f"Score: {self.score}", True, WHITE)
            self.screen.blit(score_txt, (WIDTH // 2 - score_txt.get_width() // 2, HEIGHT // 2 + 10))

            restart = self.font_small.render("Press ENTER to restart", True, WHITE)
            alpha = abs(math.sin(pygame.time.get_ticks() * 0.003)) * 255
            restart.set_alpha(int(alpha))
            self.screen.blit(restart, (WIDTH // 2 - restart.get_width() // 2, HEIGHT // 2 + 50))

        pygame.display.flip()

    def _draw_hud(self):
        """Draw score, lives, and level info at top."""
        # Background bar
        pygame.draw.rect(self.screen, HUD_BG, (0, 0, WIDTH, MAZE_OFFSET_Y))

        # Score
        score_txt = self.font_medium.render(f"SCORE  {self.score:>8}", True, WHITE)
        self.screen.blit(score_txt, (10, 8))

        # High Score
        hi_txt = self.font_small.render(f"HIGH SCORE  {self.high_score:>8}", True, (180, 180, 180))
        self.screen.blit(hi_txt, (WIDTH // 2 - hi_txt.get_width() // 2, 4))

        # Level
        lvl_txt = self.font_small.render(f"LEVEL {self.level + 1}", True, CYAN)
        self.screen.blit(lvl_txt, (WIDTH - lvl_txt.get_width() - 10, 4))

        # Lives (draw small pacmans)
        for i in range(self.lives - 1):
            lx = 20 + i * 28
            ly = MAZE_OFFSET_Y - 24
            # Mini pacman
            points = [(lx, ly)]
            for j in range(16):
                angle = math.radians(30 + (300 * j / 15))
                px = lx + 9 * math.cos(angle)
                py = ly - 9 * math.sin(angle)
                points.append((px, py))
            if len(points) > 2:
                pygame.draw.polygon(self.screen, YELLOW, points)

        # Separator line
        pygame.draw.line(self.screen, WALL_BLUE, (0, MAZE_OFFSET_Y - 1), (WIDTH, MAZE_OFFSET_Y - 1), 1)

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    game = Game()
    game.run()
