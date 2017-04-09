import logging
from math import sqrt
import os
from unittest.case import TestCase

from zombie_invasion import (Grid, Human, InvalidPositionError, Zombie, ZombieInvasionRunner)
import random


logging.basicConfig(level=getattr(logging, os.environ.get('LOGLEV', 'ERROR')))


class CharacterTestCase(TestCase):
    def setUp(self):
        self.grid = Grid()
        self.human = Human(self.grid)
        self.zombie = Zombie(self.grid)

    def test_validate_rejects_out_of_grid_positions(self):
        self.assertRaises(InvalidPositionError, self.human.validate_position,
                          (self.grid.X, self.grid.Y // 2))
        self.assertRaises(InvalidPositionError, self.human.validate_position,
                          (self.grid.X // 2, self.grid.Y))

    def test_human_move_advances_no_more_than_npaces(self):
        pos = (self.grid.X // 2, self.grid.Y // 2)
        newpos = self.human.move(pos)
        self.assertLessEqual(sqrt((newpos[0] - pos[0])**2 + (newpos[1] - pos[1])**2), self.human.npaces)

    def test_zombie_move_reaches_opposite_corner(self):
        pos = (0, 0)
        self.grid.positions[self.human] = (self.grid.X - 1, self.grid.Y - 1)
        self.zombie.npaces = self.grid.X * self.grid.Y
        newpos = self.zombie.move(pos)
        self.assertEqual(newpos, self.grid.positions[self.human])

    def test_zombie_move_reaches_random_cell(self):
        pos = (0, 0)
        self.grid.positions[self.human] = (
            random.randint(1, self.grid.X - 1),
            random.randint(1, self.grid.Y - 1),
        )
        self.zombie.npaces = self.grid.X * self.grid.Y
        newpos = self.zombie.move(pos)
        self.assertEqual(newpos, self.grid.positions[self.human])


class ZombieInvasionRunnerTestCase(TestCase):
    def setUp(self):
        self.sim = ZombieInvasionRunner()

    def test_simulator_ternminates_in_non_zero_turn_count(self):
        self.sim.run()
        self.assertGreater(self.sim.turn, 0)

    def test_simulator_leaves_no_humans_or_no_zombies(self):
        self.sim.run()
        self.assertTrue(self.sim.count_of(Human) == 0 or self.sim.count_of(Zombie) == 0)

    def test_simulator_leaves_proper_characters_count(self):
        self.sim = ZombieInvasionRunner(config=dict(character_types=(Human, Zombie)))
        self.sim.run()
        self.assertEqual(filter(None, [self.sim.count_of(Zombie), self.sim.count_of(Human)])[0],
                         Zombie.initial + Human.initial)
