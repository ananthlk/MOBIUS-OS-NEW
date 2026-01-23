/**
 * Unit tests for FactorCard component
 * 
 * Tests the DOM rendering and interaction behavior of the FactorCard component
 * used in the simplified Sidecar UI.
 */

import { FactorCard, FactorCardProps } from '../../../extension/src/components/sidecar/FactorCard';
import { Factor, FactorStep, WorkflowMode } from '../../../extension/src/types';

// =============================================================================
// Test Helpers
// =============================================================================

/**
 * Create a mock Factor for testing
 */
function createMockFactor(overrides: Partial<Factor> = {}): Factor {
  return {
    factor_type: 'eligibility',
    label: 'ELIGIBILITY',
    order: 2,
    status: 'blocked',
    status_label: 'Blocked',
    is_focus: false,
    recommendation: {
      mode: 'together',
      confidence: 0.8,
      reason: '1 of 2 steps can be automated'
    },
    mode: null,
    steps: [],
    evidence_count: 0,
    ...overrides
  };
}

/**
 * Create a mock FactorStep for testing
 */
function createMockStep(overrides: Partial<FactorStep> = {}): FactorStep {
  return {
    step_id: 'step_1',
    label: 'Verify insurance is active',
    status: 'pending',
    can_system_handle: true,
    assignee_type: 'mobius',
    assignee_icon: '🤖',
    is_user_turn: false,
    rationale: undefined,
    ...overrides
  };
}

/**
 * Create default props for FactorCard
 */
function createDefaultProps(overrides: Partial<FactorCardProps> = {}): FactorCardProps {
  return {
    factor: createMockFactor(),
    isExpanded: false,
    onModeSelect: jest.fn(),
    onStepAction: jest.fn(),
    onEvidenceClick: jest.fn(),
    onToggleExpand: jest.fn(),
    ...overrides
  };
}

// =============================================================================
// Test Suite
// =============================================================================

describe('FactorCard', () => {
  
  describe('Rendering', () => {
    
    it('renders factor label and status', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          label: 'ELIGIBILITY',
          status_label: 'Blocked'
        })
      });
      
      const card = FactorCard(props);
      
      // Check label is rendered
      const label = card.querySelector('.factor-label');
      expect(label).not.toBeNull();
      expect(label?.textContent).toBe('ELIGIBILITY');
      
      // Check status label is rendered
      const statusLabel = card.querySelector('.factor-status-label');
      expect(statusLabel).not.toBeNull();
      expect(statusLabel?.textContent).toContain('Blocked');
    });
    
    it('shows focus badge when is_focus=true', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          is_focus: true
        })
      });
      
      const card = FactorCard(props);
      
      // Check focus badge is present
      const focusBadge = card.querySelector('.factor-focus-badge');
      expect(focusBadge).not.toBeNull();
      expect(focusBadge?.textContent).toContain('YOUR FOCUS');
      
      // Check focus class is applied
      expect(card.classList.contains('factor-focus')).toBe(true);
    });
    
    it('does not show focus badge when is_focus=false', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          is_focus: false
        })
      });
      
      const card = FactorCard(props);
      
      const focusBadge = card.querySelector('.factor-focus-badge');
      expect(focusBadge).toBeNull();
    });
    
    it('renders mode selector when expanded and blocked', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked'
        }),
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      // Check mode selector is present
      const modeSelector = card.querySelector('.factor-mode-selector');
      expect(modeSelector).not.toBeNull();
      
      // Check all three mode buttons are present
      const modeButtons = card.querySelectorAll('.mode-btn');
      expect(modeButtons.length).toBe(3);
    });
    
    it('does not render mode selector when collapsed', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked'
        }),
        isExpanded: false
      });
      
      const card = FactorCard(props);
      
      const modeSelector = card.querySelector('.factor-mode-selector');
      expect(modeSelector).toBeNull();
    });
    
    it('does not render mode selector when resolved', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'resolved'
        }),
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      const modeSelector = card.querySelector('.factor-mode-selector');
      expect(modeSelector).toBeNull();
    });
    
    it('renders steps with correct assignee icons', () => {
      const steps: FactorStep[] = [
        createMockStep({
          step_id: 'step_1',
          assignee_type: 'mobius',
          assignee_icon: '🤖'
        }),
        createMockStep({
          step_id: 'step_2',
          assignee_type: 'user',
          assignee_icon: '👤'
        })
      ];
      
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked',
          steps
        }),
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      const stepIcons = card.querySelectorAll('.step-icon');
      expect(stepIcons.length).toBe(2);
      expect(stepIcons[0].textContent).toBe('🤖');
      expect(stepIcons[1].textContent).toBe('👤');
    });
    
    it('shows YOUR TURN for user steps that are current', () => {
      const steps: FactorStep[] = [
        createMockStep({
          step_id: 'step_1',
          status: 'current',
          is_user_turn: true,
          assignee_type: 'user',
          assignee_icon: '👤'
        })
      ];
      
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked',
          mode: 'together',
          steps
        }),
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      const stepStatus = card.querySelector('.step-status');
      expect(stepStatus).not.toBeNull();
      expect(stepStatus?.textContent).toContain('YOUR TURN');
    });
    
    it('shows mobius status when mode=mobius', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked',
          mode: 'mobius'
        }),
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      const mobiusStatus = card.querySelector('.factor-mobius-status');
      expect(mobiusStatus).not.toBeNull();
      expect(mobiusStatus?.textContent).toContain('Mobius is handling this');
    });
    
  });
  
  describe('Interactions', () => {
    
    it('calls onModeSelect when mode button clicked', () => {
      const onModeSelect = jest.fn();
      
      const props = createDefaultProps({
        factor: createMockFactor({
          factor_type: 'eligibility',
          status: 'blocked'
        }),
        isExpanded: true,
        onModeSelect
      });
      
      const card = FactorCard(props);
      
      // Find and click the mobius mode button
      const modeButtons = card.querySelectorAll('.mode-btn');
      const mobiusBtn = modeButtons[0] as HTMLButtonElement;
      mobiusBtn.click();
      
      expect(onModeSelect).toHaveBeenCalledTimes(1);
      expect(onModeSelect).toHaveBeenCalledWith('eligibility', 'mobius');
    });
    
    it('calls onToggleExpand when header clicked', () => {
      const onToggleExpand = jest.fn();
      
      const props = createDefaultProps({
        factor: createMockFactor({
          factor_type: 'coverage'
        }),
        onToggleExpand
      });
      
      const card = FactorCard(props);
      
      const header = card.querySelector('.factor-header') as HTMLElement;
      header.click();
      
      expect(onToggleExpand).toHaveBeenCalledTimes(1);
      expect(onToggleExpand).toHaveBeenCalledWith('coverage');
    });
    
    it('calls onEvidenceClick when evidence link clicked', () => {
      const onEvidenceClick = jest.fn();
      
      const props = createDefaultProps({
        factor: createMockFactor({
          factor_type: 'eligibility',
          status: 'blocked',
          evidence_count: 3
        }),
        isExpanded: true,
        onEvidenceClick
      });
      
      const card = FactorCard(props);
      
      const evidenceLink = card.querySelector('.factor-evidence-link') as HTMLElement;
      evidenceLink.click();
      
      expect(onEvidenceClick).toHaveBeenCalledTimes(1);
      expect(onEvidenceClick).toHaveBeenCalledWith('eligibility');
    });
    
    it('calls onStepAction when step done button clicked', () => {
      const onStepAction = jest.fn();
      
      const steps: FactorStep[] = [
        createMockStep({
          step_id: 'test_step_123',
          status: 'current',
          is_user_turn: true,
          assignee_type: 'user'
        })
      ];
      
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked',
          mode: 'together',
          steps
        }),
        isExpanded: true,
        onStepAction
      });
      
      const card = FactorCard(props);
      
      const doneBtn = card.querySelector('.done-btn') as HTMLButtonElement;
      doneBtn.click();
      
      expect(onStepAction).toHaveBeenCalledTimes(1);
      expect(onStepAction).toHaveBeenCalledWith('test_step_123', 'done');
    });
    
  });
  
  describe('Status Classes', () => {
    
    it('applies factor-resolved class for resolved status', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'resolved'
        })
      });
      
      const card = FactorCard(props);
      
      expect(card.classList.contains('factor-resolved')).toBe(true);
    });
    
    it('applies factor-blocked class for blocked status', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked'
        })
      });
      
      const card = FactorCard(props);
      
      expect(card.classList.contains('factor-blocked')).toBe(true);
    });
    
    it('applies factor-waiting class for waiting status', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'waiting'
        })
      });
      
      const card = FactorCard(props);
      
      expect(card.classList.contains('factor-waiting')).toBe(true);
    });
    
    it('applies expanded class when isExpanded=true', () => {
      const props = createDefaultProps({
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      expect(card.classList.contains('expanded')).toBe(true);
      expect(card.classList.contains('collapsed')).toBe(false);
    });
    
    it('applies collapsed class when isExpanded=false', () => {
      const props = createDefaultProps({
        isExpanded: false
      });
      
      const card = FactorCard(props);
      
      expect(card.classList.contains('collapsed')).toBe(true);
      expect(card.classList.contains('expanded')).toBe(false);
    });
    
  });
  
  describe('Status Icons', () => {
    
    it('shows checkmark icon for resolved status', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'resolved'
        })
      });
      
      const card = FactorCard(props);
      
      const icon = card.querySelector('.factor-status-icon');
      expect(icon?.textContent).toBe('✓');
    });
    
    it('shows warning icon for blocked status', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked'
        })
      });
      
      const card = FactorCard(props);
      
      const icon = card.querySelector('.factor-status-icon');
      expect(icon?.textContent).toBe('⚠️');
    });
    
    it('shows circle icon for waiting status', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'waiting'
        })
      });
      
      const card = FactorCard(props);
      
      const icon = card.querySelector('.factor-status-icon');
      expect(icon?.textContent).toBe('◯');
    });
    
  });
  
  describe('Evidence Section', () => {
    
    it('shows evidence link when evidence_count > 0', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked',
          evidence_count: 5
        }),
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      const evidenceLink = card.querySelector('.factor-evidence-link');
      expect(evidenceLink).not.toBeNull();
      expect(evidenceLink?.textContent).toContain('5 facts');
    });
    
    it('does not show evidence link when evidence_count is 0', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked',
          evidence_count: 0
        }),
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      const evidenceLink = card.querySelector('.factor-evidence-link');
      expect(evidenceLink).toBeNull();
    });
    
  });
  
  describe('Recommendation Display', () => {
    
    it('shows recommendation when expanded and blocked', () => {
      const props = createDefaultProps({
        factor: createMockFactor({
          status: 'blocked',
          recommendation: {
            mode: 'mobius',
            confidence: 0.95,
            reason: 'All steps can be automated'
          }
        }),
        isExpanded: true
      });
      
      const card = FactorCard(props);
      
      const recommendation = card.querySelector('.factor-recommendation');
      expect(recommendation).not.toBeNull();
      expect(recommendation?.textContent).toContain('Recommended');
      expect(recommendation?.textContent).toContain('95%');
    });
    
  });
  
});
