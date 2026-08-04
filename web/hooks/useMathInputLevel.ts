"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch, apiUrl } from "@/lib/api";
import { normalizeMathLevel, type MathLevel } from "@/lib/math-symbols";

// Reads/writes `ui.math_input_level` from the backend UI settings. The chat
// composer lives outside the <SettingsProvider> route tree, so (like
// useVoiceAutoplay) we can't lean on the settings context — we manage our own
// module-level cache + a CustomEvent so the palette and any future settings
// page stay in sync without re-fetching.

const GLOBAL_EVENT = "deeptutor:math-input-level";

let cached: MathLevel | null = null;
let inflight: Promise<MathLevel> | null = null;

function fetchGlobal(): Promise<MathLevel> {
  if (cached !== null) return Promise.resolve(cached);
  if (!inflight) {
    inflight = apiFetch(apiUrl("/api/v1/settings"))
      .then((r) => (r.ok ? r.json() : null))
      .then((payload) => {
        cached = normalizeMathLevel(payload?.ui?.math_input_level);
        return cached;
      })
      .catch(() => {
        cached = "full";
        return cached;
      })
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

/**
 * Read + write the persisted math symbol stage.
 *
 * The stage is set once from the palette's stage selector and remembered
 * across sessions. Components read `level` (with `loading` while the first
 * fetch is in flight) and call `setLevel` to persist a change — the local
 * state updates optimistically and a CustomEvent broadcasts the new value so
 * any other mounted palette updates without an extra round trip.
 */
export function useMathInputLevel() {
  const [level, setLevel] = useState<MathLevel>(cached ?? "full");
  const [loading, setLoading] = useState<boolean>(cached === null);

  useEffect(() => {
    let active = true;
    fetchGlobal().then((v) => {
      if (active) {
        setLevel(v);
        setLoading(false);
      }
    });
    const onGlobal = (e: Event) =>
      setLevel(normalizeMathLevel((e as CustomEvent).detail?.value));
    window.addEventListener(GLOBAL_EVENT, onGlobal);
    return () => {
      active = false;
      window.removeEventListener(GLOBAL_EVENT, onGlobal);
    };
  }, []);

  const persistLevel = useCallback(async (next: MathLevel) => {
    const normalized = normalizeMathLevel(next);
    setLevel(normalized);
    cached = normalized;
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent(GLOBAL_EVENT, { detail: { value: normalized } }),
      );
    }
    await apiFetch(apiUrl("/api/v1/settings/ui"), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ math_input_level: normalized }),
    });
  }, []);

  return { level, setLevel: persistLevel, loading };
}
