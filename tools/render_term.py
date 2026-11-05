"""Render terminal text with ANSI colours to an SVG, for README screenshots.

    python tools/render_term.py input.txt output.svg
"""
import html
import re
import sys

FG, BG, DIM = '#d4d4d8', '#101014', '#71717a'
COLORS = {'32': '#4ade80', '36': '#22d3ee', '35': '#e879f9', '33': '#facc15',
          '38;5;208': '#fb923c', '38;5;220': '#fbbf24'}
CW, LH, FS, PAD = 8.4, 20, 14, 18


def width_of(text):
    # Braille cells are single width; CJK and emoji are not expected here.
    return len(text)


def main(src, out):
    lines = open(src, encoding='utf-8').read().rstrip('\n').splitlines()
    cols = max(width_of(re.sub(r'\x1b\[[0-9;]*m', '', l)) for l in lines) if lines else 40
    w, h = int(PAD * 2 + cols * CW), int(PAD * 2 + LH * (len(lines) + 1))
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
           '<style>text{font-family:"JetBrains Mono","Fira Code","SF Mono",Menlo,Consolas,"DejaVu Sans Mono",monospace;'
           f'font-size:{FS}px;white-space:pre}}</style>',
           f'<rect width="{w}" height="{h}" rx="10" fill="{BG}"/>']
    y = PAD + LH
    for line in lines:
        color, bold, dim, col = FG, False, False, 0
        for part in re.split(r'(\x1b\[[0-9;]*m)', line):
            if not part:
                continue
            m = re.fullmatch(r'\x1b\[([0-9;]*)m', part)
            if m:
                code = m.group(1)
                if code in ('', '0'):
                    color, bold, dim = FG, False, False
                elif code == '1':
                    bold = True
                elif code == '2':
                    dim = True
                elif code in COLORS:
                    color = COLORS[code]
                elif code.startswith('38;2;'):
                    r, g, b = code.split(';')[2:5]
                    color = f'#{int(r):02x}{int(g):02x}{int(b):02x}'
                continue
            style = f'fill:{DIM if dim else color};' + ('font-weight:600;' if bold else '')
            svg.append(f'<text x="{PAD + col * CW:.1f}" y="{y}" textLength="{width_of(part) * CW:.1f}" '
                       f'lengthAdjust="spacingAndGlyphs" style="{style}">{html.escape(part)}</text>')
            col += width_of(part)
        y += LH
    svg.append('</svg>')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(svg))
    print(out, len(lines), 'lines')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
