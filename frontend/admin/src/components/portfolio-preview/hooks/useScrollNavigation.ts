import { useEffect, useRef, useState, useCallback } from 'react';

export function useScrollNavigation(sectionCount: number) {
  const [currentSection, setCurrentSection] = useState(0);
  const sectionsRef = useRef<HTMLElement[]>([]);

  const registerSection = useCallback((index: number, element: HTMLElement | null) => {
    if (element) {
      sectionsRef.current[index] = element;
    }
  }, []);

  const goToSection = useCallback((index: number) => {
    if (index >= 0 && index < sectionCount && sectionsRef.current[index]) {
      sectionsRef.current[index].scrollIntoView({ behavior: 'smooth' });
      setCurrentSection(index);
    }
  }, [sectionCount]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const index = sectionsRef.current.indexOf(entry.target as HTMLElement);
            if (index !== -1) {
              setCurrentSection(index);
            }
          }
        });
      },
      { threshold: 0.3 }
    );

    sectionsRef.current.forEach((section) => {
      if (section) observer.observe(section);
    });

    return () => observer.disconnect();
  }, []);

  return { currentSection, registerSection, goToSection };
}
