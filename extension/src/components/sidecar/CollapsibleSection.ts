/**
 * CollapsibleSection Component
 *
 * Standard panel chrome for the expanded sidecar: an uppercase label
 * header with a chevron, an optional one-line summary shown while
 * collapsed, and a body that expands/collapses with a height transition.
 *
 * Collapse state is persisted per section id in chrome.storage.local so
 * the layout survives reloads. Styling comes from sidebar.css classes
 * (`sidecar-panel*`), which consume the --mobius-* design tokens
 * (mobius-design/tokens.css via the theme system).
 */

const STORAGE_KEY = 'mobius.ui.collapsedSections';

export interface CollapsibleSectionProps {
  /** Stable id used as the persistence key (e.g. "patient", "plan"). */
  id: string;
  /** Section label, rendered uppercase in the header. */
  label: string;
  /** Optional one-line summary shown in the header while collapsed. */
  summary?: string;
  /** The section's content element. */
  content: HTMLElement;
  /** Start collapsed when no persisted preference exists. */
  defaultCollapsed?: boolean;
}

function loadCollapsedMap(): Promise<Record<string, boolean>> {
  return new Promise((resolve) => {
    chrome.storage.local.get([STORAGE_KEY], (items) => {
      const map = items?.[STORAGE_KEY];
      resolve(map && typeof map === 'object' ? (map as Record<string, boolean>) : {});
    });
  });
}

function saveCollapsed(id: string, collapsed: boolean): void {
  chrome.storage.local.get([STORAGE_KEY], (items) => {
    const map =
      items?.[STORAGE_KEY] && typeof items[STORAGE_KEY] === 'object'
        ? (items[STORAGE_KEY] as Record<string, boolean>)
        : {};
    map[id] = collapsed;
    chrome.storage.local.set({ [STORAGE_KEY]: map });
  });
}

export function CollapsibleSection(props: CollapsibleSectionProps): HTMLElement {
  const { id, label, summary, content, defaultCollapsed } = props;

  const panel = document.createElement('section');
  panel.className = 'sidecar-panel';
  panel.dataset.panelId = id;

  const header = document.createElement('button');
  header.type = 'button';
  header.className = 'sidecar-panel-header';
  header.setAttribute('aria-expanded', 'true');

  const chevron = document.createElement('span');
  chevron.className = 'sidecar-panel-chevron';
  chevron.innerHTML =
    '<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M7.41 8.59 12 13.17l4.59-4.58L18 10l-6 6-6-6z"/></svg>';

  const labelEl = document.createElement('span');
  labelEl.className = 'sidecar-panel-label';
  labelEl.textContent = label;

  const summaryEl = document.createElement('span');
  summaryEl.className = 'sidecar-panel-summary';
  if (summary) summaryEl.textContent = summary;

  header.appendChild(chevron);
  header.appendChild(labelEl);
  header.appendChild(summaryEl);

  const body = document.createElement('div');
  body.className = 'sidecar-panel-body';
  body.appendChild(content);

  panel.appendChild(header);
  panel.appendChild(body);

  const apply = (collapsed: boolean) => {
    panel.classList.toggle('collapsed', collapsed);
    header.setAttribute('aria-expanded', String(!collapsed));
  };

  let collapsed = Boolean(defaultCollapsed);
  apply(collapsed);
  void loadCollapsedMap().then((map) => {
    if (id in map) {
      collapsed = Boolean(map[id]);
      apply(collapsed);
    }
  });

  header.addEventListener('click', () => {
    collapsed = !collapsed;
    apply(collapsed);
    saveCollapsed(id, collapsed);
  });

  return panel;
}

/** Update the collapsed-state summary line after the fact. */
export function setSectionSummary(panel: HTMLElement, summary: string): void {
  const el = panel.querySelector('.sidecar-panel-summary');
  if (el) el.textContent = summary;
}
