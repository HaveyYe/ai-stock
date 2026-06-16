# AGENTS.md

## Project Overview

AiStock is a Streamlit single-page stock analysis app for A-share, HK, and US stocks. It uses AKShare-backed data providers and renders a four-part analysis dashboard:

- Value analysis
- Bollinger bands
- Fibonacci retracement
- Price Action

The main entrypoint is `app.py`. Core orchestration lives in `src/pipeline.py`.

## Run Commands

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start the app locally:

```bash
python3 -m streamlit run app.py --server.port 8501 --server.headless true
```

Validate the app is reachable:

```bash
curl -I --max-time 5 http://localhost:8501
```

## Test Commands

Run the full test suite before handing off behavior changes:

```bash
python3 -m unittest
```

The README command is also valid:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

For data provider work, run the focused provider tests first:

```bash
python3 -m unittest tests.test_akshare_provider
```

## Code Structure

- `app.py`: Streamlit UI, tabs, search box, analysis trigger, and cached analysis calls.
- `src/pipeline.py`: Resolves user input, fetches data, runs analyzers, composes the final result.
- `src/data/akshare_provider.py`: Live data provider, symbol search, market-specific fallbacks, fundamentals.
- `src/analyzers/`: Individual analysis modules.
- `src/scoring/composer.py`: Converts analyzer outputs into the final score/action.
- `src/ui/`: Chart, report, card, legend, and dashboard rendering helpers.
- `src/utils/market_detector.py`: Market detection and symbol normalization.
- `tests/`: Unit tests for provider behavior, analyzers, UI report/chart helpers, scoring, and pipeline flow.

## Important Behavior

- User input must accept stock code, Chinese name, English name, and common aliases.
- Resolve the user input before analysis starts. Do not call `get_klines()` directly on raw fuzzy text.
- Exact US ticker input should stay fast and should not load full market catalogs.
- A-share and HK exact-code display should prefer `code · stock name · market`, not duplicated code.
- Keep static aliases for common US/HK names so popular searches do not depend on slow live catalogs.

## Data Source Rules

AKShare and related upstream market data endpoints are network-sensitive. Do not assume a single source is reliable.

- A-share K-lines should try Sina first and fall back to Eastmoney.
- US K-lines should fall back to Yahoo chart data when AKShare US daily data fails.
- Missing snapshot/fundamental fields should not abort analysis if usable price data exists.
- Return clear user-facing errors only after all relevant market fallbacks fail.
- Keep provider failures localized to `src/data/akshare_provider.py`; avoid spreading network-specific recovery logic into UI code.

## UI Rules

- The first screen should remain the usable dashboard, not a landing page.
- Keep the search interaction as a searchable select/input that accepts new text.
- Pressing Enter after input should be equivalent to starting analysis.
- The top legend explains score bands and colors; keep it visible before the analysis controls.
- The analysis layout should keep the four dimensions readable and not compressed into a single crowded row.
- After significant UI changes, restart Streamlit and verify the browser at `http://localhost:8501`.

## Development Guidelines

- Prefer existing dataclasses and result types in `src/types.py`.
- Keep analyzer modules pure and testable; network calls belong in the provider layer.
- Add or update focused tests when changing provider fallbacks, input resolution, scoring, or UI report text.
- Do not commit cache artifacts such as `__pycache__/`, `.pyc`, `.DS_Store`, or IDE files.
- Avoid broad refactors while fixing data source or UI interaction bugs.

## Known Local Verification Pattern

When fixing live provider behavior, use both unit tests and one real smoke test if the network is available:

```bash
python3 - <<'PY'
from src.pipeline import run_analysis
from src.data.akshare_provider import default_provider

bundle = run_analysis("300351", provider=default_provider())
print(bundle.info.code, bundle.info.name)
print(bundle.composite_result.action, bundle.composite_result.score)
print(len(bundle.kline_result.klines))
PY
```

If the app was already running, restart Streamlit after provider changes to clear stale imports and cached failure results.
