import { useRef, useState } from 'react';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { Hero } from '@/components/layout/Hero';
import { Section } from '@/components/layout/Section';
import { LocationPicker } from '@/components/estimator/LocationPicker';
import { SizingEstimator } from '@/components/estimator/SizingEstimator';
import type { Location } from '@/types/api';

export default function App() {
  const estimatorRef = useRef<HTMLDivElement>(null);
  const scrollToEstimator = () => {
    estimatorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  // Hoisted here so the address picker (Day 13) and the sizing form
  // (Day 12) live in one page. Day 14 will replace `SizingEstimator`
  // with the full multi-card dashboard, which will read this same
  // location plus the auto-detected roof area.
  const [, setSelectedLocation] = useState<Location | null>(null);

  return (
    <div className="min-h-screen">
      <Header />
      <main>
        <Hero onCtaClick={scrollToEstimator} />
        <div ref={estimatorRef}>
          <Section
            title="Estimator"
            subtitle="Day 13 wires the address-based location picker on top of the Day-12 sizing form. Days 14–17 replace the sizing card with the full dashboard, charts, and Monte-Carlo confidence interval."
            id="estimator"
          >
            <div className="space-y-10">
              <LocationPicker onLocationChange={setSelectedLocation} />
              <SizingEstimator />
            </div>
          </Section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
