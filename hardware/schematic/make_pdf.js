// Combine the schematic sheets (sheets/*.svg) into one A3 PDF with a cover page.
// Usage: node make_pdf.js        (needs the `playwright` package and Chromium)
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const dir = __dirname;
const out = path.join(dir, 'entrix-schematic-revA.pdf');
const sheets = fs.readdirSync(path.join(dir, 'sheets')).filter(f => f.endsWith('.svg')).sort();

const TITLES = [
  'Power input and regulators', 'Microcontroller ESP32-C6', 'USB-C and programming header',
  '433 MHz receiver RXB61', 'Real-time clock and memory', 'Relay outputs',
  'Door, exit-button and tamper inputs', 'LEDs and buzzer', 'Expansion header and RS485 (optional)',
];

const gpio = [
  ['IO0', '8', 'VSENSE', 'Input-voltage sense (ADC), power-fail detection'],
  ['IO1', '9', 'RF_DATA', '433 MHz receiver data (via 10k/20k divider)'],
  ['IO2', '27', 'RELAY1', 'Relay 1 driver (Q1)'],
  ['IO3', '26', 'RELAY2', 'Relay 2 driver (Q2, optional)'],
  ['IO4', '4', 'EXP_IO4', 'RS485 DE/RE or LoRa M0 (10k pull-down)'],
  ['IO5', '5', 'EXP_IO5', 'LoRa M1 (expansion)'],
  ['IO6', '6', 'I2C_SDA', 'RTC (+ optional FRAM)'],
  ['IO7', '7', 'I2C_SCL', 'RTC (+ optional FRAM)'],
  ['IO8', '10', 'IO8_STRAP', 'Strapping pin, 10k pull-up'],
  ['IO9', '15', 'BOOT', 'SETUP / BOOT button'],
  ['IO10', '11', 'IN_DOOR', 'Door contact (opto)'],
  ['IO11', '12', 'IN_EXIT', 'Exit button (opto)'],
  ['IO12 / IO13', '13 / 14', 'USB_DN / USB_DP', 'USB-C (flashing, debugging)'],
  ['IO15', '23', '-', 'Strapping pin, left open'],
  ['IO16 / IO17', '25 / 24', 'UART0_TX / RX', 'Debug console, header J2'],
  ['IO18', '16', 'IN_TAMPER', 'Lid tamper switch'],
  ['IO19', '17', 'LED_GRN', 'Green LED'],
  ['IO20', '18', 'LED_RED', 'Red LED'],
  ['IO21', '19', 'BUZZER', 'Buzzer driver (Q3)'],
  ['IO22 / IO23', '20 / 21', 'UART1_TX / RX', 'RS485 or LoRa module (optional)'],
];

const cover = `
<section class="page cover">
  <h1>ENTRIX door controller &mdash; schematic</h1>
  <p class="sub">Rev A (draft) &middot; 2026-11-01 &middot; status: design proposal, not yet built or tested</p>
  <div class="cols">
    <div>
      <h2>Sheets</h2>
      <ol>${TITLES.map(t => `<li>${t}</li>`).join('')}</ol>
      <h2>Main parts</h2>
      <ul>
        <li><b>U3</b> ESP32-C6-WROOM-1-N8: BLE 5 + Zigbee (802.15.4) + Wi-Fi 6, 8 MB flash</li>
        <li><b>U5</b> RXB61 433.92 MHz superheterodyne receiver (RXB6 / RXB12 also fit electrically)</li>
        <li><b>U1</b> XL7015E1 80 V buck &rarr; 5 V; <b>U2</b> AP2112K-3.3 LDO &rarr; 3.3 V</li>
        <li><b>U6</b> PCF8563T RTC (SO-8) + BR2032 backup cell</li>
        <li><b>K1</b> 5 V relay, 10 A, NO/COM/NC dry contact</li>
        <li><b>U8, U9</b> PC817 inputs for door contact and exit button; tamper switch on J8</li>
      </ul>
      <h2>Connectors</h2>
      <ul>
        <li><b>J1</b> power 12&ndash;24 V AC/DC &middot; <b>J5</b> relay 1 (COM/NC/NO) &middot; <b>J7</b> inputs (DOOR/EXIT/COM)</li>
        <li><b>J8</b> tamper &middot; <b>J3</b> USB-C (service) &middot; <b>E1/J4</b> 433 MHz antenna</li>
        <li>Optional (DNP): <b>J2</b> UART header, <b>J6</b> relay 2, <b>J9</b> expansion, <b>J10</b> RS485</li>
      </ul>
      <h2>Before PCB layout, verify</h2>
      <ul>
        <li>RXB61 pin order and SHUT polarity on the actual module (no official datasheet found).</li>
        <li>ESP32-C6-WROOM-1 pin numbers against the current Espressif datasheet.</li>
        <li>XL7015 pin-out, C5 (CFF) and inductor value against the XLSEMI datasheet revision you buy.</li>
      </ul>
    </div>
    <div>
      <h2>ESP32-C6 pin map</h2>
      <table>
        <tr><th>GPIO</th><th>Module pin</th><th>Net</th><th>Use</th></tr>
        ${gpio.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}
      </table>
      <p class="small">Grey parts on the sheets are DNP (not fitted on the standard build). Netlist and BOM: netlist.md, bom.csv.</p>
    </div>
  </div>
</section>`;

const pages = sheets.map(s => {
  const svg = fs.readFileSync(path.join(dir, 'sheets', s)).toString('base64');
  return `<section class="page sheet"><img src="data:image/svg+xml;base64,${svg}"></section>`;
}).join('\n');

const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  @page { size: A3 landscape; margin: 8mm; }
  body { margin: 0; font-family: Helvetica, Arial, sans-serif; color: #111; }
  .page { width: 404mm; height: 281mm; page-break-after: always; box-sizing: border-box; }
  .sheet { display: flex; align-items: center; justify-content: center; }
  .sheet img { max-width: 100%; max-height: 100%; }
  .cover { padding: 12mm 16mm; border: 1.5px solid #000; }
  h1 { font-size: 30px; margin: 0 0 4px; }
  .sub { color: #555; margin: 0 0 18px; font-size: 15px; }
  h2 { font-size: 18px; margin: 18px 0 6px; }
  li { font-size: 14px; margin: 3px 0; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 18mm; }
  table { border-collapse: collapse; font-size: 13px; width: 100%; }
  td, th { border: 1px solid #999; padding: 3px 6px; text-align: left; }
  th { background: #eee; }
  .small { font-size: 12px; color: #555; }
</style></head><body>${cover}${pages}</body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: 'load' });
  await page.pdf({ path: out, format: 'A3', landscape: true, printBackground: true });
  await browser.close();
  console.log('wrote', out);
})();
