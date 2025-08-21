# Environment Setup

## Conda Environment
- Use conda environment: `options`
- Python path: `/Users/robertcologero/miniconda3/envs/options/bin/python`
- To activate: `conda activate options`

## How to Run Script

Use conda run to execute scripts in the correct environment:

```bash
conda run -n options python Daily_Portfolio_Script_new_parse.py --test-parser
```

For other script executions:
```bash
conda run -n options python [script_name.py] [arguments]
```

## Dependencies
- yfinance
- matplotlib
- pandas
- numpy
- Other dependencies as specified in requirements