# Entrix — Hardware Design Rev B: RS485 bus with a Raspberry Pi 3 (draft)

> **Status:** proposal for review. Rev B connects the Rev A door controller
> ([hardware-design.md](hardware-design.md)) to a Raspberry Pi 3 over a wired RS485 bus, using
> Modbus RTU.
> The Ethernet option from the first Rev B draft was dropped as too costly and complex (it is still
> in the git history).
> Prices are approximate 2025–26 prices; check them before ordering.

---

## 1. Summary

```
 Office (indoors)
┌─────────────────────────┐
│ Raspberry Pi 3          ├──── LAN / Wi-Fi: admin web page from any office PC
│ admin web UI, database  │
│ DS3231 RTC, UPS (opt.)  │
└────────────┬────────────┘
             │ USB
┌────────────┴────────────┐
│ isolated USB-RS485      │  120 Ω ON, bias ON
└────────────┬────────────┘
             │ outdoor shielded cable (A, B, GND_ISO, shield), daisy chain, ≤ 1,200 m
        ┌────┴───┐    ┌────────┐    ┌────────┐    ┌────────┐
        │ Door 1 ├────┤ Door 2 ├────┤ Door 3 ├────┤ Door 4 │  120 Ω ON at door 4
        │ addr 1 │    │ addr 2 │    │ addr 3 │    │ addr 4 │
        └────────┘    └────────┘    └────────┘    └────────┘
        each door: its local 12-24 V supply (the lock's)
```

* **One Raspberry Pi 3** is the bus master. It polls the 4 doors, keeps the central user database,
  collects the logs and serves the admin web page to your office network over its own Ethernet or
  Wi-Fi port. That is a normal office connection, not a cable to the doors.
* **One shielded twisted-pair cable** runs from the Pi to door 1, then on to doors 2, 3 and 4.
* **Each door** is the Rev A controller with an **isolated RS485 port** added.
* **Protocol: Modbus RTU** at 19,200 baud, 8 data bits, even parity, 1 stop bit (8E1), with door
  addresses 1–4.
* **Each door keeps working on its own** from its local user list and log if the Pi or the cable
  fails. The bus is only used to sync users, collect logs, set the clock, and send remote commands.

---

## 2. Shopping list

### 2.1 Raspberry Pi side (once)

| Item | Recommended | ~Price | Why |
|---|---|---|---|
| Computer | Raspberry Pi 3 (you have it) | — | Bus master, admin web UI, central database |
| **RS485 interface** | **USB-to-RS485 converter with an isolated transceiver and TVS protection, FTDI FT232RNL chip** (e.g. Waveshare isolated USB-to-RS485 converter, or its industrial DIN-rail version) | $10–25 | Plug-and-play: it appears as `/dev/ttyUSB0`. The isolation protects the Pi from surges on the outdoor cable, and FTDI chips have the best Linux support. Check whether its 120 Ω terminator is fixed or on a jumper (§4) |
| *(alternative)* | RS485 HAT on the GPIO serial port | $10–15 | Not recommended on a Pi 3: Bluetooth uses the good UART (PL011), so you must add `dtoverlay=disable-bt` in `config.txt`. Most HATs are not isolated either |
| Power supply | Official 5.1 V 2.5 A micro-USB supply | $8–10 | A weak supply is a common cause of SD-card corruption |
| microSD card | 32 GB "high endurance" type | $8–12 | The logs are written all the time |
| Real-time clock | DS3231 module (I²C, with coin cell) on the Pi's GPIO header | $2–5 | The Pi 3 has no clock. It is the time source for the doors when there is no internet time (NTP) |
| Power-loss protection | UPS HAT with an 18650 cell **or** read-only root filesystem (`raspi-config` → Overlay FS) with the database on a separate partition | $0–30 | Requirement 3 also applies to the Pi: a power cut during an SD write can corrupt the card. The doors don't depend on the Pi, so this protects history, not door operation |
| Case | Any indoor case | $5–10 | The Pi stays indoors |

### 2.2 Cable and installation (once)

| Item | Recommended | ~Price | Notes |
|---|---|---|---|
| **Bus cable** | Outdoor **shielded CAT5e** (F/UTP, black PE jacket; gel-filled if buried), or 120 Ω RS485 cable such as Belden 3106A | $0.3–0.6 per m | Length = Pi → door 1 → door 2 → door 3 → door 4, plus 10 % |
| Protection | Conduit or armoured cable where it can be hit or cut | as needed | |
| Surge protector | DIN-rail RS485 surge protector with an earth terminal, where the cable leaves the building | $15–30 | Only if the cable leaves the building, runs overhead, or runs a long way outdoors |
| Earth | Earth connection for the shield at the Pi end | — | Shield earthed at **one end only** |

**How to use the CAT5e pairs:**

| Pair | Use |
|---|---|
| Pair 1 (blue / blue-white) | A / B (data) |
| Pair 2 (orange / orange-white) | GND_ISO (both wires together): the bus reference |
| Pairs 3 and 4 | Spare, or 24 V for the controllers (§5) |
| Shield + drain wire | Continuous through every door, earthed at the Pi end only |

### 2.3 Per door (×4)

| Item | Contents | ~Price per door |
|---|---|---|
| Entrix door controller | The Rev A core: ESP32-C6, RXB61 receiver, PCF8563T RTC, relay, inputs, 12–24 V power stage, IP65 box | see §6 |
| **Isolated RS485 port** | CA-IS3082WX isolated transceiver, B0505S-1WR3 isolated DC-DC, HT7333 LDO, SM712 TVS, 2 series resistors, 120 Ω and bias jumpers, 2 × 4-pin plug-in terminals (IN / OUT) | $2.5–3.5 |
| Cable glands | 2 extra (bus IN and OUT), or one dual-hole insert | $0.5 |
| Lock power | The existing 12–24 V lock supply also powers the controller (J1) | — |
| Remotes | EV1527 or HCS301, one per user | $1–3 each |

### 2.4 Commissioning tools

* A laptop (or the Pi itself) with `mbpoll` or QModMaster to read and write Modbus registers.
* A multimeter.
* A spare USB-to-RS485 adapter, to test each door on its own before connecting the whole bus.

---

## 3. Door board: the isolated RS485 port

This replaces the optional non-isolated SP3485 block on sheet 9 of the Rev A schematic. Everything
else on the Rev A board stays the same, including the AP2112K 3.3 V regulator. The isolated
converter takes its power from the 5 V rail.

```
        board side (GND)                  ┊           bus side (GND_ISO, floating)
                                          ┊
 IO22 ──► DI ┐                            ┊
 IO23 ◄── RO ├─ CA-IS3082WX ──────────────╫──── A ──10R──┬──────────┬──── A ┐
 IO4  ──► DE/RE  (10k pull-down)          ┊     B ──10R──┼──────────┼──── B ├ IN and OUT terminals
 +3V3 ──► VCC1                            ┊              │          │       │ (+ GND_ISO, SHIELD)
                                          ┊        SM712 TVS   120 Ω + JP   ┘
 +5V ──► B0505S-1W isolated DC-DC ════════╫══► HT7333 ─► 3.3 V_ISO ─► VCC2, bias 680 Ω + JP
                                          ┊        GDT* from A/B to EARTH (*exposed runs only)
```

| Part | Value / type | Why |
|---|---|---|
| U10 | **Chipanalog CA-IS3082WX** (LCSC C970942, ~$0.7–1.0), or TI ISO3082 / Novosense NSi83085 | Half-duplex RS485 with 5 kV isolation |
| Isolated supply | **B0505S-1WR3** 5 V → 5 V 1 W, then **HT7333** → 3.3 V_ISO | The B0505S is unregulated and can exceed 6 V at light load; the LDO keeps the transceiver's supply in range |
| Line protection | SM712 TVS (A, B to GND_ISO) and two 10 Ω pulse-rated resistors (or PTCs) | Absorbs surges induced in the cable |
| Termination | 120 Ω + solder jumper | **Close only on door 4**, the end of the cable |
| Fail-safe bias | 680 Ω A → 3.3 V_ISO, 680 Ω B → GND_ISO, + jumper | Holds the bus idle when nobody transmits. **Close in one place only** (see §4) |
| Surge to earth (optional) | 3-electrode 90 V gas discharge tube (GDT) from A/B to an EARTH terminal | Only where the cable leaves the building or runs overhead |
| Terminals | 2 × 4-pin 5.08 mm plug-in terminals: A, B, GND_ISO, SHIELD (IN and OUT) | The cable loops through each door with no branch. Unplugging a door does not break the bus |

**ESP32-C6 connections** (the same pins as Rev A):

| GPIO | Signal | Notes |
|---|---|---|
| IO22 | UART1 TX → DI | |
| IO23 | UART1 RX ← RO | |
| IO4 | UART1 **RTS** → DE and /RE | `esp-modbus` switches the transceiver direction through the UART's RTS line in RS485 half-duplex mode. The 10k pull-down keeps the transceiver in receive mode during boot |

**Why isolated, even for only 4 doors:**

* The Rev A power input uses a bridge rectifier, so the board's ground is not a fixed point of the
  door's supply; with AC input it swings with the mains cycle. Connecting the grounds of four
  doors, each with its own supply, through the bus cable could short those supplies through the
  bridge diodes.
* Long outdoor cables also collect lightning surges and ground-voltage differences.

The isolated port avoids both problems for about $2 more per door.

**Door address:** set during installation from the local admin page (Bluetooth or the unit's own
hotspot) or over USB, and stored in flash. No extra hardware is needed.

---

## 4. Bus settings for your 4-door system

| Setting | Value |
|---|---|
| Wiring order | Pi adapter → door 1 IN; door 1 OUT → door 2 IN; door 2 OUT → door 3 IN; door 3 OUT → door 4 IN. Door 4 OUT stays empty. No branches |
| Termination (120 Ω) | **ON at the Pi adapter and at door 4.** OFF at doors 1–3 |
| If the Pi is in the middle of the run | Wire both cables into the adapter's terminals, turn the adapter's terminator OFF, and turn it ON at the doors at the two ends |
| Fail-safe bias | **Exactly one place.** Use the adapter if it has bias resistors; otherwise close the bias jumper on door 1 |
| Shield | Continuous through all doors; earthed at the Pi end only |
| GND_ISO | Carried on pair 2 through every door, and connected to the adapter's GND terminal |
| Speed | 19,200 baud 8E1 (the Modbus default). That works over the full 1,200 m; 38,400 baud also works for 4 doors |
| Addresses | Door 1 = 1, door 2 = 2, door 3 = 3, door 4 = 4 |

---

## 5. Powering the door controllers

* **Default: local power.** Each door already has a 12–24 V supply for its lock. Connect it to J1,
  the same as in Rev A.
* **Option: power the controllers over the cable.**
  * Put a 24 V 1 A DIN-rail supply (~$10–15) next to the Pi and send it down pairs 3 and 4, two
    wires for + and two for −.
  * Each controller draws at most about 0.1 A at 24 V. With all 4 doors at the end of a 300 m run,
    the drop is 0.4 A × 0.084 Ω/m × 300 m ≈ 10 V, which leaves ≥ 14 V at the doors. The XL7015 is
    fine with that.
  * The controllers then keep running even if a lock's supply fails.
  * **The locks still need their local supply**: their current is too high for this cable over
    distance.

---

## 6. Cost for your 4-door system

With only 4 doors, building from ready-made modules costs about the same as a small batch of custom
boards and is quicker:

| | **Module build** (no custom PCB) | **Custom PCB** (batch of 5 boards) |
|---|---|---|
| Per door | ESP32-C6 DevKit $5–9, RXB61 $1–2, relay module $1, RTC module $1–2, **isolated TTL-to-RS485 module** $4–8 (3.3 V logic, with a DE pin or automatic direction), XL7015 buck module $1.5, IP65 box + glands $5, terminals and wiring $3 → **$22–35** | Rev A board + isolated RS485 port, small-batch assembly → **$30–45** (falls to ~$13–16 at 100 pcs) |
| 4 doors | **$90–140** | **$120–180** |
| Pi side | Isolated USB-RS485 $10–25, PSU $8–10, SD $8–12, DS3231 $2–5, case $5–10 (+ UPS HAT $15–30) → **$35–60** (+UPS) | same |
| Cable | Route length × $0.3–0.6/m | same |
| Remotes | $1–3 per user | same |

**Total, excluding the Pi you already own and the cable: about $130–200 for 4 doors.**

---

## 7. Modbus RTU (recommended) instead of a raw protocol

Modbus RTU already gives you addressing, framing and a CRC-16 check. It also has free tools for
testing (`mbpoll`, QModMaster) and ready-made libraries on both ends:

* **Raspberry Pi:** Python `pymodbus` or `minimalmodbus`, or C `libmodbus`. Run the poller as a
  systemd service, with SQLite for the database and a small Flask/FastAPI app for the admin web UI.
* **ESP32-C6:** Espressif's `esp-modbus` component, in RTU slave mode with RS485 half-duplex.

A raw protocol would work too, but you would have to build all of that yourself.

**Example register map** (Modbus registers are 16 bits wide):

| Type | Address | Contents |
|---|---|---|
| Input registers | 0–9 | Status: firmware version, door contact, tamper, relay state, power-cut counter, newest log sequence number |
| Holding register | 20–21 | Log sequence number the Pi wants to read |
| Input registers | 100–115 | That log record (32 bytes = 16 registers) |
| Holding registers | 0–2 | Set time (32-bit Unix time) + apply |
| Holding registers | 10–11 | User-list version number |
| Holding registers | 200–235 | User record buffer (64 bytes = 32 registers) + record index + action (add / update / delete / disable / disable-until) |
| Holding registers | 300–315 | Authenticated command block: counter + command (e.g. remote open) + signature |

**Polling:** the Pi asks each door "anything new since log record N?" about 4 times per second
across the bus. New events then reach the central log within about a second.

**Security, because the cable runs outdoors:** Modbus has no authentication, and anyone who can
reach the cable could send commands. So:

1. Each door decides access **locally**. Normal operation never needs the bus to open a door.
2. Every write that changes users, or that opens a door remotely, carries a counter and an
   **HMAC-SHA256 signature** made with a per-door secret key. The key is set over USB or Bluetooth
   at installation. The door rejects any write with a wrong signature or an old counter. The
   ESP32-C6 has SHA hardware, and Python's `hmac` module does the same on the Pi.
3. Run the cable in conduit wherever people can reach it.

---

## 8. Installation and commissioning checklist

1. Before mounting, set each door's address (1–4) and the bus speed. Test each door alone with the
   spare USB adapter: `mbpoll -m rtu -a 1 -b 19200 -P even -t 3 -r 1 -c 10 /dev/ttyUSB0`.
2. Pull the cable as one daisy chain: Pi → door 1 → door 2 → door 3 → door 4.
3. Set the jumpers: terminator ON at the adapter and door 4; bias in one place only.
4. Connect GND_ISO (pair 2) through all doors; earth the shield at the Pi end only.
5. From the Pi, read the status registers of addresses 1–4 and check that all four answer.
6. **Offline test:** unplug the adapter from the Pi. All doors must keep opening for valid remotes
   and keep logging. Plug it back in and check that the Pi collects the missed log records.

## 9. Next steps

1. **Bench prototype:** a Pi 3, the isolated USB-RS485 adapter, and two ESP32-C6 DevKits with
   isolated TTL-to-RS485 modules on a 100–300 m cable drum. Firmware: `esp-modbus` slave with the
   register map in §7. Pi: `pymodbus` poller.
2. **Rev B schematic:** the Rev A schematic with sheet 9 replaced by the isolated RS485 port (§3).
3. **Pi software:** poller service, user database, admin web UI, HMAC-signed writes.
