"use client";

import { useEffect, useRef, useState, type ReactNode, type CSSProperties } from "react";

type RevealProps = {
  children: ReactNode;
  className?: string;
  delay?: number;
  distance?: number;
  once?: boolean;
};

export function Reveal({ children, className = "", delay = 0, distance = 22, once = true }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVisible(true);
      setReady(true);
      return;
    }
    if (!("IntersectionObserver" in window)) {
      setVisible(true);
      setReady(true);
      return;
    }
    setReady(true);
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setVisible(true);
        if (once) observer.unobserve(node);
      } else if (!once) {
        setVisible(false);
      }
    }, { threshold: 0.14, rootMargin: "0px 0px -40px 0px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [once]);

  return (
    <div
      ref={ref}
      className={`reveal ${ready ? "reveal-ready" : ""} ${visible ? "is-visible" : ""} ${className}`}
      style={{ "--reveal-distance": `${distance}px`, "--reveal-delay": `${delay}ms` } as CSSProperties}
    >
      {children}
    </div>
  );
}

export function PageEntrance({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`page-entrance ${className}`}>{children}</div>;
}
