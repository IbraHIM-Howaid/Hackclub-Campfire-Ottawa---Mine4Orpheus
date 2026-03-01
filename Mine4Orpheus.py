import pygame
import random
import sys
import math

# --- CONFIGURATION & CONSTANTS ---
WIDTH, HEIGHT = 640, 480
TILE_SIZE = 32
FPS = 60
COLS, ROWS = WIDTH // TILE_SIZE, HEIGHT // TILE_SIZE
UI_PANEL_HEIGHT = 60

# Tile IDs
EMPTY, DIRT, ROCK, BRONZE, SILVER, GOLD, DIAMOND = 0, 1, 2, 3, 4, 5, 6

TILE_COLORS = {
    EMPTY: (20, 15, 10), DIRT: (139, 69, 19), ROCK: (80, 80, 80),
    BRONZE: (205, 127, 50), SILVER: (192, 192, 192), GOLD: (255, 215, 0), DIAMOND: (180, 250, 255)
}
GLOW_BASE_COLORS = {BRONZE: (205, 127, 50), SILVER: (192, 192, 192), GOLD: (255, 215, 0), DIAMOND: (0, 255, 255)}
DURABILITY = {DIRT: 1, ROCK: 9999, BRONZE: 3, SILVER: 5, GOLD: 8, DIAMOND: 12}
ORE_CONFIG = {
    'ROCK': {'base': 10, 'scale': 0.05}, 'BRONZE': {'base': 15, 'scale': -0.1},
    'SILVER': {'base': 8, 'scale': -0.05}, 'GOLD': {'base': 3, 'scale': 0.15},
    'DIAMOND': {'base': 1, 'scale': 0.1}
}

# Overworld Constants
C_FLOOR = (45, 40, 35)
C_WALL = (80, 70, 60)
C_COUNTER = (120, 80, 40)
C_ORPHEUS = (150, 50, 200)

# H = Hole, S = Spawn, O = Orpheus, C = Counter, W = Wall, t = Torch, . = Floor
LEVEL_MAP = [
    "WWWWWWWWWWWWWWWWWWWW",
    "W..................W",
    "W..WWWW......WWWW..W",
    "W..W............W..W",
    "W........C.........W",
    "W......CCOCC.......W",
    "W........C.........W",
    "W..W............W..W",
    "W..WWWW......WWWW..W",
    "W..................W",
    "W..t...............W",
    "W.......H..........W",
    "W.........S........W",
    "WWWWWWWWWWWWWWWWWWWW",
]


# --- AUDIO MANAGER ---
class SoundManager:
    def __init__(self):
        pygame.mixer.init()
        self.sounds = {}

    def load(self, name, filepath):
        try:
            self.sounds[name] = pygame.mixer.Sound(filepath)
        except Exception:
            self.sounds[name] = None

    def play(self, name):
        if self.sounds.get(name):
            self.sounds[name].play()


# --- SHARED DATA ---
class GameSession:
    def __init__(self):
        self.inventory = {BRONZE: 0, SILVER: 0, GOLD: 0, DIAMOND: 0}
        self.money = 0
        self.shovel_level = 1
        self.has_torch = False


# --- UTILITIES ---
class Button:
    def __init__(self, x, y, width, height, text, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.color = (80, 80, 100)
        self.hover_color = (110, 110, 130)

    def draw(self, surface, mouse_pos):
        color = self.hover_color if self.rect.collidepoint(mouse_pos) else self.color
        pygame.draw.rect(surface, color, self.rect)
        pygame.draw.rect(surface, (200, 200, 200), self.rect, 2)
        text_surf = self.font.render(self.text, False, (255, 255, 255))
        surface.blit(text_surf,
                     (self.rect.centerx - text_surf.get_width() // 2, self.rect.centery - text_surf.get_height() // 2))

    def is_clicked(self, mouse_pos, mouse_pressed):
        return self.rect.collidepoint(mouse_pos) and mouse_pressed[0]


def create_light_mask(radius, intensity=255):
    mask = pygame.Surface((radius * 2, radius * 2))
    for r in range(radius, 0, -2):
        val = int(intensity * (1 - (r / radius) ** 2))
        pygame.draw.circle(mask, (val, val, val), (radius, radius), r)
    return mask


# --- UNIFIED ENTITY CLASS ---
class GridMole:
    def __init__(self, start_x, start_y):
        self.grid_x, self.grid_y = start_x, start_y
        self.can_move_timer = 0
        self.state = 'IDLE'
        self.facing_right = True
        self.frame = 0
        self.anim_timer = 0
        self.anims = self._generate_sprites()

    def _generate_sprites(self):
        s = {'IDLE': [], 'MINING': [], 'CRAWLING': []}

        surf1 = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.ellipse(surf1, (139, 69, 19), (4, 10, 24, 20))
        pygame.draw.ellipse(surf1, (0, 0, 0), (20, 14, 4, 4))
        s['IDLE'].append(surf1)

        surf2 = surf1.copy()
        pygame.draw.rect(surf2, (200, 200, 200), (20, 10, 8, 8))
        s['MINING'].append(surf1)
        s['MINING'].append(surf2)

        surf3 = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.ellipse(surf3, (139, 69, 19), (4, 4, 24, 24))
        pygame.draw.ellipse(surf3, (0, 0, 0), (20, 8, 4, 4))
        s['CRAWLING'].append(surf3)
        s['CRAWLING'].append(surf1)

        return s

    def process_animation(self, dt):
        self.anim_timer += dt
        frames_list = self.anims[self.state]
        frame_duration = 300 if self.state == 'IDLE' else 80
        if self.anim_timer > frame_duration:
            self.frame = (self.frame + 1) % len(frames_list)
            self.anim_timer = 0

    def draw(self, surface, camera_y=0):
        current_image = self.anims[self.state][min(self.frame, len(self.anims[self.state]) - 1)]
        if not self.facing_right:
            current_image = pygame.transform.flip(current_image, True, False)
        surface.blit(current_image, (self.grid_x * TILE_SIZE, (self.grid_y * TILE_SIZE) - int(camera_y)))


# --- UNDERGROUND CLASSES ---
class Particle:
    __slots__ = ['active', 'x', 'y', 'vx', 'vy', 'color', 'life']

    def __init__(self):
        self.active = False
        self.x = self.y = self.vx = self.vy = self.life = 0
        self.color = (255, 255, 255)


class ParticlePool:
    def __init__(self, size=256):
        self.pool = [Particle() for _ in range(size)]

    def emit(self, x, y, color, count=8):
        emitted = 0
        for p in self.pool:
            if not p.active:
                p.active, p.x, p.y = True, x, y
                p.vx, p.vy = random.uniform(-3, 3), random.uniform(-5, -1)
                p.color, p.life = color, 255
                emitted += 1
                if emitted >= count: break

    def update_and_draw(self, surface, camera_y):
        for p in self.pool:
            if p.active:
                p.vy += 0.3
                p.x += p.vx
                p.y += p.vy
                p.life -= 8
                if p.life <= 0:
                    p.active = False
                else:
                    surf = pygame.Surface((4, 4), pygame.SRCALPHA)
                    surf.fill((*p.color[:3], max(0, int(p.life))))
                    surface.blit(surf, (int(p.x), int(p.y) - camera_y))


class Terrain:
    def __init__(self):
        self.grid = {}
        self.highest_y_generated = -1

    def generate_row(self, y_depth):
        if (0, y_depth) in self.grid: return
        if y_depth < 10:
            for x in range(COLS): self.grid[(x, y_depth)] = [DIRT, DURABILITY[DIRT]]
            return

        choices = [DIRT, ROCK, BRONZE, SILVER, GOLD, DIAMOND]
        weights = [71, 10, 8, 4, 1, 1]
        scaled_depth = max(0, y_depth - 20)
        if scaled_depth > 0:
            weights[1] = max(5, ORE_CONFIG['ROCK']['base'] + scaled_depth * ORE_CONFIG['ROCK']['scale'])
            weights[2] = max(1, ORE_CONFIG['BRONZE']['base'] + scaled_depth * ORE_CONFIG['BRONZE']['scale'])
            weights[3] = max(1, ORE_CONFIG['SILVER']['base'] + scaled_depth * ORE_CONFIG['SILVER']['scale'])
            weights[4] = ORE_CONFIG['GOLD']['base'] + scaled_depth * ORE_CONFIG['GOLD']['scale']
            weights[5] = ORE_CONFIG['DIAMOND']['base'] + scaled_depth * ORE_CONFIG['DIAMOND']['scale']
            weights[0] = max(10, 100 - sum(weights[1:]))

        for x in range(COLS):
            tile_id = random.choices(choices, weights=weights, k=1)[0]
            self.grid[(x, y_depth)] = [tile_id, DURABILITY.get(tile_id, 1)]

    def ensure_generated(self, target_y):
        if target_y > self.highest_y_generated:
            for y in range(self.highest_y_generated + 1, target_y + 1):
                self.generate_row(y)
            self.highest_y_generated = target_y

    def draw(self, surface, camera_y, ticks):
        start_row = int(camera_y // TILE_SIZE)
        pulse = (math.sin(ticks * 0.005) + 1) / 2

        for y in range(max(0, start_row), start_row + ROWS + 2):
            for x in range(COLS):
                tile_data = self.grid.get((x, y), [DIRT, 1])
                tile_id, hp = tile_data[0], tile_data[1]
                if tile_id != EMPTY:
                    screen_x, screen_y = x * TILE_SIZE, (y * TILE_SIZE) - camera_y
                    rect = pygame.Rect(screen_x, screen_y, TILE_SIZE, TILE_SIZE)

                    if tile_id in GLOW_BASE_COLORS:
                        glow_radius = int((TILE_SIZE * 0.6) + (pulse * TILE_SIZE * 0.3))
                        glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
                        pygame.draw.circle(glow_surf, (*GLOW_BASE_COLORS[tile_id], int(30 + (pulse * 50))),
                                           (glow_radius, glow_radius), glow_radius)
                        surface.blit(glow_surf, (rect.centerx - glow_radius, rect.centery - glow_radius))

                    pygame.draw.rect(surface, TILE_COLORS[tile_id], rect)
                    pygame.draw.rect(surface, (0, 0, 0, 50), rect, 1)

                    max_hp = DURABILITY.get(tile_id, 1)
                    if tile_id != ROCK and hp < max_hp:
                        bar_width = int((TILE_SIZE - 4) * (hp / max_hp))
                        bar_y = screen_y + TILE_SIZE - 6
                        pygame.draw.rect(surface, (255, 0, 0), (screen_x + 2, bar_y, TILE_SIZE - 4, 4))
                        pygame.draw.rect(surface, (0, 255, 0), (screen_x + 2, bar_y, bar_width, 4))


# --- MAIN ENGINE ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Procedural Mining & Economics")
    clock = pygame.time.Clock()

    font_large = pygame.font.SysFont(None, 36)
    font_small = pygame.font.SysFont(None, 24)

    audio = SoundManager()
    audio.load('dig', 'dig.wav')
    audio.load('talk', 'talk.wav')

    session = GameSession()
    global_state = 'OVERWORLD'
    overworld_substate = 'WALK'
    show_inventory = False

    ow_grid = {}
    orpheus_pos = None
    hole_pos = None
    torch_pos = None
    spawn_pos = (COLS // 2, ROWS // 2)

    for r_idx, row in enumerate(LEVEL_MAP):
        for c_idx, char in enumerate(row):
            ow_grid[(c_idx, r_idx)] = char
            if char == 'O':
                orpheus_pos = (c_idx, r_idx)
            elif char == 'H':
                hole_pos = (c_idx, r_idx)
            elif char == 't':
                torch_pos = (c_idx, r_idx); ow_grid[(c_idx, r_idx)] = '.'
            elif char == 'S':
                spawn_pos = (c_idx, r_idx); ow_grid[(c_idx, r_idx)] = '.'

    ow_mole = GridMole(spawn_pos[0], spawn_pos[1])

    action_panel_rect = pygame.Rect(0, HEIGHT - UI_PANEL_HEIGHT, WIDTH, UI_PANEL_HEIGHT)

    btn_talk = Button(WIDTH // 2 - 190, HEIGHT - 50, 120, 40, "Talk (Orpheus)", font_small)
    btn_mine = Button(WIDTH // 2 - 50, HEIGHT - 50, 120, 40, "Enter Mine", font_small)
    btn_torch = Button(WIDTH // 2 + 90, HEIGHT - 50, 120, 40, "Take Torch", font_small)

    btn_inv_toggle = Button(10, 10, 90, 30, "Inventory", font_small)
    btn_surface = Button(WIDTH - 160, 10, 150, 30, "Return to Surface", font_small)

    btn_open_shop = Button(WIDTH - 150, HEIGHT - 100, 120, 40, "Open Shop", font_small)
    btn_close_shop = Button(WIDTH - 150, 20, 100, 40, "Close", font_small)
    btn_close_inv = Button(WIDTH // 2 - 50, HEIGHT - 80, 100, 40, "Close", font_small)
    btn_sell_all = Button(WIDTH // 4 - 75, HEIGHT // 2, 150, 40, "Sell All Ores", font_small)
    btn_buy_shovel = Button(WIDTH * 3 // 4 - 75, HEIGHT // 2, 150, 40, "Upgrade Shovel ($100)", font_small)

    mask_ambient_corner = create_light_mask(150, 100)
    mask_orpheus = create_light_mask(100, 150)
    mask_torch_large = create_light_mask(250, 255)
    mask_torch_small = create_light_mask(80, 200)

    terrain = Terrain()
    ug_mole = GridMole(COLS // 2, 5)
    particle_pool = ParticlePool()
    camera_y = 0.0
    terrain.ensure_generated(ROWS + 5)
    terrain.grid[(ug_mole.grid_x, ug_mole.grid_y)] = [EMPTY, 0]

    mouse_was_pressed = False

    running = True
    while running:
        dt = clock.tick(FPS)
        ticks = pygame.time.get_ticks()
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()
        mouse_clicked = mouse_pressed[0] and not mouse_was_pressed
        mouse_was_pressed = mouse_pressed[0]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if show_inventory:
                    show_inventory = False
                elif overworld_substate in ['DIALOGUE', 'SHOP']:
                    overworld_substate = 'WALK'

        if show_inventory:
            if mouse_clicked and btn_close_inv.is_clicked(mouse_pos, mouse_pressed):
                show_inventory = False
        else:
            if mouse_clicked and btn_inv_toggle.is_clicked(mouse_pos, mouse_pressed):
                if overworld_substate not in ['DIALOGUE', 'SHOP']:
                    show_inventory = True

        keys = pygame.key.get_pressed()

        if not show_inventory:
            # --- PIPELINE: OVERWORLD ---
            if global_state == 'OVERWORLD':
                if overworld_substate == 'WALK':
                    ow_mole.can_move_timer -= dt
                    dx, dy = 0, 0
                    if ow_mole.can_move_timer <= 0:
                        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                            dx, ow_mole.facing_right = -1, False
                        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                            dx, ow_mole.facing_right = 1, True
                        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                            dy = 1
                        elif keys[pygame.K_UP] or keys[pygame.K_w]:
                            dy = -1

                    if dx != 0 or dy != 0:
                        tx, ty = ow_mole.grid_x + dx, ow_mole.grid_y + dy
                        target_tile = ow_grid.get((tx, ty), 'W')
                        if target_tile in ['.', 'S']:
                            ow_mole.grid_x, ow_mole.grid_y = tx, ty
                            ow_mole.can_move_timer = 150
                            ow_mole.state = 'CRAWLING' if dy < 0 or dx != 0 else 'IDLE'
                        else:
                            ow_mole.state = 'IDLE'
                    else:
                        if ow_mole.can_move_timer <= 0: ow_mole.state = 'IDLE'

                    ow_mole.process_animation(dt)

                    dist_to_npc = math.hypot(ow_mole.grid_x - orpheus_pos[0], ow_mole.grid_y - orpheus_pos[1])
                    dist_to_hole = math.hypot(ow_mole.grid_x - hole_pos[0], ow_mole.grid_y - hole_pos[1])
                    dist_to_torch = math.hypot(ow_mole.grid_x - torch_pos[0],
                                               ow_mole.grid_y - torch_pos[1]) if torch_pos else 99

                    if dist_to_npc < 2.0 and mouse_clicked and btn_talk.is_clicked(mouse_pos, mouse_pressed):
                        audio.play('talk')
                        overworld_substate = 'DIALOGUE'
                    elif dist_to_hole < 2.0 and mouse_clicked and btn_mine.is_clicked(mouse_pos, mouse_pressed):
                        global_state = 'UNDERGROUND'
                        ug_mole.can_move_timer = 300
                    elif dist_to_torch < 2.0 and not session.has_torch and mouse_clicked and btn_torch.is_clicked(
                            mouse_pos, mouse_pressed):
                        session.has_torch = True
                        torch_pos = None

                elif overworld_substate == 'DIALOGUE':
                    if mouse_clicked and btn_open_shop.is_clicked(mouse_pos, mouse_pressed):
                        overworld_substate = 'SHOP'

                elif overworld_substate == 'SHOP':
                    if mouse_clicked:
                        if btn_close_shop.is_clicked(mouse_pos, mouse_pressed):
                            overworld_substate = 'WALK'
                        elif btn_sell_all.is_clicked(mouse_pos, mouse_pressed):
                            prices = {BRONZE: 10, SILVER: 25, GOLD: 100, DIAMOND: 500}
                            earned = sum(session.inventory[ore] * prices[ore] for ore in session.inventory)
                            session.money += earned
                            for ore in session.inventory: session.inventory[ore] = 0
                        elif btn_buy_shovel.is_clicked(mouse_pos, mouse_pressed):
                            cost = 100 * session.shovel_level
                            if session.money >= cost:
                                session.money -= cost
                                session.shovel_level += 1
                                btn_buy_shovel.text = f"Upgrade Shovel (${100 * session.shovel_level})"

            # --- PIPELINE: UNDERGROUND ---
            elif global_state == 'UNDERGROUND':
                ug_mole.can_move_timer -= dt
                dx, dy = 0, 0
                if ug_mole.can_move_timer <= 0:
                    if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                        dx, ug_mole.facing_right = -1, False
                    elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                        dx, ug_mole.facing_right = 1, True
                    elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                        dy = 1
                    elif keys[pygame.K_UP] or keys[pygame.K_w]:
                        dy = -1

                if dx != 0 or dy != 0:
                    tx, ty = ug_mole.grid_x + dx, ug_mole.grid_y + dy
                    if 0 <= tx < COLS and ty >= 0:
                        tile_data = terrain.grid.get((tx, ty), [DIRT, 1])
                        if tile_data[0] == EMPTY:
                            ug_mole.grid_x, ug_mole.grid_y = tx, ty
                            ug_mole.can_move_timer = 150
                            ug_mole.state = 'CRAWLING' if dy < 0 or dx != 0 else 'IDLE'
                        elif tile_data[0] != ROCK:
                            audio.play('dig')
                            terrain.grid[(tx, ty)][1] -= 1
                            if terrain.grid[(tx, ty)][1] <= 0:
                                if tile_data[0] in session.inventory: session.inventory[tile_data[0]] += 1
                                particle_pool.emit((tx * TILE_SIZE) + 16, (ty * TILE_SIZE) + 16,
                                                   TILE_COLORS[tile_data[0]])
                                terrain.grid[(tx, ty)][0] = EMPTY
                                ug_mole.grid_x, ug_mole.grid_y = tx, ty
                                ug_mole.can_move_timer = 150
                                ug_mole.state = 'CRAWLING' if dy < 0 or dx != 0 else 'IDLE'
                            else:
                                ug_mole.can_move_timer = max(50, 250 - (session.shovel_level * 20))
                                ug_mole.state = 'MINING'
                        else:
                            ug_mole.state = 'IDLE'
                    else:
                        ug_mole.state = 'IDLE'
                else:
                    if ug_mole.can_move_timer <= 0: ug_mole.state = 'IDLE'

                ug_mole.process_animation(dt)
                camera_y += (max(0.0, ug_mole.grid_y * TILE_SIZE - HEIGHT // 3) - camera_y) * 0.1
                terrain.ensure_generated(int((camera_y + HEIGHT) // TILE_SIZE) + 10)

                if mouse_clicked and btn_surface.is_clicked(mouse_pos, mouse_pressed):
                    global_state = 'OVERWORLD'
                    ow_mole.can_move_timer = 300

                    # --- RENDERING PIPELINE ---
        if global_state == 'OVERWORLD':
            screen.fill(C_FLOOR)
            for r in range(ROWS):
                for c in range(COLS):
                    char = ow_grid.get((c, r), '.')
                    rect = pygame.Rect(c * TILE_SIZE, r * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    if char == 'W':
                        pygame.draw.rect(screen, C_WALL, rect)
                        pygame.draw.rect(screen, (0, 0, 0), rect, 1)
                    elif char == 'C':
                        pygame.draw.rect(screen, C_COUNTER, rect)
                        pygame.draw.rect(screen, (0, 0, 0), rect, 1)
                    elif char == 'O':
                        pygame.draw.rect(screen, C_ORPHEUS, rect)
                        pygame.draw.rect(screen, (0, 0, 0), rect, 1)
                    elif char == 'H':
                        pygame.draw.rect(screen, TILE_COLORS[DIRT], rect)
                        pygame.draw.rect(screen, (0, 0, 0), rect, 1)
                        pygame.draw.rect(screen, (15, 10, 10), rect.inflate(-16, -16))
                        pygame.draw.rect(screen, C_COUNTER, (rect.x + 2, rect.y + 2, TILE_SIZE - 4, 4))
                        pygame.draw.rect(screen, C_COUNTER, (rect.x + 2, rect.bottom - 6, TILE_SIZE - 4, 4))
                        pygame.draw.rect(screen, C_COUNTER, (rect.x + 2, rect.y + 2, 4, TILE_SIZE - 4))
                        pygame.draw.rect(screen, C_COUNTER, (rect.right - 6, rect.y + 2, 4, TILE_SIZE - 4))

            if torch_pos:
                pygame.draw.rect(screen, (139, 69, 19),
                                 (torch_pos[0] * TILE_SIZE + 14, torch_pos[1] * TILE_SIZE + 16, 4, 12))
                pygame.draw.rect(screen, (255, 150, 0),
                                 (torch_pos[0] * TILE_SIZE + 12, torch_pos[1] * TILE_SIZE + 8, 8, 8))

            ow_mole.draw(screen)

            darkness_layer = pygame.Surface((WIDTH, HEIGHT))
            darkness_layer.fill((40, 40, 50))

            darkness_layer.blit(mask_ambient_corner, (-50, -50), None, pygame.BLEND_RGB_ADD)
            darkness_layer.blit(mask_ambient_corner, (WIDTH - 100, -50), None, pygame.BLEND_RGB_ADD)
            darkness_layer.blit(mask_ambient_corner, (-50, HEIGHT - 100), None, pygame.BLEND_RGB_ADD)
            darkness_layer.blit(mask_ambient_corner, (WIDTH - 100, HEIGHT - 100), None, pygame.BLEND_RGB_ADD)

            if orpheus_pos:
                darkness_layer.blit(mask_orpheus, (orpheus_pos[0] * TILE_SIZE - 84, orpheus_pos[1] * TILE_SIZE - 84),
                                    None, pygame.BLEND_RGB_ADD)
            if torch_pos:
                darkness_layer.blit(mask_torch_small, (torch_pos[0] * TILE_SIZE - 64, torch_pos[1] * TILE_SIZE - 64),
                                    None, pygame.BLEND_RGB_ADD)

            px, py = ow_mole.grid_x * TILE_SIZE + 16, ow_mole.grid_y * TILE_SIZE + 16
            if session.has_torch:
                darkness_layer.blit(mask_torch_large, (px - 250, py - 250), None, pygame.BLEND_RGB_ADD)
            else:
                darkness_layer.blit(mask_torch_small, (px - 80, py - 80), None, pygame.BLEND_RGB_ADD)

            screen.blit(darkness_layer, (0, 0), None, pygame.BLEND_RGB_MULT)

            if overworld_substate == 'WALK':
                pygame.draw.rect(screen, (20, 20, 25), action_panel_rect)
                pygame.draw.rect(screen, (100, 100, 100), action_panel_rect, 2)

                screen.blit(font_small.render(f"Money: ${session.money} | Shovel Lv: {session.shovel_level}", False,
                                              (255, 255, 255)), (120, 15))
                btn_inv_toggle.draw(screen, mouse_pos)

                dist_to_npc = math.hypot(ow_mole.grid_x - orpheus_pos[0], ow_mole.grid_y - orpheus_pos[1])
                dist_to_hole = math.hypot(ow_mole.grid_x - hole_pos[0], ow_mole.grid_y - hole_pos[1])
                dist_to_torch = math.hypot(ow_mole.grid_x - torch_pos[0],
                                           ow_mole.grid_y - torch_pos[1]) if torch_pos else 99

                if dist_to_npc < 2.0: btn_talk.draw(screen, mouse_pos)
                if dist_to_hole < 2.0: btn_mine.draw(screen, mouse_pos)
                if dist_to_torch < 2.0 and not session.has_torch: btn_torch.draw(screen, mouse_pos)

            elif overworld_substate == 'DIALOGUE':
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((0, 0, 0, 150))
                screen.blit(overlay, (0, 0))
                dialogue_rect = pygame.Rect(50, HEIGHT - 150, WIDTH - 100, 100)
                pygame.draw.rect(screen, (20, 20, 30), dialogue_rect)
                pygame.draw.rect(screen, (200, 200, 200), dialogue_rect, 2)
                screen.blit(font_large.render("Orpheus: Greetings, delver.", False, (255, 255, 255)),
                            (dialogue_rect.x + 20, dialogue_rect.y + 20))
                btn_open_shop.draw(screen, mouse_pos)

            elif overworld_substate == 'SHOP':
                screen.fill((30, 30, 40))
                screen.blit(font_large.render("ORPHEUS' EMPORIUM", False, C_ORPHEUS), (WIDTH // 2 - 120, 40))
                labels = {BRONZE: "Bronze", SILVER: "Silver", GOLD: "Gold", DIAMOND: "Diamond"}
                y_off = 120
                for ore_id in [BRONZE, SILVER, GOLD, DIAMOND]:
                    screen.blit(font_small.render(f"{labels[ore_id]}: {session.inventory[ore_id]}", False,
                                                  GLOW_BASE_COLORS[ore_id]), (WIDTH // 4 - 50, y_off))
                    y_off += 30
                screen.blit(font_large.render(f"Current Funds: ${session.money}", False, (0, 255, 0)),
                            (WIDTH // 2 - 100, HEIGHT - 80))
                btn_sell_all.draw(screen, mouse_pos)
                btn_buy_shovel.draw(screen, mouse_pos)
                btn_close_shop.draw(screen, mouse_pos)

        elif global_state == 'UNDERGROUND':
            screen.fill(TILE_COLORS[EMPTY])
            terrain.draw(screen, camera_y, ticks)
            ug_mole.draw(screen, camera_y)
            particle_pool.update_and_draw(screen, camera_y)

            darkness_layer = pygame.Surface((WIDTH, HEIGHT))
            darkness_layer.fill((10, 10, 15))

            px, py = ug_mole.grid_x * TILE_SIZE + 16, (ug_mole.grid_y * TILE_SIZE) - int(camera_y) + 16

            if session.has_torch:
                darkness_layer.blit(mask_torch_large, (px - 250, py - 250), None, pygame.BLEND_RGB_ADD)
            else:
                darkness_layer.blit(mask_torch_small, (px - 80, py - 80), None, pygame.BLEND_RGB_ADD)

            screen.blit(darkness_layer, (0, 0), None, pygame.BLEND_RGB_MULT)

            screen.blit(font_small.render(f"Depth: {ug_mole.grid_y}m", False, (255, 255, 255)), (120, 15))
            btn_inv_toggle.draw(screen, mouse_pos)
            btn_surface.draw(screen, mouse_pos)

        if show_inventory:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            screen.blit(overlay, (0, 0))

            panel_rect = pygame.Rect(WIDTH // 4, HEIGHT // 4, WIDTH // 2, HEIGHT // 2)
            pygame.draw.rect(screen, (50, 40, 30), panel_rect)
            pygame.draw.rect(screen, (200, 180, 150), panel_rect, 3)

            title = font_large.render("INVENTORY", False, (255, 255, 255))
            screen.blit(title, (panel_rect.centerx - title.get_width() // 2, panel_rect.y + 20))

            y_offset = panel_rect.y + 80
            labels = {BRONZE: "Bronze", SILVER: "Silver", GOLD: "Gold", DIAMOND: "Diamond"}
            for ore_id in [BRONZE, SILVER, GOLD, DIAMOND]:
                text = font_small.render(f"{labels[ore_id]}: {session.inventory[ore_id]}", False,
                                         GLOW_BASE_COLORS[ore_id])
                screen.blit(text, (panel_rect.x + 40, y_offset))
                y_offset += 40

            btn_close_inv.draw(screen, mouse_pos)

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
