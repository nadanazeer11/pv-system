import type { ApplianceLibraryEntry } from '@/types/api';

/**
 * Static mirror of the backend's Egyptian-residential appliance library
 * (backend/app/services/load_sizing.py::APPLIANCE_LIBRARY).
 *
 * Held on the client so the appliance dropdown is usable even when the
 * backend is unreachable — `useApplianceLibrary` seeds the query with
 * this list as `initialData`, so the UI shows options on first render
 * and silently refreshes from the API when the request resolves. Keep
 * in lockstep with the backend constant.
 */
export const APPLIANCE_LIBRARY_FALLBACK: ApplianceLibraryEntry[] = [
  { name: 'Air conditioner (1.5 ton split)', watts: 1500, typical_hours_per_day: 6, category: 'Cooling' },
  { name: 'Air conditioner (2.25 ton split)', watts: 2200, typical_hours_per_day: 6, category: 'Cooling' },
  { name: 'Air conditioner (3 ton split)', watts: 3000, typical_hours_per_day: 6, category: 'Cooling' },
  { name: 'Ceiling fan', watts: 75, typical_hours_per_day: 8, category: 'Cooling' },
  { name: 'Standing / pedestal fan', watts: 60, typical_hours_per_day: 6, category: 'Cooling' },
  { name: 'Refrigerator (medium)', watts: 150, typical_hours_per_day: 10, category: 'Refrigeration' },
  { name: 'Refrigerator (large / side-by-side)', watts: 250, typical_hours_per_day: 10, category: 'Refrigeration' },
  { name: 'Standalone freezer', watts: 200, typical_hours_per_day: 10, category: 'Refrigeration' },
  { name: 'LED bulb (10 W)', watts: 10, typical_hours_per_day: 5, category: 'Lighting' },
  { name: 'CFL bulb (20 W)', watts: 20, typical_hours_per_day: 5, category: 'Lighting' },
  { name: 'Microwave oven', watts: 1100, typical_hours_per_day: 0.3, category: 'Kitchen' },
  { name: 'Electric oven', watts: 2500, typical_hours_per_day: 0.5, category: 'Kitchen' },
  { name: 'Electric kettle', watts: 1800, typical_hours_per_day: 0.2, category: 'Kitchen' },
  { name: 'Dishwasher', watts: 1500, typical_hours_per_day: 1, category: 'Kitchen' },
  { name: 'Toaster', watts: 900, typical_hours_per_day: 0.1, category: 'Kitchen' },
  { name: 'Electric water heater (50 L)', watts: 2000, typical_hours_per_day: 2, category: 'Water heating' },
  { name: 'Electric water heater (80 L)', watts: 2500, typical_hours_per_day: 2, category: 'Water heating' },
  { name: 'Washing machine', watts: 500, typical_hours_per_day: 1, category: 'Laundry' },
  { name: 'Clothes dryer', watts: 2500, typical_hours_per_day: 0.5, category: 'Laundry' },
  { name: 'Iron', watts: 1100, typical_hours_per_day: 0.3, category: 'Laundry' },
  { name: 'LED TV (50")', watts: 100, typical_hours_per_day: 4, category: 'Electronics' },
  { name: 'Desktop computer', watts: 200, typical_hours_per_day: 4, category: 'Electronics' },
  { name: 'Laptop', watts: 65, typical_hours_per_day: 4, category: 'Electronics' },
  { name: 'Wi-Fi router / modem', watts: 10, typical_hours_per_day: 24, category: 'Electronics' },
  { name: 'Hair dryer', watts: 1500, typical_hours_per_day: 0.1, category: 'Other' },
  { name: 'Vacuum cleaner', watts: 1400, typical_hours_per_day: 0.2, category: 'Other' },
  { name: 'Water pump', watts: 750, typical_hours_per_day: 1, category: 'Other' },
];
