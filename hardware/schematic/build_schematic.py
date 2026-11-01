#!/usr/bin/env python3
"""Draw the Entrix door-controller schematic (Rev A, draft) as SVG sheets.

Requires:  pip install schemdraw==0.19
Usage:     python build_schematic.py            -> writes sheets/*.svg

Every connection drawn here is also listed in netlist.py (single source for the
netlist / BOM). If you change one, change the other and re-run both scripts.
"""
from pathlib import Path

import schemdraw
import schemdraw.elements as elm
from schemdraw.segments import Segment, SegmentArc, SegmentText

schemdraw.use('svg')

OUT = Path(__file__).parent / 'sheets'
REV = 'Rev A (draft)'
DATE = '2026-11-01'
FS = 9.5          # component label font size
NFS = 8.5         # net-flag font size
DNP_COLOR = '#888888'

SHEETS = [
    ('01-power', 'Power input and regulators'),
    ('02-mcu', 'Microcontroller ESP32-C6'),
    ('03-usb', 'USB-C and programming header'),
    ('04-rf', '433 MHz receiver RXB61'),
    ('05-rtc', 'Real-time clock and memory'),
    ('06-relays', 'Relay outputs'),
    ('07-inputs', 'Door, exit-button and tamper inputs'),
    ('08-indicators', 'LEDs and buzzer'),
    ('09-expansion', 'Expansion header and RS485 (optional)'),
]


# --------------------------------------------------------------------------
# Small drawing helpers
# --------------------------------------------------------------------------
class Text(elm.Element):
    """Free text with explicit alignment (multi-line allowed)."""
    def __init__(self, text, halign='left', valign='top', fontsize=FS, color=None, **kw):
        super().__init__(**kw)
        self.segments.append(SegmentText((0, 0), text, align=(halign, valign),
                                         fontsize=fontsize, color=color))


class Buzzer(elm.Element2Term):
    """IEC-style buzzer: flat side with a dome."""
    def __init__(self, **kw):
        super().__init__(**kw)
        w = 1.0
        self.segments.append(Segment([(0, 0), (w, 0)]))
        self.segments.append(SegmentArc((w / 2, 0), w, w * 1.1, theta1=0, theta2=180))


def R0(**kw):
    """Rectangle in absolute drawing coordinates."""
    return elm.Rect(**kw).theta(0).at((0, 0))


def P(xy, dx=0.0, dy=0.0):
    return (xy[0] + dx, xy[1] + dy)


def wire(d, a, b, shape='-', color=None):
    w = elm.Wire(shape).at(a).to(b)
    if color:
        w.color(color)
    d.add(w)


def dot(d, xy):
    d.add(elm.Dot(radius=0.09).at(xy))


def gnd(d, xy):
    d.add(elm.Ground().theta(0).at(xy))


def vcc(d, xy, name):
    d.add(elm.Vdd().theta(0).at(xy).label(name, fontsize=FS))


def nc(d, xy):
    d.add(elm.NoConnect().theta(0).at(xy))


def flag(d, xy, name, side='right'):
    """Net label (global net). side = direction the flag extends from xy."""
    w = 0.118 * len(name) + 0.75
    t = elm.Tag(width=w, height=0.55).at(xy).label(name, fontsize=NFS)
    d.add(t.right() if side == 'right' else t.left())


def text(d, xy, s, halign='left', valign='top', fontsize=FS, color=None):
    d.add(Text(s, halign=halign, valign=valign, fontsize=fontsize, color=color).theta(0).at(xy))


def two(d, cls, start, direction, ref, val, length=2.5, loc='bottom', dnp=False, **kw):
    """Place a two-terminal part. loc='bottom' -> label right of vertical parts."""
    e = cls(**kw).at(start)
    e = getattr(e, direction)().length(length)
    lbl = f'{ref}\n{val}' + ('\nDNP' if dnp else '')
    e.label(lbl, loc=loc, fontsize=FS)
    if dnp:
        e.color(DNP_COLOR)
    return d.add(e)


def ic(d, ref, value, left=(), right=(), top=(), bottom=(), anchor=None, at=(0, 0),
       pinspacing=1.0, w=None, dnp=False, lblloc='top'):
    """IC box. Pin lists are (name, number, anchorname) ordered top->bottom (sides)
    or left->right (top/bottom)."""
    pins = []
    for side, lst in (('left', left), ('right', right)):
        for name, num, an in reversed(list(lst)):
            pins.append(elm.IcPin(name=name, pin=str(num), side=side, anchorname=an))
    for side, lst in (('top', top), ('bottom', bottom)):
        for name, num, an in lst:
            pins.append(elm.IcPin(name=name, pin=str(num), side=side, anchorname=an))
    kw = dict(pins=pins, pinspacing=pinspacing, edgepadH=0.6, edgepadW=0.6,
              lsize=FS, plblsize=8)
    if w:
        n = max(len(left), len(right))
        kw['size'] = (w, max(n, 1) * pinspacing + 0.6)
    e = elm.Ic(**kw).theta(0)
    if anchor:
        e = e.anchor(anchor)
    e = e.at(at)
    e.label(f'{ref}\n{value}' + ('  (DNP)' if dnp else ''), loc=lblloc, fontsize=FS)
    if dnp:
        e.color(DNP_COLOR)
    return d.add(e)


def terminal(d, xy, label, side='left'):
    """Screw-terminal / connector pin drawn as an open circle with a label."""
    d.add(elm.Dot(open=True, radius=0.16).at(xy))
    if side == 'left':
        text(d, P(xy, -0.35, 0), label, halign='right', valign='center')
    else:
        text(d, P(xy, 0.35, 0), label, halign='left', valign='center')


def solder_jumper3(d, center, default='12', label='JP'):
    """Vertical 3-pad solder jumper. Returns (pad1_bottom, pad2_mid, pad3_top) points."""
    x, y = center
    pads = [(x, y - 1.0), (x, y), (x, y + 1.0)]
    for px, py in pads:
        d.add(R0(corner1=(px - 0.28, py + 0.22), corner2=(px + 0.28, py - 0.22)))
    # default bridge
    if default == '12':
        d.add(R0(corner1=(x - 0.12, y - 0.2), corner2=(x + 0.12, y - 0.8), fill='black'))
    text(d, (x + 0.5, y), label, valign='center')
    return pads[0], pads[1], pads[2]


def lowside_driver(d, top, ctrl_net, refs, dnp=False, load='relay'):
    """N-MOSFET low-side switch with flyback diode.

    top   : (x, y) of the load's low-side terminal (drain node).
    refs  : dict with keys Q, Rg, Rpd, D.
    Returns nothing; draws gate resistor + pull-down + flag.
    """
    col = DNP_COLOR if dnp else None
    x, y = top
    drain = (x, y - 1.0)
    wire(d, top, drain, color=col)
    q = elm.NFet().theta(0).reverse().anchor('drain').at(drain)
    text(d, (x + 0.35, drain[1] - 0.4), f"{refs['Q']}\nAO3400A" + ('\nDNP' if dnp else ''), color=col)
    if dnp:
        q.color(DNP_COLOR)
    q = d.add(q)
    gnd(d, q.source)
    g = q.gate
    gn = (g[0] - 1.2, g[1])
    wire(d, g, gn, color=col)
    dot(d, gn)
    two(d, elm.Resistor, gn, 'down', refs['Rpd'], '10k', length=2.0, loc='bottom', dnp=dnp)
    gnd(d, (gn[0], gn[1] - 2.0))
    two(d, elm.Resistor, gn, 'left', refs['Rg'], '100R', length=2.5, loc='top', dnp=dnp)
    flag(d, (gn[0] - 2.5, gn[1]), ctrl_net, side='left')


def finish(d, sheet_idx, notes=''):
    """Frame + title block, then save."""
    key, title = SHEETS[sheet_idx]
    bb = d.get_bbox()
    m = 1.2
    note_lines = notes.count('\n') + 1 if notes else 0
    tb_h = max(3.4, 0.42 * note_lines + 1.0)
    x0, x1 = bb.xmin - m, max(bb.xmax + m, bb.xmin - m + 34)
    y1 = bb.ymax + m
    y0 = bb.ymin - m - tb_h
    d.add(R0(corner1=(x0, y1), corner2=(x1, y0), lw=1.4))
    tbw = 15.5
    d.add(R0(corner1=(x1 - tbw, y0 + tb_h), corner2=(x1, y0)))
    d.add(elm.Line().at((x0, y0 + tb_h)).to((x1 - tbw, y0 + tb_h)).linewidth(0.6))
    text(d, (x1 - tbw + 0.4, y0 + tb_h - 0.35),
         f'ENTRIX door controller\n{title}', fontsize=11)
    text(d, (x1 - tbw + 0.4, y0 + 1.25),
         f'Sheet {sheet_idx + 1} of {len(SHEETS)}   {REV}   {DATE}', fontsize=8.5)
    if notes:
        text(d, (x0 + 0.4, y0 + tb_h - 0.35), notes, fontsize=8.5)
    OUT.mkdir(parents=True, exist_ok=True)
    d.save(str(OUT / f'{key}.svg'))


def new_drawing():
    d = schemdraw.Drawing(show=False)
    d.config(fontsize=FS, unit=2.5, lw=1.3)
    return d


# --------------------------------------------------------------------------
# Sheet 1: power
# --------------------------------------------------------------------------
def sheet_power():
    d = new_drawing()
    # J1 input terminal
    j1a, j1b = (0, 3), (0, -3)
    terminal(d, j1a, 'J1-1  VIN ~ / +')
    terminal(d, j1b, 'J1-2  VIN ~ / -')
    text(d, (-0.3, 0), 'J1  2-pin 5.08 mm\nterminal block\n12-24 V AC or DC\nany polarity',
         halign='right', valign='center')
    wire(d, j1a, (1, 3))
    f1 = two(d, elm.Fuse, (1, 3), 'right', 'F1', 'PTC 0.5 A / 72 V', loc='top')
    br = d.add(elm.Rectifier().theta(0).at((6, 0)))
    text(d, P(br.N, 0.3, 0.2), '~', valign='bottom')
    text(d, P(br.S, 0.3, -0.2), '~', valign='top')
    text(d, P(br.E, 0.0, 0.35), '+', halign='center', valign='bottom')
    text(d, P(br.W, 0.0, 0.35), '-', halign='center', valign='bottom')
    text(d, (9.0, -2.5), 'D1  DB107S\n1 A 1000 V')
    wire(d, f1.end, br.N, '-|')
    wire(d, j1b, br.S, '-|')
    wire(d, br.W, (5.0, 0))
    gnd(d, (5.0, 0))

    # VRECT rail
    rail_y = 0
    xr_end = 21.5
    wire(d, br.E, (xr_end, rail_y))
    for x in (11, 14, 17):
        dot(d, (x, rail_y))
    d2 = two(d, elm.Zener, (11, -3), 'up', 'D2', 'SMBJ40A\nTVS', length=3)
    gnd(d, (11, -3))
    two(d, elm.Capacitor, (14, 0), 'down', 'C1', '470uF 63V\nelectrolytic\n105 C', length=3, polar=True)
    gnd(d, (14, -3))
    two(d, elm.Capacitor, (17, 0), 'down', 'C2', '1uF 100V\nX7R 1206', length=3)
    gnd(d, (17, -3))
    dot(d, (19.5, 0))
    wire(d, (19.5, 0), (19.5, 1.5))
    flag(d, (19.5, 1.5), 'VRECT')

    # U1 XL7015
    u1 = ic(d, 'U1', 'XL7015E1 (TO252-5)',
            left=[('VIN', 1, 'VIN'), ('EN', 5, 'EN')],
            right=[('SW', 2, 'SW'), ('FB', 4, 'FB')],
            bottom=[('GND/tab', 3, 'GND')],
            anchor='VIN', at=(xr_end, rail_y), pinspacing=1.5, w=3.6)
    wire(d, u1.EN, P(u1.EN, -1.0, 0))
    gnd(d, P(u1.EN, -1.0, 0))
    text(d, P(u1.EN, -1.2, -1.0), 'EN low = ON', halign='right', fontsize=8)
    gnd(d, u1.GND)
    sw = (31, 0)
    wire(d, u1.SW, sw)
    dot(d, sw)
    two(d, elm.Schottky, (31, -3), 'up', 'D3', 'SS310\n3 A 100 V', length=3)
    gnd(d, (31, -3))
    l1 = two(d, elm.Inductor2, sw, 'right', 'L1', '100uH  Isat>=1 A\nshielded 12x12', length=3.5, loc='top')
    v5_end = 47
    wire(d, l1.end, (v5_end, 0))
    for x in (36, 38.5, 41.5, 44):
        dot(d, (x, 0))
    two(d, elm.Capacitor, (36, 0), 'down', 'C3', '220uF 25V\nlow-ESR', length=3, polar=True)
    gnd(d, (36, -3))
    two(d, elm.Capacitor, (38.5, 0), 'down', 'C4', '100nF', length=3)
    gnd(d, (38.5, -3))
    # feedback divider: Vout = 1.25 * (1 + R1/R2)
    two(d, elm.Resistor, (41.5, 0), 'down', 'R1', '10k 1%', length=2.5, loc='top')
    fb = (41.5, -2.5)
    dot(d, fb)
    two(d, elm.Resistor, fb, 'down', 'R2', '3.3k 1%', length=2.5, loc='top')
    gnd(d, (41.5, -5.0))
    two(d, elm.Capacitor, (44, 0), 'down', 'C5', '33nF (CFF)', length=2.5)
    wire(d, (44, -2.5), fb)
    flag(d, (44, -2.5), 'FB')
    wire(d, u1.FB, P(u1.FB, 1.0, 0))
    flag(d, P(u1.FB, 1.0, 0), 'FB')
    vcc(d, (v5_end, 0), '+5V')
    text(d, (v5_end + 0.6, -0.6), '5.04 V\n0.8 A max', fontsize=8)

    # ---- second row: 3.3 V LDO --------------------------------------
    y2 = -11
    vin2 = (2, y2)
    vcc(d, vin2, '+5V')
    u2 = ic(d, 'U2', 'AP2112K-3.3 (SOT-23-5)',
            left=[('VIN', 1, 'VIN'), ('EN', 3, 'EN')],
            right=[('VOUT', 5, 'VOUT'), ('NC', 4, 'NC')],
            bottom=[('GND', 2, 'GND')],
            anchor='VIN', at=(8, y2), pinspacing=1.5, w=3.6)
    wire(d, vin2, u2.VIN)
    dot(d, (4, y2))
    two(d, elm.Capacitor, (4, y2), 'down', 'C6', '10uF X7R', length=3, loc='top')
    gnd(d, (4, y2 - 3))
    dot(d, (6.5, y2))
    wire(d, u2.EN, (6.5, u2.EN[1]))
    wire(d, (6.5, u2.EN[1]), (6.5, y2))
    gnd(d, u2.GND)
    nc(d, u2.NC)
    v33 = (17.5, y2)
    wire(d, u2.VOUT, v33)
    dot(d, (15, y2))
    two(d, elm.Capacitor, (15, y2), 'down', 'C7', '10uF X7R', length=3)
    gnd(d, (15, y2 - 3))
    vcc(d, v33, '+3V3')
    text(d, (v33[0] + 0.6, y2 - 0.6), '600 mA', fontsize=8)

    # ---- VRECT sense divider -----------------------------------------
    top = (27, -9)
    flag(d, top, 'VRECT', side='left')
    r3 = two(d, elm.Resistor, top, 'down', 'R3', '220k 1%', length=2.5)
    vs = (27, -11.5)
    dot(d, vs)
    two(d, elm.Resistor, vs, 'down', 'R4', '10k 1%', length=2.5, loc='top')
    gnd(d, (27, -14))
    wire(d, vs, (30, -11.5))
    dot(d, (30, -11.5))
    two(d, elm.Capacitor, (30, -11.5), 'down', 'C8', '100nF', length=2.5)
    gnd(d, (30, -14))
    wire(d, (30, -11.5), (32, -11.5))
    flag(d, (32, -11.5), 'VSENSE')
    text(d, (33.0, -12.6), 'to ESP32 ADC (IO0)\n12 V DC in -> ~0.46 V\n24 V AC in -> ~1.5 V\nTVS clamp 65 V -> 2.8 V',
         fontsize=8)

    notes = ('NOTES\n'
             '1. Accepts 12-24 V DC (either polarity) or 12-24 V AC. 230 V sites: feed J1 from a sealed 12 V AC/DC module.\n'
             '2. XL7015 must be the 80 V (or 100 V) version: 24 V AC rectifies to ~34-37 V; the SMBJ40A clamps surges at ~65 V.\n'
             '3. Vout = 1.25 V x (1 + R1/R2) = 5.04 V.  Keep the SW / D3 / L1 / C3 loop short; C2 right at U1 pin 1.\n'
             '4. Use 105 C electrolytics (C1, C3): the box gets hot in sunlight.')
    finish(d, 0, notes)


# --------------------------------------------------------------------------
# Sheet 2: MCU
# --------------------------------------------------------------------------
def sheet_mcu():
    d = new_drawing()
    left = [('3V3', 2, 'V33'), ('EN', 3, 'EN'), ('IO9 / BOOT', 15, 'IO9'), ('IO8', 10, 'IO8'),
            ('IO15', 23, 'IO15'), ('IO12 / USB D-', 13, 'IO12'), ('IO13 / USB D+', 14, 'IO13'),
            ('TXD0 / IO16', 25, 'TXD0'), ('RXD0 / IO17', 24, 'RXD0'), ('NC', 22, 'NC'),
            ('GND', 1, 'GND1'), ('GND', 28, 'GND28'), ('EPAD (GND)', 29, 'GND29')]
    right = [('IO0 / ADC1_CH0', 8, 'IO0'), ('IO1', 9, 'IO1'), ('IO2', 27, 'IO2'), ('IO3', 26, 'IO3'),
             ('IO4 / MTMS', 4, 'IO4'), ('IO5 / MTDI', 5, 'IO5'), ('IO6', 6, 'IO6'), ('IO7', 7, 'IO7'),
             ('IO10', 11, 'IO10'), ('IO11', 12, 'IO11'), ('IO18', 16, 'IO18'), ('IO19', 17, 'IO19'),
             ('IO20', 18, 'IO20'), ('IO21', 19, 'IO21'), ('IO22', 20, 'IO22'), ('IO23', 21, 'IO23')]
    u = ic(d, 'U3', 'ESP32-C6-WROOM-1-N8  (or -1U-N8 for external antenna)',
           left=left, right=right, anchor='IO0', at=(0, 0), pinspacing=1.0, w=9)
    nets = {'IO0': 'VSENSE', 'IO1': 'RF_DATA', 'IO2': 'RELAY1', 'IO3': 'RELAY2',
            'IO4': 'EXP_IO4', 'IO5': 'EXP_IO5', 'IO6': 'I2C_SDA', 'IO7': 'I2C_SCL',
            'IO10': 'IN_DOOR', 'IO11': 'IN_EXIT', 'IO18': 'IN_TAMPER', 'IO19': 'LED_GRN',
            'IO20': 'LED_RED', 'IO21': 'BUZZER', 'IO22': 'UART1_TX', 'IO23': 'UART1_RX'}
    for an, net in nets.items():
        p = getattr(u, an)
        wire(d, p, P(p, 1.2, 0))
        flag(d, P(p, 1.2, 0), net)
    lnets = {'EN': 'EN', 'IO9': 'BOOT', 'IO8': 'IO8_STRAP', 'IO12': 'USB_DN',
             'IO13': 'USB_DP', 'TXD0': 'UART0_TX', 'RXD0': 'UART0_RX'}
    for an, net in lnets.items():
        p = getattr(u, an)
        wire(d, p, P(p, -1.2, 0))
        flag(d, P(p, -1.2, 0), net, side='left')
    # 3V3
    p = u.V33
    wire(d, p, P(p, -2.0, 0))
    vcc(d, P(p, -2.0, 0), '+3V3')
    nc(d, u.IO15)
    text(d, P(u.IO15, -0.5, 0), 'strap - leave open', halign='right', valign='center', fontsize=8)
    nc(d, u.NC)
    # GND pins to a bus
    gx = u.GND1[0] - 1.2
    for an in ('GND1', 'GND28', 'GND29'):
        p = getattr(u, an)
        wire(d, p, (gx, p[1]))
    wire(d, (gx, u.GND1[1]), (gx, u.GND29[1] - 0.6))
    dot(d, (gx, u.GND28[1]))
    gnd(d, (gx, u.GND29[1] - 0.6))

    # ---- support circuits (left) -------------------------------------
    bx = -30
    # decoupling
    vcc(d, (bx, 6), '+3V3')
    wire(d, (bx, 6), (bx, 5))
    wire(d, (bx, 5), (bx + 3.5, 5))
    dot(d, (bx, 5))
    two(d, elm.Capacitor, (bx, 5), 'down', 'C9', '22uF X5R', length=2.5)
    gnd(d, (bx, 2.5))
    two(d, elm.Capacitor, (bx + 3.5, 5), 'down', 'C10', '100nF', length=2.5)
    gnd(d, (bx + 3.5, 2.5))
    text(d, (bx + 6.0, 4.6), 'Place C9, C10 next to\nU3 pin 2 (3V3)', fontsize=8)

    # EN reset
    vcc(d, (bx, -1), '+3V3')
    two(d, elm.Resistor, (bx, -1), 'down', 'R5', '10k', length=2.5, loc='top')
    en = (bx, -3.5)
    dot(d, en)
    two(d, elm.Capacitor, en, 'down', 'C11', '1uF', length=2.5, loc='top')
    gnd(d, (bx, -6))
    wire(d, en, (bx + 4.5, -3.5))
    dot(d, (bx + 2.5, -3.5))
    sw1 = d.add(elm.Button().at((bx + 2.5, -3.5)).down().length(2.5).label('SW1\nRESET', loc='bottom', fontsize=FS))
    gnd(d, (bx + 2.5, -6))
    flag(d, (bx + 4.5, -3.5), 'EN')

    # BOOT / SETUP button
    vcc(d, (bx, -9), '+3V3')
    two(d, elm.Resistor, (bx, -9), 'down', 'R7', '10k', length=2.5, loc='top')
    bt = (bx, -11.5)
    dot(d, bt)
    wire(d, bt, (bx + 4.5, -11.5))
    dot(d, (bx + 2.5, -11.5))
    d.add(elm.Button().at((bx + 2.5, -11.5)).down().length(2.5).label('SW2\nSETUP /\nBOOT', loc='bottom', fontsize=FS))
    gnd(d, (bx + 2.5, -14))
    flag(d, (bx + 4.5, -11.5), 'BOOT')
    text(d, (bx - 0.5, -15.0), 'Hold SW2 at power-up = download mode.\nPress in normal use = admin/setup mode.', fontsize=8)

    # IO8 strap pull-up
    sx = bx + 12
    vcc(d, (sx, -9), '+3V3')
    two(d, elm.Resistor, (sx, -9), 'down', 'R6', '10k', length=2.5, loc='top')
    wire(d, (sx, -11.5), (sx + 1.0, -11.5))
    flag(d, (sx + 1.0, -11.5), 'IO8_STRAP')
    text(d, (sx - 1.5, -12.6), 'IO8 must be high for\nserial/USB download', fontsize=8)

    notes = ('NOTES\n'
             '1. Pin numbers per ESP32-C6-WROOM-1 datasheet. Check against the current Espressif datasheet before PCB layout.\n'
             '2. Strapping pins: IO8 (pull-up), IO9 (pull-up + button), IO15 (open), IO4/IO5 (expansion; IO4 has a 10k pull-down on sheet 9).\n'
             '3. Keep the PCB-antenna end of U3 over the board edge with no copper underneath, away from the relay and XL7015.\n'
             '4. Use the -1U variant + u.FL pigtail when the box is on a metal gate or Zigbee range must be extended.')
    finish(d, 1, notes)


# --------------------------------------------------------------------------
# Sheet 3: USB + programming header
# --------------------------------------------------------------------------
def sheet_usb():
    d = new_drawing()
    j3 = ic(d, 'J3', 'USB-C receptacle (USB 2.0, 16-pin)',
            right=[('VBUS  A4/A9/B4/B9', '', 'VBUS'), ('D-  A7/B7', '', 'DN'), ('D+  A6/B6', '', 'DP'),
                   ('CC1  A5', '', 'CC1'), ('CC2  B5', '', 'CC2'), ('GND  A1/A12/B1/B12', '', 'GND'),
                   ('SHIELD', '', 'SH')],
            anchor='VBUS', at=(0, 0), pinspacing=1.2, w=6.5)
    # VBUS -> D4 -> +5V
    vb = (14, 0)
    wire(d, j3.VBUS, vb)
    d4 = two(d, elm.Schottky, vb, 'right', 'D4', 'SS14', length=2.5, loc='top')
    wire(d, d4.end, (18, 0))
    vcc(d, (18, 0), '+5V')
    # ESD array U4
    u4 = ic(d, 'U4', 'USBLC6-2SC6',
            left=[('I/O1', 1, 'IO1L'), ('I/O2', 3, 'IO2L')],
            right=[('I/O1', 6, 'IO1R'), ('I/O2', 4, 'IO2R')],
            top=[('VBUS', 5, 'VB')], bottom=[('GND', 2, 'G')],
            anchor='IO1L', at=(9, j3.DN[1]), pinspacing=1.2, w=5.0, lblloc='center')
    wire(d, j3.DN, u4.IO1L)
    wire(d, j3.DP, (8.0, j3.DP[1]))
    wire(d, (8.0, j3.DP[1]), (8.0, u4.IO2L[1]))
    wire(d, (8.0, u4.IO2L[1]), u4.IO2L)
    wire(d, u4.VB, (u4.VB[0], 0))
    dot(d, (u4.VB[0], 0))
    gnd(d, u4.G)
    wire(d, u4.IO1R, P(u4.IO1R, 1.5, 0))
    flag(d, P(u4.IO1R, 1.5, 0), 'USB_DN')
    wire(d, u4.IO2R, P(u4.IO2R, 1.5, 0))
    flag(d, P(u4.IO2R, 1.5, 0), 'USB_DP')
    # CC pull-downs
    cx = 3.0
    r8 = two(d, elm.Resistor, j3.CC1, 'right', 'R8', '5.1k', length=2.5, loc='top')
    wire(d, j3.CC2, P(j3.CC2, 0.8, 0))
    r9 = two(d, elm.Resistor, P(j3.CC2, 0.8, 0), 'right', 'R9', '5.1k', length=2.5, loc='bottom')
    gx = r9.end[0] + 0.8
    wire(d, r8.end, (gx, r8.end[1]))
    wire(d, r9.end, (gx, r9.end[1]))
    dot(d, (gx, r9.end[1]))
    wire(d, (gx, r8.end[1]), (gx, j3.GND[1] - 1.5))
    gnd(d, (gx, j3.GND[1] - 1.5))
    wire(d, j3.GND, (1.5, j3.GND[1]))
    wire(d, j3.SH, (1.5, j3.SH[1]))
    wire(d, (1.5, j3.GND[1]), (1.5, j3.SH[1] - 0.5))
    dot(d, (1.5, j3.SH[1]))
    gnd(d, (1.5, j3.SH[1] - 0.5))

    # J2 UART0 header
    hx, hy = 30, 1
    names = [('1', '+3V3'), ('2', 'UART0_TX'), ('3', 'UART0_RX'), ('4', 'EN'), ('5', 'BOOT'), ('6', 'GND')]
    d.add(R0(corner1=(hx - 1.2, hy + 0.8), corner2=(hx, hy - 1.2 * (len(names) - 1) - 0.8)))
    text(d, (hx - 0.6, hy + 1.2), 'J2  UART0 / programming\n1x6 2.54 mm (DNP, factory use)', halign='center', valign='bottom')
    for i, (num, net) in enumerate(names):
        y = hy - 1.2 * i
        d.add(elm.Dot(open=True, radius=0.16).at((hx - 0.4, y)))
        text(d, (hx - 0.75, y), num, halign='right', valign='center', fontsize=8)
        wire(d, (hx, y), (hx + 1.5, y))
        if net == '+3V3':
            wire(d, (hx + 1.5, y), (hx + 2.5, y))
            vcc(d, (hx + 2.5, y), '+3V3')
        elif net == 'GND':
            gnd(d, (hx + 1.5, y))
        else:
            flag(d, (hx + 1.5, y), net)
    text(d, (hx + 6.5, hy - 1.2), 'UART0_TX = ESP32 output\n(connect to adapter RX)', fontsize=8)

    notes = ('NOTES\n'
             '1. USB-C is for flashing and debugging through the ESP32-C6 built-in USB-Serial-JTAG. It is inside the box, not used in the field.\n'
             '2. D4 lets the board run from USB on the bench (relay coil and RF receiver work at ~4.6 V). R8/R9 make the port a USB device (sink).\n'
             '3. J2 is an alternative UART flashing port (needs a 3.3 V USB-UART adapter). Hold SETUP/BOOT while resetting to enter download mode.')
    finish(d, 2, notes)


# --------------------------------------------------------------------------
# Sheet 4: RF receiver
# --------------------------------------------------------------------------
def sheet_rf():
    d = new_drawing()
    vcc(d, (0, 3), '+5V')
    r12 = two(d, elm.Resistor, (0, 3), 'right', 'R12', '22R', length=2.5, loc='top')
    n = (3.5, 3)
    wire(d, r12.end, (9.0, 3))
    dot(d, n)
    dot(d, (6.0, 3))
    two(d, elm.Capacitor, n, 'down', 'C12', '100uF 10V', length=2.5, polar=True, loc='top')
    gnd(d, (3.5, 0.5))
    two(d, elm.Capacitor, (6.0, 3), 'down', 'C13', '100nF', length=2.5)
    gnd(d, (6.0, 0.5))
    text(d, (6.6, 4.0), '+5V_RF  (RC-filtered supply)', fontsize=8, valign='bottom')
    u5 = ic(d, 'U5', 'RXB61\n433.92 MHz\nreceiver module',
            left=[('VIN', '', 'VIN')],
            right=[('DATA', '', 'DATA'), ('SHUT', '', 'SHUT')],
            top=[('ANT', '', 'ANT')], bottom=[('GND', '', 'GND')],
            anchor='VIN', at=(9.0, 3), pinspacing=1.6, w=6.0, lblloc='center')
    gnd(d, u5.GND)
    # antenna
    wire(d, u5.ANT, P(u5.ANT, 0, 1.0))
    d.add(elm.Antenna().theta(0).at(P(u5.ANT, 0, 1.0)))
    text(d, P(u5.ANT, 0.9, 2.0), 'E1 / J4: 17.3 cm wire (1/4 wave) or\nSMA edge jack + 433 MHz whip',
         fontsize=8, valign='center')
    # DATA -> divider -> RF_DATA
    dx = u5.DATA
    wire(d, dx, P(dx, 1.0, 0))
    r10 = two(d, elm.Resistor, P(dx, 1.0, 0), 'right', 'R10', '10k', length=2.5, loc='top')
    rn = P(r10.end, 1.0, 0)
    wire(d, r10.end, rn)
    dot(d, rn)
    two(d, elm.Resistor, rn, 'down', 'R11', '20k', length=2.5)
    gnd(d, P(rn, 0, -2.5))
    wire(d, rn, P(rn, 2.0, 0))
    flag(d, P(rn, 2.0, 0), 'RF_DATA')
    text(d, P(rn, 2.2, -0.7), '5 V -> 3.33 V level shift\n(ESP32 GPIOs are not 5 V tolerant)', fontsize=8)
    # SHUT -> JP1
    sx = u5.SHUT
    jc = P(sx, 2.0, -1.4)
    p1, p2, p3 = solder_jumper3(d, jc, default='12', label='JP1\n1-2 default')
    wire(d, sx, (jc[0] - 1.0, sx[1]))
    wire(d, (jc[0] - 1.0, sx[1]), (jc[0] - 1.0, jc[1]))
    wire(d, (jc[0] - 1.0, jc[1]), P(p2, -0.28, 0))
    text(d, P(p1, -0.45, -0.05), '1', halign='right', valign='center', fontsize=7.5)
    text(d, P(p2, 0.45, -0.25), '', fontsize=7.5)
    text(d, P(p3, -0.45, 0.05), '3', halign='right', valign='center', fontsize=7.5)
    wire(d, P(p1, 0, -0.22), P(p1, 0, -0.8))
    gnd(d, P(p1, 0, -0.8))
    wire(d, P(p3, 0, 0.22), P(p3, 0, 0.8))
    vcc(d, P(p3, 0, 0.8), '+5V_RF')

    notes = ('NOTES\n'
             '1. RXB61 has 5 pins: VIN, GND, DATA, ANT, SHUT. No official datasheet was found: confirm the pin order on your module\'s silkscreen\n'
             '   before PCB layout, and check the SHUT polarity (JP1 1-2 = SHUT to GND = receiver ON for active-high shutdown; use 2-3 if your module is active-low).\n'
             '2. RXB6 / RXB12 / SRX882 can be used instead: same VIN, GND, DATA and ANT signals, different footprint (no SHUT pin -> leave JP1 open).\n'
             '3. Order the 433.92 MHz version (315 MHz in North America). Keep the receiver and its antenna away from the XL7015 (L1, D3) and relay K1.\n'
             '4. Supply is 5 V for best sensitivity; R12/C12 filter the buck ripple. DATA is divided to 3.3 V by R10/R11.')
    finish(d, 3, notes)


# --------------------------------------------------------------------------
# Sheet 5: RTC + FRAM
# --------------------------------------------------------------------------
def sheet_rtc():
    d = new_drawing()
    u6 = ic(d, 'U6', 'PCF8563T (SO-8)  or BM8563',
            left=[('OSCI', 1, 'OSCI'), ('OSCO', 2, 'OSCO'), ('INT', 3, 'INT'), ('VSS', 4, 'VSS')],
            right=[('VDD', 8, 'VDD'), ('CLKOUT', 7, 'CLKOUT'), ('SCL', 6, 'SCL'), ('SDA', 5, 'SDA')],
            anchor='OSCI', at=(0, 0), pinspacing=2.0, w=5.0)
    # crystal
    xx = u6.OSCI[0] - 3.0
    wire(d, u6.OSCI, (xx - 3.0, u6.OSCI[1]))
    dot(d, (xx, u6.OSCI[1]))
    d.add(elm.Crystal().at((xx, u6.OSCI[1])).down().length(2.0).label('Y1\n32.768 kHz\nCL 12.5 pF', loc='bottom', fontsize=FS))
    wire(d, (xx, u6.OSCO[1]), u6.OSCO)
    two(d, elm.Capacitor, (xx - 3.0, u6.OSCI[1]), 'down', 'C14', '0-15pF trim', length=2.0, loc='top', dnp=True)
    gnd(d, (xx - 3.0, u6.OSCI[1] - 2.0))
    nc(d, u6.INT)
    nc(d, u6.CLKOUT)
    wire(d, u6.VSS, P(u6.VSS, -1.0, 0))
    gnd(d, P(u6.VSS, -1.0, 0))
    # VDD
    vd = P(u6.VDD, 1.5, 0)
    wire(d, u6.VDD, P(vd, 1.5, 0))
    dot(d, vd)
    two(d, elm.Capacitor, vd, 'down', 'C15', '100nF', length=2.0, loc='top')
    gnd(d, P(vd, 0, -2.0))
    flag(d, P(vd, 1.5, 0), 'VDD_RTC')
    for an, net in (('SCL', 'I2C_SCL'), ('SDA', 'I2C_SDA')):
        p = getattr(u6, an)
        wire(d, p, P(p, 1.5, 0))
        flag(d, P(p, 1.5, 0), net)

    # Backup diode-OR
    ox, oy = 20, 3
    vcc(d, (ox - 1.5, oy), '+3V3')
    wire(d, (ox - 1.5, oy), (ox, oy))
    d5a = two(d, elm.Schottky, (ox, oy), 'right', 'D5A', 'BAT54C pin 1->3', length=2.5, loc='top')
    k = (ox + 4, oy)
    wire(d, d5a.end, P(k, 2.0, 0))
    dot(d, k)
    flag(d, P(k, 2.0, 0), 'VDD_RTC')
    bx = ox - 5
    d.add(elm.Battery().at((bx, oy - 3)).down().length(2.5).label('BT1\nBR2032\n(CR2032 holder)', loc='top', fontsize=FS))
    text(d, (bx + 0.4, oy - 3.1), '+', fontsize=10, valign='bottom')
    gnd(d, (bx, oy - 5.5))
    r13 = two(d, elm.Resistor, (bx, oy - 3), 'right', 'R13', '1k', length=2.5, loc='bottom')
    wire(d, r13.end, (ox, oy - 3))
    d5b = two(d, elm.Schottky, (ox, oy - 3), 'right', 'D5B', 'BAT54C pin 2->3', length=2.5, loc='bottom')
    wire(d, d5b.end, (k[0], oy - 3))
    wire(d, (k[0], oy - 3), k)
    text(d, (ox - 1, oy - 6.4), 'D5 = one BAT54C (common cathode, SOT-23).\nR13 limits reverse current into the cell.', fontsize=8)

    # I2C pull-ups
    px = 34
    for i, (ref, net) in enumerate((('R14', 'I2C_SDA'), ('R15', 'I2C_SCL'))):
        x = px + 5.5 * i
        vcc(d, (x, 3), '+3V3')
        two(d, elm.Resistor, (x, 3), 'down', ref, '4.7k', length=2.5, loc='bottom')
        wire(d, (x, 0.5), (x, 0))
        flag(d, (x, 0), net)

    # FRAM (DNP)
    fx, fy = 30, -6
    u7 = ic(d, 'U7', 'MB85RC256V FRAM 32 KB', dnp=True,
            left=[('A0', 1, 'A0'), ('A1', 2, 'A1'), ('A2', 3, 'A2'), ('WP', 7, 'WP'), ('VSS', 4, 'VSS')],
            right=[('VDD', 8, 'VDD'), ('SCL', 6, 'SCL'), ('SDA', 5, 'SDA')],
            anchor='A0', at=(fx, fy), pinspacing=1.0, w=5.0)
    bus = fx - 1.2
    for an in ('A0', 'A1', 'A2', 'WP', 'VSS'):
        p = getattr(u7, an)
        wire(d, p, (bus, p[1]), color=DNP_COLOR)
    wire(d, (bus, u7.A0[1]), (bus, u7.VSS[1] - 0.6), color=DNP_COLOR)
    gnd(d, (bus, u7.VSS[1] - 0.6))
    wire(d, u7.VDD, P(u7.VDD, 2.5, 0), color=DNP_COLOR)
    vcc(d, P(u7.VDD, 2.5, 0), '+3V3')
    cdx = (u7.VDD[0] + 6.5, u7.VDD[1] + 2.5)
    vcc(d, cdx, '+3V3')
    two(d, elm.Capacitor, cdx, 'down', 'C16', '100nF (at U7)', length=2.0, loc='bottom', dnp=True)
    gnd(d, P(cdx, 0, -2.0))
    for an, net in (('SCL', 'I2C_SCL'), ('SDA', 'I2C_SDA')):
        p = getattr(u7, an)
        wire(d, p, P(p, 4.0, 0), color=DNP_COLOR)
        flag(d, P(p, 4.0, 0), net)

    notes = ('NOTES\n'
             '1. PCF8563T is the PCF8563 in the SO-8 package (T = SO-8, TS = TSSOP-8, BS = HVSON-10); /5 or /F4 suffixes are revision/packing only.\n'
             '   BM8563 (SO-8) is a pin-compatible lower-cost alternative. I2C address 0x51 (RTC), 0x50 (FRAM, optional).\n'
             '2. The firmware checks the PCF8563 VL (voltage-low) flag at boot; if set, time is invalid until an admin or the gateway sets it.\n'
             '3. BR2032 (Li/CF, -30...+85 C) instead of CR2032 for an outdoor box. RTC draws ~0.25 uA -> the cell lasts many years.\n'
             '4. Keep Y1 within 5 mm of U6 with a ground guard ring and no signals routed under it.')
    finish(d, 4, notes)


# --------------------------------------------------------------------------
# Sheet 6: relays
# --------------------------------------------------------------------------
def relay_channel(d, x0, y0, n, dnp):
    col = DNP_COLOR if dnp else None
    refs = {1: dict(K='K1', Q='Q1', Rg='R16', Rpd='R17', D='D6', J='J5', net='RELAY1'),
            2: dict(K='K2', Q='Q2', Rg='R18', Rpd='R19', D='D7', J='J6', net='RELAY2')}[n]
    k = elm.Relay(switch='spdt', unit=2.5).theta(0).at((x0, y0))
    text(d, (x0 + 0.9, y0 + 3.1), f"{refs['K']}  SRD-05VDC-SL-C\nor HF3FF/005-1ZS\n5 V coil, 1 Form C" + ('  DNP' if dnp else ''), color=col)
    if dnp:
        k.color(DNP_COLOR)
    k = d.add(k)
    top = P(k.in1, 0, 1.0)
    bot = P(k.in2, 0, -1.0)
    wire(d, k.in1, top, color=col)
    wire(d, k.in2, bot, color=col)
    dx = x0 - 2.5
    wire(d, top, (dx, top[1]), color=col)
    wire(d, bot, (dx, bot[1]), color=col)
    dot(d, top)
    dot(d, bot)
    wire(d, top, P(top, 0, 0.8), color=col)
    vcc(d, P(top, 0, 0.8), '+5V')
    two(d, elm.Schottky, (dx, bot[1]), 'up', refs['D'], 'SS14', length=top[1] - bot[1], loc='top', dnp=dnp)
    lowside_driver(d, bot, refs['net'], refs, dnp=dnp)
    # contacts: a = COM (top), b = NC, c = NO
    jx = x0 + 6.5
    ycom, ync, yno = k.in2[1], k.in2[1] - 1.0, k.in2[1] - 2.0
    wire(d, k.a, P(k.a, 0, 0.8), color=col)
    wire(d, P(k.a, 0, 0.8), (jx - 1.0, k.a[1] + 0.8), color=col)
    wire(d, (jx - 1.0, k.a[1] + 0.8), (jx - 1.0, ycom), color=col)
    wire(d, (jx - 1.0, ycom), (jx, ycom), color=col)
    wire(d, k.b, (k.b[0], ync), color=col)
    wire(d, (k.b[0], ync), (jx, ync), color=col)
    wire(d, k.c, (k.c[0], yno), color=col)
    wire(d, (k.c[0], yno), (jx, yno), color=col)
    text(d, P(k.a, 0.25, 0.35), 'COM', fontsize=7.5, valign='bottom')
    text(d, P(k.b, 0.2, -0.15), 'NC', fontsize=7.5)
    text(d, P(k.c, -0.2, -0.15), 'NO', fontsize=7.5, halign='right')
    j = refs['J']
    for y, lab in ((ycom, f'{j}-1  COM'), (ync, f'{j}-2  NC'), (yno, f'{j}-3  NO')):
        terminal(d, (jx, y), lab, side='right')
    text(d, (jx - 0.2, ycom + 1.6), f'{j}  3-pin 5.08 mm' + (' (DNP)' if dnp else ''), fontsize=8)


def sheet_relays():
    d = new_drawing()
    relay_channel(d, 0, 0, 1, dnp=False)
    relay_channel(d, 22, 0, 2, dnp=True)
    text(d, (-9, -9.8), 'Contacts: 10 A 250 V AC / 30 V DC (relay rating). Potential-free (dry) contact.', fontsize=8.5)
    notes = ('NOTES\n'
             '1. R17/R19 hold the MOSFET off while the ESP32 boots, so the door can never open during reset or power-up.\n'
             '2. Strike / bolt (fail-secure): PSU+ -> COM, NO -> lock+. Maglock (fail-safe): PSU+ -> COM, NC -> maglock+.\n'
             '   Gate / garage / sliding-door operator: COM + NO across its "push-button / open" input (0.5-1 s pulse).\n'
             '3. Fit a flyback diode across DC lock coils (or a varistor across AC loads) at the lock.\n'
             '4. If the relay ever switches 230 V, keep >= 6 mm creepage + a PCB slot between contacts and low-voltage circuits.\n'
             '5. Channel 2 (K2, Q2, R18, R19, D7, J6) is optional: second door, roller shutter up/down, siren.')
    finish(d, 5, notes)


# --------------------------------------------------------------------------
# Sheet 7: inputs
# --------------------------------------------------------------------------
def opto_channel(d, y0, refs, term_label, net):
    x0 = 0
    t = (x0, y0)
    terminal(d, t, term_label)
    kn = (x0 + 6.0, y0)
    wire(d, t, kn)
    cx = x0 + 2.0
    dot(d, (cx, y0))
    two(d, elm.Capacitor, (cx, y0), 'down', refs['Ct'], '100nF', length=2.0, loc='top')
    gnd(d, (cx, y0 - 2.0))
    o = elm.Optocoupler().theta(0).anchor('cathode').at(kn).label(f"{refs['U']}\nPC817", loc='bottom', fontsize=FS)
    o = d.add(o)
    dxx = x0 + 4.5
    dot(d, (dxx, y0))
    two(d, elm.Diode, (dxx, y0), 'up', refs['Dp'], '1N4148W', length=o.anode[1] - y0, loc='top')
    wire(d, (dxx, o.anode[1]), o.anode)
    dot(d, (dxx, o.anode[1]))
    two(d, elm.Resistor, (dxx, o.anode[1]), 'up', refs['Ra'], '1k', length=2.5, loc='top')
    vcc(d, (dxx, o.anode[1] + 2.5), '+5V')
    wire(d, o.emitter, P(o.emitter, 0, -1.2))
    gnd(d, P(o.emitter, 0, -1.2))
    cn = (o.collector[0] + 1.6, o.collector[1])
    wire(d, o.collector, P(cn, 4.5, 0))
    dot(d, cn)
    two(d, elm.Resistor, cn, 'up', refs['Rp'], '10k', length=2.5, loc='bottom')
    vcc(d, P(cn, 0, 2.5), '+3V3')
    c2 = P(cn, 2.5, 0)
    dot(d, c2)
    two(d, elm.Capacitor, c2, 'down', refs['Cf'], '10nF', length=2.0, loc='bottom')
    gnd(d, P(c2, 0, -2.0))
    flag(d, P(cn, 4.5, 0), net)


def sheet_inputs():
    d = new_drawing()
    opto_channel(d, 0, dict(Ct='C18', U='U8', Dp='D8', Ra='R20', Rp='R21', Cf='C17'),
                 'J7-1  DOOR contact', 'IN_DOOR')
    opto_channel(d, -9, dict(Ct='C20', U='U9', Dp='D9', Ra='R22', Rp='R23', Cf='C19'),
                 'J7-2  EXIT button', 'IN_EXIT')
    terminal(d, (0, -14.5), 'J7-3  COM (GND)')
    wire(d, (0, -14.5), (1.0, -14.5))
    gnd(d, (1.0, -14.5))
    text(d, (-0.5, -15.8), 'J7  3-pin 5.08 mm terminal', halign='right', fontsize=8)
    # tamper
    ty = -19
    terminal(d, (0, ty), 'J8-1  TAMPER switch')
    r24 = two(d, elm.Resistor, (0, ty), 'right', 'R24', '1k', length=2.5, loc='top')
    tn = (5.0, ty)
    wire(d, r24.end, P(tn, 5.0, 0))
    dot(d, tn)
    two(d, elm.Resistor, tn, 'up', 'R25', '10k', length=2.5, loc='bottom')
    vcc(d, P(tn, 0, 2.5), '+3V3')
    dot(d, P(tn, 2.5, 0))
    two(d, elm.Capacitor, P(tn, 2.5, 0), 'down', 'C21', '100nF', length=2.0)
    gnd(d, P(tn, 2.5, -2.0))
    flag(d, P(tn, 5.0, 0), 'IN_TAMPER')
    terminal(d, (0, ty - 2.5), 'J8-2  GND')
    wire(d, (0, ty - 2.5), (1.0, ty - 2.5))
    gnd(d, (1.0, ty - 2.5))
    text(d, (-0.5, ty - 3.8), 'J8  2-pin JST-XH to lid micro-switch', halign='right', fontsize=8)

    notes = ('NOTES\n'
             '1. Contacts close to J7-3 (COM). Closed = opto LED on (~3.8 mA wetting current) = GPIO reads LOW.\n'
             '2. Door contact: reed switch, closed when the door is shut. Exit button: normally-open push button.\n'
             '3. Tamper: micro-switch pressed by the closed lid (closed = LOW). Lid opened or wire cut = HIGH = tamper event.\n'
             '4. J7-3 is board ground, which is NOT isolated from J1. Do not connect J7-3 to the lock power supply.')
    finish(d, 6, notes)


# --------------------------------------------------------------------------
# Sheet 8: indicators
# --------------------------------------------------------------------------
def sheet_indicators():
    d = new_drawing()
    for i, (net, rr, led, colr) in enumerate((('LED_GRN', 'R26', 'LED1', 'green'),
                                              ('LED_RED', 'R27', 'LED2', 'red'))):
        y = -5.0 * i
        flag(d, (0, y), net, side='left')
        r = two(d, elm.Resistor, (0, y), 'right', rr, '220R', length=2.5, loc='top')
        wire(d, r.end, (4.0, y))
        two(d, elm.LED, (4.0, y), 'down', led, f'{colr} 3 mm', length=2.5)
        gnd(d, (4.0, y - 2.5))
    text(d, (-4.5, -9.5), 'LEDs sit under a light pipe in the lid\n(or wire them to an external indicator).', fontsize=8)

    # buzzer
    bx, by = 16, 2
    vcc(d, (bx, by), '+5V')
    top = (bx, by)
    dxx = bx - 2.5
    wire(d, top, (dxx, by))
    dot(d, top)
    bz = d.add(Buzzer().at(top).down().length(2.5).label('BZ1\nactive buzzer\n5 V 12x9.5 mm', loc='bottom', fontsize=FS))
    text(d, P(top, 0.3, -0.3), '+', fontsize=9)
    bot = (bx, by - 2.5)
    dot(d, bot)
    wire(d, bot, (dxx, by - 2.5))
    two(d, elm.Diode, (dxx, by - 2.5), 'up', 'D10', '1N4148W', length=2.5, loc='top')
    lowside_driver(d, bot, 'BUZZER', dict(Q='Q3', Rg='R28', Rpd='R29', D='D10'))

    notes = ('NOTES\n'
             '1. Green = access granted, red = denied / tamper, alternating = admin mode. The buzzer gives a short beep on every remote press.\n'
             '2. Use an ACTIVE buzzer (built-in oscillator): the firmware only switches it on and off.')
    finish(d, 7, notes)


# --------------------------------------------------------------------------
# Sheet 9: expansion + RS485
# --------------------------------------------------------------------------
def sheet_expansion():
    d = new_drawing()
    # J9 header
    hx, hy = 0, 0
    names = ['+5V', '+3V3', 'GND', 'UART1_TX', 'UART1_RX', 'EXP_IO4', 'EXP_IO5', 'GND']
    d.add(R0(corner1=(hx - 1.2, hy + 0.8), corner2=(hx, hy - 1.2 * (len(names) - 1) - 0.8)))
    text(d, (hx - 0.6, hy + 1.2), 'J9  expansion 1x8 2.54 mm (DNP)\ne.g. UART LoRa module E22-900T22S', halign='center', valign='bottom')
    for i, net in enumerate(names):
        y = hy - 1.2 * i
        d.add(elm.Dot(open=True, radius=0.16).at((hx - 0.4, y)))
        text(d, (hx - 0.75, y), str(i + 1), halign='right', valign='center', fontsize=8)
        wire(d, (hx, y), (hx + 1.5, y))
        if net in ('+5V', '+3V3'):
            wire(d, (hx + 1.5, y), (hx + 2.5 + 1.5 * i, y))
            vcc(d, (hx + 2.5 + 1.5 * i, y), net)
        elif net == 'GND':
            gnd(d, (hx + 1.5, y))
        else:
            flag(d, (hx + 1.5, y), net)
    text(d, (hx + 6.5, hy - 7.0), 'LoRa: M0 = EXP_IO4, M1 = EXP_IO5.\nUse 868/915 MHz modules, never 433 MHz.', fontsize=8)

    # RS485
    ux, uy = 18, -1
    u10 = ic(d, 'U10', 'SP3485EN (3.3 V RS485)', dnp=True,
             left=[('RO', 1, 'RO'), ('DI', 4, 'DI'), ('/RE', 2, 'RE'), ('DE', 3, 'DE')],
             right=[('VCC', 8, 'VCC'), ('A', 6, 'A'), ('B', 7, 'B'), ('GND', 5, 'GND')],
             anchor='RO', at=(ux, uy), pinspacing=1.5, w=4.5)
    wire(d, u10.RO, P(u10.RO, -1.5, 0), color=DNP_COLOR)
    flag(d, P(u10.RO, -1.5, 0), 'UART1_RX', side='left')
    wire(d, u10.DI, P(u10.DI, -1.5, 0), color=DNP_COLOR)
    flag(d, P(u10.DI, -1.5, 0), 'UART1_TX', side='left')
    tx = u10.RE[0] - 1.0
    wire(d, u10.RE, (tx, u10.RE[1]), color=DNP_COLOR)
    wire(d, u10.DE, (tx, u10.DE[1]), color=DNP_COLOR)
    wire(d, (tx, u10.RE[1]), (tx, u10.DE[1]), color=DNP_COLOR)
    dot(d, (tx, u10.DE[1]))
    den = (tx - 1.5, u10.DE[1])
    wire(d, (tx, u10.DE[1]), den)
    dot(d, den)
    two(d, elm.Resistor, den, 'down', 'R30', '10k (fit)', length=2.0, loc='top')
    gnd(d, P(den, 0, -2.0))
    wire(d, den, P(den, -1.0, 0))
    flag(d, P(den, -1.0, 0), 'EXP_IO4', side='left')
    # VCC
    vc = P(u10.VCC, 1.5, 0)
    wire(d, u10.VCC, vc, color=DNP_COLOR)
    wire(d, vc, P(vc, 0, 1.2), color=DNP_COLOR)
    vcc(d, P(vc, 0, 1.2), '+3V3')
    cdx = P(vc, 3.5, 3.0)
    vcc(d, cdx, '+3V3')
    two(d, elm.Capacitor, cdx, 'down', 'C22', '100nF (at U10)', length=2.0, loc='bottom', dnp=True)
    gnd(d, P(cdx, 0, -2.0))
    gnd(d, u10.GND)
    # A / B lines
    ya, yb = u10.A[1] + 0.0, u10.B[1] - 0.0
    xa = u10.A[0]
    ax_top = u10.VCC[1] + 0.0
    a_y = ya
    b_y = yb - 4.5
    wire(d, u10.A, (xa + 1.0, ya), color=DNP_COLOR)
    wire(d, (xa + 1.0, ya), (xa + 1.0, a_y), color=DNP_COLOR)
    xend = xa + 15
    wire(d, (xa + 1.0, a_y), (xend, a_y), color=DNP_COLOR)
    wire(d, u10.B, (xa + 0.5, yb), color=DNP_COLOR)
    wire(d, (xa + 0.5, yb), (xa + 0.5, b_y), color=DNP_COLOR)
    wire(d, (xa + 0.5, b_y), (xend, b_y), color=DNP_COLOR)
    # termination R31 + JP2 between A and B
    tx2 = xa + 6.5
    dot(d, (tx2, a_y))
    two(d, elm.Resistor, (tx2, a_y), 'down', 'R31', '120R', length=2.5, loc='top', dnp=True)
    jp_top = (tx2, a_y - 2.5)
    d.add(R0(corner1=(tx2 - 0.28, jp_top[1]), corner2=(tx2 + 0.28, jp_top[1] - 0.45)))
    d.add(R0(corner1=(tx2 - 0.28, jp_top[1] - 0.75), corner2=(tx2 + 0.28, jp_top[1] - 1.2)))
    text(d, (tx2 - 0.5, jp_top[1] - 0.6), 'JP2 (open)\nclose at bus ends', halign='right', valign='center', fontsize=7.5)
    wire(d, (tx2, jp_top[1] - 1.2), (tx2, b_y), color=DNP_COLOR)
    dot(d, (tx2, b_y))
    # SM712 TVS
    sx = xa + 10.5
    mid = (sx, (a_y + b_y) / 2)
    dot(d, (sx, a_y))
    dot(d, (sx, b_y))
    two(d, elm.Zener, mid, 'up', 'D11', 'SM712 (pin 1)', length=a_y - mid[1], loc='bottom', dnp=True)
    two(d, elm.Zener, mid, 'down', '', 'SM712 (pin 2)', length=mid[1] - b_y, loc='bottom', dnp=True)
    wire(d, mid, P(mid, 1.5, 0), color=DNP_COLOR)
    dot(d, mid)
    gnd(d, P(mid, 1.5, 0))
    text(d, P(mid, 1.8, 0.4), 'pin 3', fontsize=7.5)
    terminal(d, (xend, a_y), 'J10-1  A', side='right')
    terminal(d, (xend, b_y), 'J10-2  B', side='right')
    terminal(d, (xend, b_y - 1.5), 'J10-3  GND', side='right')
    wire(d, (xend, b_y - 1.5), (xend - 1.0, b_y - 1.5))
    gnd(d, (xend - 1.0, b_y - 1.5))
    text(d, (xend - 1.0, a_y + 1.4), 'J10  3-pin 5.08 mm (DNP)', fontsize=8)

    notes = ('NOTES\n'
             '1. Everything grey is DNP (not fitted). Fit it only on units that need it. R30 is always fitted: it keeps IO4 low (RS485 = receive).\n'
             '2. UART1_RX can have only one driver: fit EITHER U10 (RS485) OR a module on J9, never both.\n'
             '3. Close JP2 (120 R termination) only on the two units at the physical ends of the RS485 cable.')
    finish(d, 8, notes)


def main():
    sheet_power()
    sheet_mcu()
    sheet_usb()
    sheet_rf()
    sheet_rtc()
    sheet_relays()
    sheet_inputs()
    sheet_indicators()
    sheet_expansion()
    print('wrote', ', '.join(k for k, _ in SHEETS))


if __name__ == '__main__':
    main()
