/**
 * Shared inline SVG icons for the sidecar.
 *
 * One consistent set (Material-style, filled, currentColor) replacing the
 * emoji glyphs that used to stand in for icons (🤖 👤 🤝 ⚠️ 💡 ⏱️) — emoji
 * render inconsistently across platforms and sit outside the design system.
 * Size via the `sidecar-svg-icon` class (sidebar.css); color inherits.
 */

const svg = (path: string): string =>
  `<svg class="sidecar-svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="${path}"/></svg>`;

export const ICONS = {
  /** Mobius handles it — auto_awesome sparkle. */
  mobius: svg(
    'M19 9l1.25-2.75L23 5l-2.75-1.25L19 1l-1.25 2.75L15 5l2.75 1.25L19 9zm-7.5.5L9 4 6.5 9.5 1 12l5.5 2.5L9 20l2.5-5.5L17 12l-5.5-2.5zM19 15l-1.25 2.75L15 19l2.75 1.25L19 23l1.25-2.75L23 19l-2.75-1.25L19 15z'
  ),
  /** Manual / person. */
  person: svg(
    'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z'
  ),
  /** Together / handshake — two people. */
  together: svg(
    'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z'
  ),
  /** Warning triangle. */
  warning: svg('M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z'),
  /** Recommendation hint — lightbulb. */
  bulb: svg(
    'M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z'
  ),
  /** Typical response time — clock. */
  clock: svg(
    'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67V7z'
  ),
};

export type IconName = keyof typeof ICONS;

/** Icon for a workflow mode. */
export function modeIcon(mode: 'mobius' | 'together' | 'manual' | null | undefined): string {
  if (mode === 'mobius') return ICONS.mobius;
  if (mode === 'together') return ICONS.together;
  if (mode === 'manual') return ICONS.person;
  return '';
}
