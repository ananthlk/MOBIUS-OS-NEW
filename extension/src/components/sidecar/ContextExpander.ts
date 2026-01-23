/**
 * ContextExpander Component
 * 
 * Collapsible section showing detailed context:
 * - Full resolution plan with all steps
 * - Milestone progress
 * - Journey timeline
 * - Payer info from knowledge context
 */

import type { Milestone, KnowledgeContext, PrivacyContext, ResolvedStep } from '../../types/record';
import type { ResolutionPlan } from '../../types';
import { formatLabel, getPossessive } from '../../services/personalization';
import { getRelativeTime } from '../../services/dataHierarchy';

export interface ContextExpanderProps {
  milestones: Milestone[];
  knowledgeContext: KnowledgeContext;
  privacyContext: PrivacyContext;
  resolutionPlan?: ResolutionPlan | null;
  resolvedSteps?: ResolvedStep[];
  defaultExpanded?: boolean;
}

/**
 * Create the ContextExpander element
 */
export function ContextExpander(props: ContextExpanderProps): HTMLElement {
  const { milestones, knowledgeContext, privacyContext, resolutionPlan, resolvedSteps = [], defaultExpanded = false } = props;
  
  const container = document.createElement('div');
  container.className = 'sidecar-context-expander';
  
  // Toggle header
  const header = document.createElement('button');
  header.className = 'sidecar-context-expander-toggle';
  header.innerHTML = `
    <span class="sidecar-context-expander-arrow">${defaultExpanded ? '▾' : '▸'}</span>
    <span class="sidecar-context-expander-label">Prior Runs</span>
  `;
  
  // Content container
  const content = document.createElement('div');
  content.className = 'sidecar-context-expander-content';
  content.style.display = defaultExpanded ? 'block' : 'none';
  
  // Toggle behavior
  header.addEventListener('click', () => {
    const isExpanded = content.style.display !== 'none';
    content.style.display = isExpanded ? 'none' : 'block';
    const arrow = header.querySelector('.sidecar-context-expander-arrow');
    if (arrow) arrow.textContent = isExpanded ? '▸' : '▾';
  });
  
  // Prior Runs section (mock historical visit data)
  const priorRunsSection = createPriorRunsSection();
  content.appendChild(priorRunsSection);
  
  container.appendChild(header);
  container.appendChild(content);
  
  return container;
}

/**
 * Create the Prior Runs section showing historical visit data (mock)
 */
function createPriorRunsSection(): HTMLElement {
  const section = document.createElement('div');
  section.className = 'sidecar-prior-runs-section';
  
  // Mock prior visit data
  const priorRuns = [
    {
      date: 'Jan 8, 2026',
      type: 'Office Visit',
      outcome: 'Paid',
      summary: 'Eligibility issue resolved via phone call to Aetna. Policy confirmed active.',
    },
    {
      date: 'Nov 15, 2025',
      type: 'Lab Work',
      outcome: 'Paid',
      summary: 'Coverage verified automatically. No issues.',
    },
    {
      date: 'Sep 3, 2025',
      type: 'Office Visit',
      outcome: 'Paid (delayed)',
      summary: 'Auth required but not obtained. Resolved with retroactive auth after peer-to-peer.',
    },
  ];
  
  const list = document.createElement('div');
  list.className = 'sidecar-prior-runs-list';
  
  for (const run of priorRuns) {
    const item = document.createElement('div');
    item.className = 'sidecar-prior-run';
    
    item.innerHTML = `
      <div class="sidecar-prior-run-header">
        <span class="sidecar-prior-run-date">${run.date}</span>
        <span class="sidecar-prior-run-type">${run.type}</span>
        <span class="sidecar-prior-run-outcome sidecar-prior-run-outcome--${run.outcome.toLowerCase().includes('paid') ? 'paid' : 'issue'}">${run.outcome}</span>
      </div>
      <div class="sidecar-prior-run-summary">${run.summary}</div>
    `;
    
    list.appendChild(item);
  }
  
  section.appendChild(list);
  return section;
}

/**
 * Create the resolved steps section showing completed tasks
 */
function createResolvedStepsSection(resolvedSteps: ResolvedStep[]): HTMLElement {
  const section = document.createElement('div');
  section.className = 'sidecar-resolved-section';
  
  const title = document.createElement('div');
  title.className = 'sidecar-section-title';
  title.textContent = `Completed (${resolvedSteps.length})`;
  section.appendChild(title);
  
  const list = document.createElement('div');
  list.className = 'sidecar-resolved-list';
  
  for (const step of resolvedSteps) {
    const item = document.createElement('div');
    item.className = 'sidecar-resolved-item';
    
    // Find the selected answer label
    let answerLabel = step.selected_answer || '';
    if (step.answer_options && step.selected_answer) {
      const option = step.answer_options.find(o => o.id === step.selected_answer);
      if (option) answerLabel = option.label;
    }
    
    item.innerHTML = `
      <span class="sidecar-resolved-check">✓</span>
      <span class="sidecar-resolved-text">${step.question_text}</span>
      ${answerLabel ? `<span class="sidecar-resolved-answer">${answerLabel}</span>` : ''}
    `;
    
    list.appendChild(item);
  }
  
  section.appendChild(list);
  return section;
}

/**
 * Create the resolution plan section showing all steps
 */
function createResolutionPlanSection(plan: ResolutionPlan, privacyContext: PrivacyContext): HTMLElement {
  const section = document.createElement('div');
  section.className = 'sidecar-plan-section';
  
  const title = document.createElement('div');
  title.className = 'sidecar-section-title';
  title.textContent = 'Resolution Plan';
  section.appendChild(title);
  
  // Plan summary
  const summary = document.createElement('div');
  summary.className = 'sidecar-plan-summary';
  
  // Show factors progress
  const factorEntries = Object.entries(plan.factors || {});
  if (factorEntries.length > 0) {
    const factorsList = document.createElement('div');
    factorsList.className = 'sidecar-plan-factors';
    
    for (const [factorKey, factor] of factorEntries) {
      const factorEl = document.createElement('div');
      factorEl.className = 'sidecar-plan-factor';
      
      const factorLabel = factorKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      const progress = factor.total > 0 ? Math.round((factor.done / factor.total) * 100) : 0;
      
      factorEl.innerHTML = `
        <span class="sidecar-plan-factor-label">${factorLabel}</span>
        <span class="sidecar-plan-factor-progress">${factor.done}/${factor.total}</span>
        <div class="sidecar-plan-factor-bar">
          <div class="sidecar-plan-factor-fill" style="width: ${progress}%"></div>
        </div>
      `;
      factorsList.appendChild(factorEl);
    }
    
    summary.appendChild(factorsList);
  }
  
  section.appendChild(summary);
  
  // Current step highlight
  if (plan.current_step) {
    const currentStepEl = document.createElement('div');
    currentStepEl.className = 'sidecar-plan-current';
    currentStepEl.innerHTML = `
      <span class="sidecar-plan-current-label">Current:</span>
      <span class="sidecar-plan-current-text">${formatLabel(plan.current_step.question_text, privacyContext)}</span>
    `;
    section.appendChild(currentStepEl);
  }
  
  // Actions count
  if (plan.actions_for_user > 0) {
    const actionsEl = document.createElement('div');
    actionsEl.className = 'sidecar-plan-actions';
    actionsEl.textContent = `${plan.actions_for_user} action${plan.actions_for_user > 1 ? 's' : ''} for you`;
    section.appendChild(actionsEl);
  }
  
  return section;
}

/**
 * Create the milestones progress section
 */
function createMilestonesSection(milestones: Milestone[], privacyContext: PrivacyContext): HTMLElement {
  const section = document.createElement('div');
  section.className = 'sidecar-milestones-section';
  
  const title = document.createElement('div');
  title.className = 'sidecar-section-title';
  title.textContent = 'Progress';
  section.appendChild(title);
  
  const list = document.createElement('div');
  list.className = 'sidecar-milestones-list';
  
  for (const milestone of milestones) {
    const item = createMilestoneItem(milestone, privacyContext);
    list.appendChild(item);
  }
  
  section.appendChild(list);
  return section;
}

/**
 * Create a single milestone item (expandable)
 */
function createMilestoneItem(milestone: Milestone, privacyContext: PrivacyContext): HTMLElement {
  const item = document.createElement('div');
  item.className = `sidecar-milestone sidecar-milestone--${milestone.status}`;
  
  // Status icon
  const statusIcons: Record<string, string> = {
    complete: '✓',
    in_progress: '◐',
    blocked: '✗',
    pending: '○',
  };
  
  // Header (always visible)
  const header = document.createElement('div');
  header.className = 'sidecar-milestone-header';
  
  const icon = document.createElement('span');
  icon.className = 'sidecar-milestone-icon';
  icon.textContent = statusIcons[milestone.status] || '○';
  header.appendChild(icon);
  
  const label = document.createElement('span');
  label.className = 'sidecar-milestone-label';
  label.textContent = formatLabel(milestone.label, privacyContext);
  header.appendChild(label);
  
  // Expand arrow (if has history or substeps)
  const hasDetails = milestone.history.length > 0 || milestone.substeps.length > 0;
  if (hasDetails) {
    const arrow = document.createElement('span');
    arrow.className = 'sidecar-milestone-arrow';
    arrow.textContent = '▸';
    header.appendChild(arrow);
  }
  
  item.appendChild(header);
  
  // Details section (hidden by default)
  if (hasDetails) {
    const details = document.createElement('div');
    details.className = 'sidecar-milestone-details';
    details.style.display = 'none';
    
    // Substeps
    if (milestone.substeps.length > 0) {
      const substepsContainer = document.createElement('div');
      substepsContainer.className = 'sidecar-substeps';
      
      for (const substep of milestone.substeps) {
        const substepEl = document.createElement('div');
        substepEl.className = `sidecar-substep sidecar-substep--${substep.status}`;
        substepEl.innerHTML = `
          <span class="sidecar-substep-icon">${substep.status === 'complete' ? '✓' : substep.status === 'current' ? '●' : '○'}</span>
          <span class="sidecar-substep-label">${substep.label}</span>
        `;
        substepsContainer.appendChild(substepEl);
      }
      
      details.appendChild(substepsContainer);
    }
    
    // History/timeline
    if (milestone.history.length > 0) {
      const timeline = createTimeline(milestone.history);
      details.appendChild(timeline);
    }
    
    item.appendChild(details);
    
    // Toggle behavior
    header.style.cursor = 'pointer';
    header.addEventListener('click', () => {
      const isExpanded = details.style.display !== 'none';
      details.style.display = isExpanded ? 'none' : 'block';
      const arrowEl = header.querySelector('.sidecar-milestone-arrow');
      if (arrowEl) arrowEl.textContent = isExpanded ? '▸' : '▾';
    });
  }
  
  return item;
}

/**
 * Create a timeline from history entries
 */
function createTimeline(history: Milestone['history']): HTMLElement {
  const timeline = document.createElement('div');
  timeline.className = 'sidecar-timeline';
  
  const title = document.createElement('div');
  title.className = 'sidecar-timeline-title';
  title.textContent = 'History';
  timeline.appendChild(title);
  
  for (const entry of history.slice().reverse()) {
    const entryEl = document.createElement('div');
    entryEl.className = 'sidecar-timeline-entry';
    
    // Actor badge
    const actorBadge = document.createElement('span');
    actorBadge.className = `sidecar-timeline-actor sidecar-timeline-actor--${entry.actor}`;
    actorBadge.textContent = entry.actor_name || entry.actor;
    entryEl.appendChild(actorBadge);
    
    // Action text
    const action = document.createElement('span');
    action.className = 'sidecar-timeline-action';
    action.textContent = entry.action;
    entryEl.appendChild(action);
    
    // Timestamp
    const time = document.createElement('span');
    time.className = 'sidecar-timeline-time';
    time.textContent = getRelativeTime(entry.timestamp);
    entryEl.appendChild(time);
    
    // Artifact link (if any)
    if (entry.artifact) {
      const artifact = document.createElement('a');
      artifact.className = 'sidecar-timeline-artifact';
      artifact.textContent = entry.artifact.label;
      if (entry.artifact.url) {
        artifact.href = entry.artifact.url;
        artifact.target = '_blank';
      }
      entryEl.appendChild(artifact);
    }
    
    timeline.appendChild(entryEl);
  }
  
  return timeline;
}

/**
 * Create the payer info section
 */
function createPayerSection(knowledgeContext: KnowledgeContext): HTMLElement {
  const section = document.createElement('div');
  section.className = 'sidecar-payer-section';
  
  const title = document.createElement('div');
  title.className = 'sidecar-section-title';
  title.textContent = 'Payer Info';
  section.appendChild(title);
  
  const info = document.createElement('div');
  info.className = 'sidecar-payer-info';
  
  // Payer name
  const name = document.createElement('div');
  name.className = 'sidecar-payer-name';
  name.textContent = knowledgeContext.payer.name;
  info.appendChild(name);
  
  // Phone (if available)
  if (knowledgeContext.payer.phone) {
    const phone = document.createElement('div');
    phone.className = 'sidecar-payer-phone';
    phone.innerHTML = `📞 <a href="tel:${knowledgeContext.payer.phone}">${knowledgeContext.payer.phone}</a>`;
    info.appendChild(phone);
  }
  
  // Portal URL (if available)
  if (knowledgeContext.payer.portal_url) {
    const portal = document.createElement('div');
    portal.className = 'sidecar-payer-portal';
    portal.innerHTML = `🌐 <a href="${knowledgeContext.payer.portal_url}" target="_blank">Payer Portal</a>`;
    info.appendChild(portal);
  }
  
  // Response time (if available)
  if (knowledgeContext.payer.avg_response_time) {
    const responseTime = document.createElement('div');
    responseTime.className = 'sidecar-payer-response-time';
    responseTime.textContent = `⏱️ Typical response: ${knowledgeContext.payer.avg_response_time}`;
    info.appendChild(responseTime);
  }
  
  section.appendChild(info);
  
  // Policy excerpts (if any)
  if (knowledgeContext.policy_excerpts.length > 0) {
    const excerpts = document.createElement('div');
    excerpts.className = 'sidecar-policy-excerpts';
    
    const excerptsTitle = document.createElement('div');
    excerptsTitle.className = 'sidecar-excerpts-title';
    excerptsTitle.textContent = 'Relevant Policies';
    excerpts.appendChild(excerptsTitle);
    
    for (const excerpt of knowledgeContext.policy_excerpts.slice(0, 3)) {
      const excerptEl = document.createElement('div');
      excerptEl.className = 'sidecar-policy-excerpt';
      excerptEl.innerHTML = `
        <div class="sidecar-excerpt-topic">${excerpt.topic}</div>
        <div class="sidecar-excerpt-content">${excerpt.content}</div>
        <div class="sidecar-excerpt-source">${excerpt.source}</div>
      `;
      excerpts.appendChild(excerptEl);
    }
    
    section.appendChild(excerpts);
  }
  
  return section;
}
