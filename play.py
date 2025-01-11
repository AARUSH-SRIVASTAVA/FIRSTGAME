import pygame
import sys
import os
import random
import json
import math

# CONSTANTS:
# Map for autotiling based on neighboring tile configurations
AUTOTILE_MAP = {
    tuple(sorted([(1, 0), (0, 1)])): 0,
    tuple(sorted([(1, 0), (0, 1), (-1, 0)])): 1,
    tuple(sorted([(-1, 0), (0, 1)])): 2,
    tuple(sorted([(-1, 0), (0, -1), (0, 1)])): 3,
    tuple(sorted([(-1, 0), (0, -1)])): 4,
    tuple(sorted([(-1, 0), (0, -1), (1, 0)])): 5,
    tuple(sorted([(1, 0), (0, -1)])): 6,
    tuple(sorted([(1, 0), (0, -1), (0, 1)])): 7,
    tuple(sorted([(1, 0), (0, 1), (-1, 0), (0, -1)])): 8
}

# Offsets for neighboring tiles for autotiling
NEIGHBOUR_OFFSETS = [(1, 1), (1, 0), (1, -1), (0, 1), (0, 0), (0, -1), (-1, 1), (-1, 0), (-1, -1)]
# Set of tile types that interact with physics
PHYSICS_TILES = {'grass', 'stone'}
# Set of tile types that use autotiling
AUTOTILE_TYPES = {'grass', 'stone'}
# Base path for image assets
BASE_IMG_PATH = 'data/images/' 

# PARTICLES:
class Particle:
    def __init__(self, game, p_type, pos, velocity=[0, 0], frame=0):
        self.game = game
        self.type = p_type
        self.pos = list(pos)
        self.velocity = list(velocity)
        self.animation = self.game.assets['particle/' + p_type].copy()
        self.animation.frame = frame

    def update(self):
        # Update the particle position and animation, return whether to kill the particle
        kill = False
        if self.animation.done:
            kill = True
        self.pos[0] += self.velocity[0]
        self.pos[1] += self.velocity[1]
        self.animation.update()
        return kill

    def render(self, surf, offset=(0, 0)):
        # Render the particle on the surface
        img = self.animation.img()
        surf.blit(img, (self.pos[0] - offset[0] - img.get_width() // 2, self.pos[1] - offset[1] - img.get_height() // 2))

# ANIMATION
class Animation:
    def __init__(self, images, img_dur=5, loop=True):
        self.images = images
        self.loop = loop
        self.img_duration = img_dur
        self.done = False
        self.frame = 0

    def copy(self):
        return Animation(self.images, self.img_duration, self.loop)

    def update(self):
        # Update the frame for the animation
        if self.loop:
            self.frame = (self.frame + 1) % (self.img_duration * len(self.images))
        else:
            self.frame = min(self.frame + 1, self.img_duration * len(self.images) - 1)
            if self.frame >= self.img_duration * len(self.images) - 1:
                self.done = True

    def img(self):
        # Get the current image for the animation
        return self.images[int(self.frame / self.img_duration)]

# CLOUD
class Cloud:
    def __init__(self, pos, img, speed, depth):
        self.pos = list(pos)
        self.img = img
        self.speed = speed
        self.depth = depth

    def update(self):
        # Update cloud position based on its speed
        self.pos[0] += self.speed

    def render(self, surf, offset=(0, 0)):
        # Render the cloud on the surface with a parallax effect
        render_pos = (self.pos[0] - offset[0] * self.depth, self.pos[1] - offset[1] * self.depth)
        surf.blit(self.img, (render_pos[0] % (surf.get_width() + self.img.get_width() - self.img.get_width()), render_pos[1] % (surf.get_height() + self.img.get_height() - self.img.get_height())))

class Clouds:
    def __init__(self, cloud_images, count=16):
        # Initialize multiple cloud objects
        self.clouds = []
        for i in range(count):
            self.clouds.append(Cloud(
                (random.random() * 99999, random.random() * 99999),
                random.choice(cloud_images),
                random.random() * 0.05 + 0.05,
                random.random() * 0.6 + 0.2
            ))
        self.clouds.sort(key=lambda x: x.depth)

    def update(self):
        # Update all cloud positions
        for cloud in self.clouds:
            cloud.update()

    def render(self, surf, offset=(0, 0)):
        # Render all clouds on the surface
        for cloud in self.clouds:
            cloud.render(surf, offset=offset)

# UTILITIES
def load_image(path):
    # Load an image and set its colorkey to black for transparency
    img = pygame.image.load(BASE_IMG_PATH + path).convert()
    img.set_colorkey((0, 0, 0))
    return img

def load_images(path):
    # Load all images in a given directory and return them as a list
    images = []
    for img_name in os.listdir(BASE_IMG_PATH + path):
        images.append(load_image(path + '/' + img_name))
    return images

# TILEMAP
class Tilemap:
    def __init__(self, game, tile_size=16):
        """Initialize the tilemap with a reference to the game and a tile size."""
        self.game = game
        self.tile_size = tile_size
        self.tilemap = {}
        self.offgrid_tiles = []  # Tiles to be drawn off the grid
    
    def extract(self, id_pairs, keep=False):
        """Extract tiles based on id_pairs, optionally keeping them in the map."""
        matches = []
        for tile in self.offgrid_tiles.copy():
            if (tile['type'], tile['variant']) in id_pairs:
                matches.append(tile.copy())
                if not keep:
                    self.offgrid_tiles.remove(tile)
        for loc in self.tilemap.copy():
            tile = self.tilemap[loc]
            if (tile['type'], tile['variant']) in id_pairs:
                matches.append(tile.copy())
                matches[-1]['pos'] = matches[-1]['pos'].copy()
                matches[-1]['pos'][0] *= self.tile_size
                matches[-1]['pos'][1] *= self.tile_size
                if not keep:
                    del self.tilemap[loc]
        return matches

    def tiles_around(self, pos):
        """Return a list of tiles around a given position."""
        tiles = []
        tile_loc = (int(pos[0] // self.tile_size), int(pos[1] // self.tile_size))
        for offset in NEIGHBOUR_OFFSETS:
            check_loc = f"{tile_loc[0] + offset[0]};{tile_loc[1] + offset[1]}"
            if check_loc in self.tilemap:
                tiles.append(self.tilemap[check_loc])
        return tiles
    
    def save(self, path):
        """Save the current tilemap to a file."""
        with open(path, 'w') as f:
            json.dump({'tilemap': self.tilemap, 'tile_size': self.tile_size, 'offgrid': self.offgrid_tiles}, f)

    def load(self, path):
        """Load a tilemap from a file."""
        with open(path, 'r') as f:
            map_data = json.load(f)
        self.tilemap = map_data['tilemap']
        self.tile_size = map_data['tile_size']
        self.offgrid_tiles = map_data['offgrid']

    def solid_check(self, pos):
        """Check if a given position is solid."""
        tile_loc = str(int(pos[0] // self.tile_size)) + ';' + str(int(pos[1] // self.tile_size))
        if tile_loc in self.tilemap:
            if self.tilemap[tile_loc]['type'] in PHYSICS_TILES:
                return self.tilemap[tile_loc]

    def physics_rects_around(self, pos):
        """Return a list of physics rectangles around a given position."""
        rects = []
        for tile in self.tiles_around(pos):
            if tile['type'] in PHYSICS_TILES:
                rects.append(pygame.Rect(tile['pos'][0] * self.tile_size, tile['pos'][1] * self.tile_size, self.tile_size, self.tile_size))
        return rects

    def autotile(self):
        """Apply autotiling rules to the tilemap."""
        for loc in self.tilemap:
            tile = self.tilemap[loc]
            neighbours = set()
            for shift in [(1, 0), (-1, 0), (0, -1), (0, 1)]:
                check_loc = str(tile['pos'][0] + shift[0]) + ';' + str(tile['pos'][1] + shift[1])
                if check_loc in self.tilemap and self.tilemap[check_loc]['type'] == tile['type']:
                    neighbours.add(shift)
            neighbours = tuple(sorted(neighbours))
            if (tile['type'] in AUTOTILE_TYPES) and (neighbours in AUTOTILE_MAP):
                tile['variant'] = AUTOTILE_MAP[neighbours]

    def render(self, surf, offset=(0, 0)):
        """Render the tilemap to the given surface with an optional offset."""
        for tile in self.offgrid_tiles:
            surf.blit(self.game.assets[tile['type']][tile['variant']], (tile['pos'][0] - offset[0], tile['pos'][1] - offset[1]))
        for x in range(offset[0] // self.tile_size, (offset[0] + surf.get_width()) // self.tile_size + 1):
            for y in range(offset[1] // self.tile_size, (offset[1] + surf.get_height()) // self.tile_size + 1):
                loc = f"{x};{y}"
                if loc in self.tilemap:
                    tile = self.tilemap[loc]
                    surf.blit(self.game.assets[tile['type']][tile['variant']], ((tile['pos'][0] * self.tile_size) - offset[0], (tile['pos'][1] * self.tile_size) - offset[1]))

# ENTITIES
class PhysicsEntity:
    def __init__(self, game, e_type, pos, size):
        """Initialize a physics entity with position, size, and velocity."""
        self.game = game
        self.type = e_type
        self.pos = list(pos)
        self.size = size
        self.velocity = [0, 0]  # Velocity in x and y directions
        self.collisions = {'up': False, 'down': False, 'right': False, 'left': False}  # Collision status
        self.action = ''
        self.anim_offset = (-3, -3)
        self.flip = False
        self.set_action('idle')
        self.last_movement = [0, 0]

    def rect(self):
        """Return the rectangular area of the entity."""
        return pygame.Rect(self.pos[0], self.pos[1], self.size[0], self.size[1])

    def set_action(self, action):
        """Set the action and corresponding animation of the entity."""
        if action != self.action:
            self.action = action
            self.animation = self.game.assets[f"{self.type}/{self.action}"].copy()

    def update(self, tilemap, movement=(0, 0)):
        """Update the entity's position and handle collisions."""
        self.collisions = {'up': False, 'down': False, 'right': False, 'left': False}
        frame_movement = [movement[0] + self.velocity[0], movement[1] + self.velocity[1]]

        # Handle horizontal movement and collision
        self.pos[0] += frame_movement[0]
        entity_rect = self.rect()
        for rect in tilemap.physics_rects_around(self.pos):
            if entity_rect.colliderect(rect):
                if frame_movement[0] > 0: # Moving right
                    entity_rect.right = rect.left
                    self.collisions['right'] = True
                if frame_movement[0] < 0: # Moving left
                    entity_rect.left = rect.right
                    self.collisions['left'] = True
                self.pos[0] = entity_rect.x

        # Handle vertical movement and collision
        self.pos[1] += frame_movement[1]
        entity_rect = self.rect()
        for rect in tilemap.physics_rects_around(self.pos):
            if entity_rect.colliderect(rect):
                if frame_movement[1] > 0:  # Moving down
                    entity_rect.bottom = rect.top
                    self.collisions['down'] = True
                if frame_movement[1] < 0:  # Moving up
                    entity_rect.top = rect.bottom
                    self.collisions['up'] = True
                self.pos[1] = entity_rect.y

        if movement[0] > 0:  # Moving right
            self.flip = False
        if movement[0] < 0:  # Moving left
            self.flip = True
        self.last_movement = movement

        # Apply gravity
        self.velocity[1] = min(5, self.velocity[1] + 0.1)
        if self.collisions['down'] or self.collisions['up']:
            self.velocity[1] = 0
        self.animation.update()

    def render(self, surf, offset=(0, 0)):
        """Render the entity to the given surface with an optional offset."""
        surf.blit(pygame.transform.flip(self.animation.img(), self.flip, False), (self.pos[0] - offset[0] + self.anim_offset[0], self.pos[1] - offset[1] + self.anim_offset[1]))

# ENEMY:
class Enemy(PhysicsEntity):
    def __init__(self, game, pos, size):
        super().__init__(game, 'enemy', pos, size)
        self.walking = 0

    def update(self, tilemap, movement=(0, 0)):
        if self.walking:
            if tilemap.solid_check((self.rect().centerx + (-7 if self.flip else 7), self.pos[1] + 23)):
                if (self.collisions['right'] or self.collisions['left']):
                    self.flip = not self.flip
                else:
                    movement = (movement[0] - 0.5 if self.flip else 0.5, movement[1])
            else:
                self.flip = not self.flip
            self.walking = max(0, self.walking - 1)
            if not self.walking:
                dis = (self.game.player.pos[0] - self.pos[0], self.game.player.pos[1] - self.pos[1])
                if (abs(dis[1] < 16)):
                    if (self.flip and dis[0] < 0):
                        self.game.sfx['shoot'].play()
                        self.game.projectiles.append([[self.rect().centerx - 7, self.rect().centery], -1.5, 0])
                        for i in range(4):
                            self.game.sparks.append(Spark(self.game.projectiles[-1][0], random.random() - 0.5 + math.pi, 2 + random.random()))
                    if (not self.flip and dis[0] > 0):
                        self.game.sfx['shoot'].play()
                        self.game.projectiles.append([[self.rect().centerx + 7, self.rect().centery], 1.5, 0])
                        for i in range(4):
                            self.game.sparks.append(Spark(self.game.projectiles[-1][0], random.random() - 0.5, 2 + random.random()))

        elif random.random() < 0.01:
            self.walking = random.randint(30, 120)
        super().update(tilemap, movement)
        if movement[0] != 0:
            self.set_action('run')
        else:
            self.set_action('idle')

        if abs(self.game.player.dashing) >= 50:
            if self.rect().colliderect(self.game.player.rect()):
                self.game.screenshake = max(16, self.game.screenshake)
                self.game.sfx['hit'].play()
                for i in range(30):
                    angle = random.random() * math.pi * 2
                    speed = random.random() * 5
                    self.game.sparks.append(Spark(self.rect().center, angle, 2 + random.random()))
                    self.game.particles.append(Particle(self.game, 'particle', self.rect().center, velocity = [math.cos(angle + math.pi) * speed * 0.5, math.sin(angle + math.pi) * speed * 0.5], frame = random.randint(0, 7)))
                self.game.sparks.append(Spark(self.rect().center, 0, 5 + random.random()))
                self.game.sparks.append(Spark(self.rect().center, math.pi, 5 + random.random()))
                return True

    def render(self, surf, offset = (0, 0)):
        super().render(surf, offset = offset)
        if self.flip:
            surf.blit(pygame.transform.flip(self.game.assets['gun'], True, False), (self.rect().centerx - 4 - self.game.assets['gun'].get_width() - offset[0], self.rect().centery - offset[1]))
        else:
            surf.blit(self.game.assets['gun'], (self.rect().centerx + 4 - offset[0], self.rect().centery - offset[1]))

# PLAYER
class Player(PhysicsEntity):
    def __init__(self, game, pos, size):
        super().__init__(game, 'player', pos, size)
        self.air_time = 0
        self.jumps = 2
        self.wall_slide = False
        self.dashing = 0
    
    def update(self, tilemap, movement=(0, 0)):
        super().update(tilemap, movement=movement)
        self.air_time += 1
        if self.air_time > 300:
            if not self.game.dead:
                self.game.screenshake = max(16, self.game.screenshake)
            self.game.dead += 1
            
        if self.collisions['down']:
            self.air_time = 0
            self.jumps = 2

        self.wall_slide = False
        if (self.collisions['right'] or self.collisions['left']) and self.air_time > 4:
            self.wall_slide = True
            self.velocity[1] = min(self.velocity[1], 0.5)
            if self.collisions['right']:
                self.flip = False
            else:
                self.flip = True
            self.set_action('wall_slide')

        if not self.wall_slide:
            if self.air_time > 4:
                self.set_action('jump')
            elif movement[0] != 0:
                self.set_action('run')
            else:
                self.set_action('idle')

        if abs(self.dashing) in {60, 50}:
            for i in range(20):
                angle = random.random() * math.pi * 2
                speed = random.random() * 0.5 + 0.5
                p_velocity = [math.cos(angle) * speed, math.sin(angle) * speed]
                self.game.particles.append(Particle(self.game, 'particle', self.rect().center, velocity = p_velocity, frame = random.randint(0, 7)))

        if self.dashing > 0:
            self.dashing = max(0, self.dashing - 1)
        if self.dashing < 0:
            self.dashing = min(0, self.dashing + 1)
        if abs(self.dashing) > 50:
            self.velocity[0] = abs(self.dashing) / self.dashing * 8
            if abs(self.dashing) == 51:
                self.velocity[0] *= 0.1
            p_velocity = [abs(self.dashing) / self.dashing * random.random() * 3, 0]
            self.game.particles.append(Particle(self.game, 'particle', self.rect().center, velocity = p_velocity, frame = random.randint(0, 7)))
        
        if self.velocity[0] > 0:
            self.velocity[0] = max(self.velocity[0] - 0.1, 0)
        else:
            self.velocity[0] = min(self.velocity[0] + 0.1, 0)

    def render(self, surf, offset=(0, 0)):
        if abs(self.dashing) <= 50:
            super().render(surf, offset = offset)

    def jump(self):
        if self.wall_slide:
            if self.flip:
                self.velocity[0] = 2.5
                self.velocity[0] -= 0.2
                self.velocity[1] = -3
                self.air_time = 5 
                self.jumps = 0
                return True
            elif not self.flip:
                self.velocity[0] = -2.5
                self.velocity[0] += 0.2
                self.velocity[1] = -2
                self.air_time = 5 
                self.jumps = 0
                return True

        elif self.jumps:
            self.velocity[1] = -3
            self.jumps -= 1
            self.air_time = 5
            return True

        elif self.jumps == 1:
            self.velocity[1] = -2.5
            self.jumps -= 1
            self.air_time = 5
            return True
        
    def dash(self):
        if not self.dashing:
            self.game.sfx['dash'].play()
            if self.flip:
                self.dashing = -60 
            else:
                self.dashing = 60

# SPARKS:
class Spark:
    def __init__(self, pos, angle, speed):
        self.pos = list(pos)
        self.angle = angle
        self.speed = speed
        
    def update(self):
        self.pos[0] += math.cos(self.angle) * self.speed
        self.pos[1] += math.sin(self.angle) * self.speed
        self.speed = max(0, self.speed - 0.1)
        return not self.speed
    
    def render(self, surf, offset=(0, 0)):
        render_points = [
            (self.pos[0] + math.cos(self.angle) * self.speed * 3 - offset[0], self.pos[1] + math.sin(self.angle) * self.speed * 3 - offset[1]),
            (self.pos[0] + math.cos(self.angle + math.pi * 0.5) * self.speed * 0.5 - offset[0], self.pos[1] + math.sin(self.angle + math.pi * 0.5) * self.speed * 0.5 - offset[1]),
            (self.pos[0] + math.cos(self.angle + math.pi) * self.speed * 3 - offset[0], self.pos[1] + math.sin(self.angle + math.pi) * self.speed * 3 - offset[1]),
            (self.pos[0] + math.cos(self.angle - math.pi * 0.5) * self.speed * 0.5 - offset[0], self.pos[1] + math.sin(self.angle - math.pi * 0.5) * self.speed * 0.5 - offset[1]),
        ]
        pygame.draw.polygon(surf, (255, 255, 255), render_points)


# MAIN GAME
class Game:
    def __init__(self):
        """Initialize the game, setting up the display, clock, and assets."""
        pygame.init()

        # CONSTANTS
        WIDTH, HEIGHT = 1000, 640  # Screen dimensions

        # DISPLAY
        pygame.display.set_caption('NINJA GAME')
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.display = pygame.Surface((320, 240), pygame.SRCALPHA)  # Main game display surface
        self.display_2 = pygame.Surface((320, 240))  # Secondary display surface for effects
        self.clock = pygame.time.Clock()  # Game clock
        self.count_dead = 0

        # COLLISION
        self.movement = [0, 0]  # Movement vector [horizontal, vertical]

        # PLAYER AND MAP ASSETS
        self.assets = {
            'decor': load_images('tiles/decor'),
            'grass': load_images('tiles/grass'),
            'large_decor': load_images('tiles/large_decor'),
            'stone': load_images('tiles/stone'),
            'player': load_image('entities/player.png'),
            'background': load_image('background.png'),
            'clouds': load_images('clouds'),
            'gun': load_image('gun.png'),
            'projectile': load_image('projectile.png'),
            'enemy/idle': Animation(load_images('entities/enemy/idle'), img_dur=6),
            'enemy/run': Animation(load_images('entities/enemy/run'), img_dur=4),
            'player/idle': Animation(load_images('entities/player/idle'), img_dur=6),
            'player/run': Animation(load_images('entities/player/run'), img_dur=4),
            'player/jump': Animation(load_images('entities/player/jump')),
            'player/slide': Animation(load_images('entities/player/slide')),
            'player/wall_slide': Animation(load_images('entities/player/wall_slide')),
            'particle/leaf': Animation(load_images('particles/leaf'), img_dur=20, loop=False),
            'particle/particle': Animation(load_images('particles/particle'), img_dur=6, loop=False)
        }

        # Initialize player, map, clouds, and camera
        self.player = Player(self, (50, 50), (8, 15))
        self.tilemap = Tilemap(self, tile_size=16)
        self.level = 0
        self.load_level(self.level)
        self.screenshake = 0  # Screenshake effect intensity
        self.sfx = {
            'jump': pygame.mixer.Sound('data/sfx/jump.wav'),
            'dash': pygame.mixer.Sound('data/sfx/dash.wav'),
            'hit': pygame.mixer.Sound('data/sfx/hit.wav'),
            'shoot': pygame.mixer.Sound('data/sfx/shoot.wav'),
            'ambience': pygame.mixer.Sound('data/sfx/ambience.wav')
        }
        # Set sound effect volumes
        self.sfx['jump'].set_volume(0.9)
        self.sfx['dash'].set_volume(0.5)
        self.sfx['hit'].set_volume(1)
        self.sfx['shoot'].set_volume(0.7)
        self.sfx['ambience'].set_volume(0.4)

        self.clouds = Clouds(self.assets['clouds'], count=16)  # Cloud effects

    def load_level(self, map_id):
        """Load the level based on the given map ID."""
        self.tilemap.load('data/maps/' + str(map_id) + '.json')

        # Initialize leaf spawners
        self.leaf_spawners = []
        for tree in self.tilemap.extract([('large_decor', 2)], keep=True):
            self.leaf_spawners.append(pygame.Rect(4 + tree['pos'][0], 4 + tree['pos'][1], 23, 13))

        # Initialize enemies and player spawn points
        self.enemies = []
        for spawner in self.tilemap.extract([('spawners', 0), ('spawners', 1)]):
            if spawner['variant'] == 0:
                self.player.pos = spawner['pos']
                self.player.air_time = 0
            else:
                self.enemies.append(Enemy(self, spawner['pos'], (8, 15)))

        # Initialize projectiles, particles, sparks, and camera scroll
        self.projectiles = []
        self.particles = []
        self.sparks = []
        self.scroll = [0, 0]
        self.dead = 0
        self.transition = -30

    def run(self):
        """Main game loop."""
        pygame.mixer.music.load('data/music.wav')
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)  # Loop background music
        self.sfx['ambience'].play(-1)  # Loop ambient sound

        while True:
            self.display.fill((0, 0, 0, 0))  # Clear the display
            self.display_2.blit(self.assets['background'], (0, 0))  # Display the background
            self.screenshake = max(0, self.screenshake - 1)  # Decrease screenshake effect

            if not self.enemies:  # If no enemies left, proceed to next level
                self.transition += 1
                if self.level ==  len(os.listdir('data/maps')) - 1:
                    self.level = 0
                    self.load_level(self.level)
                    print("You died:",self.count_dead, "times.")
                    self.count_dead = 0
                if self.transition == 30:
                    self.level = min(self.level + 1, len(os.listdir('data/maps')) - 1)
                    self.load_level(self.level)

            if self.transition < 0:
                self.transition += 1

            if self.dead:
                self.dead += 1
                if self.dead >= 10:
                    self.transition = min(30, self.transition + 1)
                if self.dead > 50:
                    self.load_level(self.level)

            # CAMERA: Smoothly follow the player
            self.scroll[0] += (self.player.rect().centerx - self.display.get_width() / 2 - self.scroll[0]) / 30
            self.scroll[1] += (self.player.rect().centery - self.display.get_height() / 2 - self.scroll[1]) / 30
            render_scroll = (int(self.scroll[0]), int(self.scroll[1]))

            # Spawn leaf particles randomly around leaf spawners
            for rect in self.leaf_spawners:
                if random.random() * 49999 < rect.width * rect.height:
                    pos = (rect.x + random.random() * rect.width, rect.y + random.random() * rect.height)
                    self.particles.append(Particle(self, 'leaf', pos, velocity=[-0.1, 0.3], frame=random.randint(0, 20)))

            # CLOUDS: Render the clouds
            self.clouds.update()
            self.clouds.render(self.display_2, offset=render_scroll)

            # MAP: Render the tilemap
            self.tilemap.render(self.display, offset=render_scroll)

            # Update and render enemies
            for enemy in self.enemies.copy():
                kill = enemy.update(self.tilemap, (0, 0))
                enemy.render(self.display, offset=render_scroll)
                if kill:
                    self.enemies.remove(enemy)

            # PLAYER: Update and render the player
            if not self.dead:
                self.player.update(self.tilemap, (self.movement[1] - self.movement[0], 0))
                self.player.render(self.display, offset=render_scroll)

            # PROJECTILES: Update and render projectiles
            for projectile in self.projectiles.copy():
                projectile[0][0] += projectile[1]
                projectile[2] += 1
                img = self.assets['projectile']
                self.display.blit(img, (projectile[0][0] - img.get_width() / 2 - render_scroll[0], projectile[0][1] - img.get_height() / 2 - render_scroll[1]))
                if self.tilemap.solid_check(projectile[0]):
                    self.projectiles.remove(projectile)
                    for i in range(4):
                        self.sparks.append(Spark(projectile[0], random.random() - 0.5 + (math.pi if projectile[1] > 0 else 0), 2 + random.random()))
                elif projectile[2] > 360:
                    self.projectiles.remove(projectile)
                elif abs(self.player.dashing) < 50:
                    if self.player.rect().collidepoint(projectile[0]):
                        self.projectiles.remove(projectile)
                        self.dead += 1
                        self.count_dead += 1
                        self.sfx['hit'].play()
                        self.screenshake = max(16, self.screenshake)
                        for i in range(30):
                            angle = random.random() * math.pi * 2
                            speed = random.random() * 5
                            self.sparks.append(Spark(self.player.rect().center, angle, 2 + random.random()))
                            self.particles.append(Particle(self, 'particle', self.player.rect().center, velocity=[math.cos(angle + math.pi) * speed * 0.5, math.sin(angle + math.pi) * speed * 0.5], frame=random.randint(0, 7)))

            # SPARKS: Update and render sparks
            for spark in self.sparks.copy():
                kill = spark.update()
                spark.render(self.display, offset=render_scroll)
                if kill:
                    self.sparks.remove(spark)

            # PARTICLES: Update and render particles
            display_mask = pygame.mask.from_surface(self.display)
            display_sillhouette = display_mask.to_surface(setcolor=(0, 0, 0, 180), unsetcolor=(0, 0, 0, 0))
            for offset in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                self.display_2.blit(display_sillhouette, offset)

            for particle in self.particles.copy():
                kill = particle.update()
                particle.render(self.display, offset=render_scroll)
                if particle.type == 'leaf':
                    particle.pos[0] += math.sin(particle.animation.frame * 0.035) * 0.3
                if kill:
                    self.particles.remove(particle)

            # KEYS: Handle user input
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    s = self.level + 1
                    print("You were on", s, "level.")
                    print("You died", self.count_dead, "times.")
                    pygame.quit()
                    sys.exit()
            
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.movement[0] = 1
                        self.movement[1] = 0
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.movement[1] = 1
                        self.movement[0] = 0
                    if event.type == pygame.KEYUP:
                        if event.key in (pygame.K_LEFT, pygame.K_a):
                            self.movement[0] = 1
                            self.movement[1] = 0
                        if event.key in (pygame.K_RIGHT, pygame.K_d):
                            self.movement[1] = 1
                            self.movement[0] = 0
                    if event.key in (pygame.K_UP, pygame.K_w):
                        if self.player.jump():
                            self.sfx['jump'].play()
                    
                    if event.key == pygame.K_x:
                        self.player.dash()
                    if event.key == pygame.K_SPACE:
                        self.load_level(self.level)
                if event.type == pygame.KEYUP:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.movement[0] = 0
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.movement[1] = 0

            # LEVEL TRANSITION EFFECT
            if self.transition:
                transition_surf = pygame.Surface(self.display.get_size())
                pygame.draw.circle(transition_surf, (255, 255, 255), (self.display.get_width() // 2, self.display.get_height() // 2), (30 - abs(self.transition)) * 8)
                transition_surf.set_colorkey((255, 255, 255))
                self.display.blit(transition_surf, (0, 0))

            self.display_2.blit(self.display, (0, 0))
            screenshake_offset = (random.random() * self.screenshake - self.screenshake / 2, random.random() * self.screenshake - self.screenshake / 2)
            # Scale the display and update the screen
            self.screen.blit(pygame.transform.scale(self.display_2, self.screen.get_size()), screenshake_offset)
            pygame.display.update()
            self.clock.tick(60)

class frun:
    def __init__(self):
        """Initialize the front-runner screen."""
        pygame.init()
        self.screen = pygame.display.set_mode((1000, 640), pygame.SRCALPHA)
        self.img = pygame.image.load('data/blue.png').convert()
        self.img = pygame.transform.scale(self.img, (1000, 640))  # Scale image to screen size
        pygame.display.set_caption("PRESS SPACE TO START THE GAME")
        self.run()

    def run(self):
        """Run the front-runner screen loop."""
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        Game().run()

            self.screen.blit(self.img, (0, 0))  # Blit the scaled image to the screen
            pygame.display.flip()

try:
    if __name__ == "__main__":
        frun()
except Exception as e:
    print("Exception:", e)
    pygame.quit()
    sys.exit()