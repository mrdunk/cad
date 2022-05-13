#!/usr/bin/env python3

from typing import Dict, Tuple, List, Union
from enum import Enum

import argparse
import math 
import sys

Point2 = Tuple[float, float]
Point3 = Tuple[float, float, float]

ROUNDING = 3

class LensStyle(Enum):
    CONCAVE = 1
    CONVEX = 2

class Arc:
    def __init__(
            self,
            center: Tuple[float, ...],
            radius: float,
            start_angle: float,
            end_angle: float,
            start_height: float=0,
            end_height: float=0):
        self.center = center
        if len(center) == 2:
            self.center = (center[0], center[1], 0.0)
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle
        self.start_height = start_height
        self.end_height = end_height

    def start_point(self) -> Point3:
        return (
                round(
                    math.cos(math.radians(-self.start_angle)) * self.radius + self.center[0],
                    ROUNDING),
                round(
                    math.sin(math.radians(-self.start_angle)) * self.radius + self.center[1],
                    ROUNDING),
                self.start_height
                )

    def end_point(self) -> Point3:
        return (
                round(
                    math.cos(math.radians(-self.end_angle)) * self.radius + self.center[0],
                    ROUNDING),
                round(
                    math.sin(math.radians(-self.end_angle)) * self.radius + self.center[1],
                    ROUNDING),
                self.end_height
                )

def spiral(center: Union[Point2, Point3], apature: float, step_size: float) -> List[Arc]:
    arcs: List[Arc] = []
    loop: float = 0.25
    offset: List[float] = [0.0, 0.0]
    while loop * step_size < apature / 2:
        orientation = round(loop * 4) % 4
        if orientation == 0:
            start_angle = 0
            end_angle = 90
            offset[0] -= step_size / 4
            section_radius = loop * step_size
        elif orientation == 1:
            start_angle = 90
            end_angle = 180
            offset[1] += step_size / 4
            section_radius = loop * step_size
        elif orientation == 2:
            start_angle = 180
            end_angle = 270
            offset[0] += step_size / 4
            section_radius = loop * step_size
        elif orientation == 3:
            start_angle = 270
            end_angle = 0
            offset[1] -= step_size / 4
            section_radius = loop * step_size
        else:
            raise

        section_center = (center[0] + offset[0], center[1] + offset[1])
        arcs.append(Arc(section_center, section_radius, start_angle, end_angle))

        loop += 0.25  # 1/4 turn.
    arcs.append(Arc(center, apature / 2, end_angle, end_angle))

    return arcs

def surface_height(
        point: Point3,
        center_curvature: Point3,
        radius_curvature: float,
        style: LensStyle) -> Point3:
    # x**2 + y**2 + z**2 == radius**2
    centered_x = point[0] - center_curvature[0]
    centered_y = point[1] - center_curvature[1]
    if style is LensStyle.CONVEX:
        height_squared = radius_curvature ** 2 - centered_x ** 2 - centered_y ** 2
    else:
        height_squared = radius_curvature ** 2 + centered_x ** 2 + centered_y ** 2
    if height_squared < 0:
        height = 0
    else:
        height = math.sqrt(height_squared)
    height = round(height + center_curvature[2], ROUNDING)

    return tuple(point[:2] + (height,))

def spiral_to_lens(
        arcs: List[Arc],
        center_curvature: Point3,
        radius_curvature: float,
        style: LensStyle = LensStyle.CONVEX,
        z_offset = 0
        ) -> List[Arc]:
    previous_arc = None
    for arc in arcs:
        point = surface_height(arc.start_point(), center_curvature, radius_curvature, style)
        arc.start_height = point[2] + z_offset

        if previous_arc is not None:
            previous_arc.end_height = arc.start_height
        previous_arc = arc

    last_end_point = surface_height(
            arcs[-1].end_point(), center_curvature, radius_curvature, style)
    arcs[-1].end_height = last_end_point[2] + z_offset

def header_gcode(safe_z: float) -> List[str]:
    output = []
    output.append('(Block-name: header)')
    output.append(f'G0 Z{str(safe_z)}')

    return output

def footer_gcode(safe_z: float) -> List[str]:
    output = []
    output.append('(Block-name: footer)')
    output.append(f'G0 Z{str(safe_z)} ')

    return output

def free_part_gcode(
        center: Point3,
        apature: float,
        diameter: float,
        doc: float,
        material_thickness: float,
        safe_z: float,
        feed_z: float,
        feed_xy: float
        ) -> List[str]:

    if not diameter or diameter <= 0:
        return []
    if not doc or doc <= 0:
        return []
    if not material_thickness or material_thickness <= 0:
        return []

    combined_diamiter = apature / 2 + diameter
    output = []
    output.append(f'(Block-name: Free part)')
    output.append(f'G0 Z{str(safe_z)}')
    output.append(f'G0 X{str(center[0] + combined_diamiter)} Y{str(center[1])}')
    output.append(f'F{str(feed_z)}')
    output.append('G1 Z0')
    output.append(f'F{str(feed_xy)}')

    height = 0
    while height > -material_thickness:
        height -= doc
        output.append(
                f'G2 X{str(center[0] + combined_diamiter)} Y{str(center[1])} '
                f'Z{str(height)} '
                f'I{str(-combined_diamiter)} J0.0')

    output.append(
            f'G2 X{str(center[0] + combined_diamiter)} Y{str(center[1])} '
            f'Z{str(-material_thickness)} '
            f'I{str(-combined_diamiter)} J0.0')
    return output

def arcs_to_gcode(
        arcs: List[Arc],
        safe_z: float,
        feed_z: float,
        feed_xy: float
        ) -> Tuple[List[str], Dict[str, int]]:
    output = []
    summary_data = {
            'lowest': None,
            'highest': None,
            }

    if arcs:
        arc = arcs[0]
        output.append(f'(Block-name: Spiral)')
        output.append(f'G0 Z{str(safe_z)}')
        start_point = arc.start_point()
        output.append(f'G0 X{str(start_point[0])} Y{str(start_point[1])}')
        output.append(f'F{str(feed_z)}')
        output.append(f'G1 Z{str(start_point[2])}')
        output.append(f'F{str(feed_xy)}')

        summary_data['highest'] = start_point[2]
        summary_data['lowest'] = start_point[2]

    for arc in arcs:
        start_point = arc.start_point()
        end_point = arc.end_point()
        offset_i = arc.center[0] - start_point[0]
        offset_j = arc.center[1] - start_point[1]
        output.append(
                f'G2 X{str(end_point[0])} Y{str(end_point[1])} Z{str(end_point[2])} '
                f'I{str(offset_i)} J{str(offset_j)}')

        summary_data['highest'] = max(summary_data['highest'], end_point[2])
        summary_data['lowest'] = min(summary_data['lowest'], end_point[2])

    return (output, summary_data)

def write_gcode(gcode_lines: List[str], filename: str) -> None:
    with open(filename, 'w') as f:
        f.write('\n'.join(gcode_lines))

def check_integraty(arcs: List[Arc]) -> None:
    last_point = None
    for arc in arcs:
        print(f'{arc.start_point()}\t{arc.start_angle}\t{arc.end_point()}\t{arc.end_angle}')
        if last_point is not None:
            assert arc.start_point() == last_point
        last_point = arc.end_point()

def args_summary(args) -> None:
    print('Ran with parameters:')
    command_line = f'\t{sys.argv[0]}'
    for key, value in vars(args).items():
        command_line += f' --{key}={value}'
    print(command_line)
    if args.free_part or args.free_part_doc:
        if not args.free_part or not args.free_part_doc or not args.material_thickness:
            print()
            print("  WARNING: If either free_part or free_part_doc is set, "
            "free_part, free_part_doc and material_thickness must all be set.")
            print(f'    free_part: {args.free_part}')
            print(f'    free_part_doc: {args.free_part_doc}')
            print(f'    material_thickness: {args.material_thickness}')

def summary(summary_data, args) -> None:
    print()
    print(f'Highest point: {summary_data["highest"]}')
    print(f'Lowest point:  {summary_data["lowest"]}')
    if summary_data["highest"] >= args.safe_z:
        print('  WARNING: safe_z is lower than highest point on lens.')
    if (args.material_thickness is not None and 
            summary_data["highest"] - summary_data['lowest'] >= args.material_thickness):
        print('  WARNING: Lens thicker than material.')
        print(f'    material_thickness: {args.material_thickness}')

def main():
    parser = argparse.ArgumentParser(description='Generate gcode for lens shapes.')
    parser.add_argument(
            '-f',
            '--filename',
            metavar='FILENAME',
            help='output filename',
            default='/tmp/lens.gcode')
    parser.add_argument(
            '-t',
            '--lens_type',
            metavar='TYPE',
            choices=['concave', 'convex'],
            default='convex',
            help='type of lens. Default: convex')
    parser.add_argument(
            '-a',
            '--aperture',
            metavar='APERTURE',
            help='diameter of lens',
            type=float,
            default='100')
    parser.add_argument(
            '-c',
            '--radius_curvature',
            metavar='RADIUS_CURVATURE',
            help='radius curvature of lens. 2 * focal_length.',
            type=float,
            default='500')
    parser.add_argument(
            '-x',
            '--x_offset',
            metavar='X_OFFSET',
            help='offset X coordinate of lens and center of curvature',
            type=float,
            default='0')
    parser.add_argument(
            '-y',
            '--y_offset',
            metavar='Y_OFFSET',
            help='offset Y coordinate of lens and center of curvature',
            type=float,
            default='0')
    parser.add_argument(
            '-z',
            '--z_offset',
            metavar='Z_OFFSET',
            help='offset Z coordinate of center of lens',
            type=float,
            default='0')
    parser.add_argument(
            '-s',
            '--safe_z',
            metavar='SAFE_Z_POS',
            help='safe Z coordinate in gcode',
            type=float,
            default='1')
    parser.add_argument(
            '-fz',
            '--feed_z',
            metavar='Z_FEED_RATE',
            help='Z coordinate gcode feed rate',
            type=float,
            default='200')
    parser.add_argument(
            '-fxy',
            '--feed_xy',
            metavar='XY_FEED_RATE',
            help='X and Y coordinate gcode feed rate',
            type=float,
            default='1000')
    parser.add_argument(
            '-F',
            '--free_part',
            metavar='ADDITIONAL_DIAMETER',
            help=('generate gcode for a final circle to cut the lens free. '
                'This value is added to the --aperture value.')
            ,
            type=float
            )
    parser.add_argument(
            '-D',
            '--free_part_doc',
            metavar='DEPTH_OF_CUT',
            help=('Depth of cut if cutting part free with final circle. '
                'Used with the --free_part parameter.'),
            type=float
            )
    parser.add_argument(
            '-m',
            '--material_thickness',
            metavar='STOCK_MATERIAL_THICKNESS',
            help='thickness of stock. Used with the --free_part parameter.',
            type=float
            )

    args = parser.parse_args()

    if args.lens_type.lower() == 'convex':
        lens_type = LensStyle.CONVEX
    else:
        lens_type = LensStyle.CONCAVE

    args_summary(args)

    arcs = spiral((args.x_offset, args.y_offset), args.aperture, 1)

    center_curvature = (args.x_offset, args.y_offset, -args.radius_curvature)
    spiral_to_lens(arcs, center_curvature, args.radius_curvature, lens_type, args.z_offset)
    #check_integraty(arcs)

    gcode_lines = header_gcode(args.safe_z)
    spiral_gcode, summary_data = arcs_to_gcode(
            arcs, args.safe_z, args.feed_z, args.feed_xy)
    gcode_lines += spiral_gcode
    gcode_lines += free_part_gcode(center_curvature, args.aperture, args.free_part, args.free_part_doc, args.material_thickness, args.safe_z, args.feed_z, args.feed_xy)
    gcode_lines += footer_gcode(args.safe_z)

    write_gcode(gcode_lines, args.filename)

    summary(summary_data, args)


if __name__ == "__main__":
   main()
