#!/usr/bin/env python3
#
# Copyright (c) 2014 Nikoli Dryden
# All rights reserved.
#
# This program is licensed under a 3-clause BSD license.
# See LICENSE.BSD for license information for further information.

import sys, re, os, os.path
from lxml import etree

# KanjiVG "kanji" directory, containing individual SVG files.
kanjivg = 'kanjivg/kanji'
# Directory to save stroke diagrams in.
output_dir = 'strokes'

# Number of boxes per line in the diagrams.
boxes_per_line = 6
# Radius of the circle used to indicate the start of a stroke.
circle_radius = '3'
# Stroke-width of the circle.
circle_sw = '0'
# Fill colour for the circle.
circle_fill = 'red'
# Width and height of each box in KanjiVG.
kanjivg_width = 109
kanjivg_height = 109

license_str = """Copyright (c) 2014 Nikoli Dryden. All rights reserved.
This work is distributed under the conditions of the Creative Commons
Attribution-Share Alike 3.0 License.

See http://creativecommons.org/licenses/by-sa/3.0/ for more details.

This work is based upon KanjiVG (http://kanjivg.tagaini.net/)."""

# Used for path adjustments.
caps_re = re.compile(r'([A-Z][0-9.,-]*)(?=[a-zA-Z])?')

def circle(x, y):
    """Create a circle element at coordinates x, y."""
    return etree.Element('circle',
                         {'cx': str(x), 'cy': str(y), 'r': circle_radius,
                          'stroke-width': circle_sw, 'fill': circle_fill})

def shift_path(d, row, col):
    """Adjust the path description to have a new starting location."""
    first_x = None
    first_y = None
    x_shift = col * kanjivg_width
    y_shift = row * kanjivg_height
    pos_shift = 0
    orig_len = len(d)
    # Currently we only adjust M, C, and S.
    for m in caps_re.finditer(d):
        s = m.group()
        # Note, this changes the length of d, so we have to adjust for it.
        start = m.start() + pos_shift
        end = m.end() + pos_shift
        if s[0] == 'M':
            start_x, start_y = [float(x) for x in s[1:].split(',')]
            start_x += x_shift
            start_y += y_shift
            d = (d[0:start] +
                 'M{0},{1}'.format(start_x, start_y) +
                 d[end:])
            if first_x is None:
                first_x = start_x
                first_y = start_y
        elif s[0] == 'C':
            parts = [float(x) for x in s[1:].split(',')]
            if len(parts) % 6 != 0:
                raise ValueError(d)
            # Handle ones doing poly-Beziers.
            tmp_d = 'C'
            for i in range(0, len(parts), 6):
                parts[i] += x_shift
                parts[i + 1] += y_shift
                parts[i + 2] += x_shift
                parts[i + 3] += y_shift
                parts[i + 4] += x_shift
                parts[i + 5] += y_shift
                tmp_d += '{0:.2f},{1:.2f},{2:.2f},{3:.2f},{4:.2f},{5:.2f}'.format(*parts[i:i + 6])
            d = d[0:start] + tmp_d + d[end:]
        elif s[0] == 'S':
            parts = [float(x) for x in s[1:].split(',')]
            if len(parts) % 4 != 0:
                raise ValueError(d)
            # Handle poly-Beziers.
            tmp_d = 'S'
            for i in range(0, len(parts), 4):
                parts[i] += x_shift
                parts[i + 1] += y_shift
                parts[i + 2] += x_shift
                parts[i + 3] += y_shift
                tmp_d += '{0:.2f},{1:.2f},{2:.2f},{3:.3f}'.format(*parts[i:i + 4])
            d = d[0:start] + tmp_d + d[end:]
        else:
            raise ValueError(d)
        # Compute change in length.
        pos_shift = len(d) - orig_len
    return d, first_x, first_y

def shift_transform(mat, row, col):
    """Adjust the translation in the transform matrix for the row and col."""
    parts = mat[7:-1].split(' ')
    e = float(parts[4]) + (col * kanjivg_width)
    f = float(parts[5]) + (row * kanjivg_width)
    return 'matrix(1 0 0 1 {0:.2f} {1:.2f})'.format(e, f)

def make_diagram(kanji):
    """Make a stroke order diagram.

    kanji is the XML tree from KanjiVG for the appropriate kanji.

    """
    # Gets the second-level <g> element that contains nested groups and
    # path information.
    base = kanji[0][0]
    id_base = base.attrib['id']
    # Get the second first-level <g> element with strike numbers
    sn_base = kanji[1]
    # Get all the paths/stroke numbers that are children.
    paths = [path for path in base.iter('{*}path')]
    numbers = [n for n in sn_base.iter('{*}text')]
    # Remove all the elements under this now that we have the paths.
    for ele in base:
        base.remove(ele)
    # Likewise for the stroke numbers.
    for ele in sn_base:
        sn_base.remove(ele)
    # Draw the frames.
    cur_row = 0
    cur_col = 0
    # Note: len(paths) == len(numbers).
    for i in range(len(paths)):
        # Iterate over everything up to this.
        for j in range(i + 1):
            new_d, x, y = shift_path(paths[j].attrib['d'], cur_row, cur_col)
            # Draw the path.
            path = etree.SubElement(base, 'path',
                                    {'id': (id_base +
                                            '-s' + str(j) +
                                            '-' + str(cur_row) +
                                            '-' + str(cur_col)),
                                     'd': new_d})
            # Add the stroke number.
            mat = shift_transform(numbers[j].attrib['transform'],
                                  cur_row, cur_col)
            etree.SubElement(sn_base, 'text',
                             transform = mat).text = str(j)
        # Add the circle to the current stroke.
        new_d, x, y = shift_path(paths[j].attrib['d'], cur_row, cur_col)
        base.append(circle(x, y))
        cur_col += 1
        if cur_col >= boxes_per_line:
            cur_col = 0
            cur_row += 1
    # Update the width, height, and viewBox.
    vwidth = kanjivg_width
    vheight = kanjivg_height * (cur_row + 1)
    if cur_row == 0:
        kanji.attrib['width'] = str(kanjivg_width * (cur_col + 1))
        vwidth *= cur_col + 1
    else:
        kanji.attrib['width'] = str(kanjivg_width * boxes_per_line)
        vwidth *= boxes_per_line
    kanji.attrib['height'] = str(kanjivg_height * (cur_row + 1))
    kanji.attrib['viewBox'] = '0 0 {0} {1}'.format(vwidth, vheight)

def gen_strokes():
    """Generate stroke charts for every file."""
    if not os.path.isdir(kanjivg):
        sys.exit(kanjivg + ' is not a directory.')
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)
    parser = etree.XMLParser(remove_blank_text = True)
    cur = 0
    for f in os.listdir(kanjivg):
        cur += 1
        if cur % 200 == 0:
            print('Processed {0}...'.format(cur))
        if f[-4:] == '.svg':
            tree = etree.parse(os.path.join(kanjivg, f), parser)
            try:
                make_diagram(tree.getroot())
            except ValueError as e:
                print('Error in parsing ' + f)
                print(e)
                continue
            tree.getroot().insert(0, etree.Comment(license_str))
            tree.write(os.path.join(output_dir, f[:-4] + '-strokes.svg'),
                       pretty_print = True)
    print('Generated {0} stroke documents.'.format(cur))

if __name__ == '__main__':
    gen_strokes()
