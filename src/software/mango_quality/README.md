# Mango Quality Fusion

This module fuses three available sources:

- YOLO labels: `mango_unripe`, `mango_ripe`, `mango_overripe`
- Vision color CSV: RGB/HSV means from the YOLO ROI
- AS7341 spectrum CSV: visible bands, clear, NIR and derived spectral features

The current algorithm is a rule-based expert baseline. It does not require a
training dataset. Because no measured Brix dataset is available, sugar output is
a reference range, not a calibrated measurement.

## Realtime Run

```bash
python3 /home/elf/projects/src/software/mango_quality/mango_quality_cli.py
```

Default inputs:

- `/home/elf/projects/datas/csv/vision_color_realtime.csv`
- `/home/elf/projects/datas/spectrum_quality_samples.csv`

Default outputs:

- `/home/elf/projects/datas/csv/mango_quality_realtime.csv`
- `/home/elf/projects/datas/csv/mango_quality_realtime.json`

Run once:

```bash
python3 /home/elf/projects/src/software/mango_quality/mango_quality_cli.py --once
```

## Output Meaning

- `maturity_label`: `未熟`, `成熟`, `过熟`
- `sugar_label`: reference sugar class
- `reference_brix_range`: rough Brix range for display only
- `rot_status`: `正常`, `疑似腐烂`, `腐烂/建议剔除`
- `final_status`: `可接受`, `需要复检`, `建议剔除`, `无有效检测`

## Notes

If the vision CSV later adds these optional fields, the rot assessment will be
stronger:

- `green_ratio`
- `yellow_orange_ratio`
- `dark_spot_ratio`
- `brown_area_ratio`

Without those fields, rot assessment uses ROI mean HSV/RGB and is weaker.

The helper function `extract_mango_color_features_from_bgr_roi()` can calculate
those fields from a YOLO ROI image before writing the vision CSV.
