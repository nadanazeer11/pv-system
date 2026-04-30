import { useRef, useState } from 'react';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { Hero } from '@/components/layout/Hero';
import { Section } from '@/components/layout/Section';
import { LocationPicker } from '@/components/estimator/LocationPicker';
import { Dashboard } from '@/components/dashboard/Dashboard';
import type { Location, RoofPolygon } from '@/types/api';

export default function App() {
  const estimatorRef = useRef<HTMLDivElement>(null);
  const scrollToEstimator = () => {
    estimatorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // The address picker (Day 13) lifts both the chosen pin and the
  // OSM-detected roof up to App; the Day-14 dashboard reads them as
  // props. Holding the state here, rather than inside one of the two
  // children, is what lets the dashboard render the metric grid and the
  // form together while staying loosely coupled to the picker's
  // implementation details.
  const [location, setLocation] = useState<Location | null>(null);
  const [roof, setRoof] = useState<RoofPolygon | null>(null);

  return (
    <div className="min-h-screen">
      <Header />
      <main>
        <Hero onCtaClick={scrollToEstimator} />
        <div ref={estimatorRef}>
          <Section
            title="Estimator"
            subtitle="Pick a location, confirm the roof, and run the four-step estimate. The dashboard below shows system size, annual generation, annual savings, and payback period — each with a Know-more explainer."
            id="estimator"
          >
            <div className="space-y-10">
              <LocationPicker
                onLocationChange={setLocation}
                onRoofChange={setRoof}
              />
              <Dashboard location={location} roof={roof} />
            </div>
          </Section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
