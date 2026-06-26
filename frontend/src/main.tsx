import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "./index.css";
import App from "./App.tsx";

/*
 * Input-mode-deteksjon for fokusring-håndtering.
 *
 * `:focus-visible` fungerer ikke pålitelig for SVG-elementer (som
 * Recharts bruker) fordi Chrome sin interne heuristikk kun gjelder
 * HTMLElement — for SVG returnerer den alltid true uavhengig av
 * om fokus kom fra mus eller tastatur.
 *
 * Løsning: sett data-pointer på <body> ved peker-interaksjon,
 * fjern det ved Tab. CSS bruker attributtet i stedet for :focus-visible.
 */
document.addEventListener("mousedown",  () => document.body.setAttribute("data-pointer", "1"), true);
document.addEventListener("touchstart", () => document.body.setAttribute("data-pointer", "1"), { capture: true, passive: true });
document.addEventListener("keydown", (e) => {
  if (e.key === "Tab") document.body.removeAttribute("data-pointer");
}, true);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
