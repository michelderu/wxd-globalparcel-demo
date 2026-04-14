'''Generate the fuel data and load it into the Postgres container.'''

import pandas as pd
from sqlalchemy import create_engine

# 1. Generate Shipping Data (Lakehouse Source)
regions = ['EU_NORTH', 'EU_SOUTH', 'EU_WEST']
df_shipping = pd.DataFrame({
    'package_id': [f'PKG-{i}' for i in range(1000)],
    'region': [regions[i % 3] for i in range(1000)],
    'shipping_cost': [round(10 + (i % 50), 2) for i in range(1000)]
})
df_shipping.to_csv('shipping_data.csv', index=False)

# 2. Generate Fuel Data (Postgres Source)
df_fuel = pd.DataFrame({
    'region': regions,
    'fuel_surcharge': [5.50, 4.20, 6.10]
})

# Connection to your local Postgres container
engine = create_engine('postgresql://postgres:postgres@localhost:5432/shipping_ops')
df_fuel.to_sql('fuel_index', engine, if_exists='replace', index=False)

print("✅ Local data generated and Postgres updated.")