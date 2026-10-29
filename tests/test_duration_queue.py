import unittest
from pathlib import Path

from mirivue.duration_queue import DurationQueue


class DurationQueueTests(unittest.TestCase):
    def test_visible_arrival_precedes_unread_background_and_is_not_duplicated(self):
        queue = DurationQueue()
        background = [Path(f'/media/{index}.mkv') for index in range(100)]
        queue.add(background, background[20:23])
        self.assertEqual([queue.take() for _ in range(3)], background[20:23])
        arrival = Path('/media/new.mkv')
        queue.add([arrival, background[0]], [arrival])
        self.assertEqual(queue.take(), arrival)
        self.assertEqual(queue.drain(), background[:20] + background[23:])
        self.assertIsNone(queue.take())


if __name__ == '__main__':
    unittest.main()
