"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

import { cn } from "@/lib/format";

type ThemePreference = "system" | "light" | "dark";
const ORDER: ThemePreference[] = ["system", "light", "dark"];
const ICONS = { system: Monitor, light: Sun, dark: Moon };
const LABELS = { system: "System theme", light: "Light theme", dark: "Dark theme" };
const CHANGE_EVENT = "app:theme";

function readPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem("theme");
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

function apply(preference: ThemePreference) {
  const dark = preference === "dark" || (preference === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("dark", dark);
}

function subscribe(callback: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  const onSystemChange = () => {
    if (readPreference() === "system") apply("system");
    callback();
  };
  media.addEventListener("change", onSystemChange);
  window.addEventListener(CHANGE_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    media.removeEventListener("change", onSystemChange);
    window.removeEventListener(CHANGE_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

export function ThemeToggle({ className }: { className?: string }) {
  const preference = useSyncExternalStore(subscribe, readPreference, () => "system" as ThemePreference);

  const cycle = () => {
    const next = ORDER[(ORDER.indexOf(preference) + 1) % ORDER.length];
    try {
      if (next === "system") localStorage.removeItem("theme");
      else localStorage.setItem("theme", next);
    } catch {
      /* storage unavailable: the choice lasts for this page only */
    }
    apply(next);
    window.dispatchEvent(new Event(CHANGE_EVENT));
  };

  const Icon = ICONS[preference];
  return (
    <button
      type="button"
      onClick={cycle}
      title={`${LABELS[preference]} (click to change)`}
      aria-label={`${LABELS[preference]}. Change theme`}
      className={cn("grid size-8 place-items-center rounded-lg transition-colors", className)}
    >
      <Icon className="size-4" aria-hidden />
    </button>
  );
}
