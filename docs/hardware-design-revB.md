# Entrix — Hardware Design Rev B: wired versions (draft)

> **Status:** proposal for review. Rev B adds wired connections, RS485 or Ethernet, to the Rev A
> door controller ([hardware-design.md](hardware-design.md)).
> Prices are approximate 2025–26 LCSC / AliExpress prices for about 100 pieces; check them before
> ordering.

---

## 1. Summary

Rev B is **one PCB with two wired interfaces**, and you fit only what each door needs:

| Variant | Fitted | Use it when |
|---|---|---|
| **B-R** (RS485) | Isolated RS485 port | Doors are spread out, or more than about 100 m from any network switch. One cable runs past every door (up to 1,200 m) |
| **B-E** (Ethernet) | Ethernet port + optional PoE | Each door is within 100 m of a network switch. One cable per door carries data **and power** (PoE) |
| **B-G** (gateway) | Both | One unit where the network is (office, guard house). It bridges the LAN to the RS485 bus and is also a normal door controller |

The Rev A core stays: the ESP32-C6 module, the RXB61 433 MHz receiver, the PCF8563T RTC, the
relays, the inputs, the power input stage and the IP65 box. Firmware, enclosure and wiring are
shared across all variants. Bluetooth stays available as a local fallback admin interface if the
cable is ever cut.

**My recommendation:**

* Your doors are far from any network ("too far from any communication line"), so **RS485 (B-R) is
  probably the main product**. Run one cable past all doors and put **one B-G gateway** where the
  network is.
* Use **Ethernet + PoE (B-E)** for doors close to a building that has a switch. PoE can also power
  the lock, so the door needs no power supply at all.

---

## 2. The two wired options compared

| | **RS485** | **Ethernet** |
|---|---|---|
| Distance | Up to **1,200 m** per bus with no repeaters (at ≤ ~100 kbit/s) | **100 m** per cable, from switch to door |
| Topology | **Daisy chain**: one cable goes from door to door | **Star**: one cable from each door back to a switch |
| Cable | 1 twisted pair + reference wire (outdoor shielded CAT5e works) | Outdoor CAT5e/CAT6, one per door |
| Power on the same cable | Possible for the controller (spare pair, 24 V); not for the locks over long runs | **PoE**: 13 W (802.3af) or 25 W (802.3at), enough for the controller **and** most locks |
| Extra parts per door | ~$2.5–3.5 (isolated) | ~$3.5–5 without PoE, plus $4–8 for PoE |
| Head-end (office) | Gateway (B-G) or an isolated USB-RS485 adapter + PC/Raspberry Pi | Any switch (a PoE switch for power) + a PC/Raspberry Pi server, or no server |
| Speed | 38.4–115.2 kbit/s: a 1,000-user list takes a few seconds per door | 10/100 Mbit/s |
| Software | Master polls each door. Protocol: OSDP with Secure Channel (see §3.6) | Standard TCP/IP: HTTPS web UI per door, MQTT, network time, OTA updates |
| One cable fault affects | Possibly the whole bus (limited by isolation and protection) | One door only |
| Lightning / earth problems | Need isolation and surge protection (included in B-R) | Transformers in the Ethernet jack give 1,500 V isolation; add a surge protector for runs between buildings |

**How to choose:**

```
Is every door within 100 m (cable length) of a network switch that can be powered?
 ├─ yes ─► Ethernet + PoE (B-E)
 └─ no  ─► Are several doors along one route (fence line, car park, building row)?
           ├─ yes ─► RS485 daisy chain (B-R) + one gateway (B-G) at the network
           └─ mixed ─► B-E near the buildings, B-G at the network edge, B-R for the far doors
```

---

## 3. Solution 1: RS485 bus (variant B-R)

### 3.1 Topology

```
 Office / guard house                                         up to 1,200 m total
 ┌──────────────┐ LAN  ┌──────────┐  RS485 (A, B, GND_ISO, shield)
 │ PC / RPi     ├──────┤  B-G     ├────────────┬───────────────┬────────────── ... ──┐
 │ admin server │      │ gateway  │            │               │                     │
 └──────────────┘      │ + door 1 │       ┌────┴────┐     ┌────┴────┐           ┌────┴────┐
                       └──────────┘       │ B-R     │     │ B-R     │           │ B-R     │
                    120 Ω termination ON  │ door 2  │     │ door 3  │           │ door N  │
                    fail-safe bias ON     └─────────┘     └─────────┘           └─────────┘
                                          (terminals IN/OUT: no stubs)   120 Ω termination ON
```

* **One master** (the gateway) polls the doors. Each door has an address from 1 to 126.
* **Each door keeps working on its own** with its local user list and log if the bus or gateway
  fails. The bus is only used to sync users and logs, and for remote commands.
* Doors keep their **local power** (they already have it for the lock). A spare cable pair can carry
  24 V for the controller alone, but the voltage drop is too large for locks over long runs. For
  example, 300 m of CAT5e at 0.5 A loses about 12 V.

### 3.2 Why the RS485 port must be isolated

RS485 needs a common reference wire between all nodes. In this project that is dangerous without
isolation:

1. **The Rev A power input has a bridge rectifier**, so board ground is not tied to a fixed point of
   the door's supply. With AC input it swings with the AC waveform. Joining the grounds of several
   doors through the cable could short their supplies through the bridge diodes.
2. **Long outdoor cables** between different power systems and earth points pick up ground
   differences and lightning surges that destroy normal (non-isolated) transceivers.

An **isolated transceiver** gives the bus its own floating ground (GND_ISO), separate from every
door's power wiring. It costs about $2 more per door and avoids both problems.

### 3.3 Hardware (bus side added to the Rev A core)

```
        board side (GND)                  ┊           bus side (GND_ISO, floating)
                                          ┊
 IO22 ──► DI ┐                            ┊
 IO23 ◄── RO ├─ CA-IS3082WX ──────────────╫──── A ──PTC──┬──────────┬──── A ┐
 IO4  ──► DE/RE  (10k pull-down)          ┊     B ──PTC──┼──────────┼──── B ├ IN and OUT terminals
 +3V3 ──► VCC1                            ┊              │          │       │ (+ GND_ISO, SHIELD)
                                          ┊        SM712 TVS   120 Ω + JP   ┘
 +5V ──► B0505S-1W isolated DC-DC ════════╫══► HT7333 ─► 3.3 V_ISO ─► VCC2, bias 680 Ω + JP
                                          ┊        GDT* from A/B to EARTH (*exposed runs only)
```

| Block | Part | ~Price | Notes |
|---|---|---|---|
| Isolated transceiver | **Chipanalog CA-IS3082WX** (LCSC C970942) | $0.7–1.0 | Half-duplex, 5 kV RMS isolation, 3.3 V logic. Alternatives: TI ISO3082, Novosense NSi83085, HopeRF CMT83085 |
| Isolated supply | **B0505S-1WR3** (5 V → 5 V, 1 W) + **HT7333** LDO → 3.3 V_ISO | $0.5–1.0 | The B0505S is unregulated and can rise above 6 V at light load; the LDO keeps VCC2 in range |
| One-chip alternative | CA-IS3092W (transceiver + isolated DC-DC in one package) | higher | Fewer parts, more expensive; check the price |
| Surge protection | SM712 TVS, 2 series PTCs (or 10 Ω pulse resistors), optional 3-electrode 90 V GDT to an EARTH terminal | $0.3–0.8 | GDT is needed when the cable runs between buildings or is exposed (overhead, long buried runs) |
| Termination | 120 Ω + solder jumper | $0.02 | Close only on the **two units at the cable ends** |
| Fail-safe bias | 680 Ω A→3.3 V_ISO, 680 Ω B→GND_ISO + jumper | $0.02 | Close on **one** unit only (normally the gateway). It holds the bus idle when nobody transmits |
| Terminals | 2 × 4-pin pluggable (IN, OUT): A, B, GND_ISO, SHIELD | $0.4–0.6 | Two sets so the cable loops through each door with no stub; you can unplug a door without breaking the bus |

**Added cost per door: about $2.5–3.5.**

### 3.4 Cable and installation

* **Cable:** outdoor-rated shielded twisted pair, 120 Ω (e.g. Belden 3106A), or **outdoor shielded
  CAT5e** (PE jacket, or gel-filled for direct burial). CAT5e's 100 Ω is close enough:
  * Pair 1 → A / B.
  * Pair 2 → GND_ISO (both wires).
  * Pairs 3–4 → spare (24 V for the controller, if wanted).
  * Shield → continuous through every door, earthed **at one end only** (the gateway).
* **Speed:** 38,400 baud by default, which is fine for the full 1,200 m. Use 115,200 baud for runs up
  to ~500 m. Rule of thumb: bit rate × length ≤ 10⁸.
* **Number of doors:** at least 32 per bus (standard unit loads; check the CA-IS3082WX unit-load
  rating for more).
* **Wiring rules:** daisy chain only (no star or T-branches), terminate both ends, bias once, keep
  the cable in conduit where it can be damaged.

### 3.5 Head-end options

| Option | Hardware | ~Price | Notes |
|---|---|---|---|
| **B-G gateway** (recommended) | Rev B board with Ethernet + RS485 fitted | ~$22–28 | Also a door controller. Hosts the central web UI, or forwards to a server over the LAN |
| PC / Raspberry Pi | Isolated USB-RS485 adapter + RPi 4/5 or any PC | $10–25 + computer | The admin server runs on the computer and talks to the bus directly |

### 3.6 Protocol and security

* The bus runs **outdoors where anyone can tap it**. Never accept an unauthenticated "open door"
  command from the bus.
* Recommended: **OSDP** (Open Supervised Device Protocol, SIA / IEC 60839-11-5). It is the industry
  standard for access control over RS485: multi-drop addressing, polling, and **Secure Channel with
  AES-128**. The open-source `libosdp` library (C, Apache-2.0) handles framing and encryption.
  Entrix-specific commands (user-list sync, log upload, time set) go in OSDP's manufacturer-specific
  messages.
  * Bonus: an Entrix unit could also act as a standard OSDP device for a commercial access-control
    panel, reporting each remote press like a card read.
* Simpler alternative: Modbus RTU framing with an AES-CCM-encrypted payload and a message counter
  (the ESP32-C6 has AES hardware). It is easier to debug with standard tools, but the security has
  to be built by hand.
* **Sync model:** the server holds the master user list. Each door keeps its own copy, which carries
  a version number. The gateway sends only the changes, and pulls new log records at every poll.

---

## 4. Solution 2: Ethernet + PoE (variant B-E)

### 4.1 Topology

```
  Office                                 ≤ 100 m per cable
 ┌──────────────┐    ┌──────────────┐ ── CAT5e ──► Entrix B-E door 1  (PoE powers controller + lock)
 │ PC / RPi     ├────┤ PoE switch   │ ── CAT5e ──► Entrix B-E door 2
 │ admin server │    │ 802.3af/at   │ ── CAT5e ──► Entrix B-E door 3
 └──────────────┘    └──────────────┘ ── ... more than 100 m: PoE extender, fibre, or use RS485
```

* Each door is a normal network device: DHCP or static IP, its own **HTTPS web page** (the same UI
  as the Rev A hotspot, now over the LAN), **MQTT over TLS** to a central server for logs and user
  updates, network time (SNTP), and firmware updates over the network.
* As with RS485, each door keeps working from its local user list if the network is down. The RTC
  keeps time until network time returns.

### 4.2 Ethernet controller: keep the ESP32-C6 and add an SPI Ethernet chip

The ESP32-C6 has no built-in Ethernet MAC, so an SPI Ethernet chip is added. This keeps the same
module, pin map and firmware base as Rev A.

| Option | ~Price | ESP-IDF support | Verdict |
|---|---|---|---|
| **WIZnet W5500** (LQFP-48, LCSC C32843) | $1.8–2.5 | Espressif `w5500` driver | **Recommended for Rev B**: most widely used, best documented, easiest to debug |
| WCH CH390H (SPI, built-in MAC + PHY) | lower than W5500 (check LCSC) | Espressif component `espressif/ch390` (CH390H/D) | Cost-down candidate. Test it on a dev board first; different footprint |
| Davicom DM9051 | ~$1–1.5 | Espressif driver | Alternative |
| Classic ESP32 (WROOM-32E) + LAN8720A RMII PHY | saves ~$1.5–2 overall | Built-in MAC | Cheapest Ethernet, but different module and firmware, no Zigbee, BLE 4.2 only, and the PHY uses ~10 GPIOs. Not recommended while Rev A and Rev B share firmware |

> The ESP32-C3 (cheaper) does **not** have enough GPIOs for the gateway variant (RS485 + Ethernet +
> relays + inputs), so Rev B stays on the C6.

**Ethernet block parts:** W5500, 25 MHz crystal, RJ45 jack with integrated transformers (magjack),
a low-capacitance TVS array on the W5500 side of the transformers, and the W5500's link/activity
LEDs. Added cost: **about $3.5–5** without PoE.

**Getting the cable into an outdoor box:** use an **IP67 RJ45 cable gland** (split seal, so a
crimped plug passes through, ~$1–2). The RJ45 jack stays inside the dry box. Do not fit an RJ45
socket on the outside of the box.

### 4.3 PoE: one cable for data and power

802.3af PoE delivers 12.95 W at the device. After an isolated 12 V converter, that leaves about
10–11 W, roughly 0.85 A at 12 V. The controller uses ~2 W; the rest (~8 W, 0.65 A at 12 V)
powers most **electric strikes and maglocks (typically 0.2–0.5 A at 12 V)** through the relay. For
bigger locks, use 802.3at (25.5 W).

| Option | ~Price | Notes |
|---|---|---|
| **A. External PoE splitter** (802.3af/at → 12 V) inside the box, feeding J1 | $4–8 | Zero design risk. The board gets data only, through a standard magjack. **Use this for the first batch** |
| **B. On-board isolated PoE module**: SDAPO PM1201 (12 V, 13 W, isolated, 37–57 V in) or SDAPO DP9900LP-12V (802.3af, 1,500 V isolation), both on LCSC | $4–8 (check) | Needs a PoE-rated magjack (centre taps brought out). The 12 V output is diode-OR'ed into the existing input stage, so the rest of the board is unchanged |
| C. Discrete PoE: Skyworks Si3404 (PD + DC-DC + hot-swap in one chip, isolated flyback reference designs for 5 V/12 V) or TI TPS23753A | $3–5 | Cheapest in volume, but a flyback transformer design. Later cost-down |
| Passive 24 V "PoE" on spare pairs | ~$2 injector | **Not recommended**: non-standard, and can burn standard network equipment if plugged in by mistake |

> **Isolation is mandatory:** 802.3 requires 1,500 V isolation between the PoE port and every other
> external conductor (relay terminals, input terminals, J1). All options A–C above are isolated.
> Do not use a non-isolated PoE converter on this board.

### 4.4 Distance beyond 100 m

| Method | ~Price | Notes |
|---|---|---|
| PoE extender / repeater | $15–30 per hop | Powered by PoE itself, adds 100 m per hop (usually up to 3–4 hops) |
| Fibre + media converters | $20–40 per pair | Immune to lightning; needs power at the far end |
| 10BASE-T1L (single-pair Ethernet, 1 km) | high today | PHYs are ~$5–10 and the head-end needs T1L switches. Interesting later, not cheap yet |
| **RS485 for those doors** | ~$3 per door | Usually the cheapest answer: put a B-G gateway at the last Ethernet point |

---

## 5. Rev B board: changes from Rev A

### 5.1 Block diagram

```
                 ┌───────────────────────────── Entrix Rev B ──────────────────────────────┐
 RJ45 ═══════════╪═► magjack ─► W5500 ─── SPI ──────────► ┌────────────┐                   │
  PoE pairs ─────╪─► PoE module ─► 12 V ─► VRECT          │            │ ◄─ RXB61 433 MHz  │
 J1 12-24 V ─────╪─► fuse ─► bridge ─────► VRECT          │  ESP32-C6  │ ◄─ PCF8563T RTC   │
                 │   VRECT ─► XL7015 5 V ─► buck 3.3 V    │ (BLE kept) │ ─► relays K1, K2  │
 RS485 IN/OUT ═══╪═► protection ─► CA-IS3082WX ─ UART ──► │            │ ◄─ inputs, tamper │
  (isolated)     │   (GND_ISO, B0505S isolated supply)    └────────────┘ ─► LEDs, buzzer   │
                 └─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 What changes compared with Rev A

| Area | Rev A | Rev B |
|---|---|---|
| Wired interface | Optional non-isolated SP3485 (DNP) | **Isolated RS485** (B-R, B-G) and/or **W5500 Ethernet** (B-E, B-G), with optional PoE |
| 3.3 V regulator | AP2112K LDO | **SY8089A (or TLV62569) 5 V → 3.3 V synchronous buck**. The W5500 adds ~130 mA, and an LDO in SOT-23-5 would get too hot |
| Input TVS | SMBJ40A | Unchanged. The PoE module output is 12 V, after its own isolation |
| UART0 header J2 | Fitted as DNP | **Removed**: IO16/IO17 become Ethernet SPI. Flashing and the console use USB-C (built-in USB-Serial-JTAG) |
| Expansion header J9 / LoRa | Optional | **Removed**: its pins are used by RS485 and Ethernet |
| FRAM U7 | Optional | Unchanged (optional) |
| Radios | BLE + Zigbee + Wi-Fi in use | **BLE kept** as the local fallback admin interface. Zigbee and Wi-Fi not used (no extra cost: they are in the chip) |
| Enclosure | 2 cable glands | + 1 IP67 RJ45 gland (B-E/B-G) or + 1 gland for the RS485 cable (B-R; IN and OUT can share a dual-hole insert) |

### 5.3 Pin map changes (everything else as Rev A)

| GPIO | Rev A | Rev B | Notes |
|---|---|---|---|
| IO4 | EXP_IO4 (RS485 DE / LoRa M0) | **RS485_DE** | 10 kΩ pull-down: receive by default |
| IO5 | EXP_IO5 | **ETH_MISO** | |
| IO8 | Strap, 10 kΩ pull-up | **ETH_CS** | The pull-up keeps CS inactive during boot and keeps download mode working |
| IO15 | Strap, open | **ETH_INT** | W5500 INTn is active-low with a pull-up. The driver can also poll without it |
| IO16 | UART0_TX (J2) | **ETH_SCLK** | ROM boot messages toggle this pin while CS is high; the W5500 ignores them |
| IO17 | UART0_RX (J2) | **ETH_MOSI** | |
| IO22 | UART1_TX | **RS485_TX** (DI) | |
| IO23 | UART1_RX | **RS485_RX** (RO) | |
| — | — | W5500 RSTn ← EN | Resets with the ESP32 (SW1 / power-up) |

The SPI runs through the ESP32-C6 GPIO matrix at 20–26 MHz, which is plenty for access-control
traffic.

---

## 6. Cost per door (about 100 pcs, approximate)

| Version | Added to the Rev A core | Board + box per door | Infrastructure |
|---|---|---|---|
| Rev A (wireless) | — | ~$11–13 | Optional Zigbee gateway |
| **B-R** RS485 | Isolated RS485 block ~$2.5–3.5, 3.3 V buck ~$0.2 | **~$13–16** | One cable run past all doors (~$0.3–0.6/m outdoor STP), one gateway per site |
| **B-E** Ethernet, local power | W5500 + magjack + RJ45 gland ~$3.5–5 | **~$15–18** | Cable per door, switch port |
| **B-E** Ethernet + PoE | + PoE module or splitter $4–8 | **~$19–25** | PoE switch (~$30–60 for 4–8 ports). No power supply needed at the door, which saves the lock PSU |
| **B-G** gateway | Both blocks | ~$22–28 | One per site |

---

## 7. Open questions

| Question | Why it matters |
|---|---|
| Cable distances: door to door, and from the nearest door to the nearest network switch | Decides RS485 or Ethernet, and whether PoE extenders are needed |
| Do the cables run between buildings, overhead, or buried? | Decides whether the GDT/earth surge stage and gel-filled cable are needed |
| Is there power at every door, and of what type? | With Ethernet, PoE could replace the local lock supply |
| How many doors per site? | RS485 supports at least 32 per bus; more needs a second bus or higher-impedance transceivers |
| Must commercial access panels work with Entrix? | If yes, OSDP is the clear protocol choice for RS485 |

## 8. Next steps

1. **Bench test both interfaces** on dev boards:
   * ESP32-C6 DevKit + W5500 module + USB PoE splitter.
   * ESP32-C6 DevKit + isolated RS485 module + 300 m of cable on a drum.
   * Run `libosdp` with Secure Channel across the RS485 link.
2. **Rev B schematic:** start from the Rev A schematic and replace sheet 9 (expansion) with
   "RS485 (isolated)" and "Ethernet + PoE". The 3.3 V regulator changes on sheet 1.
3. **Gateway firmware:** LAN ↔ RS485 bridge, central web UI, user-list sync and log collection.
4. **Field test** one B-G gateway and two B-R doors on a real cable run before ordering a batch.
