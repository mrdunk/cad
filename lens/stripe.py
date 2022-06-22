#!/usr/bin/env python3

from typing import Tuple, Optional
from math import sqrt
import matplotlib.pyplot as plt

Point = Tuple[float, float, float]

def distance(a: Point, b: Point) -> float:
    return sqrt((a[0] - b[0]) ** 2 +
                (a[1] - b[1]) ** 2 +
                (a[2] - b[2]) ** 2)

def extrapolate(origin: Point, point: Point, radius: float) -> Optional[Point]:
    """ Updates the z parameter of point in place. """
    centered = (point[0] - origin[0], point[1] - origin[1], 0)
    value = round(radius ** 2 - centered[0] ** 2 - centered[1] ** 2, 2)
    if value < 0:
        return None
    return (round(centered[0] + origin[0], 2),
            round(centered[1] + origin[1], 2),
            round(sqrt(value) + origin[2], 2))


class Display:
    line_x = []
    line_y = []

    def append(self, point: Point) -> None:
        self.line_x.append(point[0])
        self.line_y.append(point[2])

    def show(self) -> None:
        plt.plot(self.line_x, self.line_y, c="blue", linewidth=1)
        self.line_x = []
        self.line_y = []

    @staticmethod
    def final():
        plt.gca().set_aspect('equal')
        plt.show()


def to_gcode(lines, size):
    filename = '/tmp/circle.gcode'
    output = []
    safe_z = 0
    feed_z = 500
    feed_xy = 1200
    count = 0
    shift_x = -size / 2
    shift_y = -size / 2

    output.append('(Block-name: header)')
    output.append(f'G0 Z{str(safe_z)}')

    for line in lines:
        output.append(f'(Block-name: Start {count})')
        count += 1
        output.append(f'G0 Z{str(safe_z)}')
        first_point = line[0]
        output.append(f'G0 X{str(first_point[0] + shift_x)} Y{str(first_point[1] + shift_y)} Z{str(safe_z)}')
        output.append(f'G1 Z{str(first_point[2])} F{str(feed_z)}')
        for point in line:
            output.append(f'G1 X{str(point[0] + shift_x)} Y{str(point[1] + shift_y)} Z{str(point[2])} F{str(feed_xy)}')

    with open(filename, 'w') as f:
        f.write('\n'.join(output))

    print(f'Written gcode to {filename}')


def main():
    display = Display()

    radius = 75
    size = 75
    range_x = size
    range_y = size
    step_size = 0.05

    origin = (range_x / 2, range_y / 2, -2 - radius)

    lines = []
    line = []

    y = 0
    while y <= range_y:
        x = 0
        while x <= range_x:
            point = extrapolate(origin, (x, y, 0), radius)
            #print(point)
            if point is not None:
                line.append(point)

            x += step_size

        y += step_size

        lines.append(line)
        line = []


    filtered_lines = []

    mid_line = lines[int(len(lines) / 2)]
    lowest_z = mid_line[0][2]
    highest_z = origin[2]
    for line in lines:
        for point in line:
            if point[2] > highest_z:
                highest_z = point[2]
                lowest_z = line[0][2]

    print(f'{lowest_z=}\t{highest_z=}\tthickness={highest_z-lowest_z}')

    filtered_lines = []
    for line in lines:
        filtered_line = [point for point in line if point[2] >= lowest_z]
        filtered_lines.append(filtered_line)

    for line in filtered_lines:
        for point in line:
            display.append(point)
        display.show()

    display.final()

    to_gcode(filtered_lines, size)

main()
