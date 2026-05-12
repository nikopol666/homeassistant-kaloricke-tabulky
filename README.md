# Kaloricke Tabulky Home Assistant integration

<img src="custom_components/kaloricke_tabulky/brand/logo.png" alt="Kaloricke Tabulky" width="260">

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=nikopol666&repository=homeassistant-kaloricke-tabulky&category=integration)

## English

Home Assistant custom integration for Kaloricke Tabulky.

### What it does

- Adds Kaloricke Tabulky through the Home Assistant UI.
- Asks for your email and password in the integration setup form.
- Creates sensors for weight, nutrition, water intake, activity energy and
  daily energy balance.
- Adds a `kaloricke_tabulky.record_weight` action for recording body weight.
- Refreshes sensors every 240 minutes by default. This is intentionally gentle
  because the Kaloricke Tabulky API used by this integration is unofficial.
- Refreshes the sensor immediately after the `record_weight` action succeeds.

You can change the refresh interval in the integration options. The minimum is
15 minutes.

### Sensors

The integration creates stable sensors for the useful values currently returned
by the Kaloricke Tabulky diary and weight endpoints.

| Sensor | Unit | Source |
| --- | --- | --- |
| Latest weight | kg | Latest record from the monthly weight endpoint |
| Energy | kcal | Daily intake total |
| Water | l | Drinking regime / water intake |
| Body weight | kg | Weight value in the daily diary summary |
| Protein | g | Daily protein total |
| Carbohydrates | g | Daily carbohydrate total |
| Fat | g | Daily fat total |
| Fiber | g | Daily fiber total |
| Sugar | g | Daily sugar total |
| Salt | g | Daily salt total |
| Activity energy | kcal | Energy from activities |
| Activity level energy | kcal | Activity level energy from the balance block |
| Energy output total | kcal | Total daily energy output |
| Maintenance intake | kcal | Maintenance energy intake |
| Energy deficit | kcal | Deficit or surplus reported by Kaloricke Tabulky |
| Energy target | kcal | Daily energy target |
| Basal metabolism | kcal | Basal metabolism |
| Energy remaining | kcal | Remaining energy intake |

Summary sensors expose these attributes when the API returns them:

- `goal`: the configured target for the metric.
- `percent`: current progress against the target.
- `source_key`: the raw metric key used by the API response.

`Latest weight` also exposes the latest date and the recent monthly weight
records as attributes.

When Kaloricke Tabulky starts returning another numeric metric with a clear
unit, the integration can expose it as an additional dynamic sensor.

### Lovelace nutrient card example

The Kaloricke Tabulky web app does not use one universal color rule for every
nutrient. For example, low sugar can be good, while low fiber is not. This
example uses the same tolerance model as the web diary gauges:

- orange: below the green range.
- green: inside the metric-specific target range.
- red: above the green range.

Replace the entity IDs with your own sensor IDs.
Set `KT_MODE` to match the diary summary mode returned by Kaloricke Tabulky.
The example uses `1`, which is the mode seen in the captured demo payload.

```yaml
type: custom:button-card
entity: sensor.tom_protein_2
show_name: false
show_icon: false
show_state: false
show_label: true
label: |
  [[[
    const NUTRIENTS = [
      { label: 'Protein',       entity: 'sensor.tom_protein_2',     key: 'protein' },
      { label: 'Carbohydrates', entity: 'sensor.tom_carbohydrates', key: 'carbohydrate' },
      { label: 'Fat',           entity: 'sensor.tom_fat',           key: 'fat' },
      { label: 'Fiber',         entity: 'sensor.tom_fiber',         key: 'fiber' },
      { label: 'Sugar',         entity: 'sensor.tom_sugar',         key: 'sugar' },
      { label: 'Salt',          entity: 'sensor.tom_salt',          key: 'salt' },
    ];

    const KT_MODE = 1;

    const THRESHOLDS = {
      0: {
        protein:      { low: 20,  high: 20 },
        carbohydrate: { low: 20,  high: 20 },
        fat:          { low: 20,  high: 20 },
        fiber:        { low: 20,  high: 30 },
        sugar:        { low: 100, high: 10 },
        salt:         { low: 40,  high: 80 },
      },
      1: {
        protein:      { low: 10,  high: 20 },
        carbohydrate: { low: 30,  high: 15 },
        fat:          { low: 30,  high: 15 },
        fiber:        { low: 20,  high: 30 },
        sugar:        { low: 100, high: 15 },
        salt:         { low: 40,  high: 80 },
      },
      2: {
        protein:      { low: 20,  high: 30 },
        carbohydrate: { low: 20,  high: 30 },
        fat:          { low: 30,  high: 20 },
        fiber:        { low: 20,  high: 30 },
        sugar:        { low: 100, high: 20 },
        salt:         { low: 40,  high: 80 },
      },
    };

    function parseKtNumber(value) {
      if (typeof value === 'number') return value;
      if (typeof value !== 'string') return NaN;
      return Number(value.replace(/\s/g, '').replace(',', '.'));
    }

    function percent(state) {
      const attrPercent = parseKtNumber(state.attributes.percent);
      if (Number.isFinite(attrPercent)) return Math.round(attrPercent);

      const value = parseKtNumber(state.state);
      const goal = parseKtNumber(state.attributes.goal);
      return Number.isFinite(goal) && goal > 0 ? Math.round((value / goal) * 100) : NaN;
    }

    function color(pct, key) {
      if (!Number.isFinite(pct)) return '#FF8040';
      const t = (THRESHOLDS[KT_MODE] || THRESHOLDS[0])[key] || { low: 20, high: 20 };
      if (pct < 100 - t.low) return '#FF8040';
      if (pct > 100 + t.high) return '#DD4B39';
      return '#99cc33';
    }

    function ring(pct, key, size) {
      const r = 34;
      const circ = 2 * Math.PI * r;
      const p = Number.isFinite(pct) ? Math.min(Math.max(pct, 0), 100) : 0;
      const dash = (p / 100) * circ;
      const c = color(pct, key);
      return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#e0e3e5" stroke-width="7"/>
        <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${c}" stroke-width="7"
          stroke-dasharray="${dash} ${circ}" stroke-linecap="round"
          transform="rotate(-90 ${size / 2} ${size / 2})"/>
        <text x="50%" y="55%" text-anchor="middle" fill="${c}" font-size="13" font-weight="bold">
          ${Number.isFinite(pct) ? pct + '%' : '?'}
        </text>
      </svg>`;
    }

    function tile(item) {
      const s = states[item.entity];
      if (!s) {
        return `<div style="width:33%;text-align:center;color:#e53935;padding:4px;font-size:11px">${item.label}<br>not found</div>`;
      }
      const value = parseKtNumber(s.state);
      const goal = parseKtNumber(s.attributes.goal);
      const pct = percent(s);
      const c = color(pct, item.key);
      const unit = s.attributes.unit_of_measurement || 'g';
      const fmt = v => Number.isFinite(v) ? (v % 1 === 0 ? v : v.toFixed(1)) : '?';
      return `<div style="width:33%;display:flex;flex-direction:column;align-items:center;padding:6px 0">
        <div style="font-weight:600;font-size:13px;margin-bottom:2px">${item.label}</div>
        <div style="color:${c};font-size:17px;font-weight:700;margin-bottom:2px">${fmt(value)} ${unit}</div>
        ${ring(pct, item.key, 88)}
        <div style="font-size:11px;color:#777;margin-top:2px">of ${fmt(goal)} ${unit}</div>
      </div>`;
    }

    const top = NUTRIENTS.slice(0, 3).map(tile).join('');
    const bottom = NUTRIENTS.slice(3).map(tile).join('');
    return `
      <div style="font-size:15px;font-weight:700;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #333">Nutrients</div>
      <div style="display:flex">${top}</div>
      <div style="display:flex;margin-top:4px">${bottom}</div>
    `;
  ]]]
styles:
  card:
    - background: "#1c1c1e"
    - border-radius: 16px
    - padding: 16px
    - color: white
    - font-family: sans-serif
  label:
    - width: 100%
    - text-align: left
    - padding: 0
```

### Installation

#### HACS custom repository

Click the HACS button at the top of this README, then select **Download** in
HACS. After Home Assistant restarts, add the integration from
**Settings -> Devices & services -> Add integration**.

If the button does not work, add this repository manually in HACS:

```text
https://github.com/nikopol666/homeassistant-kaloricke-tabulky
```

Use **Integration** as the repository category.

#### Manual installation

1. Copy `custom_components/kaloricke_tabulky` into your Home Assistant
   `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings -> Devices & services -> Add integration**.
4. Search for **Kaloricke Tabulky**.
5. Enter your Kaloricke Tabulky email and password in the form.

Home Assistant stores the credentials in its config entry storage. The
integration hashes the password with MD5 only when signing in, matching the
current Kaloricke Tabulky web endpoint behavior. You do not need to paste
browser cookies into Home Assistant.

### Action

```yaml
action: kaloricke_tabulky.record_weight
data:
  weight: 75.5
  date: "2026-05-12"
```

`date` is optional. If omitted, the integration records the weight for today.
Accepted date formats are `YYYY-MM-DD` and `DD.MM.YYYY`.

If you configure more than one Kaloricke Tabulky account, pass
`config_entry_id` to choose the account.

### Notes

This integration uses unofficial web endpoints from Kaloricke Tabulky and is
not affiliated with Kaloricke Tabulky. The endpoints can change without notice,
so API-related failures may need an integration update.

The repository includes local brand assets in
`custom_components/kaloricke_tabulky/brand/` so Home Assistant and HACS can show
the integration icon/logo without depending on an external image URL.

This project is released under the MIT License.

## Česky

Vlastní integrace Kalorické Tabulky pro Home Assistant.

### Co integrace umí

- Přidání Kalorických Tabulek přes UI Home Assistantu.
- Přihlašovací e-mail a heslo se zadávají ve formuláři při přidání integrace.
- Vytvoří senzory pro váhu, výživu, pitný režim, energii z aktivit a denní
  energetickou bilanci.
- Přidá akci `kaloricke_tabulky.record_weight` pro zápis tělesné váhy.
- Výchozí obnova senzorů je každých 240 minut. Je to záměrně šetrné, protože
  API Kalorických Tabulek použité touto integrací je neoficiální.
- Po úspěšném zápisu váhy se senzor obnoví okamžitě.

Interval obnovy jde změnit v nastavení integrace. Minimum je 15 minut.

### Senzory

Integrace vytváří stabilní senzory pro užitečné hodnoty, které teď vrací deník
a endpoint s váhou.

| Senzor | Jednotka | Zdroj |
| --- | --- | --- |
| Poslední váha | kg | Poslední záznam z měsíčního endpointu váhy |
| Energie | kcal | Celkový denní příjem |
| Pitný režim | l | Denní příjem tekutin |
| Tělesná váha | kg | Hodnota váhy v denním souhrnu |
| Bílkoviny | g | Denní součet bílkovin |
| Sacharidy | g | Denní součet sacharidů |
| Tuky | g | Denní součet tuků |
| Vláknina | g | Denní součet vlákniny |
| Cukry | g | Denní součet cukrů |
| Sůl | g | Denní součet soli |
| Energie z aktivit | kcal | Energie z aktivit |
| Energie z denního režimu | kcal | Energie z denního režimu z bloku bilance |
| Celkový výdej energie | kcal | Celkový denní výdej energie |
| Udržovací příjem | kcal | Udržovací energetický příjem |
| Energetický deficit | kcal | Deficit nebo přebytek podle Kalorických Tabulek |
| Energetický cíl | kcal | Denní energetický cíl |
| Bazální metabolismus | kcal | Bazální metabolismus |
| Zbývající energie | kcal | Zbývající energetický příjem |

Souhrnné senzory mají tyto atributy, pokud je API vrátí:

- `goal`: nastavený cíl dané hodnoty.
- `percent`: aktuální plnění cíle v procentech.
- `source_key`: surový klíč hodnoty z API odpovědi.

`Poslední váha` navíc vrací v atributech datum posledního záznamu a nedávné
měsíční záznamy váhy.

Když Kalorické Tabulky začnou vracet další číselnou hodnotu s jasnou jednotkou,
integrace ji může zobrazit jako další dynamický senzor.

### Příklad Lovelace karty pro nutrienty

Web Kalorických Tabulek nepoužívá jedno univerzální pravidlo barvy pro všechny
nutrienty. Například nízké cukry můžou být v pořádku, ale nízká vláknina ne.
Tento příklad používá stejný toleranční model jako webové kruhové grafy v
deníku:

- oranžová: pod zeleným rozsahem.
- zelená: v cílovém rozsahu konkrétní metriky.
- červená: nad zeleným rozsahem.

Entity ID si nahraď podle svých senzorů.
`KT_MODE` nastav podle hodnoty `mode`, kterou vrací denní souhrn Kalorických
Tabulek. Příklad používá `1`, protože tuhle hodnotu měl zachycený demo payload.

```yaml
type: custom:button-card
entity: sensor.tom_protein_2
show_name: false
show_icon: false
show_state: false
show_label: true
label: |
  [[[
    const NUTRIENTS = [
      { label: 'Bílkoviny', entity: 'sensor.tom_protein_2',     key: 'protein' },
      { label: 'Sacharidy', entity: 'sensor.tom_carbohydrates', key: 'carbohydrate' },
      { label: 'Tuky',      entity: 'sensor.tom_fat',           key: 'fat' },
      { label: 'Vláknina',  entity: 'sensor.tom_fiber',         key: 'fiber' },
      { label: 'Cukry',     entity: 'sensor.tom_sugar',         key: 'sugar' },
      { label: 'Sůl',       entity: 'sensor.tom_salt',          key: 'salt' },
    ];

    const KT_MODE = 1;

    const THRESHOLDS = {
      0: {
        protein:      { low: 20,  high: 20 },
        carbohydrate: { low: 20,  high: 20 },
        fat:          { low: 20,  high: 20 },
        fiber:        { low: 20,  high: 30 },
        sugar:        { low: 100, high: 10 },
        salt:         { low: 40,  high: 80 },
      },
      1: {
        protein:      { low: 10,  high: 20 },
        carbohydrate: { low: 30,  high: 15 },
        fat:          { low: 30,  high: 15 },
        fiber:        { low: 20,  high: 30 },
        sugar:        { low: 100, high: 15 },
        salt:         { low: 40,  high: 80 },
      },
      2: {
        protein:      { low: 20,  high: 30 },
        carbohydrate: { low: 20,  high: 30 },
        fat:          { low: 30,  high: 20 },
        fiber:        { low: 20,  high: 30 },
        sugar:        { low: 100, high: 20 },
        salt:         { low: 40,  high: 80 },
      },
    };

    function parseKtNumber(value) {
      if (typeof value === 'number') return value;
      if (typeof value !== 'string') return NaN;
      return Number(value.replace(/\s/g, '').replace(',', '.'));
    }

    function percent(state) {
      const attrPercent = parseKtNumber(state.attributes.percent);
      if (Number.isFinite(attrPercent)) return Math.round(attrPercent);

      const value = parseKtNumber(state.state);
      const goal = parseKtNumber(state.attributes.goal);
      return Number.isFinite(goal) && goal > 0 ? Math.round((value / goal) * 100) : NaN;
    }

    function color(pct, key) {
      if (!Number.isFinite(pct)) return '#FF8040';
      const t = (THRESHOLDS[KT_MODE] || THRESHOLDS[0])[key] || { low: 20, high: 20 };
      if (pct < 100 - t.low) return '#FF8040';
      if (pct > 100 + t.high) return '#DD4B39';
      return '#99cc33';
    }

    function ring(pct, key, size) {
      const r = 34;
      const circ = 2 * Math.PI * r;
      const p = Number.isFinite(pct) ? Math.min(Math.max(pct, 0), 100) : 0;
      const dash = (p / 100) * circ;
      const c = color(pct, key);
      return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="#e0e3e5" stroke-width="7"/>
        <circle cx="${size / 2}" cy="${size / 2}" r="${r}" fill="none" stroke="${c}" stroke-width="7"
          stroke-dasharray="${dash} ${circ}" stroke-linecap="round"
          transform="rotate(-90 ${size / 2} ${size / 2})"/>
        <text x="50%" y="55%" text-anchor="middle" fill="${c}" font-size="13" font-weight="bold">
          ${Number.isFinite(pct) ? pct + '%' : '?'}
        </text>
      </svg>`;
    }

    function tile(item) {
      const s = states[item.entity];
      if (!s) {
        return `<div style="width:33%;text-align:center;color:#e53935;padding:4px;font-size:11px">${item.label}<br>nenalezeno</div>`;
      }
      const value = parseKtNumber(s.state);
      const goal = parseKtNumber(s.attributes.goal);
      const pct = percent(s);
      const c = color(pct, item.key);
      const unit = s.attributes.unit_of_measurement || 'g';
      const fmt = v => Number.isFinite(v) ? (v % 1 === 0 ? v : v.toFixed(1)) : '?';
      return `<div style="width:33%;display:flex;flex-direction:column;align-items:center;padding:6px 0">
        <div style="font-weight:600;font-size:13px;margin-bottom:2px">${item.label}</div>
        <div style="color:${c};font-size:17px;font-weight:700;margin-bottom:2px">${fmt(value)} ${unit}</div>
        ${ring(pct, item.key, 88)}
        <div style="font-size:11px;color:#777;margin-top:2px">z ${fmt(goal)} ${unit}</div>
      </div>`;
    }

    const top = NUTRIENTS.slice(0, 3).map(tile).join('');
    const bottom = NUTRIENTS.slice(3).map(tile).join('');
    return `
      <div style="font-size:15px;font-weight:700;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #333">Nutrienty</div>
      <div style="display:flex">${top}</div>
      <div style="display:flex;margin-top:4px">${bottom}</div>
    `;
  ]]]
styles:
  card:
    - background: "#1c1c1e"
    - border-radius: 16px
    - padding: 16px
    - color: white
    - font-family: sans-serif
  label:
    - width: 100%
    - text-align: left
    - padding: 0
```

### Instalace

#### HACS custom repository

Klikni na HACS tlačítko nahoře v README a potom v HACS zvol **Download**. Po
restartu Home Assistantu přidej integraci přes **Nastavení -> Zařízení a služby
-> Přidat integraci**.

Když tlačítko nefunguje, přidej repozitář do HACS ručně:

```text
https://github.com/nikopol666/homeassistant-kaloricke-tabulky
```

Kategorie repozitáře je **Integration**.

#### Ruční instalace

1. Zkopíruj `custom_components/kaloricke_tabulky` do adresáře
   `custom_components` v Home Assistantu.
2. Restartuj Home Assistant.
3. Otevři **Nastavení -> Zařízení a služby -> Přidat integraci**.
4. Vyhledej **Kaloricke Tabulky**.
5. Do formuláře zadej svůj e-mail a heslo ke Kalorickým Tabulkám.

Home Assistant uloží údaje do svého config entry úložiště. Integrace heslo
zahashuje pomocí MD5 až při přihlášení, stejně jako současný webový endpoint
Kalorických Tabulek. Cookies z prohlížeče není potřeba do Home Assistantu
kopírovat.

### Akce

```yaml
action: kaloricke_tabulky.record_weight
data:
  weight: 75.5
  date: "2026-05-12"
```

`date` je volitelné. Když ho nevyplníš, integrace zapíše váhu pro dnešní den.
Podporované formáty data jsou `YYYY-MM-DD` a `DD.MM.YYYY`.

Pokud máš nastavený více než jeden účet Kalorických Tabulek, přidej
`config_entry_id`, aby bylo jasné, do kterého účtu se má váha zapsat.

### Poznámky

Integrace používá neoficiální webové endpointy Kalorických Tabulek a není s
Kalorickými Tabulkami nijak afiliovaná. Endpointy se můžou změnit bez
upozornění, takže případné API chyby můžou vyžadovat úpravu integrace.

Repozitář obsahuje lokální brand assety v
`custom_components/kaloricke_tabulky/brand/`, aby Home Assistant a HACS mohly
zobrazit ikonu/logo integrace bez závislosti na externí URL.

Projekt je vydaný pod licencí MIT.
