import pygame
import json
import sys
import os

# CONSTANTS:
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
NEIGHBOUR_OFFSETS = [(1, 1), (1, 0), (1, -1), (0, 1), (0, 0), (0, -1), (-1, 1), (-1, 0), (-1, -1)]
PHYSICS_TILES = {'grass', 'stone'}  # Tiles that interact with physics
AUTOTILE_TYPES = {'grass', 'stone'}
BASE_IMG_PATH = 'data/images/'  # Base path for image assets
RENDER_SCALE = 2.0

# UTILITIES:
def load_image(path):
    """Load an image and set its colorkey to black for transparency."""
    img = pygame.image.load(BASE_IMG_PATH + path).convert()
    img.set_colorkey((0, 0, 0))
    return img

def load_images(path):
    """Load all images in a given directory and return them as a list."""
    images = []
    for img_name in os.listdir(BASE_IMG_PATH + path):
        images.append(load_image(path + '/' + img_name))
    return images

# TILEMAP:
class Tilemap:
    def __init__(self, game, tile_size=16):
        """Initialize the tilemap with a reference to the game and a tile size."""
        self.game = game
        self.tile_size = tile_size
        self.tilemap = {}
        self.offgrid_tiles = []  # Tiles to be drawn off the grid
    
    def extract(self, id_pairs, keep=False):
        """Extract and optionally remove tiles from the tilemap based on type and variant."""
        matches = []
        for tile in self.offgrid_tiles.copy():
            if (tile['type'], tile['variant']) in id_pairs:
                matches.append(tile.copy())
                if not keep:
                    self.offgrid_tiles.remove(tile)
        for loc in list(self.tilemap):
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
                check_loc = f"{tile['pos'][0] + shift[0]};{tile['pos'][1] + shift[1]}"
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

# MAP_EDITOR:
class Editor:
    def __init__(self):
        """Initialize the editor, setting up the display, clock, and assets."""
        pygame.init()

        # DISPLAY DIMENSIONS:
        WIDTH, HEIGHT = 640, 480
        
        # DISPLAY SETUP:
        pygame.display.set_caption('EDITOR')
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.display = pygame.Surface((320, 240))
        self.clock = pygame.time.Clock()

        # ASSETS: Load various tiles
        self.assets = {
            'decor': load_images('tiles/decor'),
            'grass': load_images('tiles/grass'),
            'large_decor': load_images('tiles/large_decor'),
            'stone': load_images('tiles/stone'),
            'spawners': load_images('tiles/spawners')
        }
        self.assets1 = {'background': load_image('background.png')}

        # MOVEMENT FLAGS:
        self.movement = [0, 0, 0, 0]  # Movement direction flags for scrolling
        self.tilemap = Tilemap(self, tile_size=16)
        try:
            self.tilemap.load('map.json')
        except FileNotFoundError:
            pass
        self.scroll = [0, 0]  # Camera scroll offset
        self.tile_list = list(self.assets)  # List of tile types
        self.tile_group = 0  # Current tile group
        self.tile_variant = 0  # Current tile variant
        self.left_clicking = False  # Left mouse button state
        self.right_clicking = False  # Right mouse button state
        self.shift = False  # Shift key state
        self.ongrid = True  # Toggle between grid and free placement

    def run(self):
        """Main editor loop."""
        while True:
            self.display.blit(self.assets1['background'], (0, 0)) # Clear the display with a background.

            # Calculate render offset
            render_scroll = (int(self.scroll[0]), int(self.scroll[1]))
            self.tilemap.render(self.display, offset=render_scroll)

            # Display the currently selected tile type and variant in a semi-transparent manner.
            current_tile_img = self.assets[self.tile_list[self.tile_group]][self.tile_variant].copy()
            current_tile_img.set_alpha(200)
            mpos = pygame.mouse.get_pos()
            mpos = (mpos[0] / RENDER_SCALE, mpos[1] / RENDER_SCALE)
            tile_pos = (int((mpos[0] + self.scroll[0]) // self.tilemap.tile_size), int((mpos[1] + self.scroll[1]) // self.tilemap.tile_size))

            if self.ongrid:
                self.display.blit(current_tile_img, (tile_pos[0] * self.tilemap.tile_size - self.scroll[0], tile_pos[1] * self.tilemap.tile_size - self.scroll[1]))
            else:
                self.display.blit(current_tile_img, mpos)
            
            # Handle placing and removing tiles
            if self.left_clicking and self.ongrid:
                self.tilemap.tilemap[f"{tile_pos[0]};{tile_pos[1]}"] = {'type': self.tile_list[self.tile_group], 'variant': self.tile_variant, 'pos': tile_pos}
            if self.right_clicking:
                tile_loc = f"{tile_pos[0]};{tile_pos[1]}"
                if tile_loc in self.tilemap.tilemap:
                    del self.tilemap.tilemap[tile_loc]
                for tile in self.tilemap.offgrid_tiles.copy():
                    tile_img = self.assets[tile['type']][tile['variant']]
                    tile_r = pygame.Rect(tile['pos'][0] - self.scroll[0], tile['pos'][1] - self.scroll[1], tile_img.get_width(), tile_img.get_height())
                    if tile_r.collidepoint(mpos):
                        self.tilemap.offgrid_tiles.remove(tile)
            
            # Handle user input
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        self.left_clicking = True
                        if not self.ongrid:
                            self.tilemap.offgrid_tiles.append({'type': self.tile_list[self.tile_group], 'variant': self.tile_variant, 'pos': (mpos[0] + self.scroll[0], mpos[1] + self.scroll[1])})
                    if event.button == 3:
                        self.right_clicking = True
                    if self.shift:
                        if event.button == 4:
                            self.tile_variant = (self.tile_variant - 1) % len(self.assets[self.tile_list[self.tile_group]])
                        if event.button == 5:
                            self.tile_variant = (self.tile_variant + 1) % len(self.assets[self.tile_list[self.tile_group]])
                    else:
                        if event.button == 4:
                            self.tile_group = (self.tile_group - 1) % len(self.tile_list)
                            self.tile_variant = 0
                        if event.button == 5:
                            self.tile_group = (self.tile_group + 1) % len(self.tile_list)
                            self.tile_variant = 0
                if event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        self.left_clicking = False
                    if event.button == 3:
                        self.right_clicking = False
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.movement[0] = 1
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.movement[1] = 1
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.movement[2] = 1
                    if event.key in (pygame.K_DOWN, pygame.K_s):
                        self.movement[3] = 1
                    if event.key == pygame.K_g:
                        self.ongrid = not self.ongrid
                    if event.key == pygame.K_t:
                        self.tilemap.autotile() 
                    if event.key == pygame.K_o:
                        self.tilemap.save('map.json')
                    if event.key == pygame.K_LSHIFT:
                        self.shift = True
                if event.type == pygame.KEYUP:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.movement[0] = 0
                    if event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.movement[1] = 0
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.movement[2] = 0
                    if event.key in (pygame.K_DOWN, pygame.K_s):
                        self.movement[3] = 0
                    if event.key == pygame.K_LSHIFT:
                        self.shift = False

            # Update scroll position based on input
            self.scroll[0] += (self.movement[1] - self.movement[0]) * 5
            self.scroll[1] += (self.movement[3] - self.movement[2]) * 5

            # Render the tilemap with the current scroll offset
            self.tilemap.render(self.display, offset=self.scroll)

            # Scale the display and update the screen
            self.screen.blit(pygame.transform.scale(self.display, self.screen.get_size()), (0, 0))
            pygame.display.update()
            self.clock.tick(60)

if __name__ == "__main__":
    Editor().run()
