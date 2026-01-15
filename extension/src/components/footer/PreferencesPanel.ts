/**
 * PreferencesPanel Component
 * User preferences (LLM choice, Agent mode)
 */

export type LLMChoice = 'Gemini' | 'GPT-4' | 'Claude';
export type AgentMode = 'Agentic' | 'Co-pilot' | 'Manual';

export interface PreferencesPanelProps {
  llmChoice: LLMChoice;
  agentMode: AgentMode;
  onLLMChange: (llm: LLMChoice) => void;
  onAgentModeChange: (mode: AgentMode) => void;
  isExpanded?: boolean;
}

export function PreferencesPanel({
  llmChoice,
  agentMode,
  onLLMChange,
  onAgentModeChange,
  isExpanded = false
}: PreferencesPanelProps): HTMLElement {
  const panel = document.createElement('div');
  panel.className = 'preferences-panel';

  const row = document.createElement('div');
  row.className = 'preferences';
  
  // Collapsed view
  const llmItem = document.createElement('div');
  llmItem.className = 'preference-item';
  const llmValue = document.createElement('span');
  llmValue.className = 'pref-value';
  llmValue.textContent = llmChoice;
  const llmArrow = document.createElement('span');
  llmArrow.id = 'prefArrow';
  llmArrow.textContent = isExpanded ? '▲' : '▼';
  llmItem.appendChild(llmValue);
  llmItem.appendChild(llmArrow);
  
  const agentItem = document.createElement('div');
  agentItem.className = 'preference-item';
  const agentValue = document.createElement('span');
  agentValue.className = 'pref-value';
  agentValue.textContent = agentMode;
  agentItem.appendChild(agentValue);
  
  // Expanded view
  const expanded = document.createElement('div');
  expanded.className = `preferences-expanded ${isExpanded ? 'show' : ''}`;
  expanded.id = 'preferencesExpanded';
  
  const llmGroup = document.createElement('div');
  llmGroup.className = 'preference-group';
  const llmSelect = document.createElement('select');
  llmSelect.setAttribute('aria-label', 'LLM');
  const llmOptions: LLMChoice[] = ['Gemini', 'GPT-4', 'Claude'];
  llmOptions.forEach(option => {
    const opt = document.createElement('option');
    opt.value = option;
    opt.textContent = option;
    if (option === llmChoice) opt.selected = true;
    llmSelect.appendChild(opt);
  });
  llmSelect.addEventListener('change', () => {
    onLLMChange(llmSelect.value as LLMChoice);
  });
  llmGroup.appendChild(llmSelect);
  
  const agentGroup = document.createElement('div');
  agentGroup.className = 'preference-group';
  const agentSelect = document.createElement('select');
  agentSelect.setAttribute('aria-label', 'Agent mode');
  const agentOptions: AgentMode[] = ['Agentic', 'Co-pilot', 'Manual'];
  agentOptions.forEach(option => {
    const opt = document.createElement('option');
    opt.value = option;
    opt.textContent = option;
    if (option === agentMode) opt.selected = true;
    agentSelect.appendChild(opt);
  });
  agentSelect.addEventListener('change', () => {
    onAgentModeChange(agentSelect.value as AgentMode);
  });
  agentGroup.appendChild(agentSelect);
  
  expanded.appendChild(llmGroup);
  expanded.appendChild(agentGroup);
  
  const togglePreferences = () => {
    const newExpanded = !expanded.classList.contains('show');
    expanded.classList.toggle('show');
    llmArrow.textContent = newExpanded ? '▲' : '▼';
  };
  
  llmItem.addEventListener('click', togglePreferences);
  agentItem.addEventListener('click', togglePreferences);
  
  row.appendChild(llmItem);
  row.appendChild(agentItem);

  panel.appendChild(row);
  panel.appendChild(expanded);
  return panel;
}
