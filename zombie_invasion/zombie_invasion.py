from abc import ABCMeta
import logging
import random

import kdtree

log = logging.getLogger(__name__)


class InvalidPositionError(Exception):
    '''
    Exception raised when character position fails validation
    '''


def gen_random_vector(length):
    '''
    Generate a random 2-vector in one of cardinal or semi-cardinal directions (N,NE,E,SE,S,SW,W,NW)

    @param length: vector length

    @return: vector 
    '''
    vector = [0, 0]
    vector[0] = random.choice([0, length, -length])
    # second coordinate may not be null if the first one is null
    vector[1] = random.choice([0] if vector[0] else [] + [length, -length])
    return vector


class Character(object):
    '''Abstract class for all characters'''

    __metaclass__ = ABCMeta

    def __init__(self, grid):
        '''
        Initialize the character

        @param grid: a Grid instance to which the character belongs
        '''
        self.grid = grid

    @property
    def position(self):
        '''Return character position in the grid'''
        return self.grid.positions[self]

    def get_random_position(self):
        '''
        Generate a random position on the grid as a tuple of coordinates

        @return: coordinates tuple
        '''
        return (random.randint(0, self.grid.X - 1), random.randint(0, self.grid.Y - 1))

    def validate_position(self, newpos):
        '''
        Validate new character position
        If a pace places character beyond the grid or bumps into a wall
        then the pace is not taken and is forfit.

        @param newpos: new position tuple

        @raise InvalidPositionError: when new position is out of grid
        '''
        if not((0 <= newpos[0] < self.grid.X) and
               (0 <= newpos[1] < self.grid.Y)):
            raise InvalidPositionError(newpos)

    @classmethod
    def populate(cls, grid):
        '''
        Populate initial positions for this character type.

        @param cls: character class
        @param grid: a ZombieInvasion instance to which the character belongs
        '''
        for _ in range(cls.initial):
            character = cls(grid)
            grid.positions[character] = character.get_random_position()
            log.debug('Placing %s at %s', character.name, grid.positions[character])

    def interact(self, pos):
        '''
        Interact with other characters

        @param pos: this character's position
        '''
        pass

    def __repr__(self):
        return '%s %s' % (self.name, id(self))

    def __str__(self):
        return repr(self)


class Human(Character):
    '''Human character class'''

    name = 'Human'
    npaces = 3
    initial = 30

    def move(self, pos):
        '''
        Randomly move character by a number of paces.
        Directions limited to (N,NE,E,SE,S,SW,W,NW).

        @param pos: initial position

        @return: new position
        '''
        vector = gen_random_vector(self.npaces)
        log.debug('Move vector for %s: %s', self, vector)
        newpos = (pos[0] + vector[0], pos[1] + vector[1])
        return newpos


class Hunter(Human):
    '''Hunter character class'''

    initial = 60
    slugs = 3
    reload_turns = 3

    def __init__(self, *args, **kw):
        super(Hunter, self).__init__(*args, **kw)
        self.slugs_left = self.slugs
        self.last_shot = None

    def interact(self, pos):
        '''
        Interact with other characters.

        When a Witchhunter is adjacent to a Zombie
        he will shoot and kill the Zombie (removing the Zombie from the grid).
        A Witchunter can only shoot once per turn and has S number of slugs before he must reload.
        It takes R turns for the Whichhunter to reload the Shotgun.
        The Whichhunter is also Human and will be turned into a Zombie if he occupies the same square as a Zombie.

        @param pos: current position tuple
        '''
        if (self.slugs_left == 0 and
                (self.last_shot is None or self.grid.turn - self.last_shot > self.reload_turns)):
            log.debug('Restoring slug count for %s, last shot: %s', self, self.last_shot)
            self.slugs_left = self.slugs

        for character in self.grid.positions.keys():
            if (
                self.grid.is_adjacent(character.position, self.position) and
                isinstance(character, Zombie) and
                self.slugs_left > 0 and
                self.last_shot != self.grid.turn
            ):
                log.info('Shooting %s at %s', character, character.position)
                self.slugs_left -= 1
                self.last_shot = self.grid.turn
                self.grid.remove(character)


class Zombie(Character):
    '''Zombie character class'''

    name = 'Zombie'
    npaces = 1
    initial = 3

    def __init__(self, *args, **kw):
        super(Zombie, self).__init__(*args, **kw)
        self.last_hunted = None

    def get_random_position(self):
        '''
        Generate a random position.

         A number of Zombies Z will be randomly placed in the grid (In red)
         but will not occupy a sqaure that is already occupied by a Human or Zombie.

         @return: generated position tuple
        '''
        while True:  # FIXME: infinite loop
            pos = (random.randint(0, self.grid.X), random.randint(0, self.grid.Y))
            if pos not in self.grid.positions.values():
                return pos

    def _find_nearest(self, pos, character_type, max_neighbors):
        '''
        Find nearest neighbors to this character

        @param pos: position of original character
        @param character_type: type of target chracters
        @param max_neighbors: max. neighbors to consider
        '''
        target_positions = self.grid.positions_of(character_type)
        if not target_positions:
            log.debug('find nearest: no %s left', character_type)
            return []

        log.debug('Building a k-d tree of %s neighbors for %s out of %s',
                  character_type, self, target_positions)
        tree = kdtree.create(target_positions)
        node_dist_list = tree.search_knn(pos, max_neighbors)
        log.debug('Nearest nodes to %s: %s', self, node_dist_list)
        # rank by distance
        dist_list = [length[1] for length in node_dist_list
                     # distance 0 ignored: these will be turned anyway
                     if length[1] != 0]
        if not dist_list:
            log.debug('find nearest: no %s left at dist>0', character_type)
            return []
        min_dist = min(dist_list)
        log.debug('Min distance: %d', min_dist)
        # get those at min_dist
        nearest = [length[0].data for length in node_dist_list if length[1] == min_dist]
        log.debug('Nearest: %s', nearest)
        return nearest

    def _walk_to(self, pos, target):
        '''
        Walk to the target cell limiting the number of paces

        @requires: self.npaces

        @param pos: initial position tuple
        @param target: target position tuple

        @return: new position tuple
        '''
        newpos = list(pos)
        for _ in range(self.npaces):
            for dim in range(len(pos)):
                shift = (target[dim] - newpos[dim]) / (abs(target[dim] - newpos[dim]) or 1)
                log.debug('shift on dim %d = %d', dim, shift)
                newpos[dim] = newpos[dim] + shift
            log.debug('walk to: target=%s current=%s', target, tuple(newpos))
            if tuple(newpos) == tuple(target):
                break

        return tuple(newpos)

    def move(self, pos):
        '''
        Move Zombie characters.

        Each turn each Zombie will walk `npaces` paces in towards the nearest Human (measured in paces).
        If there are multiple Humans the same distance away then the Zombie will hunt
        one at random unless the Human that the Zombie hunted last turn is amongst
        the nearest Humans, if so the Zombie will always continue to hunt the same Human.

        @param pos: initial position

        @return: new position
        '''
        nearest = self._find_nearest(pos, Human,
                                     # max number of neighbors reached if they are all at the grid edges
                                     self.grid.X * 2 + self.grid.Y * 2)
        if not nearest:
            log.debug('No nearest %s found, %s standing still', Human, self)
            return pos
        if self.last_hunted not in nearest:
            self.last_hunted = random.choice(nearest)
            log.debug('Last hunted escaped, chosen new one: %s', self.last_hunted)

        assert self.last_hunted is not None
        return self._walk_to(pos, self.last_hunted)

    def interact(self, pos):
        '''
        Interact with other characters.

            If a Zombie and a Human exist on exactly the same sqaure
            then the Human is turned into a Zombie and will change colour
            and begin to behave as a Zombie.

        @param pos: current position tuple
        '''
        for character in self.grid.positions:
            if (character.position == self.position and
                    isinstance(character, Human)):
                log.info('Turning %s into %s at %s', character, self.name, pos)
                character.__class__ = self.__class__
                character.last_hunted = None


class Grid(object):
    '''
    Basic 2D grid with character positions
    '''

    X = 60
    '''Grid X size'''
    Y = 40
    '''Grid Y size'''

    def __init__(self):
        self.positions = {}
        '''
        A dict mapping characters to coordinate tuples.
        Coordinates start at upper left (NW) corner and are zero-based.
        '''
        self.turn = 0
        '''Number of turns since simulator start'''

    def populate_positions(self):
        '''
        Place initial characters into positions
        '''
        for character_type in self.character_types:
            log.debug('Placing %s characters in initial positions', character_type.name)
            character_type.populate(self)

    def move_characters(self):
        '''Request all characters to adjust positions'''
        for character in self.positions:
            pos = self.positions[character]
            newpos = character.move(pos)
            try:
                character.validate_position(newpos)
            except InvalidPositionError:
                log.debug('Forfeiting %s move due to out of grid position: %s', character, newpos)
            else:
                log.debug('New position for %s is %s', character, newpos)
                self.positions[character] = newpos

    def positions_of(self, character_type):
        '''
        Return positions list of certain type of characters

        @param character_type: character class

        @return: list of position tuples
        '''
        return [self.positions[c] for c in self.positions if isinstance(c, character_type)]

    def count_of(self, character_type):
        '''
        Return number of certain type of characters left on the grid

        @param character_type: character class

        @return: number of characters left
        '''
        return len(set([c for c in self.positions if isinstance(c, character_type)]))

    def remove(self, character):
        '''
        Remove character from the grid

        @param character: character to remove
        '''
        try:
            del self.positions[character]
        except KeyError:
            pass

    def is_adjacent(self, pos1, pos2):
        '''
        Check whether two positions are adjacent
        @param pos1: 1st position tuple
        @param pos2: 2nd position tuple

        @return: True if positions are ajacent, False otherwise
        '''
        return (abs(pos1[0] - pos2[0]) == 1) and (abs(pos1[1] - pos2[1]) == 1)


class ZombieInvasion(Grid):
    '''
    The Zombie Invasion Simulator
    '''

    character_types = (Human, Hunter, Zombie)
    '''Available character types'''

    def __init__(self, config=None):
        '''
        Initialize the simulator

        @param config: (optional) a dict with simulator parameters
        '''
        if config:
            for param in config:
                setattr(self, param, config[param])

        super(ZombieInvasion, self).__init__()
        self.populate_positions()

    def process_character_interactions(self):
        '''
        Perform state changes based on current positions
        '''
        for character in self.positions.keys():
            try:
                pos = self.positions[character]
            except KeyError:
                continue
            character.interact(pos)

    def make_turn(self):
        '''
        Advance the simulator state by a single turn
        '''
        log.debug('Making turn %d', self.turn)
        self.process_character_interactions()
        self.move_characters()
        self.turn += 1


class ZombieInvasionRunner(ZombieInvasion):
    '''
    ZombieInvasion simulator runner
    '''

    def report_status(self):
        '''
        Report simulator status
        '''
        log.debug('Turn: %d Humans: %d Zombies: %d', self.turn,
                  self.count_of(Human), self.count_of(Zombie))

    def run(self):
        '''
        Run make_turn() repeatedly until no Humans left
        and report the number of steps it took to finish
        '''
        while self.count_of(Human) > 0 and self.count_of(Zombie):
            self.make_turn()
            self.report_status()
        log.info('Completed in %d turns', self.turn)


class ZombieInvasionTerminalRunner(ZombieInvasionRunner):
    def report_status(self):
        print "\033[H\033[J"
        print 'Zombie Invasion Simulator :: ',
        print 'Turn:', self.turn,
        print "\x1b[1;32mHumans: %02d\x1b[0m" % self.count_of(Human),
        print "\x1b[1;34mHunters: %02d\x1b[0m" % self.count_of(Hunter),
        print "\x1b[1;31mZombies: %02d\x1b[0m" % self.count_of(Zombie),
        print

        revpos = {}
        for k, v in self.positions.iteritems():
            revpos.setdefault(v, []).append(k)

        for y in range(self.Y):
            for x in range(self.X):
                characters = revpos.get((x, y), None)
                if not characters:
                    print '00',
                elif any([isinstance(c, Zombie) for c in revpos[(x, y)]]):
                    print "\x1b[1;31m%02d\x1b[0m" % len(characters),
                elif any([isinstance(c, Hunter) for c in revpos[(x, y)]]):
                    print "\x1b[1;34m%02d\x1b[0m" % len(characters),
                elif all([isinstance(c, Human) for c in revpos[(x, y)]]):
                    print "\x1b[1;32m%02d\x1b[0m" % len(characters),
                else:
                    print '??',
            print


if __name__ == '__main__':
    import os
    logging.basicConfig(level=getattr(logging, os.environ.get('LOGLEV', 'WARNING')))
    ZombieInvasionTerminalRunner().run()
