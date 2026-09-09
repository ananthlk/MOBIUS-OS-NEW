/**
 * SidecarContextStrip — the "what I know" band (Phase 2).
 *
 * Derived, static context shown so the user confirms by glancing, not by
 * filling anything in: surface glyph · identity · role · wrong? (corrects
 * the detection) · a quiet tasks badge (pull) on the right.
 */

export interface ContextStripInfo {
  glyph: string;
  title: string;
  role?: string;
  taskCount?: number;
  onWrong?: () => void;
  onTasks?: () => void;
}

export function SidecarContextStrip(info: ContextStripInfo): HTMLElement {
  const strip = document.createElement('div');
  strip.className = 'sidecar-ctx-strip';

  const glyph = document.createElement('span');
  glyph.className = 'ctxs-glyph';
  glyph.textContent = info.glyph;
  strip.appendChild(glyph);

  const title = document.createElement('b');
  title.className = 'ctxs-title';
  title.textContent = info.title;
  strip.appendChild(title);

  if (info.role) {
    strip.appendChild(dot());
    const role = document.createElement('span');
    role.className = 'ctxs-role';
    role.textContent = info.role;
    strip.appendChild(role);
  }

  if (info.onWrong) {
    strip.appendChild(dot());
    const wrong = document.createElement('span');
    wrong.className = 'ctxs-wrong';
    wrong.textContent = 'wrong?';
    wrong.addEventListener('click', () => info.onWrong!());
    strip.appendChild(wrong);
  }

  if (info.taskCount && info.taskCount > 0) {
    const badge = document.createElement('button');
    badge.type = 'button';
    badge.className = 'ctxs-tasks';
    badge.innerHTML = `✓ <span class="n">${info.taskCount}</span> tasks`;
    if (info.onTasks) badge.addEventListener('click', () => info.onTasks!());
    strip.appendChild(badge);
  }

  return strip;
}

function dot(): HTMLElement {
  const d = document.createElement('span');
  d.className = 'ctxs-dot';
  return d;
}
