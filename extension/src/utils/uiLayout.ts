/**
 * Client-side dynamic layout helpers.
 *
 * Modes can build per-section ordered lists of component instances (including multiple of the same key).
 * The app renders these instances via a registry of component factories.
 */

import type { UiComponentKey, UiVisibilityDefaults } from '../types';

export type SectionId = 'header' | 'context' | 'tasks' | 'chat' | 'footer';

export type ComponentInstance = {
  /** Unique per instance; used for incremental updates later if needed. */
  id: string;
  key: UiComponentKey;
  props?: any;
};

export type ModeLayout = Record<SectionId, ComponentInstance[]>;

export type ComponentFactory = (props: any) => HTMLElement;
export type ComponentRegistry = Partial<Record<UiComponentKey, ComponentFactory>>;

export function renderSection(
  mount: HTMLElement,
  instances: ComponentInstance[],
  visibility: UiVisibilityDefaults,
  registry: ComponentRegistry
) {
  mount.innerHTML = '';

  for (const inst of instances) {
    if (visibility[inst.key] === false) continue;
    const factory = registry[inst.key];
    if (!factory) continue;

    const el = factory(inst.props ?? {});
    el.dataset.instanceId = inst.id;
    el.dataset.componentKey = inst.key;
    mount.appendChild(el);
  }
}

