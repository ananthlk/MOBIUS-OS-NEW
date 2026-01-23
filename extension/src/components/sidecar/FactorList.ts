/**
 * FactorList Component
 * 
 * Renders all 5 factors in sequence for the simplified Sidecar.
 * Manages expand/collapse state and coordinates with API.
 */

import { Factor, WorkflowMode, SidecarStateResponse } from '../../types';
import { FactorCard } from './FactorCard';

export interface FactorListProps {
  factors: Factor[];
  onModeSelect: (factorType: string, mode: WorkflowMode) => void;
  onStepAction: (stepId: string, action: 'done' | 'skip' | 'delegate', answerCode?: string) => void;
  onEvidenceClick: (factorType: string) => void;
  onResolve?: (factorType: string, status: 'resolved' | 'unresolved') => void;
  onAddRemedy?: (factorType: string, remedyText: string, outcome: 'worked' | 'partial' | 'failed', notes?: string) => void;
}

interface FactorListState {
  expandedFactors: Set<string>;
}

/**
 * Create the FactorList element
 */
export function FactorList(props: FactorListProps): HTMLElement {
  const { factors, onModeSelect, onStepAction, onEvidenceClick, onResolve, onAddRemedy } = props;
  
  // State: track which factors are expanded
  const state: FactorListState = {
    expandedFactors: new Set<string>(),
  };
  
  // Auto-expand the focus factor
  for (const factor of factors) {
    if (factor.is_focus) {
      state.expandedFactors.add(factor.factor_type);
    }
  }
  
  const container = document.createElement('div');
  container.className = 'factor-list';
  
  // Render all factors
  function render() {
    container.innerHTML = '';
    
    // Sort factors by order
    const sortedFactors = [...factors].sort((a, b) => a.order - b.order);
    
    for (const factor of sortedFactors) {
      const isExpanded = state.expandedFactors.has(factor.factor_type);
      
      const card = FactorCard({
        factor,
        isExpanded,
        onModeSelect,
        onStepAction,
        onEvidenceClick,
        onToggleExpand: (factorType: string) => {
          if (state.expandedFactors.has(factorType)) {
            state.expandedFactors.delete(factorType);
          } else {
            state.expandedFactors.add(factorType);
          }
          render();
        },
        onResolve,
        onAddRemedy,
      });
      
      container.appendChild(card);
      
      // Add separator (except after last item)
      if (factor.order < sortedFactors.length) {
        const separator = document.createElement('div');
        separator.className = 'factor-separator';
        container.appendChild(separator);
      }
    }
  }
  
  render();
  
  return container;
}

/**
 * Update the FactorList with new data
 */
export function updateFactorList(container: HTMLElement, props: FactorListProps): void {
  // Clear and re-render
  const newList = FactorList(props);
  container.innerHTML = '';
  container.appendChild(newList);
}
