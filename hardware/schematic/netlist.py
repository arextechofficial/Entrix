#!/usr/bin/env python3
"""Entrix Rev A netlist + BOM (the same circuit as build_schematic.py).

Usage:  python netlist.py      -> writes netlist.md and bom.csv, runs basic checks

Each part: (ref, value, package, description, dnp, {pin: net}).
Pin names are the datasheet pin numbers where they exist.
"""
import csv
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
NC = None  # not connected

PARTS = [
    # ---------------- sheet 1: power ----------------
    ('J1', '2-pin terminal 5.08 mm', 'THT', 'Power input 12-24 V AC/DC', False, {'1': 'VIN_A', '2': 'VIN_B'}),
    ('F1', 'PTC 0.5 A hold, >=60 V', 'radial / 1812', 'Resettable fuse, e.g. RXEF050 / MF-R050', False, {'1': 'VIN_A', '2': 'VIN_AF'}),
    ('D1', 'DB107S', 'DBS (SMD)', 'Bridge rectifier 1 A 1000 V', False, {'AC1': 'VIN_AF', 'AC2': 'VIN_B', '+': 'VRECT', '-': 'GND'}),
    ('D2', 'SMBJ40A', 'SMB', 'TVS 40 V unidirectional', False, {'K': 'VRECT', 'A': 'GND'}),
    ('C1', '470uF 63V', 'radial 10x16 mm', 'Electrolytic, 105 C', False, {'+': 'VRECT', '-': 'GND'}),
    ('C2', '1uF 100V', '1206', 'MLCC X7R', False, {'1': 'VRECT', '2': 'GND'}),
    ('U1', 'XL7015E1', 'TO252-5L', 'Buck converter 5-80 V in, 0.8 A (LCSC C73013)', False,
     {'1': 'VRECT', '2': 'SW5V', '3': 'GND', '4': 'FB', '5': 'GND'}),
    ('D3', 'SS310', 'SMA/SMC', 'Schottky 3 A 100 V', False, {'K': 'SW5V', 'A': 'GND'}),
    ('L1', '100uH Isat>=1A', '12x12 mm shielded', 'Power inductor', False, {'1': 'SW5V', '2': '+5V'}),
    ('C3', '220uF 25V', 'radial 8x12 mm', 'Electrolytic low-ESR, 105 C', False, {'+': '+5V', '-': 'GND'}),
    ('C4', '100nF 50V', '0603', 'MLCC X7R', False, {'1': '+5V', '2': 'GND'}),
    ('R1', '10k 1%', '0603', 'Feedback top', False, {'1': '+5V', '2': 'FB'}),
    ('R2', '3.3k 1%', '0603', 'Feedback bottom', False, {'1': 'FB', '2': 'GND'}),
    ('C5', '33nF', '0603', 'Feed-forward cap (per XL7015 typical application)', False, {'1': '+5V', '2': 'FB'}),
    ('U2', 'AP2112K-3.3', 'SOT-23-5', 'LDO 3.3 V 600 mA', False, {'1': '+5V', '2': 'GND', '3': '+5V', '4': NC, '5': '+3V3'}),
    ('C6', '10uF 16V', '0805', 'MLCC X7R', False, {'1': '+5V', '2': 'GND'}),
    ('C7', '10uF 10V', '0805', 'MLCC X7R', False, {'1': '+3V3', '2': 'GND'}),
    ('R3', '220k 1%', '0603', 'VRECT sense divider top', False, {'1': 'VRECT', '2': 'VSENSE'}),
    ('R4', '10k 1%', '0603', 'VRECT sense divider bottom', False, {'1': 'VSENSE', '2': 'GND'}),
    ('C8', '100nF', '0603', 'MLCC', False, {'1': 'VSENSE', '2': 'GND'}),
    # ---------------- sheet 2: MCU ----------------
    ('U3', 'ESP32-C6-WROOM-1-N8', 'module', 'Wi-Fi 6 + BLE 5 + 802.15.4 (Zigbee), 8 MB flash', False, {
        '1': 'GND', '2': '+3V3', '3': 'EN', '4': 'EXP_IO4', '5': 'EXP_IO5', '6': 'I2C_SDA', '7': 'I2C_SCL',
        '8': 'VSENSE', '9': 'RF_DATA', '10': 'IO8_STRAP', '11': 'IN_DOOR', '12': 'IN_EXIT', '13': 'USB_DN',
        '14': 'USB_DP', '15': 'BOOT', '16': 'IN_TAMPER', '17': 'LED_GRN', '18': 'LED_RED', '19': 'BUZZER',
        '20': 'UART1_TX', '21': 'UART1_RX', '22': NC, '23': NC, '24': 'UART0_RX', '25': 'UART0_TX',
        '26': 'RELAY2', '27': 'RELAY1', '28': 'GND', '29': 'GND'}),
    ('C9', '22uF 10V', '0805', 'MLCC X5R, at U3 pin 2', False, {'1': '+3V3', '2': 'GND'}),
    ('C10', '100nF', '0603', 'MLCC, at U3 pin 2', False, {'1': '+3V3', '2': 'GND'}),
    ('R5', '10k', '0603', 'EN pull-up', False, {'1': '+3V3', '2': 'EN'}),
    ('C11', '1uF', '0603', 'EN delay', False, {'1': 'EN', '2': 'GND'}),
    ('SW1', 'RESET', '6x6 mm tact', 'Push button', False, {'1': 'EN', '2': 'GND'}),
    ('R6', '10k', '0603', 'IO8 strap pull-up', False, {'1': '+3V3', '2': 'IO8_STRAP'}),
    ('R7', '10k', '0603', 'IO9 / BOOT pull-up', False, {'1': '+3V3', '2': 'BOOT'}),
    ('SW2', 'SETUP / BOOT', '6x6 mm tact', 'Push button', False, {'1': 'BOOT', '2': 'GND'}),
    # ---------------- sheet 3: USB ----------------
    ('J3', 'USB-C 16-pin', 'SMD/THT', 'USB 2.0 receptacle', False, {
        'VBUS': 'VBUS', 'D-': 'USB_DN', 'D+': 'USB_DP', 'CC1': 'CC1', 'CC2': 'CC2', 'GND': 'GND', 'SHIELD': 'GND'}),
    ('D4', 'SS14', 'SMA', 'Schottky 1 A 40 V (VBUS -> +5V)', False, {'A': 'VBUS', 'K': '+5V'}),
    ('U4', 'USBLC6-2SC6', 'SOT-23-6', 'USB ESD protection', False,
     {'1': 'USB_DN', '2': 'GND', '3': 'USB_DP', '4': 'USB_DP', '5': 'VBUS', '6': 'USB_DN'}),
    ('R8', '5.1k', '0603', 'CC1 pull-down (USB device)', False, {'1': 'CC1', '2': 'GND'}),
    ('R9', '5.1k', '0603', 'CC2 pull-down (USB device)', False, {'1': 'CC2', '2': 'GND'}),
    ('J2', '1x6 header 2.54 mm', 'THT', 'UART0 programming header', True,
     {'1': '+3V3', '2': 'UART0_TX', '3': 'UART0_RX', '4': 'EN', '5': 'BOOT', '6': 'GND'}),
    # ---------------- sheet 4: RF ----------------
    ('R12', '22R', '0603', 'RF supply filter', False, {'1': '+5V', '2': '+5V_RF'}),
    ('C12', '100uF 10V', 'radial 5x11 / 1210', 'RF supply filter', False, {'+': '+5V_RF', '-': 'GND'}),
    ('C13', '100nF', '0603', 'MLCC', False, {'1': '+5V_RF', '2': 'GND'}),
    ('U5', 'RXB61 433.92 MHz', 'module, 5 pins', '433 MHz superheterodyne OOK receiver', False,
     {'VIN': '+5V_RF', 'GND': 'GND', 'DATA': 'RF_DO', 'ANT': 'ANT433', 'SHUT': 'RF_SHUT'}),
    ('R10', '10k', '0603', 'DATA level shift top', False, {'1': 'RF_DO', '2': 'RF_DATA'}),
    ('R11', '20k', '0603', 'DATA level shift bottom', False, {'1': 'RF_DATA', '2': 'GND'}),
    ('JP1', '3-pad solder jumper', 'SMD', 'SHUT select, 1-2 bridged by default', False,
     {'1': 'GND', '2': 'RF_SHUT', '3': '+5V_RF'}),
    ('E1', '17.3 cm wire', 'pad', '433 MHz quarter-wave antenna', False, {'1': 'ANT433'}),
    ('J4', 'SMA edge jack', 'edge', 'Alternative: external 433 MHz whip', True, {'SIG': 'ANT433', 'GND': 'GND'}),
    # ---------------- sheet 5: RTC ----------------
    ('U6', 'PCF8563T', 'SO-8', 'RTC, I2C 0x51 (alt. BM8563)', False,
     {'1': 'OSCI', '2': 'OSCO', '3': NC, '4': 'GND', '5': 'I2C_SDA', '6': 'I2C_SCL', '7': NC, '8': 'VDD_RTC'}),
    ('Y1', '32.768 kHz', '3215 / 2x6 mm', 'Crystal, CL 12.5 pF', False, {'1': 'OSCI', '2': 'OSCO'}),
    ('C14', '0-15pF', '0603', 'Oscillator trim', True, {'1': 'OSCI', '2': 'GND'}),
    ('C15', '100nF', '0603', 'MLCC', False, {'1': 'VDD_RTC', '2': 'GND'}),
    ('D5', 'BAT54C', 'SOT-23', 'Dual Schottky, common cathode', False, {'1': '+3V3', '2': 'VBAT_R', '3': 'VDD_RTC'}),
    ('R13', '1k', '0603', 'Battery protection', False, {'1': 'VBAT', '2': 'VBAT_R'}),
    ('BT1', 'BR2032', 'CR2032 holder', 'Li coin cell, -30...+85 C', False, {'+': 'VBAT', '-': 'GND'}),
    ('R14', '4.7k', '0603', 'I2C SDA pull-up', False, {'1': '+3V3', '2': 'I2C_SDA'}),
    ('R15', '4.7k', '0603', 'I2C SCL pull-up', False, {'1': '+3V3', '2': 'I2C_SCL'}),
    ('U7', 'MB85RC256V', 'SO-8', 'FRAM 32 KB, I2C 0x50 (optional)', True,
     {'1': 'GND', '2': 'GND', '3': 'GND', '4': 'GND', '5': 'I2C_SDA', '6': 'I2C_SCL', '7': 'GND', '8': '+3V3'}),
    ('C16', '100nF', '0603', 'MLCC at U7', True, {'1': '+3V3', '2': 'GND'}),
    # ---------------- sheet 6: relays ----------------
    ('K1', 'SRD-05VDC-SL-C', 'T73', 'Relay 5 V coil, 1 Form C, 10 A (or HF3FF/005-1ZS)', False,
     {'C1': '+5V', 'C2': 'RLY1_D', 'COM': 'K1_COM', 'NC': 'K1_NC', 'NO': 'K1_NO'}),
    ('D6', 'SS14', 'SMA', 'Flyback diode', False, {'A': 'RLY1_D', 'K': '+5V'}),
    ('Q1', 'AO3400A', 'SOT-23', 'N-MOSFET 30 V 5.7 A', False, {'G': 'RLY1_G', 'D': 'RLY1_D', 'S': 'GND'}),
    ('R16', '100R', '0603', 'Gate resistor', False, {'1': 'RELAY1', '2': 'RLY1_G'}),
    ('R17', '10k', '0603', 'Gate pull-down', False, {'1': 'RLY1_G', '2': 'GND'}),
    ('J5', '3-pin terminal 5.08 mm', 'THT', 'Relay 1 contacts: 1 COM, 2 NC, 3 NO', False,
     {'1': 'K1_COM', '2': 'K1_NC', '3': 'K1_NO'}),
    ('K2', 'SRD-05VDC-SL-C', 'T73', 'Relay 2 (optional)', True,
     {'C1': '+5V', 'C2': 'RLY2_D', 'COM': 'K2_COM', 'NC': 'K2_NC', 'NO': 'K2_NO'}),
    ('D7', 'SS14', 'SMA', 'Flyback diode', True, {'A': 'RLY2_D', 'K': '+5V'}),
    ('Q2', 'AO3400A', 'SOT-23', 'N-MOSFET', True, {'G': 'RLY2_G', 'D': 'RLY2_D', 'S': 'GND'}),
    ('R18', '100R', '0603', 'Gate resistor', True, {'1': 'RELAY2', '2': 'RLY2_G'}),
    ('R19', '10k', '0603', 'Gate pull-down', True, {'1': 'RLY2_G', '2': 'GND'}),
    ('J6', '3-pin terminal 5.08 mm', 'THT', 'Relay 2 contacts: 1 COM, 2 NC, 3 NO', True,
     {'1': 'K2_COM', '2': 'K2_NC', '3': 'K2_NO'}),
    # ---------------- sheet 7: inputs ----------------
    ('J7', '3-pin terminal 5.08 mm', 'THT', 'Inputs: 1 DOOR, 2 EXIT, 3 COM', False, {'1': 'DOOR_T', '2': 'EXIT_T', '3': 'GND'}),
    ('C18', '100nF', '0603', 'Input filter', False, {'1': 'DOOR_T', '2': 'GND'}),
    ('D8', '1N4148W', 'SOD-123', 'Opto LED reverse protection', False, {'A': 'DOOR_T', 'K': 'OPTO1_A'}),
    ('R20', '1k', '0603', 'Opto LED current', False, {'1': '+5V', '2': 'OPTO1_A'}),
    ('U8', 'PC817', 'DIP-4 / SMD-4', 'Optocoupler', False, {'1': 'OPTO1_A', '2': 'DOOR_T', '3': 'GND', '4': 'IN_DOOR'}),
    ('R21', '10k', '0603', 'Pull-up', False, {'1': '+3V3', '2': 'IN_DOOR'}),
    ('C17', '10nF', '0603', 'Debounce', False, {'1': 'IN_DOOR', '2': 'GND'}),
    ('C20', '100nF', '0603', 'Input filter', False, {'1': 'EXIT_T', '2': 'GND'}),
    ('D9', '1N4148W', 'SOD-123', 'Opto LED reverse protection', False, {'A': 'EXIT_T', 'K': 'OPTO2_A'}),
    ('R22', '1k', '0603', 'Opto LED current', False, {'1': '+5V', '2': 'OPTO2_A'}),
    ('U9', 'PC817', 'DIP-4 / SMD-4', 'Optocoupler', False, {'1': 'OPTO2_A', '2': 'EXIT_T', '3': 'GND', '4': 'IN_EXIT'}),
    ('R23', '10k', '0603', 'Pull-up', False, {'1': '+3V3', '2': 'IN_EXIT'}),
    ('C19', '10nF', '0603', 'Debounce', False, {'1': 'IN_EXIT', '2': 'GND'}),
    ('J8', 'JST-XH 2-pin', 'THT', 'Lid tamper micro-switch', False, {'1': 'TAMPER_T', '2': 'GND'}),
    ('R24', '1k', '0603', 'Series protection', False, {'1': 'TAMPER_T', '2': 'IN_TAMPER'}),
    ('R25', '10k', '0603', 'Pull-up', False, {'1': '+3V3', '2': 'IN_TAMPER'}),
    ('C21', '100nF', '0603', 'Debounce', False, {'1': 'IN_TAMPER', '2': 'GND'}),
    # ---------------- sheet 8: indicators ----------------
    ('R26', '220R', '0603', 'LED resistor', False, {'1': 'LED_GRN', '2': 'LED1_A'}),
    ('LED1', 'green', '3 mm THT', 'Status LED', False, {'A': 'LED1_A', 'K': 'GND'}),
    ('R27', '220R', '0603', 'LED resistor', False, {'1': 'LED_RED', '2': 'LED2_A'}),
    ('LED2', 'red', '3 mm THT', 'Status LED', False, {'A': 'LED2_A', 'K': 'GND'}),
    ('BZ1', 'active buzzer 5 V', '12x9.5 mm THT', 'Magnetic, built-in oscillator', False, {'+': '+5V', '-': 'BZ_D'}),
    ('D10', '1N4148W', 'SOD-123', 'Flyback diode', False, {'A': 'BZ_D', 'K': '+5V'}),
    ('Q3', 'AO3400A', 'SOT-23', 'N-MOSFET', False, {'G': 'BZ_G', 'D': 'BZ_D', 'S': 'GND'}),
    ('R28', '100R', '0603', 'Gate resistor', False, {'1': 'BUZZER', '2': 'BZ_G'}),
    ('R29', '10k', '0603', 'Gate pull-down', False, {'1': 'BZ_G', '2': 'GND'}),
    # ---------------- sheet 9: expansion / RS485 ----------------
    ('J9', '1x8 header 2.54 mm', 'THT', 'Expansion (UART LoRa module etc.)', True, {
        '1': '+5V', '2': '+3V3', '3': 'GND', '4': 'UART1_TX', '5': 'UART1_RX', '6': 'EXP_IO4', '7': 'EXP_IO5', '8': 'GND'}),
    ('U10', 'SP3485EN', 'SO-8', 'RS485 transceiver 3.3 V', True,
     {'1': 'UART1_RX', '2': 'EXP_IO4', '3': 'EXP_IO4', '4': 'UART1_TX', '5': 'GND', '6': 'RS485_A', '7': 'RS485_B', '8': '+3V3'}),
    ('C22', '100nF', '0603', 'MLCC at U10', True, {'1': '+3V3', '2': 'GND'}),
    ('R30', '10k', '0603', 'IO4 pull-down (always fitted)', False, {'1': 'EXP_IO4', '2': 'GND'}),
    ('D11', 'SM712', 'SOT-23', 'RS485 TVS', True, {'1': 'RS485_A', '2': 'RS485_B', '3': 'GND'}),
    ('R31', '120R', '0805', 'RS485 termination', True, {'1': 'RS485_A', '2': 'RS485_TERM'}),
    ('JP2', '2-pad solder jumper', 'SMD', 'Termination enable (open by default)', True, {'1': 'RS485_TERM', '2': 'RS485_B'}),
    ('J10', '3-pin terminal 5.08 mm', 'THT', 'RS485: 1 A, 2 B, 3 GND', True, {'1': 'RS485_A', '2': 'RS485_B', '3': 'GND'}),
]

# Nets that legitimately have only one connection on a fully-populated board
SINGLE_OK = set()


def build():
    refs = [p[0] for p in PARTS]
    dup = {r for r in refs if refs.count(r) > 1}
    assert not dup, f'duplicate refs: {dup}'

    nets = defaultdict(list)
    for ref, val, pkg, desc, dnp, pins in PARTS:
        for pin, net in pins.items():
            if net is not None:
                nets[net].append((ref, pin, dnp))

    problems = []
    for net, conns in nets.items():
        if len(conns) < 2 and net not in SINGLE_OK:
            problems.append(f'net {net} has only {conns}')
        fitted = [c for c in conns if not c[2]]
        if len(fitted) < 2 and len(conns) >= 2:
            # only DNP parts on this net (fine) -- or one fitted pin dangling
            if len(fitted) == 1:
                pass
    return nets, problems


def write_outputs(nets):
    # netlist.md
    lines = ['# Entrix Rev A netlist', '',
             'Generated by `netlist.py`. Pins marked * belong to parts that are not fitted (DNP) on the standard build.', '',
             '| Net | Connections |', '|---|---|']
    def key(n):
        order = {'GND': 0, '+3V3': 1, '+5V': 2, 'VRECT': 3}
        return (order.get(n, 9), n)
    for net in sorted(nets, key=key):
        conns = ', '.join(f'{r}.{p}' + ('*' if d else '') for r, p, d in sorted(nets[net], key=lambda c: (refkey(c[0]), c[1])))
        lines.append(f'| `{net}` | {conns} |')
    lines += ['', '## Parts', '', '| Ref | Value | Package | Description | Fitted |', '|---|---|---|---|---|']
    for ref, val, pkg, desc, dnp, pins in sorted(PARTS, key=lambda p: refkey(p[0])):
        lines.append(f'| {ref} | {val} | {pkg} | {desc} | {"DNP" if dnp else "yes"} |')
    (HERE / 'netlist.md').write_text('\n'.join(lines) + '\n')

    # bom.csv grouped by value + package + fitted
    groups = defaultdict(list)
    for ref, val, pkg, desc, dnp, pins in sorted(PARTS, key=lambda p: refkey(p[0])):
        groups[(val, pkg, dnp)].append((ref, desc))
    with open(HERE / 'bom.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Qty', 'Value / part', 'Package', 'References', 'Description', 'Fitted'])
        for (val, pkg, dnp), items in sorted(groups.items(), key=lambda kv: (kv[0][2], refkey(kv[1][0][0]))):
            descs = {dsc for _, dsc in items}
            desc = descs.pop() if len(descs) == 1 else CATEGORY.get(refkey(items[0][0])[0], '')
            w.writerow([len(items), val, pkg, ' '.join(r for r, _ in items), desc, 'DNP' if dnp else 'yes'])


CATEGORY = {'R': 'Resistor', 'C': 'Capacitor', 'D': 'Diode', 'J': 'Terminal block / connector',
            'Q': 'N-MOSFET', 'U': 'IC', 'SW': 'Push button', 'LED': 'LED'}


def refkey(ref):
    i = len(ref.rstrip('0123456789'))
    return (ref[:i], int(ref[i:] or 0))


if __name__ == '__main__':
    nets, problems = build()
    write_outputs(nets)
    fitted = sum(1 for p in PARTS if not p[4])
    print(f'{len(PARTS)} parts ({fitted} fitted, {len(PARTS) - fitted} DNP), {len(nets)} nets')
    if problems:
        print('PROBLEMS:')
        for p in problems:
            print('  ', p)
        raise SystemExit(1)
    print('check OK: every net has at least two connections')
