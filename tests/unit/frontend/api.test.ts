/**
 * Unit tests for Sidecar API functions
 * 
 * Tests the setFactorMode and fetchEvidence API functions used by the
 * simplified Sidecar UI.
 */

import { setFactorMode, fetchEvidence, SetFactorModeResponse, GetEvidenceResponse } from '../../../extension/src/services/api';

// =============================================================================
// Mock Setup
// =============================================================================

// Mock chrome.storage for auth service
const mockStorage: { [key: string]: any } = {};
global.chrome = {
  storage: {
    local: {
      get: (keys: string[], callback: (result: { [key: string]: any }) => void) => {
        const result: { [key: string]: any } = {};
        keys.forEach(key => {
          result[key] = mockStorage[key] || null;
        });
        callback(result);
      },
      set: (items: { [key: string]: any }, callback?: () => void) => {
        Object.assign(mockStorage, items);
        if (callback) callback();
      }
    }
  }
} as any;

// Mock fetch
global.fetch = jest.fn();

// Mock getAuthService
jest.mock('../../../extension/src/services/auth', () => ({
  getAuthService: () => ({
    getAccessToken: jest.fn().mockResolvedValue('mock-access-token')
  })
}));

// =============================================================================
// Test Suite: setFactorMode
// =============================================================================

describe('setFactorMode', () => {
  const apiBaseUrl = 'http://localhost:5001/api/v1';
  
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  it('calls POST /sidecar/factor-mode with correct payload', async () => {
    const mockResponse: SetFactorModeResponse = {
      ok: true,
      factor_type: 'eligibility',
      mode: 'mobius',
      steps_updated: 3,
      assignments: [
        { step_id: 'step_1', assignee_type: 'mobius' },
        { step_id: 'step_2', assignee_type: 'mobius' },
        { step_id: 'step_3', assignee_type: 'mobius' }
      ]
    };
    
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });
    
    const result = await setFactorMode('demo_001', 'eligibility', 'mobius');
    
    // Verify fetch was called with correct URL
    expect(global.fetch).toHaveBeenCalledWith(
      `${apiBaseUrl}/sidecar/factor-mode`,
      expect.objectContaining({
        method: 'POST'
      })
    );
    
    // Verify request body
    const callArgs = (global.fetch as jest.Mock).mock.calls[0];
    const requestBody = JSON.parse(callArgs[1].body);
    expect(requestBody).toEqual({
      patient_key: 'demo_001',
      factor_type: 'eligibility',
      mode: 'mobius'
    });
    
    // Verify response
    expect(result).toEqual(mockResponse);
    expect(result.ok).toBe(true);
    expect(result.mode).toBe('mobius');
    expect(result.steps_updated).toBe(3);
  });
  
  it('includes authorization header', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ok: true, factor_type: 'eligibility', mode: 'together', steps_updated: 2, assignments: [] })
    });
    
    await setFactorMode('demo_001', 'eligibility', 'together');
    
    const callArgs = (global.fetch as jest.Mock).mock.calls[0];
    const headers = callArgs[1].headers;
    
    expect(headers.get('Authorization')).toBe('Bearer mock-access-token');
    expect(headers.get('Content-Type')).toBe('application/json');
  });
  
  it('throws error on non-ok response', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ ok: false, error: 'Invalid mode' })
    });
    
    await expect(
      setFactorMode('demo_001', 'eligibility', 'invalid' as any)
    ).rejects.toThrow('Invalid mode');
  });
  
  it('handles network errors', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(
      new Error('Network error')
    );
    
    await expect(
      setFactorMode('demo_001', 'eligibility', 'mobius')
    ).rejects.toThrow('Network error');
  });
  
  it('sends correct mode values', async () => {
    const modes: Array<'mobius' | 'together' | 'manual'> = ['mobius', 'together', 'manual'];
    const mockFetch = global.fetch as jest.Mock;
    
    for (const mode of modes) {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true, factor_type: 'eligibility', mode, steps_updated: 1, assignments: [] })
      });
      
      await setFactorMode('demo_001', 'eligibility', mode);
      
      const callArgs = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
      const requestBody = JSON.parse(callArgs[1].body);
      expect(requestBody.mode).toBe(mode);
    }
  });
  
  it('returns assignments array with step assignees', async () => {
    const mockResponse: SetFactorModeResponse = {
      ok: true,
      factor_type: 'coverage',
      mode: 'together',
      steps_updated: 2,
      assignments: [
        { step_id: 'step_auto', assignee_type: 'mobius' },
        { step_id: 'step_manual', assignee_type: 'user' }
      ]
    };
    
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });
    
    const result = await setFactorMode('demo_001', 'coverage', 'together');
    
    expect(result.assignments).toHaveLength(2);
    expect(result.assignments[0].assignee_type).toBe('mobius');
    expect(result.assignments[1].assignee_type).toBe('user');
  });
  
});

// =============================================================================
// Test Suite: fetchEvidence
// =============================================================================

describe('fetchEvidence', () => {
  const apiBaseUrl = 'http://localhost:5001/api/v1';
  
  beforeEach(() => {
    jest.clearAllMocks();
  });
  
  it('calls GET /sidecar/evidence with query params', async () => {
    const mockResponse: GetEvidenceResponse = {
      ok: true,
      factor_type: 'eligibility',
      evidence: [],
      count: 0
    };
    
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });
    
    await fetchEvidence('demo_001', 'eligibility');
    
    // Verify fetch was called with correct URL including query params
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining(`${apiBaseUrl}/sidecar/evidence`),
      expect.objectContaining({
        method: 'GET'
      })
    );
    
    // Check query params
    const callUrl = (global.fetch as jest.Mock).mock.calls[0][0];
    expect(callUrl).toContain('patient_key=demo_001');
    expect(callUrl).toContain('factor=eligibility');
  });
  
  it('handles optional factor and step_id params', async () => {
    // Test with only patient_key (no factor or step_id)
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ok: true, factor_type: null, evidence: [], count: 0 })
    });
    
    await fetchEvidence('demo_001');
    
    let callUrl = (global.fetch as jest.Mock).mock.calls[0][0];
    expect(callUrl).toContain('patient_key=demo_001');
    expect(callUrl).not.toContain('factor=');
    expect(callUrl).not.toContain('step_id=');
    
    // Test with step_id
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ok: true, factor_type: null, evidence: [], count: 0 })
    });
    
    await fetchEvidence('demo_001', undefined, 'step_123');
    
    callUrl = (global.fetch as jest.Mock).mock.calls[1][0];
    expect(callUrl).toContain('patient_key=demo_001');
    expect(callUrl).toContain('step_id=step_123');
    expect(callUrl).not.toContain('factor=');
    
    // Test with both factor and step_id
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ok: true, factor_type: 'eligibility', evidence: [], count: 0 })
    });
    
    await fetchEvidence('demo_001', 'eligibility', 'step_456');
    
    callUrl = (global.fetch as jest.Mock).mock.calls[2][0];
    expect(callUrl).toContain('patient_key=demo_001');
    expect(callUrl).toContain('factor=eligibility');
    expect(callUrl).toContain('step_id=step_456');
  });
  
  it('returns evidence array with source info', async () => {
    const mockResponse: GetEvidenceResponse = {
      ok: true,
      factor_type: 'eligibility',
      evidence: [
        {
          evidence_id: 'ev_1',
          factor_type: 'eligibility',
          fact_type: 'insurance_status',
          fact_summary: 'Insurance is active',
          fact_data: { status: 'active', verified_at: '2024-01-15' },
          impact_direction: 'positive',
          impact_weight: 0.3,
          is_stale: false,
          source: {
            source_id: 'src_1',
            label: 'Portal Eligibility Check',
            type: 'eligibility_check',
            system: 'pverify',
            date: '2024-01-15',
            trust_score: 0.95
          }
        },
        {
          evidence_id: 'ev_2',
          factor_type: 'eligibility',
          fact_type: 'card_on_file',
          fact_summary: 'Insurance card uploaded',
          fact_data: { uploaded: true },
          impact_direction: 'positive',
          impact_weight: 0.2,
          is_stale: false,
          source: null
        }
      ],
      count: 2
    };
    
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });
    
    const result = await fetchEvidence('demo_001', 'eligibility');
    
    expect(result.evidence).toHaveLength(2);
    expect(result.count).toBe(2);
    
    // First evidence has source
    expect(result.evidence[0].source).not.toBeNull();
    expect(result.evidence[0].source?.label).toBe('Portal Eligibility Check');
    expect(result.evidence[0].source?.trust_score).toBe(0.95);
    
    // Second evidence has no source
    expect(result.evidence[1].source).toBeNull();
  });
  
  it('throws error on non-ok response', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ ok: false, error: 'Patient not found' })
    });
    
    await expect(
      fetchEvidence('nonexistent')
    ).rejects.toThrow('Patient not found');
  });
  
  it('handles network errors', async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(
      new Error('Network error')
    );
    
    await expect(
      fetchEvidence('demo_001', 'eligibility')
    ).rejects.toThrow('Network error');
  });
  
  it('includes authorization header', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ok: true, factor_type: null, evidence: [], count: 0 })
    });
    
    await fetchEvidence('demo_001');
    
    const callArgs = (global.fetch as jest.Mock).mock.calls[0];
    const headers = callArgs[1].headers;
    
    expect(headers.get('Authorization')).toBe('Bearer mock-access-token');
  });
  
});
