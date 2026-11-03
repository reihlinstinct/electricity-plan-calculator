// GENERATED from data/tariffs.json and data/benchmarks.json by scripts/gen_web_data.py - do not edit by hand
export const TARIFFS = {
  "version": "2026-07-01",
  "retrieved": "2026-11-02",
  "currency": "ILS",
  "vat_included": true,
  "notes": "Rates include 18% VAT. Supplier discounts apply to the energy (per-kWh) component only. Fixed monthly fees are identical for flat and supplier plans (single-phase 25.57 / three-phase 27.09 NIS pre-VAT, schedule 5.4-1); the Taoz fixed fee is higher (47.63 pre-VAT). Taoz holidays: yom-tov days and eves are off-peak in summer/transition only (decision 63609); winter peak applies daily.",
  "sources": [
    {
      "name": "Electricity Authority tariff book, January 2026 (schedule 5.2-1, low voltage)",
      "url": "https://www.gov.il/BlobFolder/generalpage/maagar_tarrifr_histoty/he/sefer_tariff_01_2026.pdf",
      "verified": "2026-08-06"
    },
    {
      "name": "chashmali.com tariff verification (cross-checked against the tariff book)",
      "url": "https://chashmali.com/electricity-tariff/",
      "verified": "2026-08-06"
    },
    {
      "name": "shtipser.com tariff page (cross-checked against IEC tariff page)",
      "url": "https://shtipser.com/tariff/",
      "verified": "2026-08-01"
    },
    {
      "name": "Taoz peak/off-peak hours, EA decision 63609 (schedule 5.1-1)",
      "url": "https://kolhabait.com/chashmal/taoz",
      "verified": "2026-10-01"
    },
    {
      "name": "Private supplier plans (verified against supplier sites)",
      "url": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "url": "https://www.hebcal.com/hebcal?v=1&cfg=json&maj=on&i=on&year=2026",
      "description": "Hebcal API - Israel yom-tov dates for 2026; paired with the 2027 source below",
      "retrieved": "2026-11-02",
      "verified": "2026-11-03"
    },
    {
      "url": "https://www.hebcal.com/hebcal?v=1&cfg=json&maj=on&i=on&year=2027",
      "description": "Hebcal API - Israel yom-tov dates for 2027; all 8 dates cross-checked against the stored holiday list",
      "verified": "2026-11-03"
    }
  ],
  "regulated": {
    "flat_rate_per_kwh": 0.6352,
    "flat_rate_per_kwh_pre_vat": 0.5383,
    "effective_from": "2026-07-01",
    "next_update_expected": "2027-01-01",
    "fixed_fees_monthly_pre_vat": {
      "single_phase": {
        "distribution": 9.97,
        "supply": 15.6,
        "total": 25.57
      },
      "three_phase": {
        "total": 27.09
      }
    }
  },
  "taoz": {
    "requires_smart_meter": true,
    "voluntary_below_annual_kwh": 40000,
    "holidays": [
      "2026-04-02",
      "2026-04-08",
      "2026-05-22",
      "2026-09-12",
      "2026-09-13",
      "2026-09-21",
      "2026-09-26",
      "2026-10-03",
      "2027-04-22",
      "2027-04-28",
      "2027-06-11",
      "2027-10-02",
      "2027-10-03",
      "2027-10-11",
      "2027-10-16",
      "2027-10-23"
    ],
    "seasons": {
      "summer": {
        "months": [
          6,
          7,
          8,
          9
        ],
        "peak": {
          "days": "sun-thu",
          "start": "17:00",
          "end": "23:00"
        },
        "rates": {
          "peak": 1.7223,
          "off_peak": 0.5042
        }
      },
      "winter": {
        "months": [
          12,
          1,
          2
        ],
        "peak": {
          "days": "all",
          "start": "17:00",
          "end": "22:00"
        },
        "rates": {
          "peak": 1.147,
          "off_peak": 0.4663
        }
      },
      "transition": {
        "months": [
          3,
          4,
          5,
          10,
          11
        ],
        "peak": {
          "days": "sun-thu",
          "start": "17:00",
          "end": "22:00"
        },
        "rates": {
          "peak": 0.4958,
          "off_peak": 0.4578
        }
      }
    },
    "fixed_fee_monthly_pre_vat": {
      "distribution": 32.1,
      "supply": 15.53,
      "total": 47.63
    },
    "holiday_eves": [
      "2026-04-01",
      "2026-04-07",
      "2026-05-21",
      "2026-09-11",
      "2026-09-20",
      "2026-09-25",
      "2026-10-02",
      "2027-04-21",
      "2027-04-27",
      "2027-06-10",
      "2027-10-01",
      "2027-10-10",
      "2027-10-15",
      "2027-10-22"
    ]
  },
  "supplier_plans": [
    {
      "supplier": "ELECTRA POWER",
      "plan": "Power",
      "discount": 0.065,
      "window": null,
      "meter": "any",
      "eligibility": "כל סוגי המונים",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "אמישראגז חשמל",
      "plan": "אמישראגז חשמל",
      "discount": 0.07,
      "window": null,
      "meter": "any",
      "eligibility": "לקוחות גז של אמישראגז בלבד",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27",
      "requires_gas_customer": true,
      "requires_hot_customer": false
    },
    {
      "supplier": "בזק energy",
      "plan": "חוסכים חכם 24/7",
      "discount": 0.06,
      "window": null,
      "meter": "any",
      "eligibility": "כל סוגי המונים",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "HOT energy",
      "plan": "חוסכים קבוע",
      "discount": 0.06,
      "window": null,
      "meter": "any",
      "eligibility": "לקוחות HOT ו-NEXT",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27",
      "requires_gas_customer": false,
      "requires_hot_customer": true
    },
    {
      "supplier": "HOT energy",
      "plan": "חוסכים 24/7",
      "discount": 0.05,
      "window": null,
      "meter": "any",
      "eligibility": "כל סוגי המונים",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "פזגז",
      "plan": "חוסכים קבוע",
      "discount": 0.05,
      "window": null,
      "meter": "any",
      "eligibility": "ללא התחייבות",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "Partner Power",
      "plan": "הנחה קבועה",
      "discount": 0.05,
      "window": null,
      "meter": "any",
      "eligibility": "כל סוגי המונים; ההנחה עולה ל-7% לאורך שלוש שנים",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "סלקום אנרג׳י",
      "plan": "חסכון משתלם",
      "discount": 0.075,
      "window": {
        "days": "sun-thu",
        "start": "00:00",
        "end": "00:00"
      },
      "meter": "any",
      "eligibility": "ימים ראשון-חמישי בלבד",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "ELECTRA POWER",
      "plan": "מסלול יום",
      "discount": 0.21,
      "window": {
        "days": "sun-thu",
        "start": "07:00",
        "end": "17:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "סלקום אנרג׳י",
      "plan": "חסכון ביום",
      "discount": 0.2,
      "window": {
        "days": "sun-thu",
        "start": "07:00",
        "end": "17:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "בזק energy",
      "plan": "חוסכים חכם ביום",
      "discount": 0.15,
      "window": {
        "days": "sun-thu",
        "start": "07:00",
        "end": "17:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "HOT energy",
      "plan": "חוסכים ביום",
      "discount": 0.15,
      "window": {
        "days": "sun-thu",
        "start": "07:00",
        "end": "17:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "Partner Power",
      "plan": "עובדים מהבית",
      "discount": 0.15,
      "window": {
        "days": "sun-thu",
        "start": "07:00",
        "end": "17:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "סלקום אנרג׳י",
      "plan": "חסכון למשפחות",
      "discount": 0.18,
      "window": {
        "days": "sun-thu",
        "start": "14:00",
        "end": "20:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "ELECTRA POWER",
      "plan": "10X10",
      "discount": 0.1,
      "window": {
        "days": "sun-thu",
        "start": "10:00",
        "end": "22:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "ELECTRA POWER",
      "plan": "לילה פלוס",
      "discount": 0.21,
      "window": {
        "days": "sun-thu",
        "start": "23:00",
        "end": "07:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "בזק energy",
      "plan": "חוסכים חכם בלילה",
      "discount": 0.2,
      "window": {
        "days": "sun-thu",
        "start": "23:00",
        "end": "07:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "HOT energy",
      "plan": "חוסכים בלילה",
      "discount": 0.2,
      "window": {
        "days": "sun-thu",
        "start": "23:00",
        "end": "07:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "Partner Power",
      "plan": "חיות לילה",
      "discount": 0.2,
      "window": {
        "days": "sun-thu",
        "start": "23:00",
        "end": "07:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    },
    {
      "supplier": "סלקום אנרג׳י",
      "plan": "חסכון בלילה",
      "discount": 0.15,
      "window": {
        "days": "all",
        "start": "23:00",
        "end": "07:00"
      },
      "meter": "smart",
      "eligibility": "מונה חכם",
      "source": "https://shtipser.com/plans/",
      "verified": "2026-09-27"
    }
  ],
  "vat_rate": 0.18
};
export const BENCHMARKS = {
  "accessed": "2026-11-02",
  "note": "Typical-technology benchmark figures for efficiency context only. Never a verdict on a specific appliance.",
  "washer": {
    "typical_modern_kwh_per_cycle": 0.5,
    "israel_2021_kwh_per_cycle": 0.93,
    "israel_2024_kwh_per_cycle": 0.55,
    "unit_note": "Benchmark 0.5 kWh/cycle is consistent with the Israeli 2024 average 0.55 (ynet); the EC page gives the eco 40-60 label methodology (kWh per 100 cycles), it is not the source of the figure. Program and temperature change consumption materially",
    "sources": [
      {
        "label": "European Commission - washing machines energy label (consumption per 100 cycles, eco 40-60)",
        "url": "https://energy-efficient-products.ec.europa.eu/product-list/washing-machines_en"
      },
      {
        "label": "Israeli Ministry of Energy market study via ynet: 0.93 kWh/cycle (2021) vs 0.55 (2024), -41%",
        "url": "https://www.ynet.co.il/economy/article/h1tu9ogzgl"
      }
    ]
  },
  "ac": {
    "inverter_savings_min": 0.2,
    "inverter_savings_max": 0.4,
    "unit_note": "Range across studies for inverter vs on/off room AC: 11-38% (Istanbul field test), ~24% (Saudi Arabia 1989: measured single-speed unit vs simulated inverter), ~44% (Jeddah)",
    "sources": [
      {
        "label": "Istanbul Technical University field test: inverter saves 11-38%",
        "url": "https://research.itu.edu.tr/en/publications/an-experimental-investigation-of-energy-saving-potentials-for-roo/"
      },
      {
        "label": "KFUPM 1989 (ASHRAE Transactions): measured single-speed unit vs simulated inverter; inverter used 24% less energy",
        "url": "https://pure.kfupm.edu.sa/en/publications/an-assessment-of-inverter-driven-variable-speed-air-conditioners-/"
      },
      {
        "label": "Springer (Jeddah): inverter saves up to 44%",
        "url": "https://link.springer.com/article/10.1007/s41825-020-00033-y"
      }
    ]
  },
  "fridge": {
    "typical_modern_kwh_per_year": 181,
    "old_1990_kwh_per_year": 477,
    "unit_note": "EU average fridge-freezer, kWh/year; 2020 vs 1990",
    "sources": [
      {
        "label": "European Commission - fridges and freezers (181 kWh/a in 2020, 477 kWh/a in 1990)",
        "url": "https://energy-efficient-products.ec.europa.eu/product-list/fridges-and-freezers_en"
      },
      {
        "label": "Israeli Ministry of Energy market study via ynet: -29% fridge consumption 2021->2024, ~80 NIS/year",
        "url": "https://www.ynet.co.il/economy/article/h1tu9ogzgl"
      }
    ]
  }
};
