import { useRef } from 'react';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { Hero } from '@/components/layout/Hero';
import { Section } from '@/components/layout/Section';
import { SizingEstimator } from '@/components/estimator/SizingEstimator';

export default function App() {
  const estimatorRef = useRef<HTMLDivElement>(null);
  const scrollToEstimator = () => {
    estimatorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="min-h-screen">
      <Header />
      <main>
        <Hero onCtaClick={scrollToEstimator} />
        <div ref={estimatorRef}>
          <Section
            title="Estimator"
            subtitle="Day-12 scaffold — only roof area and system size are wired today. Days 13–17 layer in address autodetection, the full dashboard, and Monte-Carlo charts."
            id="estimator"
          >
            <SizingEstimator />
          </Section>
        </div>
      </main>
      <Footer />
    </div>
  );
}
