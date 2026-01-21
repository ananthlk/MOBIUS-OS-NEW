/**
 * Onboarding Wizard Component for User Awareness Sprint
 * 
 * First-login wizard that captures:
 * - Preferred name
 * - Activities (what the user does)
 * - AI comfort level (deductive questions)
 */

import { getAuthService } from '../../services/auth';

import { API_V1_URL } from '../../config';

const API_BASE = API_V1_URL;

export interface Activity {
  activity_code: string;
  label: string;
  description?: string;
}

export interface OnboardingWizardProps {
  /** User's first name (for greeting) */
  firstName?: string;
  /** User's email */
  email?: string;
  /** Callback when onboarding is completed */
  onComplete: () => void;
  /** Callback when user wants to skip (close) */
  onSkip?: () => void;
}

/**
 * Create the onboarding wizard component
 */
export async function OnboardingWizard(props: OnboardingWizardProps): Promise<HTMLElement> {
  const { firstName, email, onComplete, onSkip } = props;
  
  // Fetch available activities
  let activities: Activity[] = [];
  try {
    const response = await fetch(`${API_BASE}/auth/activities`);
    const data = await response.json();
    if (data.ok) {
      activities = data.activities;
    }
  } catch (error) {
    console.error('[OnboardingWizard] Error fetching activities:', error);
    // Fallback activities
    activities = [
      { activity_code: 'schedule_appointments', label: 'Schedule appointments' },
      { activity_code: 'check_in_patients', label: 'Check in patients' },
      { activity_code: 'verify_eligibility', label: 'Verify eligibility' },
      { activity_code: 'submit_claims', label: 'Submit claims' },
      { activity_code: 'rework_denials', label: 'Rework denied claims' },
      { activity_code: 'prior_authorization', label: 'Handle prior authorizations' },
      { activity_code: 'patient_outreach', label: 'Patient outreach' },
      { activity_code: 'document_notes', label: 'Document clinical notes' },
    ];
  }
  
  const wizard = document.createElement('div');
  wizard.className = 'mobius-onboarding-wizard';
  
  // State
  let currentStep = 0;
  let preferredName = firstName || '';
  const selectedActivities: string[] = [];
  let aiExperienceLevel = 'beginner';
  let autonomyRoutine = 'confirm_first';
  let autonomySensitive = 'confirm_first';
  
  // Render function
  const render = () => {
    wizard.innerHTML = '';
    
    switch (currentStep) {
      case 0:
        renderWelcome();
        break;
      case 1:
        renderActivities();
        break;
      case 2:
        renderAIComfort();
        break;
      case 3:
        renderReady();
        break;
    }
  };
  
  // Step 0: Welcome + Name
  const renderWelcome = () => {
    wizard.innerHTML = `
      <div class="mobius-onboarding-step">
        <div class="mobius-onboarding-progress">
          <div class="mobius-onboarding-progress-bar" style="width: 25%"></div>
        </div>
        <div class="mobius-onboarding-header">
          <h2>Welcome to Mobius!</h2>
          <p>Let's personalize your experience</p>
        </div>
        <div class="mobius-onboarding-content">
          <label class="mobius-onboarding-label">What should we call you?</label>
          <input type="text" class="mobius-onboarding-input" placeholder="Your preferred name" value="${escapeHtml(preferredName)}" />
          <p class="mobius-onboarding-hint">This is how we'll greet you</p>
        </div>
        <div class="mobius-onboarding-actions">
          ${onSkip ? '<button class="mobius-onboarding-btn-text" data-action="skip">Skip for now</button>' : ''}
          <button class="mobius-onboarding-btn-primary" data-action="next">Continue</button>
        </div>
      </div>
    `;
    
    const input = wizard.querySelector('input') as HTMLInputElement;
    input?.addEventListener('input', (e) => {
      preferredName = (e.target as HTMLInputElement).value;
    });
    
    wireActions();
  };
  
  // Step 1: Activities
  const renderActivities = () => {
    wizard.innerHTML = `
      <div class="mobius-onboarding-step">
        <div class="mobius-onboarding-progress">
          <div class="mobius-onboarding-progress-bar" style="width: 50%"></div>
        </div>
        <div class="mobius-onboarding-header">
          <h2>What do you do?</h2>
          <p>Select the activities you work on (you can change this later)</p>
        </div>
        <div class="mobius-onboarding-content">
          <div class="mobius-onboarding-activities">
            ${activities.map(a => `
              <label class="mobius-onboarding-activity ${selectedActivities.includes(a.activity_code) ? 'selected' : ''}">
                <input type="checkbox" value="${a.activity_code}" ${selectedActivities.includes(a.activity_code) ? 'checked' : ''} />
                <span class="mobius-onboarding-activity-check">
                  <svg viewBox="0 0 24 24" width="14" height="14">
                    <path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                  </svg>
                </span>
                <span class="mobius-onboarding-activity-label">${escapeHtml(a.label)}</span>
              </label>
            `).join('')}
          </div>
        </div>
        <div class="mobius-onboarding-actions">
          <button class="mobius-onboarding-btn-text" data-action="back">Back</button>
          <button class="mobius-onboarding-btn-primary" data-action="next">Continue</button>
        </div>
      </div>
    `;
    
    // Wire up checkboxes
    wizard.querySelectorAll('.mobius-onboarding-activity input').forEach((cb) => {
      cb.addEventListener('change', (e) => {
        const code = (e.target as HTMLInputElement).value;
        const checked = (e.target as HTMLInputElement).checked;
        const label = (e.target as HTMLInputElement).closest('.mobius-onboarding-activity');
        
        if (checked) {
          if (!selectedActivities.includes(code)) {
            selectedActivities.push(code);
          }
          label?.classList.add('selected');
        } else {
          const idx = selectedActivities.indexOf(code);
          if (idx > -1) {
            selectedActivities.splice(idx, 1);
          }
          label?.classList.remove('selected');
        }
      });
    });
    
    wireActions();
  };
  
  // Step 2: AI Comfort
  const renderAIComfort = () => {
    wizard.innerHTML = `
      <div class="mobius-onboarding-step">
        <div class="mobius-onboarding-progress">
          <div class="mobius-onboarding-progress-bar" style="width: 75%"></div>
        </div>
        <div class="mobius-onboarding-header">
          <h2>Your preferences</h2>
          <p>Help us understand how you'd like Mobius to work with you</p>
        </div>
        <div class="mobius-onboarding-content">
          <div class="mobius-onboarding-question">
            <label class="mobius-onboarding-qlabel">Have you used AI assistants like ChatGPT before?</label>
            <div class="mobius-onboarding-options">
              <label class="mobius-onboarding-option ${aiExperienceLevel === 'none' ? 'selected' : ''}">
                <input type="radio" name="ai_exp" value="none" ${aiExperienceLevel === 'none' ? 'checked' : ''} />
                <span>Never tried them</span>
              </label>
              <label class="mobius-onboarding-option ${aiExperienceLevel === 'beginner' ? 'selected' : ''}">
                <input type="radio" name="ai_exp" value="beginner" ${aiExperienceLevel === 'beginner' ? 'checked' : ''} />
                <span>A few times</span>
              </label>
              <label class="mobius-onboarding-option ${aiExperienceLevel === 'regular' ? 'selected' : ''}">
                <input type="radio" name="ai_exp" value="regular" ${aiExperienceLevel === 'regular' ? 'checked' : ''} />
                <span>I use them regularly</span>
              </label>
            </div>
          </div>
          
          <div class="mobius-onboarding-question">
            <label class="mobius-onboarding-qlabel">For routine tasks (like checking eligibility), would you want Mobius to...</label>
            <div class="mobius-onboarding-options">
              <label class="mobius-onboarding-option ${autonomyRoutine === 'automatic' ? 'selected' : ''}">
                <input type="radio" name="routine" value="automatic" ${autonomyRoutine === 'automatic' ? 'checked' : ''} />
                <span>Do it automatically and show me the result</span>
              </label>
              <label class="mobius-onboarding-option ${autonomyRoutine === 'confirm_first' ? 'selected' : ''}">
                <input type="radio" name="routine" value="confirm_first" ${autonomyRoutine === 'confirm_first' ? 'checked' : ''} />
                <span>Show me a preview, then I'll confirm</span>
              </label>
              <label class="mobius-onboarding-option ${autonomyRoutine === 'manual' ? 'selected' : ''}">
                <input type="radio" name="routine" value="manual" ${autonomyRoutine === 'manual' ? 'checked' : ''} />
                <span>Just tell me what to do, I'll do it myself</span>
              </label>
            </div>
          </div>
          
          <div class="mobius-onboarding-question">
            <label class="mobius-onboarding-qlabel">What about tasks that affect billing or patient records?</label>
            <div class="mobius-onboarding-options">
              <label class="mobius-onboarding-option ${autonomySensitive === 'automatic' ? 'selected' : ''}">
                <input type="radio" name="sensitive" value="automatic" ${autonomySensitive === 'automatic' ? 'checked' : ''} />
                <span>Same as above - automatic is fine</span>
              </label>
              <label class="mobius-onboarding-option ${autonomySensitive === 'confirm_first' ? 'selected' : ''}">
                <input type="radio" name="sensitive" value="confirm_first" ${autonomySensitive === 'confirm_first' ? 'checked' : ''} />
                <span>Always show me before taking action</span>
              </label>
              <label class="mobius-onboarding-option ${autonomySensitive === 'manual' ? 'selected' : ''}">
                <input type="radio" name="sensitive" value="manual" ${autonomySensitive === 'manual' ? 'checked' : ''} />
                <span>Never act without my explicit approval</span>
              </label>
            </div>
          </div>
        </div>
        <div class="mobius-onboarding-actions">
          <button class="mobius-onboarding-btn-text" data-action="back">Back</button>
          <button class="mobius-onboarding-btn-primary" data-action="next">Continue</button>
        </div>
      </div>
    `;
    
    // Wire up radio buttons
    wizard.querySelectorAll('input[name="ai_exp"]').forEach(r => {
      r.addEventListener('change', (e) => {
        aiExperienceLevel = (e.target as HTMLInputElement).value;
        updateRadioStyles('ai_exp');
      });
    });
    
    wizard.querySelectorAll('input[name="routine"]').forEach(r => {
      r.addEventListener('change', (e) => {
        autonomyRoutine = (e.target as HTMLInputElement).value;
        updateRadioStyles('routine');
      });
    });
    
    wizard.querySelectorAll('input[name="sensitive"]').forEach(r => {
      r.addEventListener('change', (e) => {
        autonomySensitive = (e.target as HTMLInputElement).value;
        updateRadioStyles('sensitive');
      });
    });
    
    wireActions();
  };
  
  // Step 3: Ready
  const renderReady = () => {
    wizard.innerHTML = `
      <div class="mobius-onboarding-step">
        <div class="mobius-onboarding-progress">
          <div class="mobius-onboarding-progress-bar" style="width: 100%"></div>
        </div>
        <div class="mobius-onboarding-header">
          <h2>You're all set, ${escapeHtml(preferredName || 'there')}!</h2>
          <p>Mobius will personalize your experience based on your preferences</p>
        </div>
        <div class="mobius-onboarding-content">
          <div class="mobius-onboarding-summary">
            <div class="mobius-onboarding-summary-item">
              <strong>Your activities:</strong>
              <span>${selectedActivities.length > 0 
                ? selectedActivities.map(c => activities.find(a => a.activity_code === c)?.label || c).join(', ')
                : 'None selected'}</span>
            </div>
            <div class="mobius-onboarding-summary-item">
              <strong>Routine tasks:</strong>
              <span>${autonomyRoutine === 'automatic' ? 'Automatic' : autonomyRoutine === 'confirm_first' ? 'Ask first' : 'Manual'}</span>
            </div>
            <div class="mobius-onboarding-summary-item">
              <strong>Sensitive tasks:</strong>
              <span>${autonomySensitive === 'automatic' ? 'Automatic' : autonomySensitive === 'confirm_first' ? 'Ask first' : 'Manual'}</span>
            </div>
          </div>
          <p class="mobius-onboarding-hint">You can change these settings anytime from the menu</p>
        </div>
        <div class="mobius-onboarding-actions">
          <button class="mobius-onboarding-btn-text" data-action="back">Back</button>
          <button class="mobius-onboarding-btn-primary" data-action="finish">Get Started</button>
        </div>
      </div>
    `;
    
    wireActions();
  };
  
  // Update radio styles
  const updateRadioStyles = (name: string) => {
    wizard.querySelectorAll(`input[name="${name}"]`).forEach(r => {
      const label = (r as HTMLInputElement).closest('.mobius-onboarding-option');
      if ((r as HTMLInputElement).checked) {
        label?.classList.add('selected');
      } else {
        label?.classList.remove('selected');
      }
    });
  };
  
  // Wire up action buttons
  const wireActions = () => {
    wizard.querySelector('[data-action="skip"]')?.addEventListener('click', () => {
      onSkip?.();
    });
    
    wizard.querySelector('[data-action="back"]')?.addEventListener('click', () => {
      currentStep--;
      render();
    });
    
    wizard.querySelector('[data-action="next"]')?.addEventListener('click', () => {
      currentStep++;
      render();
    });
    
    wizard.querySelector('[data-action="finish"]')?.addEventListener('click', async () => {
      // Submit onboarding data
      try {
        const authService = getAuthService();
        const token = await authService.getAccessToken();
        
        if (token) {
          const response = await fetch(`${API_BASE}/auth/onboarding`, {
            method: 'PUT',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              preferred_name: preferredName,
              activities: selectedActivities,
              ai_experience_level: aiExperienceLevel,
              autonomy_routine_tasks: autonomyRoutine,
              autonomy_sensitive_tasks: autonomySensitive,
            }),
          });
          
          if (response.ok) {
            console.log('[OnboardingWizard] Onboarding completed');
          }
        }
      } catch (error) {
        console.error('[OnboardingWizard] Error saving onboarding:', error);
      }
      
      onComplete();
    });
  };
  
  // Initial render
  render();
  
  return wizard;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * CSS styles for onboarding wizard
 */
export const ONBOARDING_STYLES = `
.mobius-onboarding-wizard {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.mobius-onboarding-step {
  background: white;
  border-radius: 16px;
  width: 90%;
  max-width: 400px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.mobius-onboarding-progress {
  height: 3px;
  background: #e2e8f0;
  border-radius: 3px 3px 0 0;
  overflow: hidden;
}

.mobius-onboarding-progress-bar {
  height: 100%;
  background: #3b82f6;
  transition: width 0.3s;
}

.mobius-onboarding-header {
  padding: 20px 20px 0;
  text-align: center;
}

.mobius-onboarding-header h2 {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 600;
  color: #0b1220;
}

.mobius-onboarding-header p {
  margin: 0;
  font-size: 12px;
  color: #64748b;
}

.mobius-onboarding-content {
  padding: 20px;
}

.mobius-onboarding-label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

.mobius-onboarding-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  box-sizing: border-box;
}

.mobius-onboarding-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.mobius-onboarding-hint {
  margin: 8px 0 0;
  font-size: 10px;
  color: #94a3b8;
}

/* Activities */
.mobius-onboarding-activities {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.mobius-onboarding-activity {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.mobius-onboarding-activity:hover {
  background: #f1f5f9;
}

.mobius-onboarding-activity.selected {
  background: #eff6ff;
  border-color: #3b82f6;
}

.mobius-onboarding-activity input {
  display: none;
}

.mobius-onboarding-activity-check {
  width: 16px;
  height: 16px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.mobius-onboarding-activity.selected .mobius-onboarding-activity-check {
  background: #3b82f6;
  border-color: #3b82f6;
}

.mobius-onboarding-activity-label {
  font-size: 11px;
  color: #374151;
}

/* Questions */
.mobius-onboarding-question {
  margin-bottom: 16px;
}

.mobius-onboarding-question:last-child {
  margin-bottom: 0;
}

.mobius-onboarding-qlabel {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 8px;
}

.mobius-onboarding-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mobius-onboarding-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.mobius-onboarding-option:hover {
  background: #f1f5f9;
}

.mobius-onboarding-option.selected {
  background: #eff6ff;
  border-color: #3b82f6;
}

.mobius-onboarding-option input {
  display: none;
}

.mobius-onboarding-option span {
  font-size: 11px;
  color: #374151;
}

/* Summary */
.mobius-onboarding-summary {
  background: #f8fafc;
  border-radius: 8px;
  padding: 12px;
}

.mobius-onboarding-summary-item {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  padding: 6px 0;
  border-bottom: 1px solid #e2e8f0;
}

.mobius-onboarding-summary-item:last-child {
  border-bottom: none;
}

.mobius-onboarding-summary-item strong {
  color: #374151;
}

.mobius-onboarding-summary-item span {
  color: #64748b;
}

/* Actions */
.mobius-onboarding-actions {
  display: flex;
  justify-content: space-between;
  padding: 16px 20px 20px;
  gap: 12px;
}

.mobius-onboarding-btn-primary {
  flex: 1;
  padding: 10px 16px;
  background: #3b82f6;
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
}

.mobius-onboarding-btn-primary:hover {
  background: #2563eb;
}

.mobius-onboarding-btn-text {
  padding: 10px 16px;
  background: none;
  border: none;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
}

.mobius-onboarding-btn-text:hover {
  color: #374151;
}
`;
