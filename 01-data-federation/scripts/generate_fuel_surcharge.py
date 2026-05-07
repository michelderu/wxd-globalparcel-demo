'''Generate fuel surcharge reference data as CSV.'''

from pathlib import Path

import pandas as pd

# Write CSV to the process working directory (run from `01-data-federation/`).

# Generate fuel surcharge data.
regions = ['EU_NORTH', 'EU_SOUTH', 'EU_WEST']
df_fuel = pd.DataFrame({
    'region': regions,
    'fuel_surcharge': [5.50, 4.20, 6.10]
})
df_fuel.to_csv(Path.cwd() / 'fuel_surcharge.csv', index=False)

print("Fuel surcharge CSV generated: fuel_surcharge.csv")